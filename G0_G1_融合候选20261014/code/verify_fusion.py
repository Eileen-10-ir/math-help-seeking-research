"""Independent artifact audit of exploratory fusion predictions and fold composition."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parent
OLD = ROOT / "G0_G1严谨对照20261014"
LAB = ["high", "medium", "low"]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def csvrows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

hashes = json.loads((OUT / "data/input_hashes.json").read_text(encoding="utf-8"))
assert all(sha(ROOT / p) == h for p, h in hashes.items())
summary = json.loads((OUT / "results/summary.json").read_text(encoding="utf-8"))
audit = json.loads((OUT / "data/fold_audit.json").read_text(encoding="utf-8"))
assert len(audit) == 20
old_folds = json.loads((OLD / "data/fold_audit.json").read_text(encoding="utf-8"))
lookup = {(int(r["seed"]), int(r["fold"])): r for r in old_folds}
generated = defaultdict(list)
for row in csvrows(OLD / "data/generated_outer_corpora.csv"):
    if row["generator"] in ("G0", "G1_ALSP"):
        generated[(int(row["seed"]), int(row["fold"]), row["generator"])].append(row)
for item in audit:
    key = (item["seed"], item["fold"])
    original = lookup[key]
    assert item["train_ids"] == original["train_ids"]
    assert item["heldout_ids"] == original["heldout_ids"]
    assert item["equal_synthetic_total"] == 91
    assert item["full_synthetic_total"] == 182
    for name, selected_key, count_key in (("G0", "selected_G0_keys", "equal_G0_selected"),
                                           ("G1_ALSP", "selected_G1_keys", "equal_G1_selected")):
        pool = generated[key + (name,)]
        selected = item[selected_key]
        assert len(selected) == item[count_key]
        assert len(set(selected)) == len(selected)
        assert set(selected) <= {row["feature_key"] for row in pool}
        if name == "G1_ALSP":
            assert all(row["parent_id"] in item["train_ids"] for row in pool)
    assert not set(item["selected_G0_keys"]) & set(item["selected_G1_keys"])

predictions = csvrows(OUT / "results/predictions.csv")
by = defaultdict(list)
for row in predictions:
    key = (row["variant"], int(row["seed"]))
    by[key].append(row)
    fold = lookup[(int(row["seed"]), int(row["fold"]))]
    assert row["sample_id"] in fold["heldout_ids"]
    p = [float(row["p_" + label]) for label in LAB]
    assert abs(sum(p) - 1) < 1e-10
    assert row["prediction"] == LAB[max(range(3), key=lambda i: p[i])]
assert len(by) == 10
metrics = defaultdict(list)
low_cases = defaultdict(dict)
for (variant, seed), rows in by.items():
    assert len(rows) == 47 and len({row["sample_id"] for row in rows}) == 47
    cm = [[0] * 3 for _ in LAB]
    for row in rows:
        cm[LAB.index(row["truth"])][LAB.index(row["prediction"])] += 1
        if row["truth"] == "low":
            low_cases[variant].setdefault(row["sample_id"], {})[seed] = row["prediction"]
    f1 = []
    for i in range(3):
        denominator = sum(cm[i]) + sum(cm[j][i] for j in range(3))
        f1.append(2 * cm[i][i] / denominator if denominator else 0)
    metrics[variant].append((sum(f1) / 3, sum(cm[i][i] for i in range(3)) / 47, cm))
for variant, rows in metrics.items():
    assert abs(sum(row[0] for row in rows) / 5 - summary["metrics"][variant]["macro_f1"]) < 1e-12
    assert abs(sum(row[1] for row in rows) / 5 - summary["metrics"][variant]["accuracy"]) < 1e-12

result = {"source_hashes_unchanged": True, "twenty_folds_match_previous": True,
          "student_holdouts_and_G1_parent_ids_isolated": True,
          "equal_budget_91_and_full_budget_182_verified": True,
          "all_470_new_predictions_recomputed": True,
          "low_class_predictions_by_student": low_cases,
          "independent_semantic_review": "pending"}
(OUT / "results/independent_artifact_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "low_class_predictions_by_student"}, ensure_ascii=False))
