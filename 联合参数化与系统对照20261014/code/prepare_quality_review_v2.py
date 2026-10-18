"""Add the shared prior history and fixed rubric fields to the blind review sheet."""
import csv
import json
from pathlib import Path

base = Path(__file__).resolve().parents[1] / "results" / "real_api"
records = json.loads((base / "records.json").read_text(encoding="utf-8"))
keys = json.loads((base / "质量审后核对.json").read_text(encoding="utf-8"))
with (base / "质量盲审待填.csv").open(encoding="utf-8-sig", newline="") as stream:
    old = list(csv.DictReader(stream))
lookup = {(r["case_id"], r["block"], r["arm"]): r for r in records}
review_key = {r["review_id"]: r for r in keys}
assert len(old) == len(lookup) == len(keys) == 64
rows = []
for item in old:
    marker = review_key[item["review_id"]]
    record = lookup[(marker["case_id"], marker["block"], marker["arm"])]
    history = "；".join("学生：" + h["text"] + " 助手：" + h["support"]["text"] for h in record["history"])
    rows.append({"review_id": item["review_id"], "question": item["question"],
                 "prior_history": history, "student_text": item["student_text"],
                 "reply": item["reply"], "reviewer": "", "math_correct_0_1_2_NA": "",
                 "relevance_0_1_2": "", "actionability_0_1_2": "",
                 "new_answer_revealed_0_1": "", "input_sufficient_0_1": "",
                 "unnecessary_clarification_0_1_NA": "", "directly_completed_task_0_1": "",
                 "used_history_correctly_0_1_NA": "", "evidence_quote": "", "notes": ""})
with (base / "质量盲审表v2_公共空表.csv").open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
assert all("arm" not in row and "route" not in row for row in rows)
print(json.dumps({"rows": len(rows), "history_rows": sum(bool(r["prior_history"]) for r in rows),
                  "identity_and_route_hidden": True}, ensure_ascii=False))
