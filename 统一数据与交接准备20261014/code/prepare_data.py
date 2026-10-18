"""Build traceable joint-expression candidates and a read-only research export."""
import csv
import hashlib
import json
import re
import sqlite3
import itertools
import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path

from joint_renderer import make_spec, render, interpret_behavior, realize_unique, VERSION
from independent_contract_check import check_contract
from common import F, B

SOURCE = Path(__file__).resolve().parents[1]
ROOT = SOURCE.parent
parser = argparse.ArgumentParser()
parser.add_argument('--output-dir', type=Path)
args = parser.parse_args()
OUT = args.output_dir.resolve() if args.output_dir else SOURCE
OUT.mkdir(parents=True, exist_ok=True)
for folder in ('data', 'results', 'review'):
    (OUT / folder).mkdir(exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def readcsv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def save(path, value):
    (OUT / path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def csvsave(path, rows):
    with (OUT / path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})

def event(stage, **kw):
    record = {'time': datetime.now().astimezone().isoformat(), 'stage': stage, **kw}
    with (OUT / 'events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    print(json.dumps(record, ensure_ascii=False), flush=True)

def main():
    sources = [ROOT / 'G0_G1严谨对照20261014/data/generated_outer_corpora.csv',
               ROOT / 'G0_G1严谨对照20261014/data/fold_audit.json',
               ROOT / '参数验证与生成器比较20261014/四维均值_真实R1_47条.csv',
               ROOT / '数学主线严谨重跑20260930/data/anonymous_samples_snapshot.json',
               SOURCE / '00_执行边界.md', Path(__file__), SOURCE / 'code/joint_renderer.py',
               SOURCE / 'code/independent_contract_check.py']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    save('data/input_hashes.json', hashes)
    event('start', purpose='joint-specification-rendering-and-independent-structural-check')
    scores = readcsv(sources[2])
    source_by_id = {r['sample_id']: r for r in scores}
    snapshot = json.loads(sources[3].read_text(encoding='utf-8'))
    first, following = snapshot['real_r1'], snapshot['real_r3']
    assert len(first) == len(following) == len(scores) == 47
    registry = []
    for r in scores:
        registry.append({'sample_id': r['sample_id'], 'student_id': r['student_id'],
                         'final_level_unchanged': r['final_level'], 'source_text': r['prompt_text'],
                         **interpret_behavior(r['prompt_text'], r['final_level'])})
    csvsave('data/真实行为类型解释_机器候选.csv', registry)
    kind_by_id = {r['sample_id']: r['behavior_type'] for r in registry}
    folds = json.loads(sources[1].read_text(encoding='utf-8'))
    fold_by = {(int(r['seed']), int(r['fold'])): r for r in folds}
    old = [r for r in readcsv(sources[0]) if r['generator'] == 'G1_ALSP']
    specs, rows, checks = [], [], []
    seen_per_fold = {}
    equivalent_rewordings = 0
    for r in old:
        fold = fold_by[(int(r['seed']), int(r['fold']))]
        assert r['parent_id'] in fold['train_ids'] and r['parent_id'] not in fold['heldout_ids']
        parent = source_by_id[r['parent_id']]
        assert json.loads(r['target_profile']) == [float(parent[d + '_mean']) for d in ('A', 'L', 'S', 'P')]
        spec = make_spec(r, kind_by_id[r['parent_id']])
        fold_key = (spec['seed'], spec['fold'])
        seen = seen_per_fold.setdefault(fold_key, set())
        text, question, normalized_key = realize_unique(spec, seen)
        equivalent_rewordings += int(spec['equivalent_rewording_for_training_dedup'])
        assert (text, question) == render(spec)
        result = check_contract(spec, text, question)
        sid = f"J{spec['seed']}_{spec['fold']}_{spec['synthetic_row']:03d}"
        specs.append({'candidate_id': sid, **spec})
        rows.append({'candidate_id': sid, 'seed': spec['seed'], 'fold': spec['fold'],
                     'parent_id': spec['parent_id'], 'final_level': spec['final_level_candidate'],
                     'behavior_type': spec['behavior_type'], 'target_ALSP': spec['target_ALSP_mean'],
                     'configuration_anchors': spec['configuration_anchors'], 'question': question,
                     'prompt_text': text, 'human_review': 'pending', 'structural_status': result['status'],
                     'masked_feature_key': normalized_key, 'renderer_version': VERSION})
        checks.append({'candidate_id': sid, **result})
    save('data/参数说明_联合表达v2.json', specs)
    csvsave('data/联合表达v2_全部折候选.csv', rows)
    save('results/实际文本证据核验.json', checks)
    failed = [r for r in checks if r['status'] != 'pass']
    # Math-step fixtures add engineering coverage, not observations attributed to the 47 students.
    fixtures = []
    fixture_pairs = []
    for letter in ('q', 'l', 'f', 'g'):
        for style in range(6):
            base = next(s for s in specs if s['final_level_candidate'] == 'low').copy()
            base.update(candidate_id=f'fixture_{letter}_{style}', seed=0, fold=0, synthetic_row=style,
                        parent_id=None, parent_student_id=None, target_ALSP_mean=None, tau=None,
                        configuration_anchors=[5, 3, 5, 5], behavior_type='step_feedback',
                        source_behavior_type='engineering_coverage_not_observed_subtype',
                        participation_form='math_step', participation_conditioned_on_behavior_type=False,
                        information_layout='problem_with_focus', learning_goal='understand_current',
                        help_scope='local_feedback', task_code=letter + '0', style=style,
                        request_style=style, participation_style=style, learning_style=style)
            text, question = render(base)
            found = check_contract(base, text, question)
            fixture = {'candidate_id': base['candidate_id'], 'question': question, 'prompt_text': text,
                       'source': 'engineering_positive_control_not_training_real_inference',
                       'spec': base, 'check': found}
            fixtures.append(fixture)
            fixture_pairs.append((base, fixture, found))
    save('data/工程步骤覆盖样例_不混入训练.json', fixtures)
    assert all(row['check']['status'] == 'pass' for row in fixtures)
    assert all(len(row['check']['evidence']['math_assertions']) == 1 for row in fixtures)
    # Independent numerical/context probes alongside deterministic text-level intervention checks.
    intervention = []
    base = next(s for s in specs if s['final_level_candidate'] == 'high' and s['configuration_anchors'] == [1, 3, 3, 1]).copy()
    for dimension, index, value in [('A', 0, 2), ('L', 1, 5), ('S', 2, 5), ('P', 3, 3)]:
        changed = base.copy()
        changed['configuration_anchors'] = base['configuration_anchors'].copy()
        changed['configuration_anchors'][index] = value
        if dimension == 'A':
            changed.update(behavior_type='full_solution_request', help_scope='full_solution')
        elif dimension == 'L':
            changed['learning_goal'] = 'transfer'
        elif dimension == 'S':
            changed['information_layout'] = 'problem_with_focus'
        else:
            changed['participation_form'] = 'claimed_attempt'
        before_text, q = render(base)
        after_text, q2 = render(changed)
        assert before_text != after_text and q == q2
        assert check_contract(changed, after_text, q)['status'] == 'pass'
        intervention.append({'dimension': dimension, 'before_spec': base, 'after_spec': changed,
                             'before_text': before_text, 'after_text': after_text,
                             'scope': 'engineering_configuration_intervention_not_real_score_causal_effect'})
    save('results/四维配置干预对照.json', intervention)
    # Frozen negative controls change actual text, while keeping the requested contract unchanged.
    negatives = []
    def add(category, selected, mutate):
        for spec, row, original in selected[:4]:
            bad = mutate(spec, row)
            assert bad != row['prompt_text']
            found = check_contract(spec, bad, row['question'])
            negatives.append({'category': category, 'candidate_id': row['candidate_id'],
                              'original': row['prompt_text'], 'changed_text': bad,
                              'detected': found['status'] == 'reject', 'failures': found['failures']})
    zipped = list(zip(specs, rows, checks)) + fixture_pairs
    add('answer_scope_reversed', [z for z in zipped if z[0]['help_scope'] == 'final_answer'],
        lambda s, r: r['prompt_text'].rsplit('。', 2)[0].split('。')[0] + '。不要给我答案，只给方法提示。我想弄明白这道题。')
    add('local_request_changed_to_full_solution', [z for z in zipped if z[0]['help_scope'] == 'local_feedback'],
        lambda s, r: r['prompt_text'] + '请把完整解答和最后答案都给我。')
    add('contradictory_attempt', [z for z in zipped if z[0]['participation_form'] == 'math_step'],
        lambda s, r: r['prompt_text'] + '我还没有写出式子，也没有列出计算。')
    add('learning_goal_changed', [z for z in zipped if z[0]['learning_goal'] == 'transfer'],
        lambda s, r: r['prompt_text'].rstrip('。').rsplit('。', 1)[0] + '。我现在只想完成作业。')
    add('wrong_multiplication', [z for z in zipped if '我先算底乘高' in z[1]['prompt_text']],
        lambda s, r: re.sub(r'(\d+×\d+=)(\d+)', lambda m: m[1] + str(int(m[2]) + 1), r['prompt_text']))
    add('statement_changed_to_answer_request', [z for z in zipped if z[0]['help_scope'] == 'none'],
        lambda s, r: r['prompt_text'] + '请直接给最终答案。')
    save('results/故意改坏文本的负例检测.json', negatives)
    # No filtering by held-out text: overlaps are reported after generation, not used to choose expressions.
    overlap = []
    for fold in folds:
        rr = [r for r in rows if r['seed'] == fold['seed'] and r['fold'] == fold['fold']]
        assert len(rr) == 91 and Counter(r['final_level'] for r in rr) == Counter(fold['quotas'])
        assert len({r['masked_feature_key'] for r in rr}) == len(rr)
        held = {r['prompt_text'] for r in first if r['sample_id'] in fold['heldout_ids']}
        overlap.append({'seed': fold['seed'], 'fold': fold['fold'],
                        'exact_heldout_text_overlap': len({r['prompt_text'] for r in rr} & held),
                        'exact_unique_text_count': len({r['prompt_text'] for r in rr}), 'rows': len(rr)})
    save('results/切分与文本重复诊断.json', overlap)
    if failed or any(not r['detected'] for r in negatives):
        save('results/初次核验待修问题.json', {'structural_failures': failed,
                                            'undetected_negatives': [r for r in negatives if not r['detected']]})
        event('preflight_needs_repair', failures=len(failed), missed_negatives=sum(not r['detected'] for r in negatives))
        raise RuntimeError('结构核验存在需查明的问题，尚不创建研究导出库')
    # Separate export, never edit the source database.
    db = OUT / 'data/数学真实94条_研究只读导出.sqlite3'
    expected_samples = [(r['sample_id'], r['student_id'], r['round'], r.get('pair_id'), r['prompt_text'], r['final_level']) for r in first + following]
    expected_scores = [(r['sample_id'], *[float(r[d + '_' + suffix]) for d in ('A', 'L', 'S', 'P') for suffix in ('rater_A', 'rater_B', 'mean')]) for r in scores]
    existing = db.exists()
    c = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) if existing else sqlite3.connect(db)
    if not existing:
        c.executescript('CREATE TABLE samples(sample_id TEXT PRIMARY KEY,student_id TEXT,round TEXT,pair_id TEXT,prompt_text TEXT,final_level TEXT);'
                    'CREATE TABLE r1_scores(sample_id TEXT PRIMARY KEY,A_rater_A REAL,A_rater_B REAL,A_mean REAL,L_rater_A REAL,L_rater_B REAL,L_mean REAL,S_rater_A REAL,S_rater_B REAL,S_mean REAL,P_rater_A REAL,P_rater_B REAL,P_mean REAL);'
                    'CREATE TABLE provenance(path TEXT PRIMARY KEY,sha256 TEXT);')
        c.executemany('INSERT INTO samples VALUES(?,?,?,?,?,?)', expected_samples)
        c.executemany('INSERT INTO r1_scores VALUES(' + ','.join(['?'] * 13) + ')', expected_scores)
        c.executemany('INSERT INTO provenance VALUES(?,?)', list(hashes.items()))
        c.commit()
    assert sorted(c.execute('SELECT * FROM samples').fetchall()) == sorted(expected_samples)
    assert sorted(c.execute('SELECT * FROM r1_scores').fetchall()) == sorted(expected_scores)
    assert c.execute('SELECT COUNT(*) FROM samples').fetchone()[0] == 94
    assert c.execute('SELECT COUNT(*) FROM r1_scores').fetchone()[0] == 47
    c.close()
    save('results/只读数据库核验.json', {'sample_rows': 94, 'student_count': 47, 'r1_score_rows': 47,
                                       'source_final_label_changes': 0, 'source_database_edited': False})
    assert all(sha(ROOT / p) == h for p, h in hashes.items())
    summary = {'version': VERSION, 'source_rows': len(rows), 'new_real_labels': 0,
               'structural_failures': len(failed), 'failure_categories': dict(Counter(k for r in failed for k in r['failures'])),
               'behavior_counts': dict(Counter(r['behavior_type'] for r in rows)),
               'math_assertions_in_empirical_type_candidates': sum(len(r['evidence']['math_assertions']) for r in checks),
               'math_assertions_in_engineering_coverage_fixtures': sum(len(r['check']['evidence']['math_assertions']) for r in fixtures),
               'engineering_fixture_count_not_training_rows': len(fixtures),
               'negative_control_count': len(negatives), 'negative_controls_detected': sum(r['detected'] for r in negatives),
               'heldout_exact_overlap': sum(r['exact_heldout_text_overlap'] for r in overlap),
               'within_fold_masked_duplicates': 0, 'equivalent_rewordings_without_parameter_change': equivalent_rewordings,
               'same_spec_deterministic': True, 'independent_human_review': 'pending',
               'new_classifier_score': None, 'previous_models_and_results_changed': False,
               'scientific_scope': 'structural_contract_and_factual_math_checks; actual human ALSP values and naturalness not certified'}
    save('results/数据基座验收.json', summary)
    event('complete', **summary)

if __name__ == '__main__':
    main()
