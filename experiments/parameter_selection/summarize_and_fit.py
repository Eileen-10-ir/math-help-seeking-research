"""Summarize held-out predictions, calibrate gates on training, fit deployment candidates."""
import run_selection as s
import sys,json,copy,hashlib
from collections import Counter
import numpy as np,joblib
sys.path.insert(0,str(s.ROOT/'数学共同主线定版20261018/code'))
from state_v5 import State,advance
CONFIG=json.loads((s.ROOT/'数学共同主线定版20261018/data/runtime_state_config_v4.json').read_text(encoding='utf-8'))

def gate(rows,p,stage,cut):
 labels=s.LAB if stage=='R1' else s.LAB+[s.ACK]
 hits=[];ack=0;graded=sum(r['final_level'] in s.LAB for r in rows)
 for r,probs in zip(rows,p):
  state=State();state.events=int(stage=='R3')
  cfg={**CONFIG,'stage_cutoffs':{'R1':cut,'R3':cut}}
  result=advance(state,r['prompt_text'],dict(zip(labels,probs)),cfg)
  if result['risk_updated']:
   if r['final_level'] in s.LAB:hits.append(result['current_behavior_level']==r['final_level'])
   else:ack+=1
 return dict(cutoff=cut,graded=graded,accepted=len(hits),correct=sum(hits),ACK_updates=ack,
             coverage=len(hits)/graded if graded else 0,accepted_accuracy=sum(hits)/len(hits) if hits else 0)

def choosegate(rows,p,stage,target=.85):
 opts=[gate(rows,p,stage,c) for c in [.35,.4,.45,.5,.55,.6,.65]]
 feasible=[r for r in opts if r['accepted_accuracy']>=target and r['ACK_updates']==0]
 chosen=max(feasible,key=lambda r:(r['coverage'],r['accepted_accuracy'],r['cutoff'])) if feasible else min(opts,key=lambda r:(r['ACK_updates'],r['accepted']-r['correct'],-r['coverage'],-r['cutoff']))
 return dict(chosen=chosen,constraints_satisfied=bool(feasible),options=opts)

