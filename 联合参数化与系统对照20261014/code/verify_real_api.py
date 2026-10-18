"""Audit the frozen four-arm real API run without changing its records."""
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

out = Path(__file__).resolve().parents[1]
base = out / "results" / "real_api"
records = json.loads((base / "records.json").read_text(encoding="utf-8"))
manifest = json.loads((base / "frozen_run_manifest.json").read_text(encoding="utf-8"))
assert len(records) == len(manifest["order"]) == 64
assert [(r["block"], r["case_id"], r["arm"]) for r in records] == [tuple(x) for x in manifest["order"]]
for block in (1, 2):
    for case in {r["case_id"] for r in records}:
        same = [r for r in records if r["block"] == block and r["case_id"] == case]
        assert len(same) == 4
        assert len({r["arm"] for r in same}) == 4
        for field in ("text", "task_id", "initial_state", "history", "shared_analysis_sha256"):
            assert len({json.dumps(r[field], ensure_ascii=False, sort_keys=True) for r in same}) == 1, (block, case, field)

def percentile(values, proportion):
    values = sorted(values)
    if not values:
        return None
    i = (len(values) - 1) * proportion
    lo = math.floor(i)
    hi = math.ceil(i)
    return values[lo] + (values[hi] - values[lo]) * (i - lo)

byarm = defaultdict(list)
for r in records:
    byarm[r["arm"]].append(r)

result = {"source": "real_api_fixed_engineering_cases_not_students", "frozen_cases": 8, "repeats": 2, "records": 64,
          "same_input_history_state_analysis_by_case_block": True,
          "quality_status": "independent_blind_review_pending", "arms": {}}
for arm, rows in sorted(byarm.items()):
    usage = [r["support"]["usage"] for r in rows if r["support"].get("usage")]
    latency = [r["actual_total_latency_ms"] for r in rows if r["actual_total_latency_ms"] is not None]
    success_latency = [r["actual_total_latency_ms"] for r in rows if r["support"]["status"] in ("success", "local_success")]
    costs = [r["cost_estimate"] for r in rows if r["cost_estimate"]]
    assert len(latency) == 16 and len(success_latency) == 16
    result["arms"][arm] = {
        "records": len(rows),
        "cloud_attempts": sum(r["support"]["external_cloud_attempts"] for r in rows),
        "cloud_successes": sum(r["support"]["external_cloud_successes"] for r in rows),
        "routes": dict(Counter(r["support"]["route_requested"] for r in rows)),
        "status": dict(Counter(r["support"]["status"] for r in rows)),
        "returned_model": dict(Counter(r["support"].get("model_returned") for r in rows if r["support"].get("model_returned"))),
        "finish_reason": dict(Counter(r["support"].get("finish_reason") for r in rows if r["support"].get("finish_reason"))),
        "prompt_tokens": sum(x["prompt_tokens"] for x in usage),
        "completion_tokens": sum(x["completion_tokens"] for x in usage),
        "total_tokens": sum(x["total_tokens"] for x in usage),
        "cost_usd_lower_offpeak": sum(x["usd_lower_offpeak"] for x in costs),
        "cost_usd_upper_peak": sum(x["usd_upper_peak"] for x in costs),
        "mean_total_ms": statistics.mean(latency),
        "p50_total_ms": percentile(latency, .50),
        "p95_total_ms": percentile(latency, .95),
        "mean_success_ms": statistics.mean(success_latency),
        "quality_scored": 0,
    }
assert sum(x["cloud_attempts"] for x in result["arms"].values()) == 42
assert all(x["cloud_attempts"] == x["cloud_successes"] for x in result["arms"].values())
assert result["arms"]["edge_fixed"]["cloud_attempts"] == 0
assert result["arms"]["hybrid"]["routes"].get("edge_verify") == 2
(base / "独立记录核验与用量汇总.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
