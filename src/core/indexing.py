from __future__ import annotations

import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.retriever import embeddings_model, invalidate_tenant_cache
from src.core.storage import ensure_dirs, tenant_paths


def reset_tenant_vectorstore(tenant_id: str) -> None:
    paths = tenant_paths(tenant_id)
    if paths.vectorstore_dir.exists():
        shutil.rmtree(paths.vectorstore_dir)
    ensure_dirs(paths.vectorstore_dir)


def build_tenant_index(tenant_id: str, pdf_path: str | Path) -> int:
    paths = tenant_paths(tenant_id)
    ensure_dirs(paths.truth_dir, paths.vectorstore_dir)
    pdf = Path(pdf_path)
    if not pdf.is_file():
        raise FileNotFoundError(str(pdf))

    loader = PyPDFLoader(str(pdf))
    pages = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
    chunks = text_splitter.split_documents(pages)
    chunks = [c for c in chunks if (c.page_content or "").strip()]
    if not chunks:
        raise ValueError(
            "No extractable text in PDF after chunking; upload a text-based PDF or OCR'd document."
        )
    embeddings = embeddings_model()
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(paths.vectorstore_dir),
    )
    invalidate_tenant_cache(paths.tenant_id)
    return len(chunks)


def reindex_tenant_from_truth_pdf(tenant_id: str, pdf_path: str | Path | None = None) -> int:
    paths = tenant_paths(tenant_id)
    pdf = Path(pdf_path) if pdf_path is not None else paths.truth_pdf_path
    reset_tenant_vectorstore(paths.tenant_id)
    return build_tenant_index(paths.tenant_id, pdf)
