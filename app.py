import streamlit as st
import hashlib
import PyPDF2
from sqlalchemy import create_engine, MetaData, Table, inspect
import pandas as pd

# Fetch the DATABASE_URL from st.secrets
DATABASE_URL = st.secrets["DATABASE_URL"]

# Fix the URL if it starts with 'postgres://', change it to 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create a SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Metadata object to hold schema information
metadata = MetaData()

# Define the table schema (it won't create the table here, just defines it)
pdf_data_table = Table(
    'pdf_data', metadata,
    autoload_with=engine
)

 # Check if the table exists


# Function to check if a table exists in the database
def check_if_table_exists(table_name):
    inspector = inspect(engine)
    return inspector.has_table(table_name)

# Function to generate a hash based on PDF content
def generate_pdf_hash(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    pdf_text = ''
    for page_num in range(len(pdf_reader.pages)):
        pdf_text += pdf_reader.pages[page_num].extract_text()
    return hashlib.md5(pdf_text.encode('utf-8')).hexdigest()

# Function to check if the PDF has already been read
def check_pdf_status(uploaded_file):
    pdf_hash = generate_pdf_hash(uploaded_file)
    query = pdf_data_table.select().where(pdf_data_table.c.hash == pdf_hash)
    
    with engine.connect() as conn:
        result = conn.execute(query).fetchone()

        if result:
            if result[2] == "Read":  # Status is in the third position (index 2)
                return "read", result[1]  # File name is in the second position (index 1)
            else:
                return "exists", result[1]
    return "new", None

# New function to insert real values into the table
def insert_real_values(uploaded_file):
    pdf_hash = generate_pdf_hash(uploaded_file)
    
    # Prepare the values for the columns
    real_values = {
        "hash": pdf_hash,
        "file_name": uploaded_file.name,
        "status": "Read"  # Assuming the PDF is being marked as "Read"
    }
    
    # Insert the row into the table
    try:
        with engine.connect() as conn:
            conn.execute(pdf_data_table.insert().values(real_values))
            conn.commit()  # Explicit commit of the transaction
        st.success(f"Filen '{uploaded_file.name}' har markerats som läst!")
    except Exception as e:
        st.warning(f"An error occurred: {e}")

# Function to display classified PDFs
def list_classified_pdfs():
    query = pdf_data_table.select()
    with engine.connect() as conn:
        result = conn.execute(query).fetchall()
    
    if result:
        # Convert result to DataFrame and select only 'file_name' and 'status' columns
        df = pd.DataFrame(result, columns=["hash", "file_name", "status"])
        df = df[["file_name", "status"]]  # Select only file_name and status columns
        
        # Rename the columns
        df = df.rename(columns={"file_name": "Filnamn", "status": "Status"})
        
        # Display the DataFrame in Streamlit
        st.dataframe(df)
    else:
        st.write("No PDFs have been classified yet.")

# Streamlit app UI
def main():
    st.title("Jossos dubletter - en app för SIP-projektet")

    if not check_if_table_exists("pdf_data"):
        st.warning("No table exists in the database.")
        return

    # File upload section (single file only)
    st.subheader("Ladda upp en PDF så checkar appen automatiskt om du läst en fil med samma innehåll förut, oavsett filnamn")
    
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf", accept_multiple_files=False)

    if uploaded_file is not None:
        st.write(f"File name: {uploaded_file.name}")
        
        # Use session state to store the result of the status check
        if 'status_checked' not in st.session_state:
            st.session_state.status_checked = False
            st.session_state.status = None
            st.session_state.existing_file = None

        # Only perform the status check if it hasn't been done already
        if not st.session_state.status_checked:
            with st.spinner("Kollar om en fil med detta innehåll har lästs, detta kan ta lite tid beroende på filens storlek..."):
                status, existing_file = check_pdf_status(uploaded_file)
                st.session_state.status = status
                st.session_state.existing_file = existing_file
                st.session_state.status_checked = True

        status = st.session_state.status
        existing_file = st.session_state.existing_file
        mark_as_read_button = None

        if status == "read":
            st.error(f"En fil med samma innehåll har redan markerats som läst (File: {existing_file}).")
            mark_as_read_button = st.button("Mark as read", disabled=True)
        elif status == "exists":
            st.info(f"A file with the same content already exists (File: {existing_file}), but it hasn't been marked as 'Read' yet.")
            mark_as_read_button = st.button("Mark as read", disabled=False)
        else:
            st.success("Detta är en ny PDF!")
            mark_as_read_button = st.button("Markera som läst", disabled=False)

        # If "Mark as read" is pressed
        if mark_as_read_button and uploaded_file is not None:
            with st.spinner("Uppdaterar databasen, detta kan ta lite tid beroende på filens storlek..."):
                insert_real_values(uploaded_file)
                st.session_state.status_checked = False  # Reset after marking as read

    # Section to list all classified PDFs
    st.subheader("Redan lästa PDF:er:")
    list_classified_pdfs()

if __name__ == "__main__":
  # Stop further execution if the table doesn't exist
    main()
