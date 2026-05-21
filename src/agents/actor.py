import os
import json
from groq import Groq
from src.core.retriever import get_compliance_context
from src.core.config import settings

def _client() -> Groq:
    api_key = settings.GROQ_API_KEY
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
    
    CRITICAL INSTRUCTIONS:
    1. GROUNDING: Ensure no contradictions with the provided rules.
    2. REDACTION: Redact any missed sensitive information (PII, secrets).
    3. PARTIAL CONTEXT AWARENESS: You are provided with the top {len(relevant_docs)} most relevant snippets. 
       If the [BOT RESPONSE] references a specific policy, rule ID, or procedure that is NOT fully detailed in the snippets, 
       do NOT assume it is valid. Instead, flag it as 'FAIL' with a reason stating "Missing context for rule: [Rule Name]".
    4. GENERAL COMPLIANCE: If the response violates general industry best practices even if not explicitly in the snippets, 
       you should still flag it.
    
    COMPLIANCE RULES (Relevant Snippets):
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
        model=settings.ACTOR_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    tokens_used = response.usage.total_tokens if response.usage else 0
    
    return {
        "current_text": result.get("revised_text", ai_output),
        "actor_status": result.get("status"),
        "actor_reason": result.get("reason"),
        "iterations": state.get("iterations", 0) + 1,
        "total_tokens": state.get("total_tokens", 0) + tokens_used,
        "models_used": state.get("models_used", []) + [settings.ACTOR_MODEL]
    }
