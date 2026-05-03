from __future__ import annotations

import os
import shutil

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from src.storage import ensure_dirs, tenant_paths

# Load environment variables (like your Groq Key)
load_dotenv()

def reset_tenant_vectorstore(tenant_id: str) -> None:
    paths = tenant_paths(tenant_id)
    if paths.vectorstore_dir.exists():
        shutil.rmtree(paths.vectorstore_dir)
    ensure_dirs(paths.vectorstore_dir)


def build_compliance_vault(tenant_id: str, pdf_path: str) -> int:
    paths = tenant_paths(tenant_id)
    ensure_dirs(paths.truth_dir, paths.vectorstore_dir)

    print(f" Starting ingestion for tenant='{paths.tenant_id}': {pdf_path}")
    
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
    embeddings = HuggingFaceEmbeddings(model_name=model_name, cache_folder="./model_cache")
    
    # 4. Create the Local Vector Store
    # This creates a folder named 'chroma_db' which acts as your database
    print(" Storing chunks in ChromaDB...")
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(paths.vectorstore_dir),
    )
    
    print(f" Success! {len(chunks)} compliance rules are now searchable.")
    return len(chunks)

if __name__ == "__main__":
    tenant = os.environ.get("VERITAS_TENANT", "default")
    POLICY_FILE = os.environ.get("VERITAS_POLICY_PDF", "data/policy.pdf")

    paths = tenant_paths(tenant)

    # Check if the database already exists and has content
    if paths.vectorstore_dir.exists() and any(paths.vectorstore_dir.iterdir()):
        print(f" Compliance Vault already exists at {paths.vectorstore_dir}. Skipping ingestion.")
        print(" To re-index, delete the tenant vectorstore folder and run again.")
    else:
        if os.path.exists(POLICY_FILE):
            build_compliance_vault(tenant, POLICY_FILE)
        else:
            print(f" Error: Please put a PDF at {POLICY_FILE}")