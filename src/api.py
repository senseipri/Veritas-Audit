from __future__ import annotations

import csv
import datetime
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from src.storage import ensure_dirs, repo_root, tenant_paths


app = FastAPI(
    title="Veritas API",
    version="1.0.0",
    description="Tenant-aware AI compliance middleware API.",
)


@dataclass(frozen=True)
class AuthContext:
    api_key: str
    tenant_id: str | None
    is_admin: bool


_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = Lock()


def _parse_tenant_key_pairs() -> dict[str, str]:
    """
    Parses VERITAS_API_KEYS env var:
    VERITAS_API_KEYS=tenant-a:key-a,tenant-b:key-b
    """
    raw = os.environ.get("VERITAS_API_KEYS", "").strip()
    pairs: dict[str, str] = {}
    if not raw:
        return pairs

    for item in raw.split(","):
        entry = item.strip()
        if not entry:
            continue
        if ":" not in entry:
            continue
        tenant, key = entry.split(":", 1)
        tenant = tenant.strip()
        key = key.strip()
        if tenant and key:
            pairs[tenant] = key
    return pairs


def _authenticate_api_key(request: Request) -> AuthContext:
    api_key = request.headers.get("x-api-key", "").strip()
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing x-api-key header.")

    tenant_map = _parse_tenant_key_pairs()
    admin_key = os.environ.get("VERITAS_ADMIN_KEY", "").strip()

    if admin_key and api_key == admin_key:
        return AuthContext(api_key=api_key, tenant_id=None, is_admin=True)

    if not tenant_map:
        raise HTTPException(
            status_code=500,
            detail="Server auth is not configured. Set VERITAS_API_KEYS and VERITAS_ADMIN_KEY.",
        )

    for tenant_id, key in tenant_map.items():
        if api_key == key:
            return AuthContext(api_key=api_key, tenant_id=tenant_id, is_admin=False)

    raise HTTPException(status_code=403, detail="Invalid API key.")


def _authorize_tenant_access(auth: AuthContext, tenant_id: str) -> str:
    target = tenant_paths(tenant_id).tenant_id
    if auth.is_admin:
        return target
    if auth.tenant_id != target:
        raise HTTPException(status_code=403, detail="API key cannot access this tenant.")
    return target


def _rate_limit_per_minute() -> int:
    raw = os.environ.get("VERITAS_RATE_LIMIT_PER_MINUTE", "60").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 60
    return max(1, parsed)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Keep /health open for infra probes.
    if not request.url.path.startswith("/v1"):
        return await call_next(request)

    api_key = request.headers.get("x-api-key", "").strip()
    if not api_key:
        return JSONResponse(status_code=401, content={"detail": "Missing x-api-key header."})

    now = time.time()
    window_seconds = 60
    max_requests = _rate_limit_per_minute()

    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS[api_key]
        while bucket and (now - bucket[0]) > window_seconds:
            bucket.popleft()
        if len(bucket) >= max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded ({max_requests}/minute)."},
            )
        bucket.append(now)

    return await call_next(request)


class AuditRequest(BaseModel):
    tenant_id: str = Field(default="default", min_length=1)
    response_text: str = Field(min_length=1, description="The chatbot response to audit.")
    fail_closed: bool = Field(
        default=True,
        description="If true, missing context/rules should be treated as blocked in caller policy.",
    )


class AuditResponse(BaseModel):
    tenant_id: str
    status: str
    decision: str
    reason: str
    violated_rule_snippet: str | None = None
    latency_ms: int
    timestamp_utc: str


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "veritas-api"}


@app.get("/v1/tenants")
def list_tenants(auth: AuthContext = Depends(_authenticate_api_key)) -> dict:
    if not auth.is_admin:
        return {"tenants": [auth.tenant_id], "count": 1}
    tenants_root = repo_root() / "tenants"
    ensure_dirs(tenants_root)
    tenants = sorted([p.name for p in tenants_root.iterdir() if p.is_dir()])
    return {"tenants": tenants, "count": len(tenants)}


