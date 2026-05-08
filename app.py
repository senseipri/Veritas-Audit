import csv
import os
import sys
from pathlib import Path

import requests
import streamlit as st

# Repo root on sys.path for `src.*` imports (same pattern as tests)
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.core.storage import tenant_paths  # noqa: E402

st.set_page_config(page_title="Veritas AI Auditor", page_icon="⚖️")

st.title("⚖️ Veritas-Audit Dashboard")
st.markdown("### Production-Ready AI Compliance Monitoring")
st.divider()

tenant = st.sidebar.text_input("Tenant ID", value=os.environ.get("VERITAS_TENANT", "default"))

st.sidebar.subheader("API Configuration")
api_url = st.sidebar.text_input("API Base URL", value=os.environ.get("VERITAS_API_URL", "http://localhost:8000"))
api_key = st.sidebar.text_input("API Key", value=os.environ.get("VERITAS_API_KEY", ""), type="password")

tab_audit, tab_logs = st.tabs(["Audit", "Tenant logs"])

with tab_audit:
    st.subheader("Audit a Bot Response")
    user_input = st.text_area(
        "Paste the AI generated response here:",
        placeholder="e.g., We store all user passwords in plain text for 24 hours...",
        key="audit_input",
    )

    if st.button("Run Compliance Audit"):
        if user_input.strip():
            with st.spinner("Analyzing against legal documents and Groq Cloud..."):
                if not api_key:
                    st.error("Missing API Key. Please provide it in the sidebar.")
                else:
                    try:
                        headers = {
                            "x-api-key": api_key,
                            "Content-Type": "application/json",
                        }
                        payload = {
                            "tenant_id": tenant,
                            "response_text": user_input,
                            "fail_closed": True,
                        }

                        endpoint = f"{api_url.rstrip('/')}/v1/audit"
                        response = requests.post(endpoint, headers=headers, json=payload, timeout=120)

                        if response.status_code == 200:
                            result = response.json()

                            st.divider()
                            if result.get("status") == "PASS":
                                st.success("AUDIT PASSED")
                            else:
                                st.error("AUDIT FAILED")

                            st.write(f"**Decision:** {result.get('decision', '')}")
                            st.write(f"**Reasoning:** {result.get('reason', '')}")
                            violations = result.get("violations") or []
                            if violations:
                                st.write("**Violations:**")
                                for v in violations:
                                    st.write(f"- {v}")
                            else:
                                st.caption("No violations reported for this response.")

                            with st.expander("Raw API response"):
                                st.json(result)

                            st.caption(
                                f"Latency: {result.get('latency_ms', 0)} ms | "
                                f"Timestamp: {result.get('timestamp_utc', '')}"
                            )
                        else:
                            st.error(f"API Error: {response.status_code} - {response.text}")

                    except Exception as e:
                        st.error(f"Error connecting to API: {e}")
        else:
            st.warning("Please enter some text to audit.")

with tab_logs:
    st.subheader("Tenant audit history (local CSV)")
    paths = tenant_paths(tenant)
    log_file = paths.logs_dir / "audit_history.csv"
    st.caption(f"Reading: `{log_file}`")

    if not log_file.is_file():
        st.info("No audit log file yet for this tenant. Run audits via the API to populate `audit_history.csv`.")
    else:
        with open(log_file, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            st.warning("Log file exists but is empty.")
        else:
            st.dataframe(rows, use_container_width=True, hide_index=True)

st.sidebar.title("System Info")
st.sidebar.info("""
- **Model:** Llama 3.3 70B (via Groq)
- **Engine:** RAG (ChromaDB)
- **Agents:** Actor + Critic (LangGraph)
""")
