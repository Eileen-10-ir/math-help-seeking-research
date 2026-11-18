"""Nested student-isolated, checkpointed model/generator selection; no API calls."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import sys,json,csv,itertools,hashlib,time,warnings
from pathlib import Path
from collections import Counter
import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score,accuracy_score,confusion_matrix
import joblib
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
sys.path[:0]=[str(ROOT/'数学主线严谨重跑20260930/code'),str(ROOT/'统一数据与交接准备20261014/code')]
from common import Classifier,LAB,ACK
from joint_renderer import sample_and_render
BASE=ROOT/'联合表达v2数学全线20261014/data'
realdata=json.loads((BASE/'anonymous_samples_snapshot.json').read_text(encoding='utf-8'))
real=realdata['real_r1'];later=realdata['real_r3']
folds=json.loads((BASE/'fold_audit.json').read_text(encoding='utf-8'))
def loadcsv(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
cal=[{k:float(v) if k.endswith(('_mean','_rater_A','_rater_B')) else v for k,v in r.items()
      if k in ['sample_id','student_id','final_level'] or k.endswith(('_mean','_rater_A','_rater_B'))}
     for r in loadcsv(ROOT/'参数验证与生成器比较20261014/四维均值_真实R1_47条.csv')]
kinds={r['sample_id']:r['behavior_type'] for r in loadcsv(ROOT/'统一数据与交接准备20261014/data/真实行为类型解释_机器候选.csv')}
GRID=[dict(C=c,ngram=n,balance=b) for c,n,b in itertools.product([.25,1.,2.,4.],[2,3,4],[False,True])]
GGRID=[dict(tau=t,mult=m,ratio=r) for t,m,r in itertools.product([.5,1.,2.],[1,2,4],['old','equal','empirical'])]
DEFAULT=dict(tau=1.,mult=2,ratio='old');SYNSEEDS=[1301,2711,4051]
def dump(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def event(**d):
 d['time']=time.strftime('%Y-%m-%d %H:%M:%S')
 with (OUT/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(d,ensure_ascii=False)+'\n')
 print(json.dumps(d,ensure_ascii=False),flush=True)
def split(records,seed):
 y=[r['final_level'] for r in records];n=min(3,min(Counter(y).values()))
 # Singleton class: diagnostics only; selection() freezes the preregistered model.
 with warnings.catch_warnings():
  warnings.simplefilter('ignore',UserWarning)
  return list(StratifiedKFold(n_splits=max(2,n),shuffle=True,random_state=seed).split(y,y))
def quota(records,g):
 n=int(g['mult']*len(records));counts=Counter(r['final_level'] for r in records)
 w=np.array([36,36,19] if g['ratio']=='old' else [1,1,1] if g['ratio']=='equal' else [counts[l] for l in LAB],float)
 raw=w/w.sum()*n;q=np.floor(raw).astype(int)
 for i in np.argsort(-(raw-q),kind='stable')[:n-sum(q)]:q[i]+=1
 return dict(zip(LAB,map(int,q)))
def synthetic(records,g,seed):
 ids={r['sample_id'] for r in records}
 out=sample_and_render([r for r in cal if r['sample_id'] in ids],kinds,quota(records,g),seed,tau=g['tau'])
 assert all(r['spec']['parent_id'] in ids for r in out)
 return [dict(prompt_text=r['prompt_text'],final_level=r['spec']['final_level_candidate'],parent_id=r['spec']['parent_id']) for r in out]
def fit(records,c,following=False):
 m=Classifier(intent=False,context=following,balance=c['balance'])
 m.vec.set_params(ngram_range=(1,c['ngram']))
 m.clf.set_params(C=c['C'])
 with warnings.catch_warnings(record=True) as ww:
  warnings.simplefilter('always');m.fit([r['prompt_text'] for r in records],[r['final_level'] for r in records])
  if any('converge' in str(w.message).lower() for w in ww):raise RuntimeError('Nonconverged fit')
 return m
def score(y,p,labels):
 pred=np.array(labels)[np.asarray(p).argmax(1)]
 return dict(macro_f1=float(f1_score(y,pred,labels=labels,average='macro',zero_division=0)),accuracy=float(accuracy_score(y,pred)),confusion_matrix=confusion_matrix(y,pred,labels=labels).tolist())
def selection(records,seed,stage):
 labels=LAB if stage=='R1' else LAB+[ACK];parts=split(records,seed);syn_cache={};cache={};audit=[]
 for a,b in parts:
  assert not {records[i]['student_id'] for i in a}&{records[i]['student_id'] for i in b}
  audit.append(dict(train=[records[i]['student_id'] for i in a],validation=[records[i]['student_id'] for i in b]))
 def evaluate(c,g=None,multi=True):
  ss=SYNSEEDS if g and multi else [SYNSEEDS[0]];key=json.dumps([c,g,ss],sort_keys=True)
  if key in cache:return cache[key]
  ps=[];metrics=[]
  for offset in ss:
   p=np.zeros((len(records),len(labels)))
   for i,(a,b) in enumerate(parts):
    tr=[records[k] for k in a];te=[records[k] for k in b];syn=[]
    if g:
     sk=json.dumps([i,g,offset],sort_keys=True)
     if sk not in syn_cache:
      try:syn_cache[sk]=synthetic(tr,g,seed*1000+i*100+offset)
      except RuntimeError as exc:
       ans=dict(classifier=c,generator=g,f1=None,seed_f1=[],predictions=[],infeasible=str(exc),inner_fold=i)
       cache[key]=ans;return ans
     syn=syn_cache[sk]
     assert not {r['parent_id'] for r in syn}&{r['sample_id'] for r in te}
    m=fit(tr+syn,c,stage=='R3');p[b]=m.probs([r['prompt_text'] for r in te],labels)
   ps.append(p);metrics.append(score([r['final_level'] for r in records],p,labels)['macro_f1'])
  ans=dict(classifier=c,generator=g,f1=float(np.mean(metrics)),seed_f1=metrics,predictions=ps[0].tolist())
  cache[key]=ans;return ans
 def ranked(seq):return sorted([r for r in seq if r['f1'] is not None],key=lambda r:(-r['f1'],(r['generator'] or {}).get('mult',0),r['classifier']['C'],r['classifier']['ngram'],r['classifier']['balance'],json.dumps(r['generator'],sort_keys=True)))
 if min(Counter(r['final_level'] for r in records).values())<2:
  fixed=evaluate(dict(C=2.,ngram=3 if stage=='R3' else 4,balance=True))
  fixed['selection_status']='frozen_due_to_singleton_class; inner predictions diagnostic only'
  return {'real':fixed},[{k:v for k,v in fixed.items() if k!='predictions'}],audit
 rs=ranked([evaluate(c) for c in GRID]);chosen={'real':rs[0]}
 if stage=='R1':
  ms=ranked([evaluate(c,DEFAULT) for c in GRID]);gs=ranked([evaluate(ms[0]['classifier'],g) for g in GGRID])
  cross=ranked([evaluate(c['classifier'],g['generator']) for c in ms[:2] for g in gs[:2]])
  for candidate in ranked(cross+gs):
   try:
    for offset in SYNSEEDS:synthetic(records,candidate['generator'],seed*1000+offset)
    chosen['mixed']=candidate;break
   except RuntimeError as exc:candidate['full_training_infeasible']=str(exc)
  assert 'mixed' in chosen,'No feasible mixed candidate'
 return chosen,[{k:v for k,v in r.items() if k!='predictions'} for r in cache.values()],audit
def run_fold(fold):
 seed,fi=fold['seed'],fold['fold'];path=OUT/'results'/f'fold_{seed}_{fi}.json'
 if path.exists():return
 train=[r for r in real if r['sample_id'] in fold['train_ids']];test=[r for r in real if r['sample_id'] in fold['heldout_ids']]
 students={r['student_id'] for r in train};res=dict(seed=seed,fold=fi,stages={})
 for stage,tr,te in [('R1',train,test),('R3',[r for r in later if r['student_id'] in students],[r for r in later if r['student_id'] not in students])]:
  chosen,candidates,audit=selection(tr,seed*100+fi,stage);labels=LAB if stage=='R1' else LAB+[ACK];preds=[]
  for variant,s in chosen.items():
   for offset in (SYNSEEDS if s['generator'] else [SYNSEEDS[0]]):
    syn=synthetic(tr,s['generator'],(seed*100+fi)*1000+offset) if s['generator'] else []
    assert not {r['parent_id'] for r in syn}&{r['sample_id'] for r in te}
    m=fit(tr+syn,s['classifier'],stage=='R3');p=m.probs([r['prompt_text'] for r in te],labels)
    for r,v in zip(te,p):preds.append(dict(variant=variant,gen_seed=offset,sample_id=r['sample_id'],student_id=r['student_id'],truth=r['final_level'],prediction=labels[int(v.argmax())],probabilities=v.tolist()))
  res['stages'][stage]=dict(chosen=chosen,candidates=candidates,inner_students=audit,predictions=preds,training_ids=[r['sample_id'] for r in tr])
  event(stage=stage,seed=seed,fold=fi,chosen={k:{a:b for a,b in v.items() if a!='predictions'} for k,v in chosen.items()})
 dump(path,res)
def main():
 args=sys.argv[1:];protocol=OUT/'执行协议.md'
 manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [protocol,Path(__file__),BASE/'anonymous_samples_snapshot.json',BASE/'fold_audit.json']}
 mp=OUT/'input_manifest.json'
 if mp.exists():assert json.loads(mp.read_text(encoding='utf-8'))==manifest,'Changed sources: use new run directory'
 else:dump(mp,manifest)
 subset=folds[:1] if '--smoke' in args else folds
 for fold in subset:run_fold(fold)
 event(stage='outer_complete',folds=len(subset))
if __name__=='__main__':main()
