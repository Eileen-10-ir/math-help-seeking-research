"""Nested real-student budget curve, per-class nested synthetic prefixes."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import sys,json,csv,hashlib,time
from pathlib import Path
from collections import Counter
import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score,accuracy_score,confusion_matrix
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
sys.path[:0]=[str(ROOT/'数学主线严谨重跑20260930/code'),str(ROOT/'统一数据与交接准备20261014/code')]
from common import Classifier,LAB,F,B
from joint_renderer import sample_and_render
from independent_contract_check import check_contract
BUDGETS=[0,45,91]
MAX_BUDGET=max(BUDGETS)
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def csvread(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(rel,v):
    p=OUT/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def csvsave(rel,rows):
    p=OUT/rel;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def event(stage,**kw):
    obj={'stage':stage,**kw}
    with (OUT/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n')
    print(json.dumps(obj,ensure_ascii=False),flush=True)
def quotas(n):
    ideal=np.array([36,36,19])*n/91;q=np.floor(ideal).astype(int)
    for i in np.argsort(-(ideal-q),kind='stable')[:n-int(q.sum())]:q[i]+=1
    return dict(zip(LAB,map(int,q)))
assert quotas(91)==dict(zip(LAB,[36,36,19]))

def main():
    assert not (OUT/'results/summary.json').exists()
    assert read(OUT/'capacity_check.json')['selected_maximum_safe_grid_budget']==MAX_BUDGET
    base=ROOT/'数学共同主线定版20261018'
    real=read(base/'data/anonymous_samples_snapshot.json')['real_r1'];folds=read(base/'data/fold_audit.json')
    scores=csvread(ROOT/'参数验证与生成器比较20261014/四维均值_真实R1_47条.csv')
    cal=[{k:(float(v) if k.endswith(('_mean','_rater_A','_rater_B')) else v) for k,v in r.items() if k in ['sample_id','student_id','final_level'] or k.endswith(('_mean','_rater_A','_rater_B'))} for r in scores]
    kinds={r['sample_id']:r['behavior_type'] for r in csvread(ROOT/'统一数据与交接准备20261014/data/真实行为类型解释_机器候选.csv')}
    inputs=[Path(__file__),OUT/'01_执行前协议.md',OUT/'capacity_check.json',ROOT/'统一数据与交接准备20261014/code/joint_renderer.py',
            ROOT/'G0_G1严谨对照20261014/code/g1_generator.py',base/'data/anonymous_samples_snapshot.json',
            base/'data/fold_audit.json',ROOT/'参数验证与生成器比较20261014/四维均值_真实R1_47条.csv']
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    save('input_hashes.json',hashes);predictions=[];selections=[];audits=[]
    def bank(records,seed):
        ids={r['sample_id'] for r in records}
        fresh=sample_and_render([r for r in cal if r['sample_id'] in ids],kinds,quotas(MAX_BUDGET),seed,tau=1.)
        keys=[B.safe_mask(F.normalize_prompt(r['prompt_text'])) for r in fresh]
        assert len(fresh)==len(set(keys))==MAX_BUDGET
        assert all(check_contract(r['spec'],r['prompt_text'],r['question'])['status']=='pass' and r['spec']['parent_id'] in ids for r in fresh)
        return fresh
    def subset(fresh,n):
        q=quotas(n);result=[]
        for k in LAB:result.extend([r for r in fresh if r['spec']['final_level_candidate']==k][:q[k]])
        assert len(result)==n
        return result
    def fitpredict(tr,te,synthetic):
        texts=[r['prompt_text'] for r in tr]+[r['prompt_text'] for r in synthetic]
        labels=[r['final_level'] for r in tr]+[r['spec']['final_level_candidate'] for r in synthetic]
        model=Classifier(intent=False).fit(texts,labels)
        return model.probs([r['prompt_text'] for r in te])
    for fold in folds:
        seed,fi=fold['seed'],fold['fold'];tr=[r for r in real if r['sample_id'] in fold['train_ids']]
        te=[r for r in real if r['sample_id'] in fold['heldout_ids']];labels=np.array([r['final_level'] for r in tr])
        scores_inner={n:[] for n in BUDGETS};inneraudit=[]
        for j,(a,b) in enumerate(StratifiedKFold(n_splits=3,shuffle=True,random_state=seed*100+fi).split(labels,labels)):
            itr=[tr[i] for i in a];iva=[tr[i] for i in b]
            generation_seed=20261018+seed*100+fi+(j+1)*10000
            fresh=bank(itr,generation_seed)
            parents={r['spec']['parent_id'] for r in fresh};assert not parents&{r['sample_id'] for r in iva+te}
            inneraudit.append({'inner_fold':j,'train_ids':[r['sample_id'] for r in itr],'valid_ids':[r['sample_id'] for r in iva],
                               'generated_parent_ids':sorted(parents),'generation_seed':generation_seed})
            for n in BUDGETS:
                p=fitpredict(itr,iva,subset(fresh,n));prediction=np.array(LAB)[p.argmax(1)]
                scores_inner[n].append(float(f1_score([r['final_level'] for r in iva],prediction,labels=LAB,average='macro',zero_division=0)))
        mean={n:float(np.mean(v)) for n,v in scores_inner.items()};sem={n:float(np.std(v,ddof=1)/np.sqrt(3)) for n,v in scores_inner.items()}
        best=max(BUDGETS,key=lambda n:(mean[n],-n));selected=min(n for n in BUDGETS if mean[n]>=mean[best]-sem[best]-1e-12)
        selections.append({'seed':seed,'fold':fi,'best_inner_budget':best,'one_SE_selected_budget':selected,
                           'inner_macro_f1':mean,'inner_standard_error':sem})
        generation_seed=20261018+seed*100+fi;fresh=bank(tr,generation_seed)
        parents={r['spec']['parent_id'] for r in fresh};assert not parents&set(fold['heldout_ids'])
        for n in BUDGETS:
            p=fitpredict(tr,te,subset(fresh,n))
            for r,prob in zip(te,p):
                predictions.append({'budget':n,'seed':seed,'fold':fi,'sample_id':r['sample_id'],'student_id':r['student_id'],
                    'truth':r['final_level'],'prediction':LAB[int(prob.argmax())],'selected_by_inner':n==selected,
                    **{'p_'+k:float(prob[i]) for i,k in enumerate(LAB)}})
        audits.append({'seed':seed,'fold':fi,'train_ids':fold['train_ids'],'heldout_ids':fold['heldout_ids'],
            'generated_parent_ids':sorted(parents),'generation_seed':generation_seed,'max_unique_rows':MAX_BUDGET,'tau':1.,
            'budgets':{n:quotas(n) for n in BUDGETS},'nested_prefixes':True,'inner':inneraudit})
        csvsave('results/predictions.csv',predictions);save('results/inner_selection.json',selections);save('results/lineage_audit.json',audits)
        event('fold_complete',seed=seed,fold=fi,rows=len(predictions),selected=selected)
    repeated=[];summary=[]
    for name in [*map(str,BUDGETS),'nested_one_SE']:
        for seed in [17,29,43,71,101]:
            rr=[r for r in predictions if r['seed']==seed and (r['selected_by_inner'] if name=='nested_one_SE' else r['budget']==int(name))]
            assert len(rr)==47 and len({r['student_id'] for r in rr})==47
            y=[r['truth'] for r in rr];p=[r['prediction'] for r in rr];cm=confusion_matrix(y,p,labels=LAB)
            repeated.append({'variant':name,'seed':seed,'macro_f1':float(f1_score(y,p,labels=LAB,average='macro',zero_division=0)),
                'accuracy':float(accuracy_score(y,p)),**{k+'_recall':float(cm[i,i]/cm[i].sum()) for i,k in enumerate(LAB)},
                'high_to_low':float(cm[0,2]/cm[0].sum()),'low_to_high':float(cm[2,0]/cm[2].sum())})
        rr=[r for r in repeated if r['variant']==name]
        summary.append({'variant':name,**{k:float(np.mean([r[k] for r in rr])) for k in rr[0] if k not in ['variant','seed']}})
    csvsave('results/repeat_metrics.csv',repeated);csvsave('results/metrics.csv',summary)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    result={'status':'completed','fixed_budgets':BUDGETS,'metrics':summary,'inner_chosen_counts':dict(Counter(r['one_SE_selected_budget'] for r in selections)),
        'predictions':len(predictions),'real_students':47,'source_hashes_unchanged':True,'runtime_changed':False,'API_calls':0,
        'scope':'conditional budget comparison with fixed ratio/tau/renderer/LR; no global optimum proof or external validation'}
    save('results/summary.json',result);event('complete',**result)
if __name__=='__main__':main()
