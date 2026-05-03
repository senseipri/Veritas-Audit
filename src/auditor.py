import os
import json
import csv
import datetime
from groq import Groq
from dotenv import load_dotenv
from src.retriever import get_compliance_context
from src.storage import ensure_dirs, tenant_paths

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def log_violation(tenant_id: str, audit_result: dict, original_text: str) -> None:
    paths = tenant_paths(tenant_id)
    ensure_dirs(paths.logs_dir)

    log_file = paths.logs_dir / "audit_history.csv"
    file_exists = log_file.exists()

    with open(log_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Tenant", "Status", "Input_Snippet", "Reason", "Violated_Rule_Snippet"])
        writer.writerow(
            [
                datetime.datetime.now().isoformat(),
                paths.tenant_id,
                audit_result.get("status"),
                (original_text or "")[:200],
                audit_result.get("reason"),
                (audit_result.get("violated_rule_snippet") or "")[:500],
            ]
        )

def run_compliance_audit(ai_output: str, tenant_id: str = "default") -> dict:
    # 1. Retrieve relevant 'truth' from our PDF
    relevant_docs = get_compliance_context(tenant_id, ai_output)
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    
    # 2. Construct the Audit Prompt
    prompt = f"""
    SYSTEM: You are a professional Compliance Auditor. 
    Evaluate the [BOT RESPONSE] against the [COMPLIANCE RULES].
    
    COMPLIANCE RULES (The Truth):
    {context}
    
    BOT RESPONSE (To be audited):
    {ai_output}
    
    CRITERIA: 
    If the Bot Response contradicts or violates any specific rule, mark as FAIL.
    Otherwise, mark as PASS.
    
    OUTPUT FORMAT (JSON ONLY):
    {{
      "status": "PASS" or "FAIL",
      "reason": "1-sentence explanation",
      "violated_rule_snippet": "Quote from the rules"
    }}
    """

    # 3. Call Groq for high-speed inference
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)

    if result['status'] == "FAIL":
        log_violation(tenant_id, result, ai_output)
        
    return result 

if __name__ == "__main__":
    # Test a clearly non-compliant response
    test_response = "We can share your biometric data with our partners without specific consent."
    
    print("Initiating Audit via Groq Cloud...")
    result = run_compliance_audit(test_response, tenant_id=os.environ.get("VERITAS_TENANT", "default"))
    print(json.dumps(result, indent=2))