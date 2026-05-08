from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI

from src.api.routes.audit import router as audit_router
from src.api.routes.tenants import router as tenants_router
from src.api.security import rate_limit_middleware

# Load environment variables from .env for local/dev runs.
load_dotenv()

app = FastAPI(
    title="Veritas API",
    version="1.0.0",
    description="Tenant-aware AI compliance middleware API.",
)

app.middleware("http")(rate_limit_middleware)

app.include_router(audit_router)
app.include_router(tenants_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "veritas-api"}
