import csv
import datetime
from typing import TypedDict, List
from langgraph.graph import StateGraph, END

from src.agents.actor import run_actor
from src.agents.critic import run_critic
from src.core.storage import tenant_paths, ensure_dirs
from src.core.nist import map_risk_to_nist

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

def log_audit_trail(state: AuditState) -> None:
    """Logs the final state to the tenant's audit_history.csv"""
    paths = tenant_paths(state["tenant_id"])
    ensure_dirs(paths.logs_dir)
    log_file = paths.logs_dir / "audit_history.csv"
    file_exists = log_file.exists()

    with open(log_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Tenant", "Status", "Original_Input", "Final_Output", "Violations", "NIST_Tags", "Severity", "Iterations"])
        
        writer.writerow([
            datetime.datetime.now().isoformat(),
            state["tenant_id"],
            state.get("actor_status", "UNKNOWN"),
            (state.get("original_text") or "")[:200],
            (state.get("current_text") or "")[:200],
            ", ".join(state.get("violations", [])),
            ", ".join(state.get("nist_tags", [])),
            state.get("risk_severity", "LOW"),
            state.get("iterations", 0)
        ])

def should_continue(state: AuditState) -> str:
    """Router to determine whether to loop back or end."""
    # Prevent infinite loops (e.g. max 3 iterations)
    if state.get("iterations", 0) >= 3:
        return "end"
    
    if state.get("critic_status") == "APPROVED":
        return "end"
    else:
        return "actor"

def process_nist_mapping(state: AuditState) -> dict:
    """Maps violations to NIST risks before concluding."""
    mapping = map_risk_to_nist(state.get("violations", []))
    return {
        "nist_tags": mapping["nist_tags"],
        "risk_severity": mapping["risk_severity"]
    }

# Define the State Machine
workflow = StateGraph(AuditState)

# Add nodes
workflow.add_node("actor", run_actor)
workflow.add_node("critic", run_critic)
workflow.add_node("nist", process_nist_mapping)

# Add edges
workflow.set_entry_point("actor")
workflow.add_edge("actor", "critic")
workflow.add_conditional_edges("critic", should_continue, {
    "actor": "actor",
    "end": "nist"
})
workflow.add_edge("nist", END)

# Compile graph
audit_app = workflow.compile()

def run_deep_audit(tenant_id: str, ai_output: str) -> dict:
    """Entry point for the FastAPI Ingress Layer to call."""
    initial_state = {
        "tenant_id": tenant_id,
        "original_text": ai_output,
        "current_text": ai_output,
        "iterations": 0,
        "violations": []
    }
    
    final_state = audit_app.invoke(initial_state)
    
    # Log the final result
    log_audit_trail(final_state)
    
    return final_state
