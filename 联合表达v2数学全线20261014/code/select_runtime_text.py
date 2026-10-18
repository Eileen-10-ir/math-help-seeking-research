"""Versioned development selection; reuse frozen corpora and OOF predictions."""
import csv, json, hashlib, sys
from pathlib import Path
from collections import defaultdict
from statistics import mean
import joblib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '数学主线严谨重跑20260930/code'))
from common import Classifier, LAB
from runtime_state_v4 import State, advance

MODEL_VERSION = 'math-joint-expression-v2-text-20261015'
VARIANT = 'joint_mixed_text'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p, value): p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def apply_selection(out):
    out = Path(out)
    snapshot = read(out / 'data/anonymous_samples_snapshot.json')
    fresh = read(out / 'data/runtime_joint_specs_and_texts.json')
    summary = read(out / 'results/summary.json')
    real = snapshot['real_r1']
    assert len(real) == 47 and len(fresh) == 91
    texts = [r['prompt_text'] for r in fresh + real]
    labels = [r['spec']['final_level_candidate'] if 'spec' in r else r['final_level'] for r in fresh + real]
    first = Classifier(intent=False).fit(texts, labels)
    models = joblib.load(out / 'data/runtime_models_joint_v2.joblib')
    models['first'] = first
    assert not first.intent
    for name in ['runtime_models_joint_v2.joblib', 'runtime_models_v1.joblib']:
        joblib.dump(models, out / 'data' / name)
    with (out / 'results/predictions.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['variant'] == VARIANT]
    byid = defaultdict(list)
    for r in rows: byid[r['sample_id']].append(r)
    assert len(rows) == 235 and len(byid) == 47 and all(len(v) == 5 for v in byid.values())
    grid = []
    for threshold in [.3, .4, .5, .6, .7, .8]:
        tp = sum(v[0]['truth'] == 'high' and mean(float(r['p_high']) for r in v) >= threshold for v in byid.values())
        fp = sum(v[0]['truth'] != 'high' and mean(float(r['p_high']) for r in v) >= threshold for v in byid.values())
        grid.append({'threshold': threshold, 'TP': tp, 'FN': 12 - tp, 'FP': fp, 'TN': 35 - fp,
                     'balanced_accuracy': (tp / 12 + (35 - fp) / 35) / 2})
    selected = sorted(grid, key=lambda r: (-r['balanced_accuracy'], r['threshold'] != .5, r['threshold']))[0]
    cfg = read(out / 'data/runtime_state_config_v4.json')
    review = {'classifier_version': MODEL_VERSION, 'variant': VARIANT, 'source': '47 per-student mean 5-repeat OOF scores',
        'threshold_grid': grid, 'single_turn_proxy_candidate': selected['threshold'],
        'active_history_threshold': cfg['history_high_threshold'], 'active_alpha': cfg['lambda'],
        'applied_new_history_threshold': False, 'independently_validated': False,
        'decision': 'Keep state engineering reference pending state-level coverage, false-blocking and lag comparisons; single-turn label is not cumulative-state truth.'}
    save(out / 'data/state_parameter_review_20261015.json', review)
    profiles = read(out / 'results/real_two_point_profiles.json')
    sensitivities = []
    baseline = []
    for alpha in [.2, .35, .5, .65, .8, 1.0]:
        batch = []
        for row in profiles:
            pair = next(r for r in real if r['student_id'] == row['student_id'])
            p1 = {k: mean(float(r['p_' + k]) for r in byid[pair['sample_id']]) for k in LAB}
            state = State()
            conf = dict(cfg, **{'lambda': alpha})
            a = advance(state, row['r1_text'], p1, conf)
            b = advance(state, row['r3_text'], row['r3_analysis']['model_scores'], conf)
            batch.append({'student_id': row['student_id'], 'source': row['source'],
                'r1_text': row['r1_text'], 'r3_text': row['r3_text'], 'original_labels': row['original_labels'],
                'r1_analysis': a, 'r3_analysis': b, 'state': vars(state)})
        if alpha == .5:
            baseline = batch
            save(out / 'results/real_two_point_profiles.json', batch)
        sensitivities.append({'alpha': alpha, 'second_valid_updates': sum(r['r3_analysis']['risk_updated'] for r in batch),
            'history_protections': sum(r['r3_analysis']['history_high_protection'] for r in batch),
            'decisions': [r['r3_analysis']['decision_level'] for r in batch]})
    for r in sensitivities:
        r['changed_decisions_vs_alpha_0_5'] = sum(a != b['r3_analysis']['decision_level'] for a, b in zip(r.pop('decisions'), baseline))
    review['real_two_point_sensitivity'] = sensitivities
    save(out / 'data/state_parameter_review_20261015.json', review)
    card = read(out / 'data/runtime_model_card.json')
    card.update({'model_version': MODEL_VERSION, 'artifact_sha256': sha(out / 'data/runtime_models_joint_v2.joblib'),
        'first_candidate': 'joint_mixed_text_post_development_selection_20261015',
        'active_variant': VARIANT, 'original_prespecified_variant': 'joint_mixed_intent',
        'first_oof_reference': summary['metrics'][VARIANT],
        'selection_is_post_development': True, 'independent_selection_confirmation': False,
        'state_parameter_review': 'state_parameter_review_20261015.json',
        'state_parameter_review_sha256': sha(out / 'data/state_parameter_review_20261015.json')})
    save(out / 'data/runtime_model_card.json', card)
    summary['runtime_active_variant'] = VARIANT
    summary['runtime_model_sha256'] = card['artifact_sha256']
    summary['runtime_selection'] = {'selected_after_development': True, 'version': MODEL_VERSION,
        'original_prespecified_variant_unchanged': summary['runtime_prespecified_variant'],
        'rationale': 'For operational use: higher observed macro-F1 and lower low-to-high error, with lower high and low recall acknowledged. Original results remain unchanged.'}
    save(out / 'results/summary.json', summary)
    return {'model_version': MODEL_VERSION, 'active_variant': VARIANT, 'first_real': 47, 'first_synthetic': 91,
        'following_model_unchanged': True, 'selection_is_post_development': True,
        'metrics': summary['metrics'][VARIANT], 'state_review': review, 'paid_calls': 0}

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--output-dir', type=Path, required=True)
    print(json.dumps(apply_selection(parser.parse_args().output_dir), ensure_ascii=False, indent=2))
