"""Fixed-configuration ablations. No selection using outer outcomes."""
import run_selection as s
from generator_variants import generate_variant
from collections import Counter
import json,numpy as np

def main():
 out=s.OUT/'results/generation_ablation.json'
 results=json.loads(out.read_text(encoding='utf-8')) if out.exists() else []
 choices=[('ALSP','mean'),('ALP','mean'),('uniform','mean'),('ALSP','rater_A'),('ALSP','rater_B')]
 for fold in s.folds:
  tr=[r for r in s.real if r['sample_id'] in fold['train_ids']];te=[r for r in s.real if r['sample_id'] in fold['heldout_ids']]
  cal=[r for r in s.cal if r['sample_id'] in fold['train_ids']]
  for mode,rater in choices:
   for gs in s.SYNSEEDS:
    key=dict(seed=fold['seed'],fold=fold['fold'],mode=mode,rater=rater,gen_seed=gs)
    if any(all(r[k]==v for k,v in key.items()) for r in results):continue
    seed=(fold['seed']*100+fold['fold'])*1000+gs
    try:
     syn=generate_variant(cal,s.kinds,s.quota(tr,s.DEFAULT),seed,mode=mode,rater=rater)
     assert not {r['parent_id'] for r in syn}&set(fold['heldout_ids'])
     if mode=='ALSP' and rater=='mean':
      assert [r['prompt_text'] for r in syn]==[r['prompt_text'] for r in s.synthetic(tr,s.DEFAULT,seed)],'ALSP parity'
     m=s.fit(tr+syn,dict(C=2.,ngram=4,balance=True));p=m.probs([r['prompt_text'] for r in te],s.LAB)
     results.append(dict(**key,n_synthetic=len(syn),vocabulary_size=len(m.vec.vocabulary_),
       predictions=[dict(sample_id=r['sample_id'],truth=r['final_level'],probabilities=pp.tolist()) for r,pp in zip(te,p)]))
    except RuntimeError as e:results.append(dict(**key,infeasible=str(e)))
    s.dump(out,results)
  print('ablation',fold['seed'],fold['fold'],flush=True)
 summary={}
 for mode,rater in choices:
  metrics=[]
  for seed in [17,29,43,71,101]:
   for gs in s.SYNSEEDS:
    group=[r for r in results if r['mode']==mode and r['rater']==rater and r['seed']==seed and r['gen_seed']==gs]
    if len(group)!=4 or any('infeasible' in r for r in group):continue
    pp=[p for r in group for p in r['predictions']]
    metrics.append(s.score([p['truth'] for p in pp],[p['probabilities'] for p in pp],s.LAB))
  summary[mode+'_'+rater]={'complete_repetitions':len(metrics),'macro_f1':float(np.mean([r['macro_f1'] for r in metrics])) if metrics else None,'accuracy':float(np.mean([r['accuracy'] for r in metrics])) if metrics else None}
 s.dump(s.OUT/'results/generation_ablation_summary.json',{'fixed_classifier':{'C':2,'ngram':4,'balance':True},'generator':s.DEFAULT,'results':summary,'max_vocabulary':max(r.get('vocabulary_size',0) for r in results),'role':'sensitivity only; no automatic promotion'})
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