@app.post("/v1/tenants/{tenant_id}/truth")
async def upload_tenant_truth(
    tenant_id: str,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(_authenticate_api_key),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    authorized_tenant = _authorize_tenant_access(auth, tenant_id)
    paths = tenant_paths(authorized_tenant)
    ensure_dirs(paths.truth_dir)

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    paths.truth_pdf_path.write_bytes(pdf_bytes)
    return {
        "tenant_id": paths.tenant_id,
        "truth_pdf_path": str(paths.truth_pdf_path),
        "bytes_written": len(pdf_bytes),
    }


@app.post("/v1/tenants/{tenant_id}/reindex")
def reindex_tenant(tenant_id: str, auth: AuthContext = Depends(_authenticate_api_key)) -> dict:
    # Lazy import to keep API import fast (and tests lightweight).
    from src.ingest import build_compliance_vault, reset_tenant_vectorstore
    from src.retriever import invalidate_tenant_cache

    authorized_tenant = _authorize_tenant_access(auth, tenant_id)
    paths = tenant_paths(authorized_tenant)
    if not paths.truth_pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No truth PDF found for tenant. Upload one first.",
        )

    reset_tenant_vectorstore(paths.tenant_id)
    chunks = build_compliance_vault(paths.tenant_id, str(paths.truth_pdf_path))
    invalidate_tenant_cache(paths.tenant_id)
    return {"tenant_id": paths.tenant_id, "chunks_indexed": chunks}


@app.get("/v1/tenants/{tenant_id}/logs.csv")
def get_tenant_logs_csv(tenant_id: str, auth: AuthContext = Depends(_authenticate_api_key)):
    authorized_tenant = _authorize_tenant_access(auth, tenant_id)
    paths = tenant_paths(authorized_tenant)
    log_file = paths.logs_dir / "audit_history.csv"
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="No logs found for tenant.")
    return FileResponse(path=log_file, media_type="text/csv", filename=f"{paths.tenant_id}_audit_history.csv")


@app.get("/v1/tenants/{tenant_id}/logs")
def get_tenant_logs_json(
    tenant_id: str,
    limit: int = 100,
    auth: AuthContext = Depends(_authenticate_api_key),
) -> dict:
    authorized_tenant = _authorize_tenant_access(auth, tenant_id)
    paths = tenant_paths(authorized_tenant)
    log_file = paths.logs_dir / "audit_history.csv"
    if not log_file.exists():
        return {"tenant_id": paths.tenant_id, "count": 0, "rows": []}

    rows = []
    with open(log_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    return {"tenant_id": paths.tenant_id, "count": len(rows), "rows": rows[-max(1, limit):]}


@app.post("/v1/audit", response_model=AuditResponse)
def audit_message(payload: AuditRequest, auth: AuthContext = Depends(_authenticate_api_key)) -> AuditResponse:
    # Lazy import to avoid heavy ML imports when running tests/admin endpoints.
    from src.auditor import run_compliance_audit

    started = time.perf_counter()
    authorized_tenant = _authorize_tenant_access(auth, payload.tenant_id)
    paths = tenant_paths(authorized_tenant)

    if not paths.vectorstore_dir.exists() or not any(paths.vectorstore_dir.iterdir()):
        if payload.fail_closed:
            raise HTTPException(
                status_code=412,
                detail="Tenant has no indexed truth. Upload a PDF and call reindex first.",
            )

    audit_result = run_compliance_audit(payload.response_text, tenant_id=paths.tenant_id)
    latency_ms = int((time.perf_counter() - started) * 1000)
    status = (audit_result.get("status") or "FAIL").upper()
    decision = "ALLOW" if status == "PASS" else "BLOCK"

    return AuditResponse(
        tenant_id=paths.tenant_id,
        status=status,
        decision=decision,
        reason=audit_result.get("reason", "No reason provided."),
        violated_rule_snippet=audit_result.get("violated_rule_snippet"),
        latency_ms=latency_ms,
        timestamp_utc=datetime.datetime.utcnow().isoformat() + "Z",
    )

