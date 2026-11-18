"""Aggregate denominators and conditional student-cluster uncertainty."""
from pathlib import Path
import json,csv,collections
import numpy as np
OUT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def f1(cm):
 den=cm.sum(-1)+cm.sum(-2);di=np.diagonal(cm,axis1=-2,axis2=-1)
 return np.divide(2*di,den,out=np.zeros_like(di,dtype=float),where=den!=0).mean(-1)
def main():
 folds=[read(p) for p in sorted((OUT/'results').glob('fold_*.json'))]
 labels=['high','medium','low'];student_truth={};tables={}
 for group in folds:
  for r in group['stages']['R1']['predictions']:
   sid=r['student_id'];student_truth[sid]=labels.index(r['truth'])
   tables[(group['seed'],r['variant'],r['gen_seed'],sid)]=labels.index(r['prediction'])
 ids=sorted(student_truth);truth=np.array([student_truth[k] for k in ids]);tensor=[]
 for seed in [17,29,43,71,101]:
  for gs in [1301,2711,4051]:
   pair=[]
   for variant in ['real','mixed']:
    cells=np.zeros((47,3,3))
    for i,sid in enumerate(ids):cells[i,truth[i],tables[(seed,variant,1301 if variant=='real' else gs,sid)]]=1
    pair.append(cells)
   tensor.append(pair)
 arr=np.array(tensor);rng=np.random.default_rng(1811);differences=[]
 for _ in range(2000):
  indices=np.concatenate([rng.choice(np.where(truth==i)[0],size=sum(truth==i),replace=True) for i in range(3)])
  scores=f1(arr[:,:,indices].sum(2));differences.append(float((scores[:,1]-scores[:,0]).mean()))
 gates=read(OUT/'results/gate_sensitivity.json');gate_summary=[]
 for stage in ['R1','R3']:
  for variant in ['real','mixed']:
   for target in [.8,.85,.9]:
    rows=[r for r in gates if r['stage']==stage and r['variant']==variant and r['target']==target]
    if not rows:continue
    totals={k:sum(r['heldout'][k] for r in rows) for k in ['graded','accepted','correct','ACK_updates']}
    gate_summary.append(dict(stage=stage,variant=variant,target=target,**totals,
      coverage=totals['accepted']/totals['graded'],accepted_accuracy=totals['correct']/totals['accepted'] if totals['accepted'] else None,
      constraint_failure_splits=len({(r['seed'],r['fold']) for r in rows if r['selection']['constraints_satisfied'] is False}),
      frozen_singleton_splits=len({(r['seed'],r['fold']) for r in rows if r['selection'].get('frozen_singleton')})))
 counts=collections.Counter();infeasible=0
 for f in folds:
  for st,info in f['stages'].items():
   for v,c in info['chosen'].items():counts[st+' '+v+' '+json.dumps(c['classifier'],sort_keys=True)]+=1
   infeasible+=sum(c.get('f1') is None for c in info['candidates'])
 save(OUT/'results/statistical_summary.json',{'paired_difference_mixed_minus_real':float((f1(arr.sum(2))[:,1]-f1(arr.sum(2))[:,0]).mean()),
  'conditional_95_interval':np.quantile(differences,[.025,.975]).tolist(),'bootstrap_repetitions':2000,'independent_students':47,
  'method':'Stratified student-cluster bootstrap of stored OOF predictions. Same student is sampled jointly across all split/augmentation repetitions; no retraining. Conditional on data, fitted models and prior development; not external validity.',
  'gate_summary':gate_summary,'selected_classifier_counts':dict(counts),'infeasible_inner_candidates':infeasible})
 print(json.dumps({'delta':float(np.mean(differences)),'conditional_interval':np.quantile(differences,[.025,.975]).tolist(),'gate_summary':gate_summary},ensure_ascii=False))
if __name__=='__main__':main()
