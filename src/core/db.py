"""
src/core/db.py
SQLite persistence layer for Veritas-Audit.

Replaces the per-tenant CSV log files with a single, queryable SQLite
database stored at the repo root (veritas.db).

Schema
------
audit_logs
  id              TEXT  PRIMARY KEY  (UUID)
  tenant_id       TEXT  NOT NULL
  timestamp       TEXT  NOT NULL     (ISO-8601 UTC)
  input_hash      TEXT  NOT NULL     (SHA-256 of original text)
  status          TEXT  NOT NULL     (PASS | FAIL)
  decision        TEXT  NOT NULL     (ALLOW | BLOCK)
  reason          TEXT
  violations_json TEXT              (JSON array)
  nist_tags_json  TEXT              (JSON array)
  risk_severity   TEXT
  iterations      INTEGER
  latency_ms      INTEGER

Usage
-----
Call `init_db()` once at application startup (done in main.py).
Use `get_session()` as a FastAPI dependency or a plain context manager.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

from sqlmodel import Field, Session, SQLModel, create_engine, text

from src.core.storage import repo_root


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_DB_PATH = repo_root() / "veritas.db"
_DB_URL = f"sqlite:///{_DB_PATH}"

_engine = create_engine(
    _DB_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    tenant_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    input_hash: str
    status: str
    decision: str
    reason: str | None = None
    violations_json: str | None = None   # JSON-encoded list
    nist_tags_json: str | None = None    # JSON-encoded list
    risk_severity: str | None = None
    iterations: int | None = None
    latency_ms: int | None = None


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables if they don't exist. Call once at startup."""
    SQLModel.metadata.create_all(_engine)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Plain context-manager session for use outside FastAPI dependency injection."""
    with Session(_engine) as session:
        yield session


def get_fastapi_session() -> Generator[Session, None, None]:
    """FastAPI `Depends`-compatible session generator."""
    with Session(_engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Write helper
# ---------------------------------------------------------------------------

def log_audit_to_db(
    tenant_id: str,
    original_text: str,
    status: str,
    decision: str,
    reason: str | None,
    violations: list[str],
    nist_tags: list[str],
    risk_severity: str,
    iterations: int,
    latency_ms: int | None = None,
) -> AuditLog:
    """
    Persist one audit result to the database.

    Returns the newly created AuditLog row.
    """
    entry = AuditLog(
        tenant_id=tenant_id,
        input_hash=hashlib.sha256(original_text.encode()).hexdigest(),
        status=status,
        decision=decision,
        reason=reason,
        violations_json=json.dumps(violations),
        nist_tags_json=json.dumps(nist_tags),
        risk_severity=risk_severity,
        iterations=iterations,
        latency_ms=latency_ms,
    )
    with get_session() as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)
    return entry
