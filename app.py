import streamlit as st
import requests
import os

# 1. Page Configuration
st.set_page_config(page_title="Veritas AI Auditor", page_icon="⚖️")

st.title("⚖️ Veritas-Audit Dashboard")
st.markdown("### Production-Ready AI Compliance Monitoring")
st.divider()

# 2. User Input
st.subheader("Audit a Bot Response")
tenant = st.sidebar.text_input("Tenant ID", value=os.environ.get("VERITAS_TENANT", "default"))


st.sidebar.subheader("API Configuration")
api_url = st.sidebar.text_input("API Base URL", value=os.environ.get("VERITAS_API_URL", "http://localhost:8000"))
api_key = st.sidebar.text_input("API Key", value=os.environ.get("VERITAS_API_KEY", ""), type="password")

user_input = st.text_area(
    "Paste the AI generated response here:",
    placeholder="e.g., We store all user passwords in plain text for 24 hours..."
)

# 3. Execution Logic
if st.button("Run Compliance Audit"):
    if user_input.strip():
        with st.spinner("Analyzing against legal documents and Groq Cloud..."):
            if not api_key:
                st.error("Missing API Key. Please provide it in the sidebar.")
            else:
                try:
                    headers = {
                        "x-api-key": api_key,
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "tenant_id": tenant,
                        "response_text": user_input,
                        "fail_closed": True
                    }
                    
                    endpoint = f"{api_url.rstrip('/')}/v1/audit"
                    response = requests.post(endpoint, headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # 4. Display Results
                        st.divider()
                        if result['status'] == "PASS":
                            st.success("✅ AUDIT PASSED")
                        else:
                            st.error("❌ AUDIT FAILED")
                        
                        st.write(f"**Reasoning:** {result['reason']}")
                        
                        with st.expander("View Violated Rule Snippet"):
                            st.info(result.get('violated_rule_snippet', "No specific rule violated.") or "No specific rule violated.")
                            
                        st.caption(f"Latency: {result.get('latency_ms', 0)} ms | Timestamp: {result.get('timestamp_utc', '')}")
                    else:
                        st.error(f"API Error: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    st.error(f"Error connecting to API: {e}")
    else:
        st.warning("Please enter some text to audit.")

# Sidebar for Project Info
st.sidebar.title("System Info")
st.sidebar.info("""
- **Model:** Llama 3.3 70B (via Groq)
- **Engine:** RAG (ChromaDB)
- **Evaluation:** 100% Accuracy
""")