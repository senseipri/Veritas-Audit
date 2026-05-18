"""
src/core/guardrails.py
Tier-0 guardrails layer powered by NVIDIA NeMo Guardrails.

Responsibilities:
  - Fast local regex PII scrubbing (SSN, credit card, email, phone, IP).
  - Optional NeMo Guardrails rails integration for LLM-level policy enforcement.

The public interface (intercept_pii) is drop-in compatible with the old
bedrock.py so no callers need to change their call signatures.
"""

import os
import re
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Optional NeMo Guardrails integration
# ---------------------------------------------------------------------------
try:
    from nemoguardrails import RailsConfig, LLMRails  # type: ignore

    _NEMO_CONFIG_PATH = os.environ.get("NEMO_GUARDRAILS_CONFIG", "config/nemo_guardrails")

    def _load_nemo_rails() -> "LLMRails | None":
        """Load NeMo rails from the config directory if it exists."""
        if os.path.isdir(_NEMO_CONFIG_PATH):
            config = RailsConfig.from_path(_NEMO_CONFIG_PATH)
            return LLMRails(config)
        return None

    _rails: "LLMRails | None" = _load_nemo_rails()
    NEMO_AVAILABLE = True

except ImportError:
    _rails = None
    NEMO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Tier-0: Fast regex PII interception
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[str, str, str]] = [
    ("SSN",         r"\b\d{3}-\d{2}-\d{4}\b",                                      "[REDACTED_SSN]"),
    ("CREDIT_CARD", r"\b\d{4}-\d{4}-\d{4}-\d{4}\b",                               "[REDACTED_CC]"),
    ("EMAIL",       r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",      "[REDACTED_EMAIL]"),
    ("PHONE",       r"\b(?:\+?\d{1,3}[.\-\s]?)?\(?\d{3}\)?[.\-\s]?\d{3}[.\-\s]?\d{4}\b",
                    "[REDACTED_PHONE]"),
    ("IP_ADDRESS",  r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",                    "[REDACTED_IP]"),
]


def intercept_pii(text: str) -> Dict[str, Any]:
    """
    Tier-0 (Fast Intercept) logic.

    Runs high-speed local regex to scrub PII before passing text to LLM agents.
    This is the 'Free Tier' protection layer, powered by NeMo Guardrails-compatible
    pipeline (regex front-end + optional NeMo rails for LLM-level policy).

    Returns:
        {
            "is_blocked":    bool   — True if any PII was found,
            "redacted_text": str    — text with PII replaced by tokens,
            "violations":    list   — list of violation type strings,
        }
    """
    violations: list[str] = []
    redacted = text

    for label, pattern, replacement in _PII_PATTERNS:
        if re.search(pattern, redacted):
            violations.append(label)
            redacted = re.sub(pattern, replacement, redacted)

    return {
        "is_blocked": len(violations) > 0,
        "redacted_text": redacted,
        "violations": violations,
    }


# ---------------------------------------------------------------------------
# NeMo Guardrails LLM-level check (optional, async-friendly)
# ---------------------------------------------------------------------------

async def check_nemo_rails(text: str) -> Dict[str, Any]:
    """
    Run text through NeMo Guardrails rails (if configured).

    Returns a dict with:
        {
            "blocked":  bool,
            "output":   str   — guardrail-filtered output or original text,
            "reason":   str,
        }

    If NeMo Guardrails is not installed or not configured, returns
    {"blocked": False, "output": text, "reason": "NeMo Guardrails not configured"}.
    """
    if not NEMO_AVAILABLE or _rails is None:
        return {
            "blocked": False,
            "output": text,
            "reason": "NeMo Guardrails not configured",
        }

    try:
        result = await _rails.generate_async(messages=[{"role": "user", "content": text}])
        output_text = result if isinstance(result, str) else result.get("content", text)
        return {
            "blocked": False,
            "output": output_text,
            "reason": "Passed NeMo Guardrails",
        }
    except Exception as exc:  # pragma: no cover
        return {
            "blocked": True,
            "output": "",
            "reason": f"NeMo Guardrails error: {exc}",
        }
