"""Independent metric/count/lineage/model equivalence checks for the release."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,json,hashlib,math,sys
import numpy as np,joblib
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
sys.path[:0]=[str(OUT/'code'),str(ROOT/'数学主线严谨重跑20260930/code')]
import route_models
from common import LAB,ACK

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def csvread(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def verify():
    base=ROOT/'联合表达v2数学全线20261014';snapshot=read(base/'data/anonymous_samples_snapshot.json')
    source={r['sample_id']:r for key in ['real_r1','real_r3'] for r in snapshot[key]}
    rows=csvread(OUT/'results/recognition_predictions.csv');assert len(rows)==1645
    summary=csvread(OUT/'results/recognition_metrics.csv');groups=defaultdict(list)
    folds={(str(f['seed']),str(f['fold'])):f for f in read(base/'data/fold_audit.json')}
    for r in rows:
        origin=source[r['sample_id']];assert r['truth']==origin['final_level'] and r['student_id']==origin['student_id']
        train_ids=set(folds[r['seed'],r['fold']]['train_ids'])
        assert r['student_id'] not in {source[k]['student_id'] for k in train_ids}
        probs=[float(r['p_'+k]) for k in LAB+([ACK] if r['stage']=='R3' else [])]
        assert abs(sum(probs)-1)<1e-10 and min(probs)>=0 and all(math.isfinite(p) for p in probs)
        groups[r['stage'],r['variant'],r['seed']].append(r)
    aggregate=defaultdict(list);raw_metrics=defaultdict(list)
    def compute(rr,pred_key,labels):
        cm=Counter((r['truth'],r[pred_key]) for r in rr);supports={k:sum(cm[k,p] for p in labels) for k in labels}
        f1=[2*cm[k,k]/(supports[k]+sum(cm[t,k] for t in labels)) if supports[k]+sum(cm[t,k] for t in labels) else 0 for k in labels]
        return {'macro_f1':sum(f1)/len(labels),'accuracy':sum(cm[k,k] for k in labels)/47,
            'high_to_low':cm['high','low']/supports['high'],'low_to_high':cm['low','high']/supports['low'],
            **{k+'_recall':cm[k,k]/supports[k] for k in labels}}
    for (stage,variant,seed),rr in groups.items():
        assert len(rr)==47 and len({r['student_id'] for r in rr})==47
        labels=LAB+([ACK] if stage=='R3' else [])
        aggregate[stage,variant].append(compute(rr,'prediction',labels))
        if 'bm25' in variant:raw_metrics[stage,variant].append(compute(rr,'raw_retrieval_prediction',labels))
    for r in summary:
        values=aggregate[r['stage'],r['variant']];assert len(values)==5
        for k in values[0]:assert abs(sum(v[k] for v in values)/5-float(r[k]))<1e-12,(r['variant'],k)
    # Reproduced reference predictions match the frozen previous first-stage comparison.
    old={(r['sample_id'],r['seed']):r for r in csvread(base/'results/predictions.csv') if r['variant']=='joint_mixed_text'}
    for r in rows:
        if r['variant']=='mixed_lr':
            previous=old[r['sample_id'],r['seed']]
            assert r['prediction']==previous['prediction']
            assert max(abs(float(r['p_'+k])-float(previous['p_'+k])) for k in LAB)<1e-12
    audits=read(OUT/'data/nested_audit.json');assert len(audits)==40
    missing=0
    for a in audits:
        assert not set(a['train_students'])&set(a['heldout_students'])
        allowed={k for k,v in source.items() if v['student_id'] in a['train_students']}
        for inner in a['inner']:
            tr=set(inner['training_ids']);va=set(inner['heldout_ids'])
            assert not tr&va and tr|va<=allowed
            assert set(inner['synthetic_parent_ids'])<=tr
            missing+=bool(inner['missing_training_classes'])
    previous_models=joblib.load(base/'data/runtime_models_v1.joblib')
    current_models=joblib.load(OUT/'data/runtime_models_v1.joblib');differences={}
    for stage,key in [('real_r1','first'),('real_r3','following')]:
        labels=LAB+([ACK] if key=='following' else [])
        texts=[r['prompt_text'] for r in snapshot[stage]]
        differences[key]=float(np.max(np.abs(previous_models[key].probs(texts,labels)-current_models[key].probs(texts,labels))))
        assert differences[key]<1e-12,differences
    for p,expected in read(OUT/'data/input_hashes.json').items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==expected,p
    raw=[]
    for (stage,variant),values in raw_metrics.items():raw.append({'stage':stage,'variant':variant+'_raw',**{k:sum(v[k] for v in values)/5 for k in values[0]}})
    result={'passed':True,'predictions_recomputed':len(rows),'method_stage_groups':len(summary),'outer_stage_audits':len(audits),
        'inner_splits_with_missing_training_class':missing,'fullfit_probability_difference_from_r3':differences,
        'source_hashes_unchanged':True,'raw_retrieval_metrics':raw,'paid_calls':0}
    return result
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=False)
    result=verify();(a.output_dir/'独立结果核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
