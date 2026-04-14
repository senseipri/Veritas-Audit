import streamlit as st
from src.auditor import run_compliance_audit

# 1. Page Configuration
st.set_page_config(page_title="Veritas AI Auditor", page_icon="⚖️")

st.title("⚖️ Veritas-Audit Dashboard")
st.markdown("### Production-Ready AI Compliance Monitoring")
st.divider()

# 2. User Input
st.subheader("Audit a Bot Response")
user_input = st.text_area(
    "Paste the AI generated response here:",
    placeholder="e.g., We store all user passwords in plain text for 24 hours..."
)

# 3. Execution Logic
if st.button("Run Compliance Audit"):
    if user_input.strip():
        with st.spinner("Analyzing against legal documents and Groq Cloud..."):
            try:
                # Call the logic you built on Day 2
                result = run_compliance_audit(user_input)
                
                # 4. Display Results
                st.divider()
                if result['status'] == "PASS":
                    st.success("✅ AUDIT PASSED")
                else:
                    st.error("❌ AUDIT FAILED")
                
                st.write(f"**Reasoning:** {result['reason']}")
                
                with st.expander("View Violated Rule Snippet"):
                    st.info(result.get('violated_rule_snippet', "No specific rule violated."))
                    
            except Exception as e:
                st.error(f"Error during audit: {e}")
    else:
        st.warning("Please enter some text to audit.")

# Sidebar for Project Info
st.sidebar.title("System Info")
st.sidebar.info("""
- **Model:** Llama 3.3 70B (via Groq)
- **Engine:** RAG (ChromaDB)
- **Evaluation:** 100% Accuracy
""")