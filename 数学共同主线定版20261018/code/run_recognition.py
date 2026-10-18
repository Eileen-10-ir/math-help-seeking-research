"""Shared outer students, regenerated inner synthetics, frozen route comparison."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import sys,json,csv,hashlib,time,warnings
from pathlib import Path
from collections import Counter
import numpy as np,joblib
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score,accuracy_score,confusion_matrix

OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
sys.path[:0]=[str(OUT/'code'),str(ROOT/'统一数据与交接准备20261014/code'),str(ROOT/'数学主线严谨重跑20260930/code')]
from route_models import BM25,CalibratedBM25,fit_lr
from common import LAB,ACK
from joint_renderer import sample_and_render,VERSION
from independent_contract_check import check_contract
from runtime_state_v4 import State,advance

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def csvread(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(rel,data):
    path=OUT/rel;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def csvsave(rel,rows):
    path=OUT/rel;path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r))
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def event(stage,**kw):
    value={'stage':stage,**kw}
    with (OUT/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n')
    print(json.dumps(value,ensure_ascii=False),flush=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

BASE=ROOT/'联合表达v2数学全线20261014'
snapshot=read(BASE/'data/anonymous_samples_snapshot.json');real=snapshot['real_r1'];later=snapshot['real_r3']
folds=read(BASE/'data/fold_audit.json');joint=csvread(ROOT/'统一数据与交接准备20261014/data/联合表达v2_全部折候选.csv')
score_rows=csvread(ROOT/'参数验证与生成器比较20261014/四维均值_真实R1_47条.csv')
calibration=[{k:(float(v) if k.endswith(('_mean','_rater_A','_rater_B')) else v) for k,v in r.items()
              if k in ['sample_id','student_id','final_level'] or k.endswith(('_mean','_rater_A','_rater_B'))} for r in score_rows]
kinds={r['sample_id']:r['behavior_type'] for r in csvread(ROOT/'统一数据与交接准备20261014/data/真实行为类型解释_机器候选.csv')}
CONFIG=read(BASE/'data/runtime_state_config_v4.json')
R1_NAMES=['mixed_lr','parametric_lr','parametric_bm25_cal','mixed_bm25_cal','real_lr_reference']
R3_NAMES=['following_lr','following_bm25_cal']

def generate(ids,seed):
    fresh=sample_and_render([r for r in calibration if r['sample_id'] in ids],kinds,
        {'high':36,'medium':36,'low':19},seed,tau=1.,fold=-1)
    records=[]
    for i,r in enumerate(fresh):
        assert r['spec']['parent_id'] in ids
        assert check_contract(r['spec'],r['prompt_text'],r['question'])['status']=='pass'
        records.append({'sample_id':f'inner-{seed}-{i}','parent_id':r['spec']['parent_id'],
                        'prompt_text':r['prompt_text'],'final_level':r['spec']['final_level_candidate']})
    return records

def splits(truth,seed):
    nfold=3 if min(Counter(truth).values())>=3 else 2
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='The least populated class in y has only')
        return list(StratifiedKFold(n_splits=nfold,shuffle=True,random_state=seed).split(truth,truth))

def calibration_scores(records,stage,seed,labels,mixed):
    truth=np.array([r['final_level'] for r in records]);result=np.zeros((len(records),len(labels)))
    for i,(train,valid) in enumerate(splits(truth,seed)):
        tr=[records[j] for j in train];te=[records[j] for j in valid]
        syn=generate({r['sample_id'] for r in tr},seed*10+i) if stage=='R1' else []
        corpus=syn+tr if mixed and stage=='R1' else syn if stage=='R1' else tr
        result[valid]=BM25(corpus,labels).scores([r['prompt_text'] for r in te])
    return result

def inner_predictions(records,stage,seed):
    labels=LAB if stage=='R1' else LAB+[ACK]
    names=R1_NAMES if stage=='R1' else R3_NAMES
    truth=np.array([r['final_level'] for r in records])
    arrays={k:np.zeros((len(records),len(labels))) for k in names}
    bm_scores={k:np.zeros((len(records),len(labels))) for k in names if 'bm25' in k}
    audits=[]
    for i,(train,valid) in enumerate(splits(truth,seed)):
        tr=[records[j] for j in train];te=[records[j] for j in valid]
        ids={r['sample_id'] for r in tr};held={r['sample_id'] for r in te}
        syn=generate(ids,seed*10+i) if stage=='R1' else []
        assert not ids&held and not {r['student_id'] for r in tr}&{r['student_id'] for r in te}
        audits.append({'inner_fold':i,'training_ids':sorted(ids),'heldout_ids':sorted(held),
                       'synthetic_parent_ids':sorted({r['parent_id'] for r in syn}),'tau':1. if syn else None,
                       'missing_training_classes':sorted(set(labels)-{r['final_level'] for r in tr})})
        corpora={'mixed_lr':syn+tr,'parametric_lr':syn,'parametric_bm25_cal':syn,
                 'mixed_bm25_cal':syn+tr,'real_lr_reference':tr} if stage=='R1' else {'following_lr':tr,'following_bm25_cal':tr}
        for name in names:
            if 'bm25' in name:
                bm_scores[name][valid]=BM25(corpora[name],labels).scores([r['prompt_text'] for r in te])
                # Mapping development is nested inside this inner training split.
                subraw=calibration_scores(tr,stage,seed*10+i+77,labels,name.startswith('mixed'))
                mapping=CalibratedBM25(corpora[name],labels,subraw,[r['final_level'] for r in tr])
                arrays[name][valid]=mapping.probs([r['prompt_text'] for r in te],labels)
            else:arrays[name][valid]=fit_lr(corpora[name],stage=='R3').probs([r['prompt_text'] for r in te],labels)
    return arrays,bm_scores,audits

def gate_stats(records,probs,labels,cut):
    accepted=[];ack_updates=0;graded=0
    for r,p in zip(records,probs):
        a=advance(State(),r['prompt_text'],dict(zip(labels,map(float,p))),dict(CONFIG,cutoff=cut))
        if r['final_level'] in LAB:
            graded+=1
            if a['risk_updated']:accepted.append(a['current_behavior_level']==r['final_level'])
        elif a['risk_updated']:ack_updates+=1
    return {'cutoff':cut,'graded':graded,'accepted':len(accepted),'correct':sum(accepted),
            'coverage':len(accepted)/graded,'accepted_accuracy':sum(accepted)/len(accepted) if accepted else 0.,'ACK_updates':ack_updates}

def choose_cut(records,probs,labels):
    options=[gate_stats(records,probs,labels,c) for c in [.35,.4,.45,.5,.55,.6,.65]]
    safe=[r for r in options if r['accepted_accuracy']>=.85 and r['ACK_updates']==0]
    if safe:chosen=max(safe,key=lambda r:(r['coverage'],r['accepted_accuracy'],r['cutoff']))
    else:chosen=min(options,key=lambda r:(r['ACK_updates'],r['accepted']-r['correct'],-r['coverage'],-r['cutoff']))
    return {'chosen':chosen,'constraints_satisfied':bool(safe),'options':options}

def main():
    assert not (OUT/'results/recognition_summary.json').exists(),'Keep completed results.'
    files=[BASE/'data/统一主线交接契约.json',BASE/'data/anonymous_samples_snapshot.json',BASE/'data/fold_audit.json',
           ROOT/'统一数据与交接准备20261014/data/联合表达v2_全部折候选.csv',
           OUT/'01_执行前协议.md',Path(__file__),OUT/'code/route_models.py']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files};save('data/input_hashes.json',hashes)
    predictions=[];gates=[];audits=[]
    resume='--resume-completed-folds' in sys.argv
    if resume:
        predictions=csvread(OUT/'results/recognition_predictions.csv')
        for r in predictions:
            for k in ['seed','fold']:r[k]=int(r[k])
            for k in ['selected_cutoff']+['p_'+c for c in LAB+[ACK]]:
                if r[k]!='':r[k]=float(r[k])
        gates=read(OUT/'results/gate_selection.json');audits=read(OUT/'data/nested_audit.json')
        assert len(predictions)==1645 and len(gates)==140 and len(audits)==40
        previous=read(OUT/'history/折外完成后序列化修复/input_hashes.json')
        assert all(sha(ROOT/p)==h for p,h in previous.items() if p!=str(Path(__file__).relative_to(ROOT)))
        event('resume_completed_outer_predictions',rows=len(predictions),reason='CSV heterogeneous fields fix; saved predictions unchanged')
    for fold in ([] if resume else folds):
        seed,fi=fold['seed'],fold['fold'];tr=[r for r in real if r['sample_id'] in fold['train_ids']]
        te=[r for r in real if r['sample_id'] in fold['heldout_ids']];students={r['student_id'] for r in tr}
        syn=[r for r in joint if int(r['seed'])==seed and int(r['fold'])==fi]
        assert len(syn)==91 and all(r['parent_id'] in fold['train_ids'] for r in syn)
        for stage,train,test in [('R1',tr,te),('R3',[r for r in later if r['student_id'] in students],[r for r in later if r['student_id'] not in students])]:
            labels=LAB if stage=='R1' else LAB+[ACK]
            inner,raw,inner_audit=inner_predictions(train,stage,seed*100+fi)
            corpora={'mixed_lr':syn+train,'parametric_lr':syn,'parametric_bm25_cal':syn,'mixed_bm25_cal':syn+train,'real_lr_reference':train} if stage=='R1' else {'following_lr':train,'following_bm25_cal':train}
            for name,corpus in corpora.items():
                choice=choose_cut(train,inner[name],labels)
                model=CalibratedBM25(corpus,labels,raw[name],[r['final_level'] for r in train]) if 'bm25' in name else fit_lr(corpus,stage=='R3')
                probabilities=model.probs([r['prompt_text'] for r in test],labels)
                raw_classes=np.array(labels)[BM25(corpus,labels).scores([r['prompt_text'] for r in test]).argmax(1)] if 'bm25' in name else None
                for i,(r,p) in enumerate(zip(test,probabilities)):
                    predictions.append({'stage':stage,'variant':name,'seed':seed,'fold':fi,'sample_id':r['sample_id'],
                        'student_id':r['student_id'],'truth':r['final_level'],'prediction':labels[int(p.argmax())],
                        'raw_retrieval_prediction':str(raw_classes[i]) if raw_classes is not None else '',
                        'selected_cutoff':choice['chosen']['cutoff'],
                        **{'p_'+k:float(p[labels.index(k)]) if k in labels else '' for k in LAB+[ACK]}})
                gates.append({'stage':stage,'variant':name,'seed':seed,'fold':fi,**choice,
                              'heldout':gate_stats(test,probabilities,labels,choice['chosen']['cutoff'])})
            audits.append({'seed':seed,'fold':fi,'stage':stage,'train_students':sorted(students),
                'heldout_students':sorted({r['student_id'] for r in test}),'inner':inner_audit})
        csvsave('results/recognition_predictions.csv',predictions);save('results/gate_selection.json',gates);save('data/nested_audit.json',audits)
        event('outer_fold_complete',seed=seed,fold=fi,rows=len(predictions))
    summary=[];repeated=[]
    for stage,names in [('R1',R1_NAMES),('R3',R3_NAMES)]:
        labels=LAB if stage=='R1' else LAB+[ACK]
        for name in names:
            for seed in [17,29,43,71,101]:
                rows=[r for r in predictions if r['stage']==stage and r['variant']==name and r['seed']==seed]
                assert len(rows)==47 and len({r['student_id'] for r in rows})==47
                truth=[r['truth'] for r in rows];pred=[r['prediction'] for r in rows]
                cm=confusion_matrix(truth,pred,labels=labels);probs=np.array([[r['p_'+k] for k in labels] for r in rows])
                one=np.array([[float(t==k) for k in labels] for t in truth])
                repeated.append({'stage':stage,'variant':name,'seed':seed,'macro_f1':float(f1_score(truth,pred,labels=labels,average='macro',zero_division=0)),
                    'accuracy':float(accuracy_score(truth,pred)), 'high_to_low':float(cm[0,2]/cm[0].sum()),'low_to_high':float(cm[2,0]/cm[2].sum()),
                    'brier':float(np.mean(np.sum((probs-one)**2,axis=1))),
                    **{k+'_recall':float(cm[i,i]/cm[i].sum()) for i,k in enumerate(labels)}})
            rr=[r for r in repeated if r['stage']==stage and r['variant']==name]
            summary.append({'stage':stage,'variant':name,**{k:float(np.mean([r[k] for r in rr])) for k in rr[0] if k not in ['stage','variant','seed']}})
    csvsave('results/recognition_metrics.csv',summary);csvsave('results/recognition_repeats.csv',repeated)
    baseline=next(r for r in summary if r['variant']=='mixed_lr');candidates=[r for r in summary if r['stage']=='R1' and r['variant']!='real_lr_reference']
    allowed=[r for r in candidates if r['macro_f1']>=baseline['macro_f1']-1e-12 and r['low_to_high']<=baseline['low_to_high']+1e-12 and r['high_to_low']<=baseline['high_to_low']+1e-12]
    selected=max(allowed,key=lambda r:r['macro_f1'])['variant']
    base3=next(r for r in summary if r['variant']=='following_lr')
    allowed3=[r for r in summary if r['stage']=='R3' and r['macro_f1']>=base3['macro_f1']-1e-12 and r['low_to_high']<=base3['low_to_high']+1e-12 and r['high_to_low']<=base3['high_to_low']+1e-12 and r[ACK+'_recall']>=base3[ACK+'_recall']-1e-12]
    selected3=max(allowed3,key=lambda r:r['macro_f1'])['variant']
    # Freeze full-fit settings using all-data training-inner predictions, not outer scores.
    models={};fullgates={}
    fresh=read(BASE/'data/runtime_joint_specs_and_texts.json')
    fullsyn=[{'sample_id':f'fullsyn{i}','parent_id':r['spec']['parent_id'],'prompt_text':r['prompt_text'],'final_level':r['spec']['final_level_candidate']} for i,r in enumerate(fresh)]
    for stage,records,name in [('R1',real,selected),('R3',later,selected3)]:
        labels=LAB if stage=='R1' else LAB+[ACK]
        inner,raw,inneraudit=inner_predictions(records,stage,20261018)
        corpus=fullsyn+records if name=='mixed_lr' or name=='mixed_bm25_cal' else fullsyn if name in ['parametric_lr','parametric_bm25_cal'] else records
        model=CalibratedBM25(corpus,labels,raw[name],[r['final_level'] for r in records]) if 'bm25' in name else fit_lr(corpus,stage=='R3')
        models['first' if stage=='R1' else 'following']=model;fullgates[stage]=choose_cut(records,inner[name],labels)
        save('data/fullfit_inner_audit_'+stage+'.json',inneraudit)
    (OUT/'data').mkdir(exist_ok=True);joblib.dump(models,OUT/'data/runtime_models_v1.joblib')
    save('data/fullfit_gate_selection.json',fullgates)
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    result={'status':'recognition_comparison_complete','scope':'post-development internal evaluation; calibration mappings are real-supervised',
        'selected_first':selected,'selected_following':selected3,'metrics':summary,'prediction_rows':len(predictions),
        'fullfit_cutoffs':{k:v['chosen']['cutoff'] for k,v in fullgates.items()},'source_hashes_unchanged':True,'paid_calls':0}
    save('results/recognition_summary.json',result);event('recognition_complete',**result)
if __name__=='__main__':main()
