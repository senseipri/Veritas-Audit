import json
import time
from src.auditor import run_compliance_audit

def run_benchmark():
    with open("tests/scenarios.json", "r") as f:
        scenarios = json.load(f)
    
    results = []
    passed_evals = 0
    
    print(f"🚀 Starting Benchmark: {len(scenarios)} scenarios found.\n")
    
    for item in scenarios:
        print(f"Testing ID {item['id']} [{item['category']}]...")
        
        # Run the audit
        audit_result = run_compliance_audit(item['bot_response'])
        
        # Compare result to expectation
        is_correct = audit_result['status'] == item['expected_status']
        if is_correct:
            passed_evals += 1
            
        results.append({
            "id": item['id'],
            "bot_response": item['bot_response'],
            "predicted": audit_result['status'],
            "expected": item['expected_status'],
            "correct": is_correct,
            "reason": audit_result['reason']
        })
        
        # Small sleep to respect Groq rate limits (optional)
        time.sleep(0.5)

    # Calculate Score
    accuracy = (passed_evals / len(scenarios)) * 100
    
    # Save the report
    report = {
        "benchmark_accuracy": f"{accuracy}%",
        "total_scenarios": len(scenarios),
        "details": results
    }
    
    with open("compliance_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✅ Benchmark Complete! Accuracy: {accuracy}%")
    print("Results saved to 'compliance_report.json'")

if __name__ == "__main__":
    run_benchmark()