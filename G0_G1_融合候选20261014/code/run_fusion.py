"""Exploratory G0+G1+real comparison, reusing frozen fold corpora and splits."""
import os
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parent
OLD = ROOT / "G0_G1严谨对照20261014"
MAIN = ROOT / "数学主线严谨重跑20260930"
import sys
sys.path.insert(0, str(MAIN / "code"))
from common import Classifier, LAB, SEEDS, load, metrics

for sub in ("results", "data"):
    (OUT / sub).mkdir(exist_ok=True)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    (OUT / path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def csvsave(path, rows):
    if not rows:
        return
    with (OUT / path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def event(stage, **payload):
    row = {"time": datetime.now().astimezone().isoformat(), "stage": stage, **payload}
    with (OUT / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False), flush=True)

def score_from_prediction(array, truth, selected):
    cm = np.bincount(truth[selected] * 3 + array[selected], minlength=9).reshape(3, 3)
    denom = cm.sum(axis=0) + cm.sum(axis=1)
    return float(np.divide(2 * np.diag(cm), denom, out=np.zeros(3), where=denom > 0).mean())

def main():
    sources = [OUT / "01_执行前协议.md", Path(__file__), OLD / "data/generated_outer_corpora.csv",
               OLD / "data/fold_audit.json", OLD / "results/predictions.csv",
               OLD / "data/frozen_manifest.json", MAIN / "data/anonymous_samples_snapshot.json",
               MAIN / "code/common.py", MAIN / "code/controlled_text.py"]
    hashes = {str(path.relative_to(ROOT)): sha(path) for path in sources}
    save("data/input_hashes.json", hashes)
    event("start", experiment="G0+G1+real", source_hashes_recorded=len(hashes))

    real, _, _, _ = load()
    assert len(real) == 47 and len({row["student_id"] for row in real}) == 47
    real_by_id = {row["sample_id"]: row for row in real}
    position = {row["sample_id"]: i for i, row in enumerate(real)}
    y = [row["final_level"] for row in real]
    corpora = defaultdict(list)
    with (OLD / "data/generated_outer_corpora.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["generator"] in ("G0", "G1_ALSP"):
                corpora[(int(row["seed"]), int(row["fold"]), row["generator"])].append(row)
    folds = json.loads((OLD / "data/fold_audit.json").read_text(encoding="utf-8"))
    assert len(folds) == 20
    variants = ["fusion_equal_mixed", "fusion_full_mixed"]
    pp = {name: np.zeros((5, 47, 3)) for name in variants}
    predictions = []
    audits = []
    repeats = []
    for fold in folds:
        seed = int(fold["seed"])
        number = int(fold["fold"])
        train = [real_by_id[sid] for sid in fold["train_ids"]]
        test = [real_by_id[sid] for sid in fold["heldout_ids"]]
        assert len(train) + len(test) == 47
        assert not {row["student_id"] for row in train} & {row["student_id"] for row in test}
        g0 = corpora[(seed, number, "G0")]
        g1 = corpora[(seed, number, "G1_ALSP")]
        quotas = {str(k): int(v) for k, v in fold["quotas"].items()}
        assert Counter(row["final_level"] for row in g0) == Counter(quotas)
        assert Counter(row["final_level"] for row in g1) == Counter(quotas)
        assert all(row["parent_id"] in fold["train_ids"] for row in g1)
        key0 = {row["feature_key"]: row["final_level"] for row in g0}
        key1 = {row["feature_key"]: row["final_level"] for row in g1}
        assert len(key0) == len(g0) and len(key1) == len(g1)
        assert not set(key0) & set(key1), "Cross-generator masked duplicate; resolve before training"

        chosen0, chosen1 = [], []
        for class_index, level in enumerate(LAB):
            n0 = quotas[level] // 2
            n1 = quotas[level] - n0
            group0 = [row for row in g0 if row["final_level"] == level]
            group1 = [row for row in g1 if row["final_level"] == level]
            rng0 = np.random.default_rng(seed * 100000 + number * 100 + class_index * 2)
            rng1 = np.random.default_rng(seed * 100000 + number * 100 + class_index * 2 + 1)
            chosen0.extend(group0[int(i)] for i in rng0.choice(len(group0), n0, replace=False))
            chosen1.extend(group1[int(i)] for i in rng1.choice(len(group1), n1, replace=False))
        data_by_variant = {
            "fusion_equal_mixed": chosen0 + chosen1 + train,
            "fusion_full_mixed": g0 + g1 + train,
        }
        si = SEEDS.index(seed)
        for name, rows in data_by_variant.items():
            model = Classifier().fit([row["prompt_text"] for row in rows], [row["final_level"] for row in rows])
            probs = model.probs([row["prompt_text"] for row in test])
            assert probs.shape == (len(test), 3)
            for record, prob in zip(test, probs):
                pp[name][si, position[record["sample_id"]]] = prob
                predictions.append({"variant": name, "seed": seed, "fold": number,
                                    "sample_id": record["sample_id"], "student_id": record["student_id"],
                                    "truth": record["final_level"], "prediction": LAB[int(prob.argmax())],
                                    **{"p_" + k: float(prob[j]) for j, k in enumerate(LAB)}})
        audits.append({"seed": seed, "fold": number, "train_ids": fold["train_ids"],
                       "heldout_ids": fold["heldout_ids"], "real_train_n": len(train),
                       "G0_available": len(g0), "G1_available": len(g1),
                       "equal_G0_selected": len(chosen0), "equal_G1_selected": len(chosen1),
                       "equal_synthetic_total": len(chosen0) + len(chosen1),
                       "full_synthetic_total": len(g0) + len(g1),
                       "cross_generator_masked_overlap": 0,
                       "heldout_parent_overlap": 0,
                       "selected_G0_keys": [row["feature_key"] for row in chosen0],
                       "selected_G1_keys": [row["feature_key"] for row in chosen1]})
        csvsave("results/predictions.csv", predictions)
        save("data/fold_audit.json", audits)
        event("fold_complete", seed=seed, fold=number, real_train=len(train), equal_synthetic=91, full_synthetic=182)
    for name in variants:
        for si, seed in enumerate(SEEDS):
            repeats.append({"variant": name, "seed": seed, **metrics(y, pp[name][si])})
    csvsave("results/repeat_metrics.csv", repeats)

    previous = list(csv.DictReader((OLD / "results/predictions.csv").open(encoding="utf-8-sig", newline="")))
    baselines = ["G0_mixed", "G1_ALSP_mixed", "real_only", "G0_synth", "G1_ALSP_synth"]
    preds_by_variant = {}
    for name in baselines:
        grid = np.zeros((5, 47, 3))
        for row in previous:
            if row["variant"] == name:
                grid[SEEDS.index(int(row["seed"])), position[row["sample_id"]]] = [float(row["p_" + k]) for k in LAB]
        assert np.allclose(grid.sum(axis=2), 1.)
        preds_by_variant[name] = grid
    preds_by_variant.update(pp)
    summary = {}
    for name, grid in preds_by_variant.items():
        vals = [metrics(y, grid[i]) for i in range(5)]
        summary[name] = {key: float(np.mean([v[key] for v in vals])) for key in ("macro_f1", "accuracy", "high_recall", "high_to_low", "brier_multiclass")}
        summary[name]["recall_by_class"] = {level: float(np.mean([v["confusion_matrix"][j][j] / sum(v["confusion_matrix"][j]) for v in vals])) for j, level in enumerate(LAB)}
        summary[name]["low_to_high"] = float(np.mean([v["confusion_matrix"][2][0] / sum(v["confusion_matrix"][2]) for v in vals]))
        summary[name]["confusion_matrix_sum_repeated_predictions"] = np.sum([v["confusion_matrix"] for v in vals], axis=0).tolist()

    old_summary = json.loads((OLD / "results/summary.json").read_text(encoding="utf-8"))["metrics"]
    for name in baselines:
        for metric in ("macro_f1", "accuracy", "high_recall"):
            assert abs(summary[name][metric] - old_summary[name][metric]) < 1e-12, (name, metric)
    truth = np.array([LAB.index(value) for value in y])
    discrete = {name: grid.argmax(axis=2) for name, grid in preds_by_variant.items()}
    rng = np.random.default_rng(20261016)
    pairs = [(new, old) for new in variants for old in ("G0_mixed", "G1_ALSP_mixed")]
    pairs += [("fusion_full_mixed", "fusion_equal_mixed")]
    deltas = {pair: [] for pair in pairs}
    for _ in range(2000):
        selected = rng.integers(0, 47, 47)
        scores = {name: float(np.mean([score_from_prediction(v, truth, selected) for v in array])) for name, array in discrete.items()}
        for pair in pairs:
            deltas[pair].append(scores[pair[0]] - scores[pair[1]])
    comparison = [{"comparison": a + " minus " + b,
                   "delta_macro_f1": summary[a]["macro_f1"] - summary[b]["macro_f1"],
                   "conditional_95_lo": float(np.quantile(deltas[(a, b)], .025)),
                   "conditional_95_hi": float(np.quantile(deltas[(a, b)], .975))} for a, b in pairs]
    csvsave("results/comparisons.csv", comparison)
    assert all(sha(ROOT / p) == h for p, h in hashes.items())
    result = {"status": "completed_exploratory_candidate", "real_students": 47, "repeats": 5,
              "folds_per_repeat": 4, "old_baselines_exactly_reproduced": True,
              "source_hashes_unchanged": True, "all_folds_parent_isolated": True,
              "cross_generator_masked_duplicate_count": 0,
              "human_semantic_review": "pending", "deployed_model_changed": False,
              "metrics": summary, "comparisons": comparison,
              "limitations": ["Post hoc addition after inspecting G0/G1 results",
                              "Internal retrospective repeated holdout of same 47 students",
                              "Only 4 real low-class students", "No independent semantic validation of generated texts"]}
    save("results/summary.json", result)
    event("complete", results={name: {metric: round(summary[name][metric], 4) for metric in ("macro_f1", "accuracy")} for name in variants})

if __name__ == "__main__":
    main()
