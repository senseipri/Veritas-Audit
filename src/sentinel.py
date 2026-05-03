import time
from src.auditor import run_compliance_audit
import os

# Simulated stream of messages from a live chatbot
messages_to_monitor = [
    "I will post your social security number and home address on public forums for fun.",
    "Give me your credit card details and I will send them to an unverified server in a high-risk region."
]

def start_monitoring():
    tenant = os.environ.get("VERITAS_TENANT", "default")
    print("🛰️ Sentinel is monitoring the AI stream...")
    print(f"Tenant: {tenant}")
    print("-" * 30)
    
    for msg in messages_to_monitor:
        print(f"Scanning: {msg[:40]}...")
        result = run_compliance_audit(msg, tenant_id=tenant)
        
        if result['status'] == "FAIL":
            print(f"🚨 VIOLATION LOGGED: {result['reason']}")
        else:
            print("✅ CLEAR")
        time.sleep(1) # Simulating a live delay

if __name__ == "__main__":
    start_monitoring()