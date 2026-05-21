import csv
import datetime
from typing import TypedDict, List
from langgraph.graph import StateGraph, END

from src.agents.actor import run_actor
from src.agents.critic import run_critic
from src.core.storage import tenant_paths, ensure_dirs
from src.core.nist import map_risk_to_nist
from src.core.db import log_audit_to_db


class AuditState(TypedDict):
    tenant_id: str
    original_text: str
    current_text: str
    iterations: int
    actor_status: str
    actor_reason: str
    critic_status: str
    critic_feedback: str
    violations: List[str]
    nist_tags: List[str]
    risk_severity: str
    total_tokens: int
    models_used: List[str]


def log_audit_trail_csv(state: AuditState) -> None:
    """
    Optional CSV export for tenant-visible audit history.
    This is NOT the primary audit store — use the SQLite DB for that.
    """
    paths = tenant_paths(state["tenant_id"])
    ensure_dirs(paths.logs_dir)
    log_file = paths.logs_dir / "audit_history.csv"
    file_exists = log_file.exists()

    with open(log_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Timestamp", "Tenant", "Status", "Original_Input",
                "Final_Output", "Violations", "NIST_Tags", "Severity", "Iterations"
            ])
        writer.writerow([
            datetime.datetime.now().isoformat(),
            state["tenant_id"],
            state.get("actor_status", "UNKNOWN"),
            (state.get("original_text") or "")[:200],
            (state.get("current_text") or "")[:200],
            ", ".join(state.get("violations", [])),
            ", ".join(state.get("nist_tags", [])),
            state.get("risk_severity", "LOW"),
            state.get("iterations", 0),
        ])


def should_continue(state: AuditState) -> str:
    """Router to determine whether to loop back or end."""
    if state.get("iterations", 0) >= 3:
        return "end"
    if state.get("critic_status") == "APPROVED":
        return "end"
    return "actor"


def process_nist_mapping(state: AuditState) -> dict:
    """Maps violations to NIST risks before concluding."""
    mapping = map_risk_to_nist(state.get("violations", []))
    return {
        "nist_tags": mapping["nist_tags"],
        "risk_severity": mapping["risk_severity"],
    }


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------

workflow = StateGraph(AuditState)

workflow.add_node("actor", run_actor)
workflow.add_node("critic", run_critic)
workflow.add_node("nist", process_nist_mapping)

workflow.set_entry_point("actor")
workflow.add_edge("actor", "critic")
workflow.add_conditional_edges("critic", should_continue, {
    "actor": "actor",
    "end": "nist",
})
workflow.add_edge("nist", END)

audit_app = workflow.compile()


def run_deep_audit(tenant_id: str, ai_output: str, latency_ms: int | None = None) -> dict:
    """Entry point for the FastAPI Ingress Layer to call."""
    initial_state: dict = {
        "tenant_id": tenant_id,
        "original_text": ai_output,
        "current_text": ai_output,
        "iterations": 0,
        "violations": [],
        "total_tokens": 0,
        "models_used": [],
    }

    final_state = audit_app.invoke(initial_state)

    # ── Primary audit log: SQLite DB ────────────────────────────────────────
    status = "PASS" if final_state.get("critic_status") == "APPROVED" else "FAIL"
    decision = "ALLOW" if status == "PASS" else "BLOCK"

    log_audit_to_db(
        tenant_id=tenant_id,
        original_text=ai_output,
        status=status,
        decision=decision,
        reason=final_state.get("actor_reason"),
        violations=final_state.get("violations", []),
        nist_tags=final_state.get("nist_tags", []),
        risk_severity=final_state.get("risk_severity", "LOW"),
        iterations=final_state.get("iterations", 0),
        latency_ms=latency_ms,
    )

    # ── Optional: keep tenant-visible CSV export ─────────────────────────────
    log_audit_trail_csv(final_state)

    return final_state