def main():
 fs=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((s.OUT/'results').glob('fold_*.json'))]
 assert len(fs)==20
 summary={};allrows=[];gates=[];selection_counts=Counter()
 for f in fs:
  for stage,v in f['stages'].items():
   chosen=v['chosen'];best=max(chosen,key=lambda k:(chosen[k]['f1'],k=='real'))
   selection_counts[stage+'_'+best]+=1
   for r in v['predictions']:
    allrows.append(dict(r,stage=stage,seed=f['seed'],fold=f['fold']))
    if r['variant']==best:allrows.append(dict(r,variant='adaptive',stage=stage,seed=f['seed'],fold=f['fold']))
   for variant,c in chosen.items():
    source=s.real if stage=='R1' else s.later
    tr=[r for r in source if r['sample_id'] in v['training_ids']]
    for target in [.8,.85,.9]:
     if 'selection_status' in c:
      choice={'chosen':{'cutoff':CONFIG['stage_cutoffs'][stage]},'constraints_satisfied':None,'frozen_singleton':True}
     else:choice=choosegate(tr,c['predictions'],stage,target)
     for gs in (s.SYNSEEDS if variant=='mixed' else s.SYNSEEDS[:1]):
      pp=[r for r in v['predictions'] if r['variant']==variant and r['gen_seed']==gs]
      rr=[next(x for x in source if x['sample_id']==r['sample_id']) for r in pp]
      metric=gate(rr,[r['probabilities'] for r in pp],stage,choice['chosen']['cutoff'])
      gates.append(dict(stage=stage,variant=variant,seed=f['seed'],fold=f['fold'],gen_seed=gs,target=target,selection=choice,heldout=metric))
 for stage in ['R1','R3']:
  labels=s.LAB if stage=='R1' else s.LAB+[s.ACK]
  for variant in ['real','mixed','adaptive']:
   rr=[r for r in allrows if r['stage']==stage and r['variant']==variant]
   if not rr:continue
   repetitions=[]
   for seed in [17,29,43,71,101]:
    # Adaptive: replicate real predictions across generation seeds where a fold chose real.
    for gs in (s.SYNSEEDS if stage=='R1' and variant!='real' else s.SYNSEEDS[:1]):
     batch=[]
     for sid in sorted({r['sample_id'] for r in rr}):
      rows=[r for r in rr if r['seed']==seed and r['sample_id']==sid]
      batch.append(next((r for r in rows if r['gen_seed']==gs),rows[0]))
     metric=s.score([r['truth'] for r in batch],[r['probabilities'] for r in batch],labels)
     cm=np.array(metric['confusion_matrix']);metric['recall_by_label']=dict(zip(labels,(cm.diagonal()/cm.sum(1)).tolist()))
     repetitions.append(dict(seed=seed,gen_seed=gs,**metric))
   summary[stage+'_'+variant]={'macro_f1':float(np.mean([r['macro_f1'] for r in repetitions])),
       'accuracy':float(np.mean([r['accuracy'] for r in repetitions])),
       'f1_min_max':[min(r['macro_f1'] for r in repetitions),max(r['macro_f1'] for r in repetitions)],
       'recall_by_label':{l:float(np.mean([r['recall_by_label'][l] for r in repetitions])) for l in labels},'repetitions':repetitions}
 s.dump(s.OUT/'results/recognition_summary.json',dict(metrics=summary,selection_counts=dict(selection_counts),unique_students=47,
      interpretation='Nested internal retrospective evaluation; repetitions and generation seeds are not new students. Adaptive is training-side selection between real and mixed, not an ensemble.'))
 s.dump(s.OUT/'results/gate_sensitivity.json',gates)
 print(json.dumps({k:{x:y for x,y in v.items() if x!='repetitions'} for k,v in summary.items()},ensure_ascii=False),flush=True)
 deployment={};models={};stagecuts={}
 for stage,records in [('R1',s.real),('R3',s.later)]:
  chosen,candidates,audit=s.selection(records,20261118,stage)
  best=max(chosen,key=lambda k:(chosen[k]['f1'],k=='real'));c=chosen[best]
  for variant,option in chosen.items():
   syn=s.synthetic(records,option['generator'],20261118*1000+s.SYNSEEDS[0]) if option['generator'] else []
   model=s.fit(records+syn,option['classifier'],stage=='R3')
   joblib.dump(model,s.OUT/'models'/f'{stage}_{variant}.joblib')
   if variant==best:models['first' if stage=='R1' else 'following']=model
  gatesel=choosegate(records,c['predictions'],stage)
  stagecuts[stage]=gatesel['chosen']['cutoff']
  deployment[stage]=dict(selected_variant=best,chosen={k:{a:b for a,b in v.items() if a!='predictions'} for k,v in chosen.items()},gate=gatesel,
        candidates=candidates,inner_students=audit)
 joblib.dump(models,s.OUT/'models/runtime_models_v1.joblib')
 cfg=copy.deepcopy(CONFIG);cfg['stage_cutoffs']=stagecuts
 cfg['cutoff_selection_source']='20261118 full-data internal cross-validation, matching selected classifier; target 85%, zero ACK updates when feasible'
 cfg['lambda_selection_source']='Retained engineering working point; 110-configuration sensitivity reported, no validated human longitudinal optimum'
 s.dump(s.OUT/'models/runtime_state_config_v4.json',cfg)
 s.dump(s.OUT/'results/deployment_selection.json',deployment)
 print(json.dumps({'deployment':{k:(v['selected_variant'],v['chosen'][v['selected_variant']]['classifier']) for k,v in deployment.items()},'stage_cutoffs':stagecuts},ensure_ascii=False))
if __name__=='__main__':main()
