from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TenantPaths:
    tenant_id: str
    root: Path
    truth_dir: Path
    vectorstore_dir: Path
    logs_dir: Path
    truth_pdf_path: Path


def repo_root() -> Path:
    # src/core/ -> repo root
    return Path(__file__).resolve().parents[2]


def tenant_paths(tenant_id: str) -> TenantPaths:
    safe_tenant = (tenant_id or "default").strip()
    if not safe_tenant:
        safe_tenant = "default"

    root = repo_root() / "tenants" / safe_tenant
    truth_dir = root / "truth"
    vectorstore_dir = root / "chroma_db"
    logs_dir = root / "logs"
    truth_pdf_path = truth_dir / "truth.pdf"

    return TenantPaths(
        tenant_id=safe_tenant,
        root=root,
        truth_dir=truth_dir,
        vectorstore_dir=vectorstore_dir,
        logs_dir=logs_dir,
        truth_pdf_path=truth_pdf_path,
    )


def ensure_dirs(*paths: os.PathLike | str) -> None:
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)

