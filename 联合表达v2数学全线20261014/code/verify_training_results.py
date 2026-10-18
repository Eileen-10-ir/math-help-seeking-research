"""Recompute new scores from predictions independently of the training runner."""
import csv, json, hashlib, sys, argparse
from pathlib import Path
from collections import Counter
import numpy as np
import joblib
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path);args=parser.parse_args()
RESULTDIR=args.output_dir.resolve() if args.output_dir else OUT/'results'
RESULTDIR.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'数学主线严谨重跑20260930/code'))
LAB=['high','medium','low']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvread(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
summary=json.loads((OUT/'results/summary.json').read_text(encoding='utf-8'))
hashes=json.loads((OUT/'data/input_hashes.json').read_text(encoding='utf-8'))
assert all(sha(ROOT/p)==h for p,h in hashes.items())
rows=csvread(OUT/'results/predictions.csv');assert len(rows)==940
folds=json.loads((OUT/'data/fold_audit.json').read_text(encoding='utf-8'))
assert len(folds)==20 and all(not set(f['train_ids'])&set(f['heldout_ids']) for f in folds)
byfold={(f['seed'],f['fold']):f for f in folds}
snapshot=json.loads((OUT/'data/anonymous_samples_snapshot.json').read_text(encoding='utf-8'))
truth={r['sample_id']:r for r in snapshot['real_r1']}
for r in rows:
    fold=byfold[int(r['seed']),int(r['fold'])]
    assert r['sample_id'] in fold['heldout_ids'] and r['truth']==truth[r['sample_id']]['final_level']
    p=np.array([float(r['p_'+k]) for k in LAB])
    assert np.isfinite(p).all() and abs(p.sum()-1)<1e-10 and r['prediction']==LAB[int(p.argmax())]
for name in summary['new_variants']:
    scores=[];acc=[];cms=[];briers=[]
    for seed in [17,29,43,71,101]:
        rr=[r for r in rows if r['variant']==name and int(r['seed'])==seed]
        assert len(rr)==47 and len({r['sample_id'] for r in rr})==47
        cm=np.zeros((3,3),dtype=int)
        for r in rr:
            cm[LAB.index(r['truth']),LAB.index(r['prediction'])]+=1
        denom=cm.sum(0)+cm.sum(1)
        scores.append(float(np.divide(2*np.diag(cm),denom,out=np.zeros(3),where=denom>0).mean()))
        acc.append(float(np.trace(cm)/47));cms.append(cm)
        briers.append(float(np.mean([sum((float(r['p_'+k])-int(r['truth']==k))**2 for k in LAB) for r in rr])))
    m=summary['metrics'][name]
    assert abs(np.mean(scores)-m['macro_f1'])<1e-12
    assert abs(np.mean(acc)-m['accuracy'])<1e-12
    assert abs(np.mean(briers)-m['brier_multiclass'])<1e-12
    assert np.array_equal(np.sum(cms,axis=0),m['confusion_matrix_sum_repeats'])
card=json.loads((OUT/'data/runtime_model_card.json').read_text(encoding='utf-8'))
artifact=OUT/'data/runtime_models_joint_v2.joblib'
assert sha(artifact)==card['artifact_sha256']==sha(OUT/'data/runtime_models_v1.joblib')
new=joblib.load(artifact);old=joblib.load(ROOT/'数学主线严谨重跑20260930/data/runtime_models_v1.joblib')
assert not new['first'].intent and card['active_variant']=='joint_mixed_text'
assert card['selection_is_post_development'] and not card['independent_selection_confirmation']
texts=[r['prompt_text'] for r in snapshot['real_r3']]
assert np.array_equal(new['following'].probs(texts,LAB+['接受引导/非提问']),old['following'].probs(texts,LAB+['接受引导/非提问']))
fresh=json.loads((OUT/'data/runtime_joint_specs_and_texts.json').read_text(encoding='utf-8'))
assert len(fresh)==91 and Counter(r['spec']['final_level_candidate'] for r in fresh)==Counter(high=36,medium=36,low=19)
assert all(r['spec']['parent_id'] in truth for r in fresh)
from common import Classifier
fulltexts=[r['prompt_text'] for r in fresh]+[r['prompt_text'] for r in snapshot['real_r1']]
fully=[r['spec']['final_level_candidate'] for r in fresh]+[r['final_level'] for r in snapshot['real_r1']]
refit=Classifier(intent=False).fit(fulltexts,fully)
assert np.array_equal(new['first'].probs(fulltexts),refit.probs(fulltexts))
assert summary['runtime_active_variant']==card['active_variant']
assert card['first_oof_reference']==summary['metrics'][card['active_variant']]
proof={'passed':True,'new_predictions':940,'new_variants':4,'folds':20,'real_students':47,
       'metrics_recomputed_from_predictions':True,'runtime_first_rows':138,'runtime_synthetic_rows':91,
       'following_reused_unchanged':True,'original_source_hashes_unchanged':True,'paid_calls':0}
(RESULTDIR/'训练独立核验.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False))
