import os
import json
from groq import Groq
from src.core.retriever import get_compliance_context
from src.core.config import settings

def _client() -> Groq:
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required to run critic audit.")
    return Groq(api_key=api_key)

def run_critic(state: dict) -> dict:
    """
    The Critic (Evaluator): Scrutinizes the Actor's work to find 
    hallucinations, bias, or missed PII.
    """
    tenant_id = state.get("tenant_id", "default")
    ai_output = state.get("current_text", "")
    
    # 1. Retrieve relevant 'truth'
    relevant_docs = get_compliance_context(tenant_id, ai_output)
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    
    # 2. Prompt for Critic
    prompt = f"""
    SYSTEM: You are the Critic Evaluator. Your job is to find flaws in the [ACTOR RESPONSE].
    Check for:
    1. Hallucinations (claims not supported by the Truth).
    2. Bias or ungrounded statements.
    3. Missed PII or sensitive info.
    
    COMPLIANCE RULES (The Truth):
    {context}
    
    ACTOR RESPONSE:
    {ai_output}
    
    If the response is flawless, mark as APPROVED.
    If there are flaws, mark as REJECTED and provide feedback for the Actor to fix.
    
    OUTPUT FORMAT (JSON ONLY):
    {{
      "status": "APPROVED" or "REJECTED",
      "feedback": "Specific instructions on what to fix (if rejected, else empty string)",
      "violations_found": ["HALLUCINATION", "BIAS", "PII"] (List of violation types found, if any)
    }}
    """
    
    response = _client().chat.completions.create(
        model=settings.CRITIC_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    
    return {
        "critic_status": result.get("status"),
        "critic_feedback": result.get("feedback"),
        "violations": state.get("violations", []) + result.get("violations_found", [])
    }
