from common import *
from controlled_text import calibrated,pool
def run():
 real,eedi,llm,r3=load();param,meta=calibrated(real,20260930);_,test=pool('test');data={'eedi_only':eedi,'real_only':real,'parameter_primary':param,'parameter_real':param+real,'parameter_eedi_real':param+eedi+real}
 result={}
 for name,corpus in data.items():
    model=Classifier().fit([r['prompt_text'] for r in corpus],[r['final_level'] for r in corpus])
    p=model.probs([r['prompt_text'] for r in test]);result[name]={'train_rows':len(corpus),'controlled_unique_test':metrics([r['final_level'] for r in test],p)}
 write_json('results/controlled_holdout_diagnostics.json',{'calibration':meta,'test_n':len(test),'comparisons':result,
    'scope':'Separate frozen grammar/task holdout diagnostic; real47 used for full calibration/training here, NEVER report real in-sample scores as validation'})
 # Meaning-preserving mask diagnostics on all human real R1 and all grammar examples.
 checks=[]
 for name,rows in [('real47',real),('controlled',pool()[0])]:
    for r in rows:
      t=F.normalize_prompt(r['prompt_text']);old=F.mask_math_content(t);new=B.safe_mask(t)
      original_features=F.extract_intent_features(t);old_features=F.extract_intent_features(old);new_features=F.extract_intent_features(new)
      checks.append({'source':name,'sample_id':r.get('sample_id',r.get('template_family','')),'text':t,'old_mask':old,'bounded_mask':new,
                     'old_lost_intent_count':int(np.sum((original_features>0)&(old_features==0))),
                     'bounded_lost_intent_count':int(np.sum((original_features>0)&(new_features==0)))})
 write_csv('results/masking_semantic_audit.csv',checks)
 write_json('results/masking_semantic_summary.json',{name:{'n':sum(r['source']==name for r in checks),
    'old_any_intent_lost':sum(r['source']==name and r['old_lost_intent_count']>0 for r in checks),
    'bounded_any_intent_lost':sum(r['source']==name and r['bounded_lost_intent_count']>0 for r in checks)} for name in ['real47','controlled']})
 print('Controlled grammar holdout and semantic masking diagnostics complete.')
if __name__=='__main__':run()
