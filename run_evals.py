# run_evals.py
import json
import requests

BASE_URL = "http://localhost:8000/query"

with open("mock-data/evaluation_questions.json") as f:
    questions = json.load(f)

results = []
for q in questions:
    try:
        resp = requests.post(BASE_URL, json={"question": q}, timeout=60)
        data = resp.json()
        results.append({
            "question": q,
            "status": resp.status_code,
            "answer_preview": data.get("answer", "")[:150],
            "sources": data.get("sources", []),
        })
    except Exception as e:
        results.append({"question": q, "status": "ERROR", "error": str(e)})

passed = sum(1 for r in results if r.get("status") == 200)
print(f"\n{passed}/{len(questions)} returned 200 OK\n")

for r in results:
    print(f"[{r['status']}] {r['question']}")
    print(f"    -> {r.get('answer_preview', r.get('error'))}")
    print(f"    sources: {r.get('sources')}\n")