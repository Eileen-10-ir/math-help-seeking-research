import sys,json,time
from collections import Counter
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold,StratifiedKFold
from common import *
from controlled_text import pool,calibrated
def run():
 manifest=source_manifest();real,eedi,llm,r3=load();all_predictions=[];records=[];splits=[]
 _,paramtest=pool('test');raw,paramtrain=pool('train')
 assert not {r['template_family'] for r in paramtrain}&{r['template_family'] for r in paramtest}
 assert not {r['task_id'] for r in paramtrain}&{r['task_id'] for r in paramtest}
 assert not {r['feature_key'] for r in paramtrain}&{r['feature_key'] for r in paramtest}
 write_csv('data/受控文本训练语法候选.csv',raw);write_csv('data/受控文本留出候选.csv',paramtest)
 write_json('data/controlled_corpus_manifest.json',{'raw_train':len(raw),'distinct_masked_train':len(paramtrain),
    'distinct_masked_test':len(paramtest),'templates_train':36,'templates_test':12,'human_review':'pending',
    'split_checks':{'template_family':True,'task_id':True,'masked_text':True}})
 variants={'full':{},'no_intent':{'intent':False},'no_mask':{'mask':'none'},'no_balance':{'balance':False},'old_mask':{'mask':'old'}}
 # Same grouped folds for each component; full source corpus never includes real-derived LLM.
 y=np.array([r['final_level'] for r in eedi]);groups=np.array([F.sha256_group(r['prompt_text']) for r in eedi]);targetdiag={}
 for name,kw in variants.items():
    model=Classifier(**kw).fit([r['prompt_text'] for r in eedi],y)
    tp=model.probs([r['prompt_text'] for r in real]);targetdiag[name]=metrics([r['final_level'] for r in real],tp)
    all_predictions.extend(collect_predictions('E1_real_development',name,0,-1,real,tp))
    for seed in SEEDS:
      p=np.zeros((len(eedi),3));splitter=StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=seed)
      for fold,(tr,te) in enumerate(splitter.split(np.zeros(len(y)),y,groups)):
        assert not set(groups[tr])&set(groups[te])
        m=Classifier(**kw).fit([eedi[i]['prompt_text'] for i in tr],y[tr]);p[te]=m.probs([eedi[i]['prompt_text'] for i in te])
        all_predictions.extend(collect_predictions('E1_public_oof',name,seed,fold,[eedi[i] for i in te],p[te]))
      records.append({'experiment':'E1','variant':name,'seed':seed,**metrics(y,p)})
    print(f'E1 {name} completed',flush=True)
 write_json('results/E1_summary.json',{'public_oof':summarize(records),'real47_development':targetdiag,
    'groups_available':'normalized_text_only; original public student/task relations unknown'})
 write_csv('results/E1_repeat_metrics.csv',records)
 # Retrospective student-level cross-fitting. Every descendant of a held-out parent is excluded.
 y=np.array([r['final_level'] for r in real]);eedi_model=Classifier().fit([r['prompt_text'] for r in eedi],[r['final_level'] for r in eedi])
 eedi_probs=eedi_model.probs([r['prompt_text'] for r in real]);names=['majority','eedi_only','real_only','eedi_real_llm','parameter_primary','parameter_real','parameter_eedi_real_llm']
 cross=[]
 for seed in SEEDS:
   pp={name:np.zeros((len(real),3)) for name in names}
   for fold,(tr,te) in enumerate(StratifiedKFold(4,shuffle=True,random_state=seed).split(np.zeros(len(y)),y)):
     train=[real[i] for i in tr];test=[real[i] for i in te];ids={r['sample_id'] for r in train};held={r['sample_id'] for r in test}
     allowed=[r for r in llm if r['parent_id'] in ids];assert not any(r['parent_id'] in held for r in allowed)
     param,cal=calibrated(train,seed*100+fold);assert not set(cal['calibration_ids'])&held
     splits.append({'seed':seed,'fold':fold,'training_real_ids':sorted(ids),'heldout_real_ids':sorted(held),
                    'allowed_llm_ids':[r['sample_id'] for r in allowed],'excluded_llm_ids':[r['sample_id'] for r in llm if r['parent_id'] in held],
                    'parameter_calibration':cal})
     corpora={'real_only':train,'eedi_real_llm':eedi+train+allowed,'parameter_primary':param,
              'parameter_real':param+train,'parameter_eedi_real_llm':param+eedi+train+allowed}
     for name in names:
       if name=='majority':p=majority(y[tr],len(te))
       elif name=='eedi_only':p=eedi_probs[te]
       else:
         data=corpora[name];m=Classifier().fit([r['prompt_text'] for r in data],[r['final_level'] for r in data]);p=m.probs([r['prompt_text'] for r in test])
       pp[name][te]=p;all_predictions.extend(collect_predictions('E2_student_crossfit',name,seed,fold,test,p))
   for name,p in pp.items():cross.append({'experiment':'E2','variant':name,'seed':seed,**metrics(y,p)})
   print(f'E2 seed {seed} completed',flush=True)
 write_csv('results/E2_repeat_metrics.csv',cross);write_json('results/E2_summary.json',summarize(cross));write_json('data/E2_family_calibration_splits.json',splits)
 # Four-category R3 feasibility; context includes only observed texts and historical guide type.
 by={r['sample_id']:r for r in real};labels=LAB+[ACK];y=np.array([r['final_level'] for r in r3]);r3metrics=[]
 def text(r,kind):
    if kind=='r3_only':return r['prompt_text']
    parent=by[r['pair_id']]['prompt_text']
    return '[前次学生]'+parent+('[历史引导类型]'+r['ai_type'] if kind=='context_guide' else '')+'[本次学生]'+r['prompt_text']
 for seed in SEEDS:
   names3=['majority','r3_only','context','context_guide'];pp={name:np.zeros((len(r3),4)) for name in names3}
   for fold,(tr,te) in enumerate(StratifiedKFold(4,shuffle=True,random_state=seed).split(np.zeros(len(y)),y)):
     assert not {r3[i]['student_id'] for i in tr}&{r3[i]['student_id'] for i in te}
     for name in names3:
       if name=='majority':p=majority(y[tr],len(te),labels)
       else:
         model=Classifier(intent=False,mask='bounded',context=True).fit([text(r3[i],name) for i in tr],y[tr])
         p=model.probs([text(r3[i],name) for i in te],labels)
       pp[name][te]=p;all_predictions.extend(collect_predictions('E3_r3_crossfit',name,seed,fold,[r3[i] for i in te],p,labels))
   for name,p in pp.items():r3metrics.append({'experiment':'E3','variant':name,'seed':seed,**metrics(y,p,labels)})
   print(f'E3 seed {seed} completed',flush=True)
 write_csv('results/E3_repeat_metrics.csv',r3metrics);write_json('results/E3_summary.json',summarize(r3metrics))
 write_csv('results/recognition_predictions.csv',all_predictions)
 if (ROOT/'7月数据/依赖标注数据库.db').exists():
    assert sha(ROOT/'7月数据/依赖标注数据库.db')==manifest['sources'][str(ROOT/'7月数据/依赖标注数据库.db')]
 print('E1/E2/E3 complete. Source DB unchanged.',flush=True)
if __name__=='__main__':run()
