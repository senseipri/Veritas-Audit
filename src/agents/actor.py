import os
import json
from groq import Groq
from src.core.retriever import get_compliance_context

def _client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required to run actor audit.")
    return Groq(api_key=api_key)

def run_actor(state: dict) -> dict:
    """
    The Actor (Auditor): Audits the text, attempts redaction, 
    and grounds the response based on retrieved truth.
    """
    tenant_id = state.get("tenant_id", "default")
    ai_output = state.get("current_text", "")
    
    # 1. Retrieve relevant 'truth'
    relevant_docs = get_compliance_context(tenant_id, ai_output)
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    
    # 2. Prompt for Actor
    prompt = f"""
    SYSTEM: You are a professional Compliance Auditor and Redactor. 
    Evaluate and, if necessary, rewrite the [BOT RESPONSE] against the [COMPLIANCE RULES].
    Ensure no contradictions, and redact any missed sensitive information not caught by Tier-0.
    
    COMPLIANCE RULES (The Truth):
    {context}
    
    BOT RESPONSE (To be audited):
    {ai_output}
    
    Feedback from Critic (If any):
    {state.get('critic_feedback', 'None')}
    
    OUTPUT FORMAT (JSON ONLY):
    {{
      "revised_text": "The audited and potentially redacted text",
      "status": "PASS" or "FAIL",
      "reason": "1-sentence explanation"
    }}
    """
    
    response = _client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    
    return {
        "current_text": result.get("revised_text", ai_output),
        "actor_status": result.get("status"),
        "actor_reason": result.get("reason"),
        "iterations": state.get("iterations", 0) + 1
    }
