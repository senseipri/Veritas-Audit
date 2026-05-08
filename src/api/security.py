import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from fastapi import HTTPException, Request
from src.core.storage import tenant_paths

@dataclass(frozen=True)
class AuthContext:
    api_key: str
    tenant_id: str | None
    is_admin: bool

_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = Lock()

def _parse_tenant_key_pairs() -> dict[str, str]:
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
        if tenant.strip() and key.strip():
            pairs[tenant.strip()] = key.strip()
    return pairs

def authenticate_api_key(request: Request) -> AuthContext:
    api_key = request.headers.get("x-api-key", "").strip()
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing x-api-key header.")

    tenant_map = _parse_tenant_key_pairs()
    admin_key = os.environ.get("VERITAS_ADMIN_KEY", "").strip()

    if admin_key and api_key == admin_key:
        return AuthContext(api_key=api_key, tenant_id=None, is_admin=True)

    if not tenant_map:
        raise HTTPException(status_code=500, detail="Server auth is not configured.")

    for tenant_id, key in tenant_map.items():
        if api_key == key:
            return AuthContext(api_key=api_key, tenant_id=tenant_id, is_admin=False)

    raise HTTPException(status_code=403, detail="Invalid API key.")

def authorize_tenant_access(auth: AuthContext, tenant_id: str) -> str:
    target = tenant_paths(tenant_id).tenant_id
    if auth.is_admin:
        return target
    if auth.tenant_id != target:
        raise HTTPException(status_code=403, detail="API key cannot access this tenant.")
    return target

def _rate_limit_per_minute() -> int:
    try:
        return max(1, int(os.environ.get("VERITAS_RATE_LIMIT_PER_MINUTE", "60").strip()))
    except ValueError:
        return 60

async def rate_limit_middleware(request: Request, call_next):
    if not request.url.path.startswith("/v1"):
        return await call_next(request)

    api_key = request.headers.get("x-api-key", "").strip()
    if not api_key:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Missing x-api-key header."})

    now = time.time()
    max_requests = _rate_limit_per_minute()

    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS[api_key]
        while bucket and (now - bucket[0]) > 60:
            bucket.popleft()
        if len(bucket) >= max_requests:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=429, content={"detail": f"Rate limit exceeded."})
        bucket.append(now)

    return await call_next(request)
