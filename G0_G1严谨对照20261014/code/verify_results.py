"""Read generated evidence and independently reconstruct core counts/metrics."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import csv,json,hashlib,re,math
from collections import defaultdict,Counter
from datetime import datetime
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
LAB=['high','medium','low'];DIMS=['A','L','S','P']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(name):return list(csv.DictReader((OUT/name).open(encoding='utf-8-sig')))
def save(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
summary=json.loads((OUT/'results/summary.json').read_text(encoding='utf-8'))
manifest=json.loads((OUT/'data/frozen_manifest.json').read_text(encoding='utf-8'))
for p,h in manifest['sources'].items():assert sha(ROOT/p)==h,p
folds=json.loads((OUT/'data/fold_audit.json').read_text(encoding='utf-8'))
fby={(str(a['seed']),str(a['fold'])):a for a in folds}
snap=json.loads((ROOT/'数学主线严谨重跑20260930/data/anonymous_samples_snapshot.json').read_text(encoding='utf-8'))
real={r['sample_id']:r for r in snap['real_r1']}
scores=list(csv.DictReader((ROOT/'参数验证与生成器比较20261014/四维均值_真实R1_47条.csv').open(encoding='utf-8-sig')))
sby={r['sample_id']:r for r in scores}
pred=read('results/predictions.csv');buckets=defaultdict(list)
for r in pred:
    a=fby[(r['seed'],r['fold'])];assert r['sample_id'] in a['heldout_ids']
    assert r['truth']==real[r['sample_id']]['final_level']
    ps=[float(r['p_'+k]) for k in LAB];assert abs(sum(ps)-1)<1e-10
    assert r['prediction']==LAB[max(range(3),key=lambda i:ps[i])]
    buckets[(r['variant'],r['seed'])].append(r)
recomputed=defaultdict(list)
for (name,seed),rr in buckets.items():
    assert len(rr)==47 and {r['sample_id'] for r in rr}==set(real)
    cm=[[0]*3 for _ in LAB]
    for r in rr:cm[LAB.index(r['truth'])][LAB.index(r['prediction'])]+=1
    f1=[]
    for i in range(3):
        denom=sum(cm[i])+sum(cm[j][i] for j in range(3));f1.append(2*cm[i][i]/denom if denom else 0)
    recomputed[name].append((sum(f1)/3,sum(cm[i][i] for i in range(3))/47))
for n,v in recomputed.items():
    assert abs(sum(x[0] for x in v)/5-summary['metrics'][n]['macro_f1'])<1e-12
    assert abs(sum(x[1] for x in v)/5-summary['metrics'][n]['accuracy'])<1e-12

g=read('data/generated_outer_corpora.csv');bygen=defaultdict(list);dist=defaultdict(list);jointcounts=Counter()
for r in g:
    key=(r['seed'],r['fold'],r['generator']);bygen[key].append(r);a=fby[key[:2]]
    assert r['human_review']=='pending'
    if r['generator']!='G0':
        assert r['parent_id'] in a['train_ids'] and r['parent_id'] not in a['heldout_ids']
        assert r['parent_student_id']==real[r['parent_id']]['student_id']
        target=json.loads(r['target_profile']);prof=json.loads(r['profile']);source=sby[r['parent_id']]
        expected=[float(source[d+'_'+r['rater_source']]) for d in DIMS];assert target==expected
        assert r['final_level']==source['final_level']
        jointcounts[(r['generator'],r['final_level'])]+=1
        for i,d in enumerate(DIMS):dist[(r['generator'],r['final_level'],d)].append((target[i],prof[i]))
for key,rr in bygen.items():
    assert dict(Counter(r['final_level'] for r in rr))==fby[key[:2]]['quotas']
    assert len({r['feature_key'] for r in rr})==len(rr)
for a in folds:
    tr=set(a['train_ids']);te=set(a['heldout_ids']);assert len(tr|te)==47 and not tr&te
    for inner in a['inner']:
        it=set(inner['calibration_ids']);iv=set(inner['validation_ids'])
        assert it|iv==tr and not it&iv and not (it|iv)&te

# Parse numeric claims from rendered strings, rather than trusting math_check metadata.
unique={r['feature_key']:r for r in g if r['generator']!='G0'}
math_checks=Counter();fail=[]
for r in unique.values():
    t=r['prompt_text']
    q=re.search(r'x²−(\d+)x\+(\d+)=0',t)
    pair=re.search(r'我先试了−(\d+)和−(\d+)，它们的和是−(\d+)，积是(\d+)',t)
    if pair:
        a,b,s,p=map(int,pair.groups());ok=(a+b==s and a*b==p)
        if q:ok=ok and tuple(map(int,q.groups()))==(s,p)
        math_checks['factor_pair_claims']+=1
        if not ok:fail.append(r['candidate_id'])
    lin=re.search(r'解方程(\d+)x\+3=(\d+)',t);step=re.search(r'我先把两边都减3，写成(\d+)x=(\d+)',t)
    if lin and step:
        a,b=map(int,lin.groups());c,d=map(int,step.groups());math_checks['linear_transformations']+=1
        if not (a==c and b-3==d):fail.append(r['candidate_id'])
    mul=re.search(r'我先算底乘高：(\d+)×(\d+)=(\d+)',t)
    if mul:
        a,b,c=map(int,mul.groups());math_checks['multiplication_claims']+=1
        if a*b!=c:fail.append(r['candidate_id'])
    fraction=re.search(r'我先写成\(2\+3\)/(\d+)，把分子相加得到5',t)
    qf=re.search(r'计算2/(\d+)\+3/(\d+)',t)
    if fraction and qf:
        math_checks['fraction_transformations']+=1
        if not (int(qf[1])==int(qf[2])==int(fraction[1])):fail.append(r['candidate_id'])
assert not fail,fail
stats=[]
for (name,lv,d),pairs in sorted(dist.items()):
    stats.append({'generator':name,'final_level':lv,'dimension':d,'synthetic_rows_across_repeats':len(pairs),'target_mean':sum(a for a,b in pairs)/len(pairs),'prototype_mean':sum(b for a,b in pairs)/len(pairs),'prototype_target_MAE':sum(abs(a-b) for a,b in pairs)/len(pairs)})
with (OUT/'results/profile_fidelity_by_class.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(stats[0]));w.writeheader();w.writerows(stats)

cases=[]
for sid,r in real.items():
    if r['final_level']!='low':continue
    case={'sample_id':sid,'prompt_text':r['prompt_text'],'final_level':r['final_level'],'original_ALSP_means':{d:float(sby[sid][d+'_mean']) for d in DIMS},'predictions_by_seed':{}}
    for name in ['G0_synth','G1_ALSP_synth','G0_mixed','G1_ALSP_mixed']:
        case['predictions_by_seed'][name]={x['seed']:x['prediction'] for x in pred if x['sample_id']==sid and x['variant']==name}
    cases.append(case)
save('results/low_class_case_audit.json',cases)
result={'verified_at':datetime.now().astimezone().isoformat(),'all_frozen_hashes_unchanged':True,'metrics_recomputed_from_predictions':True,'real_final_labels_preserved':True,'all_20_outer_and_60_inner_splits_isolated':True,'targets_exactly_from_training_parent_joint_vector':True,'all_120_generated_corpus_budgets_verified':True,'generated_rows':len(g),'unique_G1_masked_texts_across_outer_runs':len(unique),'numeric_checks_on_rendered_text':dict(math_checks),'numeric_failures':0,'synthetic_human_review_pending':True,'not_claimed':'No independent human semantic validation, no educational effect, no untouched external test.'}
save('results/independent_artifact_verification.json',result)
with (OUT/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'time':result['verified_at'],'stage':'artifact_verification_pass','details':result},ensure_ascii=False)+'\n')
print(json.dumps(result,ensure_ascii=False))
