import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# Load environment variables (like your Groq Key)
load_dotenv()

def build_compliance_vault(pdf_path):
    print(f"🚀 Starting ingestion for: {pdf_path}")
    
    # 1. Load the PDF
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()
    
    # 2. Split into 'Semantic Chunks'
    # We use 600 characters so Groq receives concise context
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100
    )
    chunks = text_splitter.split_documents(pages)
    
    # 3. Initialize FREE Local Embeddings
    # This runs on your CPU, so it costs $0 and is very fast
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    embeddings = HuggingFaceEmbeddings(model_name=model_name)
    
    # 4. Create the Local Vector Store
    # This creates a folder named 'chroma_db' which acts as your database
    print("📦 Storing chunks in ChromaDB...")
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./chroma_db"
    )
    
    print(f" Success! {len(chunks)} compliance rules are now searchable.")

if __name__ == "__main__":
    POLICY_FILE = "data/policy.pdf"
    DB_DIR = "./chroma_db"
    
    # Check if the database already exists and has content
    if os.path.exists(DB_DIR) and os.listdir(DB_DIR):
        print(f" Compliance Vault already exists at {DB_DIR}. Skipping ingestion.")
        print(" To re-index, delete the 'chroma_db' folder and run again.")
    else:
        if os.path.exists(POLICY_FILE):
            build_compliance_vault(POLICY_FILE)
        else:
            print(f" Error: Please put a PDF at {POLICY_FILE}")