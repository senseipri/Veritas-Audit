from __future__ import annotations

from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from src.core.storage import ensure_dirs, tenant_paths


@lru_cache(maxsize=1)
def _embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        cache_folder="./model_cache",
        model_kwargs={"device": "cpu"},
    )


def embeddings_model() -> HuggingFaceEmbeddings:
    """Shared embedding model for indexing and retrieval."""
    return _embeddings()


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


def get_compliance_context(tenant_id: str, query: str, k: int = 6):
    """
    Finds the top k relevant law/policy snippets from the local vector store.
    Uses MMR (Max Marginal Relevance) to ensure diversity in retrieved snippets.
    """
    # 1. Connect to tenant-isolated vector DB (cached for low latency)
    db = _tenant_db(tenant_id)

    # 2. Perform the search with MMR for better diversity
    # k is the final number of docs, fetch_k is how many to initially retrieve for re-ranking
    docs = db.max_marginal_relevance_search(query, k=k, fetch_k=min(k * 4, 20))
    
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