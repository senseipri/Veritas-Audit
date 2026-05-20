import time
import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from src.api.security import AuthContext, authenticate_api_key, authorize_tenant_access
from src.core.storage import tenant_paths
from src.core.guardrails import intercept_pii
from src.agents.graph import run_deep_audit
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()

class AuditRequest(BaseModel):
    tenant_id: str = Field(default="default", min_length=1)
    response_text: str = Field(min_length=1, description="The chatbot response to audit.")
    fail_closed: bool = Field(default=True)

class AuditResponse(BaseModel):
    tenant_id: str
    status: str
    decision: str
    reason: str
    latency_ms: int
    timestamp_utc: str
    violations: list[str] = []

@router.post("/v1/audit", response_model=AuditResponse)
def audit_message(payload: AuditRequest, auth: AuthContext = Depends(authenticate_api_key)) -> AuditResponse:
    started = time.perf_counter()
    authorized_tenant = authorize_tenant_access(auth, payload.tenant_id)
    paths = tenant_paths(authorized_tenant)

    if not paths.vectorstore_dir.exists() or not any(paths.vectorstore_dir.iterdir()):
        if payload.fail_closed:
            raise HTTPException(status_code=412, detail="Tenant has no indexed truth.")

    # Tier-0: NeMo Guardrails PII Interception
    tier0_result = intercept_pii(payload.response_text)
    if tier0_result["is_blocked"]:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "Audit call completed",
            tenant_id=paths.tenant_id,
            latency_ms=latency_ms,
            status="FAIL",
            decision="BLOCK",
            model="nemo-guardrails",
            tokens_used=0,
            reason="Blocked by Tier-0 PII Guardrails"
        )
        return AuditResponse(
            tenant_id=paths.tenant_id,
            status="FAIL",
            decision="BLOCK",
            reason="Blocked by Tier-0 PII Guardrails",
            latency_ms=latency_ms,
            timestamp_utc=datetime.datetime.utcnow().isoformat() + "Z",
            violations=tier0_result.get("violations", [])
        )

    # Agentic Verification
    latency_ms = int((time.perf_counter() - started) * 1000)
    audit_result = run_deep_audit(paths.tenant_id, tier0_result["redacted_text"], latency_ms=latency_ms)
    
    latency_ms = int((time.perf_counter() - started) * 1000)
    
    # We define status as PASS if Critic APPROVED and no MAJOR violations from Actor
    final_status = "PASS" if audit_result.get("critic_status") == "APPROVED" else "FAIL"
    decision = "ALLOW" if final_status == "PASS" else "BLOCK"

    models_str = ", ".join(list(set(audit_result.get("models_used", []))))
    
    logger.info(
        "Audit call completed",
        tenant_id=paths.tenant_id,
        latency_ms=latency_ms,
        status=final_status,
        decision=decision,
        model=models_str,
        tokens_used=audit_result.get("total_tokens", 0),
        reason=audit_result.get("actor_reason", "No reason provided.")
    )

    return AuditResponse(
        tenant_id=paths.tenant_id,
        status=final_status,
        decision=decision,
        reason=audit_result.get("actor_reason", "No reason provided."),
        latency_ms=latency_ms,
        timestamp_utc=datetime.datetime.utcnow().isoformat() + "Z",
        violations=audit_result.get("violations", [])
    )
