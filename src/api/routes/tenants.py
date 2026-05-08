import csv
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from src.api.security import AuthContext, authenticate_api_key, authorize_tenant_access
from src.core.storage import ensure_dirs, repo_root, tenant_paths

router = APIRouter()

@router.get("/v1/tenants")
def list_tenants(auth: AuthContext = Depends(authenticate_api_key)) -> dict:
    if not auth.is_admin:
        return {"tenants": [auth.tenant_id], "count": 1}
    tenants_root = repo_root() / "tenants"
    ensure_dirs(tenants_root)
    tenants = sorted([p.name for p in tenants_root.iterdir() if p.is_dir()])
    return {"tenants": tenants, "count": len(tenants)}

@router.post("/v1/tenants/{tenant_id}/truth")
async def upload_tenant_truth(
    tenant_id: str,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(authenticate_api_key),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    authorized_tenant = authorize_tenant_access(auth, tenant_id)
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


@router.post("/v1/tenants/{tenant_id}/reindex")
def reindex_tenant(tenant_id: str, auth: AuthContext = Depends(authenticate_api_key)) -> dict:
    from src.core.indexing import reindex_tenant_from_truth_pdf

    authorized_tenant = authorize_tenant_access(auth, tenant_id)
    paths = tenant_paths(authorized_tenant)
    if not paths.truth_pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No truth PDF found for tenant. Upload one first.",
        )
    chunks = reindex_tenant_from_truth_pdf(paths.tenant_id, paths.truth_pdf_path)
    return {"tenant_id": paths.tenant_id, "chunks_indexed": chunks}


@router.get("/v1/tenants/{tenant_id}/logs.csv")
def get_tenant_logs_csv(tenant_id: str, auth: AuthContext = Depends(authenticate_api_key)):
    authorized_tenant = authorize_tenant_access(auth, tenant_id)
    paths = tenant_paths(authorized_tenant)
    log_file = paths.logs_dir / "audit_history.csv"
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="No logs found for tenant.")
    return FileResponse(path=log_file, media_type="text/csv", filename=f"{paths.tenant_id}_audit_history.csv")

@router.get("/v1/tenants/{tenant_id}/logs")
def get_tenant_logs_json(
    tenant_id: str,
    limit: int = 100,
    auth: AuthContext = Depends(authenticate_api_key),
) -> dict:
    authorized_tenant = authorize_tenant_access(auth, tenant_id)
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
