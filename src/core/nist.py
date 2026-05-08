from typing import Dict, Any, List

def map_risk_to_nist(violations: List[str]) -> Dict[str, Any]:
    """
    NIST AI RMF Risk Mapping module.
    Maps system violations (like PII, Hallucination, Bias) to NIST AI RMF categories.
    """
    nist_tags = []
    severity = "LOW"
    
    if "SSN" in violations or "CREDIT_CARD" in violations or "PII" in violations:
        nist_tags.append("NIST-AI-RMF: MEASURE-2.1 (Privacy Risk)")
        severity = "HIGH"
        
    if "HALLUCINATION" in violations:
        nist_tags.append("NIST-AI-RMF: MEASURE-2.5 (Accuracy & Reliability)")
        severity = "HIGH" if severity == "HIGH" else "MEDIUM"
        
    if "BIAS" in violations:
        nist_tags.append("NIST-AI-RMF: MEASURE-2.4 (Bias & Fairness)")
        severity = "HIGH"
        
    if not violations:
        nist_tags.append("NIST-AI-RMF: COMPLIANT")
        
    return {
        "nist_tags": nist_tags,
        "risk_severity": severity
    }
