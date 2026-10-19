"""Small coverage-first blind sheet for joint-expression v2, not a population sample."""
import csv
import json
import random
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--data-dir', type=Path)
args = parser.parse_args()
OUT = args.data_dir.resolve() if args.data_dir else Path(__file__).resolve().parents[1]
with (OUT / 'data/联合表达v2_全部折候选.csv').open(encoding='utf-8-sig', newline='') as f:
    generated = list(csv.DictReader(f))
specs = {r['candidate_id']: r for r in json.loads((OUT / 'data/参数说明_联合表达v2.json').read_text(encoding='utf-8'))}
fixtures = json.loads((OUT / 'data/工程步骤覆盖样例_不混入训练.json').read_text(encoding='utf-8'))
chosen, texts = [], set()
types = ['answer_request', 'full_solution_request', 'method_help', 'concept_or_reason_help',
         'method_clue_local_help', 'autonomy_declared_request', 'autonomous_statement']
for kind in types:
    same = [r for r in generated if r['behavior_type'] == kind]
    selected = []
    for letter in ('q', 'l', 'f', 'g'):
        options = [r for r in same if specs[r['candidate_id']]['task_code'].startswith(letter) and r['prompt_text'] not in texts]
        if options:
            row = options[0]; selected.append(row); texts.add(row['prompt_text'])
    while len(selected) < 4:
        row = next(r for r in same if r['prompt_text'] not in texts)
        selected.append(row); texts.add(row['prompt_text'])
    chosen += [{'selection': 'behavior_type_coverage', 'source_kind': 'training_fold_candidate', **r,
                'spec': specs[r['candidate_id']]} for r in selected]
border = [r for r in generated if r['prompt_text'] not in texts and
          (specs[r['candidate_id']]['learning_goal'] == 'transfer' and r['final_level'] == 'high' or
           specs[r['candidate_id']]['information_layout'] in ('deictic', 'topic'))]
for r in border:
    if r['prompt_text'] in texts:
        continue
    texts.add(r['prompt_text'])
    chosen.append({'selection': 'mixed_goal_or_context_boundary', 'source_kind': 'training_fold_candidate',
                   **r, 'spec': specs[r['candidate_id']]})
    if len(chosen) == 36:
        break
assert len(chosen) == 36
for letter in ('q', 'l', 'f', 'g'):
    for row in [r for r in fixtures if r['spec']['task_code'].startswith(letter)][:2]:
        chosen.append({'selection': 'mathematical_step_coverage', 'source_kind': 'engineering_fixture_not_empirical_training',
                       'final_level': 'low', **row})
random.Random(2026101407).shuffle(chosen)
blind, key = [], []
for i, row in enumerate(chosen):
    rid = f'JREV{i+1:03d}'
    blind.append({'review_id': rid, 'known_question_context': row['question'], 'prompt_text': row['prompt_text'],
                  'reviewer': '', 'proposed_level_high_medium_low_unclear': '', 'visible_behavior': '',
                  'scope_contradiction_0_1': '', 'math_error_0_1_NA': '', 'naturalness_0_1_2': '',
                  'information_sufficient_0_1_context_needed': '', 'evidence_quote': '', 'notes': ''})
    key.append({'review_id': rid, **row})
with (OUT / 'review/联合表达v2_44条盲审公共空表.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(blind[0]));writer.writeheader();writer.writerows(blind)
(OUT / 'review/目标与来源_审后核对.json').write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'blind_records': len(blind), 'training_candidates': 36, 'engineering_fixtures': 8,
                  'human_review': 'pending', 'original_real_labels_changed': 0}, ensure_ascii=False))
