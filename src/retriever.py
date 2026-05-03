from __future__ import annotations

from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from src.storage import ensure_dirs, tenant_paths


@lru_cache(maxsize=1)
def _embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        cache_folder="./model_cache",
        model_kwargs={"device": "cpu"},
    )


@lru_cache(maxsize=128)
def _tenant_db(tenant_id: str) -> Chroma:
    paths = tenant_paths(tenant_id)
    ensure_dirs(paths.vectorstore_dir)
    return Chroma(persist_directory=str(paths.vectorstore_dir), embedding_function=_embeddings())


def invalidate_tenant_cache(tenant_id: str | None = None) -> None:
    if tenant_id is None:
        _tenant_db.cache_clear()
        return
    # targeted invalidation by clearing all cache entries (small cache, simple + safe)
    _tenant_db.cache_clear()


def get_compliance_context(tenant_id: str, query: str, k: int = 3):
    """
    Finds the top k relevant law/policy snippets from the local vector store.
    """
    # 1. Connect to tenant-isolated vector DB (cached for low latency)
    db = _tenant_db(tenant_id)

    # 2. Perform the search
    # This turns your query into a vector and finds the closest matches
    docs = db.similarity_search(query, k=k)
    
    return docs

if __name__ == "__main__":
    # Test query: Change this to something relevant to your policy.pdf
    tenant = "default"
    sample_query = "What are the restrictions on data sharing?"
    results = get_compliance_context(tenant, sample_query)
    
    print(f"\n Searching for rules related to: '{sample_query}'")
    for i, doc in enumerate(results):
        print(f"\n--- MATCH {i+1} ---")
        print(doc.page_content)