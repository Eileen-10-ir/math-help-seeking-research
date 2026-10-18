"""Portable package audit. Fresh generation is a mechanism check, not a new score."""
import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path)
args = parser.parse_args()
ROOT = args.root.resolve() if args.root else Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest = json.loads((ROOT / 'release_manifest.json').read_text(encoding='utf-8'))
for path, expected in manifest['protected_files'].items():
    assert sha(ROOT / path) == expected, ('Source changed or incomplete', path)

sys.path[:0] = [str(ROOT / '统一数据与交接准备20261014/code'),
               str(ROOT / '数学主线严谨重跑20260930/code'),
               str(ROOT / 'G0_G1严谨对照20261014/code')]
from common import LAB, F, B
from joint_renderer import sample_and_render
from independent_contract_check import check_contract
import joblib
import sklearn
import numpy

snapshot = json.loads((ROOT / '数学主线严谨重跑20260930/data/anonymous_samples_snapshot.json').read_text(encoding='utf-8'))
assert len(snapshot['real_r1']) == len(snapshot['real_r3']) == 47
assert Counter(r['final_level'] for r in snapshot['real_r1']) == Counter(high=12, medium=31, low=4)
assert Counter(r['final_level'] for r in snapshot['real_r3']) == Counter({'high': 7, 'medium': 21, 'low': 5, '接受引导/非提问': 14})
with (ROOT / '参数验证与生成器比较20261014/四维均值_真实R1_47条.csv').open(encoding='utf-8-sig', newline='') as f:
    scores = list(csv.DictReader(f))
score_by = {r['sample_id']: r for r in scores}
for r in scores:
    for dim in 'ALSP':
        assert float(r[dim + '_mean']) == (float(r[dim + '_rater_A']) + float(r[dim + '_rater_B'])) / 2
    assert r['final_level'] == next(x['final_level'] for x in snapshot['real_r1'] if x['sample_id'] == r['sample_id'])
db = ROOT / '统一数据与交接准备20261014/data/数学真实94条_研究只读导出.sqlite3'
c = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
assert c.execute('SELECT COUNT(*) FROM samples').fetchone()[0] == 94
assert c.execute('SELECT COUNT(*) FROM r1_scores').fetchone()[0] == 47
actual = {r[0]: r[1:] for r in c.execute('SELECT sample_id,student_id,round,pair_id,prompt_text,final_level FROM samples')}
expected = {r['sample_id']: (r['student_id'], r['round'], r.get('pair_id'), r['prompt_text'], r['final_level']) for r in snapshot['real_r1'] + snapshot['real_r3']}
assert actual == expected
c.close()
folds = json.loads((ROOT / 'G0_G1严谨对照20261014/data/fold_audit.json').read_text(encoding='utf-8'))
by_fold = {(r['seed'], r['fold']): r for r in folds}
specs = json.loads((ROOT / '统一数据与交接准备20261014/data/参数说明_联合表达v2.json').read_text(encoding='utf-8'))
with (ROOT / '统一数据与交接准备20261014/data/联合表达v2_全部折候选.csv').open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))
by_id = {r['candidate_id']: r for r in rows}
assert len(rows) == len(specs) == 1820
for spec in specs:
    fold = by_fold[(spec['seed'], spec['fold'])]
    assert spec['parent_id'] in fold['train_ids'] and spec['parent_id'] not in fold['heldout_ids']
    assert spec['target_ALSP_mean'] == [float(score_by[spec['parent_id']][dim + '_mean']) for dim in 'ALSP']
    row = by_id[spec['candidate_id']]
    assert row['final_level'] == spec['final_level_candidate']
    assert check_contract(spec, row['prompt_text'], row['question'])['status'] == 'pass'
for key, fold in by_fold.items():
    rr = [r for r in rows if (int(r['seed']), int(r['fold'])) == key]
    assert len(rr) == 91 and len({B.safe_mask(F.normalize_prompt(r['prompt_text'])) for r in rr}) == 91
    assert Counter(r['final_level'] for r in rr) == Counter(fold['quotas'])
summary = json.loads((ROOT / '统一数据与交接准备20261014/results/数据基座验收.json').read_text(encoding='utf-8'))
assert summary['negative_controls_detected'] == summary['negative_control_count'] == 24
assert summary['math_assertions_in_engineering_coverage_fixtures'] == 24
with (ROOT / '统一数据与交接准备20261014/data/真实行为类型解释_机器候选.csv').open(encoding='utf-8-sig', newline='') as f:
    types = {r['sample_id']: r['behavior_type'] for r in csv.DictReader(f)}
train_ids = folds[0]['train_ids']
calibration = []
for sid in train_ids:
    original = score_by[sid]
    r = {k: original[k] for k in ('sample_id', 'student_id', 'final_level')}
    r.update({dim + '_' + suffix: float(original[dim + '_' + suffix]) for dim in 'ALSP' for suffix in ('mean', 'rater_A', 'rater_B')})
    calibration.append(r)
new = sample_and_render(calibration, {sid: types[sid] for sid in train_ids},
                        {'high': 6, 'medium': 6, 'low': 6}, seed=20261407, tau=1.0)
again = sample_and_render(calibration, {sid: types[sid] for sid in train_ids},
                          {'high': 6, 'medium': 6, 'low': 6}, seed=20261407, tau=1.0)
assert new == again and all(check_contract(r['spec'], r['prompt_text'], r['question'])['status'] == 'pass' for r in new)
card = json.loads((ROOT / '数学主线严谨重跑20260930/data/runtime_model_card.json').read_text(encoding='utf-8'))
artifact = ROOT / '数学主线严谨重跑20260930/data/runtime_models_v1.joblib'
assert sha(artifact) == card['artifact_sha256']
models = joblib.load(artifact)
prob = models['first'].probs(['这道题可以给我一点解题思路吗？'])
assert prob.shape == (1, 3) and abs(float(prob.sum()) - 1) < 1e-9
result = {'protected_files_verified': len(manifest['protected_files']), 'real_samples': 94,
          'real_students': 47, 'joint_rows_verified': 1820, 'fixed_folds': 20,
          'fresh_generation_samples': 18, 'new_seed_deterministic': True,
          'model_loaded': True, 'python': sys.version.split()[0], 'numpy': numpy.__version__,
          'sklearn': sklearn.__version__, 'human_semantic_review': 'pending', 'API_called': False}
dest = ROOT / '交付结果/包核验'
dest.mkdir(parents=True, exist_ok=True)
(dest / '核验结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
