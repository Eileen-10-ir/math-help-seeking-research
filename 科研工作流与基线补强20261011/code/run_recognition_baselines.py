"""Post-exposure baseline supplement; existing research outputs stay intact."""
from pathlib import Path
import sys, json, csv, hashlib
from collections import defaultdict
import numpy as np
import sklearn
from sklearn.model_selection import StratifiedKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent
OLD = ROOT / '数学主线严谨重跑20260930'
sys.path.insert(0, str(OLD / 'code'))
from common import load, F, B, Classifier, LAB, SEEDS
from controlled_text import calibrated
OUT = BASE / 'results'
OUT.mkdir(exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
protected = [OLD/'results/E2_summary.json', OLD/'results/recognition_predictions.csv',
             OLD/'data/anonymous_samples_snapshot.json', ROOT/'7月数据/依赖标注数据库.db']
hashes = {str(p): sha(p) for p in protected}
protocol_sha = sha(BASE / '补充识别实验协议.md')
real, _, _, _ = load()
assert len(real) == 47 and len({r['student_id'] for r in real}) == 47
y = np.array([r['final_level'] for r in real])
archive = list(csv.DictReader((OLD/'results/recognition_predictions.csv').open(encoding='utf-8-sig')))
reference = {(int(r['seed']), r['variant'], r['sample_id']): r for r in archive if r['experiment'] == 'E2_student_crossfit'}
splits = {(r['seed'], r['fold']): r for r in json.loads((OLD/'data/E2_family_calibration_splits.json').read_text(encoding='utf-8'))}
predictions, audit, repeat_metrics = [], [], []
all_pred = {}
def metric(pred, truth=y):
    cm = confusion_matrix(truth, pred, labels=LAB)
    return {'macro_f1': float(f1_score(truth, pred, labels=LAB, average='macro', zero_division=0)),
            'accuracy': float(accuracy_score(truth, pred)), 'high_recall': float(cm[0,0]/cm[0].sum()),
            'high_to_low': float(cm[0,2]/cm[0].sum()), 'confusion_matrix': cm.tolist()}
for seed in SEEDS:
    preds = {f'{a}_{d}': np.empty(47, dtype=object) for a in ['text_lr', 'text_svm', 'text_nb', 'intent_lr'] for d in ['real', 'mixed']}
    for fold, (tr, te) in enumerate(StratifiedKFold(4, shuffle=True, random_state=seed).split(np.zeros(47), y)):
        train, test = [real[i] for i in tr], [real[i] for i in te]
        train_ids, held_ids = {r['sample_id'] for r in train}, {r['sample_id'] for r in test}
        frozen = splits[seed, fold]
        assert train_ids == set(frozen['training_real_ids'])
        assert held_ids == set(frozen['heldout_real_ids']) and not train_ids & held_ids
        param, cal = calibrated(train, seed*100 + fold)
        assert not set(cal['calibration_ids']) & held_ids
        audit.append({'seed':seed, 'fold':fold, 'held_ids': sorted(held_ids), 'calibration':cal})
        for domain, corpus in [('real', train), ('mixed', train + param)]:
            texts = [r['prompt_text'] for r in corpus]
            labels = [r['final_level'] for r in corpus]
            test_texts = [r['prompt_text'] for r in test]
            vec = TfidfVectorizer(analyzer='char', ngram_range=(1,4), max_features=12000, sublinear_tf=True)
            tx = vec.fit_transform([B.safe_mask(F.normalize_prompt(t)) for t in texts])
            vx = vec.transform([B.safe_mask(F.normalize_prompt(t)) for t in test_texts])
            models = {'text_lr': LogisticRegression(C=2, class_weight='balanced', max_iter=4000, solver='lbfgs'),
                      'text_svm': LinearSVC(C=1, class_weight='balanced', random_state=seed),
                      'text_nb': MultinomialNB(alpha=1, fit_prior=False)}
            for algo, model in models.items():
                pred = model.fit(tx, labels).predict(vx)
                preds[f'{algo}_{domain}'][te] = pred
            base_model = Classifier().fit(texts, labels)
            preds[f'intent_lr_{domain}'][te] = np.array(LAB)[base_model.probs(test_texts).argmax(axis=1)]
            ref_name = 'real_only' if domain == 'real' else 'parameter_real'
            assert all(preds[f'intent_lr_{domain}'][i] == reference[seed, ref_name, real[i]['sample_id']]['prediction'] for i in te), 'Frozen result did not reproduce'
        for name, arr in preds.items():
            for i in te:
                predictions.append({'variant':name, 'seed':seed, 'fold':fold, 'student_id':real[i]['student_id'],
                                    'sample_id':real[i]['sample_id'], 'truth':y[i], 'prediction':arr[i]})
    for name, arr in preds.items():
        all_pred[seed, name] = arr
        repeat_metrics.append({'variant':name, 'seed':seed, **metric(arr)})
    print(f'Baseline supplement seed {seed}: eight variants complete; original predictions matched', flush=True)
variants = sorted({r['variant'] for r in repeat_metrics})
summary = []
for name in variants:
    rr = [r for r in repeat_metrics if r['variant'] == name]
    summary.append({'variant':name, 'students':47, 'repeats':5, **{m:float(np.mean([r[m] for r in rr])) for m in ['macro_f1','accuracy','high_recall','high_to_low']}})
def macro_fast(truth, pred):
    # Equivalent to macro F1 over fixed labels, including zero-denominator convention.
    return np.mean([2*np.sum((truth==k)&(pred==k))/(np.sum(truth==k)+np.sum(pred==k)) if np.sum(truth==k)+np.sum(pred==k) else 0. for k in LAB])
rng = np.random.default_rng(20261011)
draws = rng.integers(0,47,(2000,47))
comparisons = []
for a,b in [('intent_lr_mixed','intent_lr_real'),('text_svm_mixed','text_svm_real'),('text_lr_mixed','text_lr_real'),
            ('text_nb_mixed','text_nb_real'),('intent_lr_mixed','text_svm_mixed'),('intent_lr_mixed','text_lr_mixed')]:
    diffs = [np.mean([macro_fast(y[ix],all_pred[seed,a][ix])-macro_fast(y[ix],all_pred[seed,b][ix]) for seed in SEEDS]) for ix in draws]
    mean_a = next(r['macro_f1'] for r in summary if r['variant']==a)
    mean_b = next(r['macro_f1'] for r in summary if r['variant']==b)
    comparisons.append({'a':a,'b':b,'delta_macro_f1':mean_a-mean_b,'conditional_95_interval':np.quantile(diffs,[.025,.975]).tolist(),
                        'interpretation':'Fixed predictions; retrospective student resampling, not independent external validation or full training uncertainty'})
def csv_out(name, rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
csv_out('识别基线汇总.csv',summary)
csv_out('识别基线逐学生预测.csv',predictions)
(OUT/'识别基线重复指标.json').write_text(json.dumps(repeat_metrics,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'识别基线条件区间.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2),encoding='utf-8')
assert all(sha(Path(p))==digest for p,digest in hashes.items())
(OUT/'识别基线审计.json').write_text(json.dumps({'protocol_sha256':protocol_sha,'sklearn':sklearn.__version__,'numpy':np.__version__,
    'source_sha256':hashes,'source_files_unchanged':True,'original_predictions_exact_match':True,
    'fold_checks':audit,'new_students':0,'external_calls':0,'prospective_registration':False,
    'experiment':'retrospective classifier baseline supplement'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False),flush=True)
