from __future__ import annotations

from dotenv import load_dotenv
import uuid
import structlog
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes.audit import router as audit_router
from src.api.routes.tenants import router as tenants_router
from src.api.security import rate_limit_middleware
from src.core.db import init_db
from src.core.logging_config import setup_logging

# Load environment variables from .env for local/dev runs.
load_dotenv()

# Initialize structured logging
setup_logging()
logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Veritas API",
    version="1.0.0",
    description="Tenant-aware AI compliance middleware API.",
)

@app.middleware("http")
async def structlog_request_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    
    response = await call_next(request)
    return response

# Initialise database on startup (creates tables if they don't exist)
@app.on_event("startup")
def on_startup() -> None:
    init_db()

app.middleware("http")(rate_limit_middleware)


app.include_router(audit_router)
app.include_router(tenants_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "veritas-api"}
