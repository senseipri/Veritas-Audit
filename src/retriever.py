from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings

def get_compliance_context(query, k=3):
    """
    Finds the top k relevant law/policy snippets from the local vector store.
    """
    # 1. Initialize the SAME embeddings model used in Day 1
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'token': os.getenv("HF_TOKEN")}
        )
    
    # 2. Connect to the existing ChromaDB folder
    db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    
    # 3. Perform the search
    # This turns your query into a vector and finds the closest matches
    docs = db.similarity_search(query, k=k)
    
    return docs

if __name__ == "__main__":
    # Test query: Change this to something relevant to your policy.pdf
    sample_query = "What are the restrictions on data sharing?"
    results = get_compliance_context(sample_query)
    
    print(f"\n Searching for rules related to: '{sample_query}'")
    for i, doc in enumerate(results):
        print(f"\n--- MATCH {i+1} ---")
        print(doc.page_content)