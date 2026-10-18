from common import *
from controlled_text import calibrated
from parameter_v2 import pool_v2,calibrated_v2
from sklearn.model_selection import StratifiedKFold
from uncertainty import bootstrap_prediction_metrics
def run():
 real,eedi,llm,r3=load();raw,train=pool_v2();rawtest,test=pool_v2('test')
 for key in ['template_family','task_id','feature_key']:assert not {r[key] for r in train}&{r[key] for r in test},key
 write_csv('data/E7_v2训练候选.csv',train);write_csv('data/E7_v2受控留出候选.csv',test)
 write_json('data/E7_v2语法清单.json',{'raw_train':len(raw),'unique_train':len(train),'raw_test':len(rawtest),'unique_test':len(test),
   'classes':dict(Counter(r['final_level'] for r in train)),'length_bins':dict(Counter(str(r['length_bin']) for r in train)),
   'split_checks':{'template_family':True,'task_id':True,'masked_text':True},'human_review':'pending'})
 y=np.array([r['final_level'] for r in real]);pred=[];summary=[];splits=[]
 for seed in SEEDS:
  pp={k:np.zeros((47,3)) for k in ['v1_parameter','v2_parameter','v2_parameter_real','real_only']}
  for fold,(tr,te) in enumerate(StratifiedKFold(4,shuffle=True,random_state=seed).split(np.zeros(47),y)):
   training=[real[i] for i in tr];testing=[real[i] for i in te];p1,c1=calibrated(training,seed*100+fold);p2,c2=calibrated_v2(training,seed*100+fold)
   assert not set(c2['calibration_ids'])&{r['sample_id'] for r in testing}
   splits.append({'seed':seed,'fold':fold,'heldout_ids':[r['sample_id'] for r in testing],'v2_calibration':c2})
   for variant,corpus in [('v1_parameter',p1),('v2_parameter',p2),('v2_parameter_real',p2+training),('real_only',training)]:
    m=Classifier().fit([r['prompt_text'] for r in corpus],[r['final_level'] for r in corpus]);p=m.probs([r['prompt_text'] for r in testing]);pp[variant][te]=p
    pred.extend(collect_predictions('E7_parameter_coverage',variant,seed,fold,testing,p))
  for variant,p in pp.items():summary.append({'variant':variant,'seed':seed,**metrics(y,p)})
  print(f'E7 seed {seed} complete',flush=True)
 write_csv('results/E7_predictions.csv',pred);write_csv('results/E7_repeat_metrics.csv',summary);write_json('results/E7_summary.json',summarize(summary));write_json('data/E7_calibration_splits.json',splits)
 draws={};bands={}
 for variant in pp:
  d,b=bootstrap_prediction_metrics([r for r in pred if r['variant']==variant],LAB);draws[variant]=d;bands[variant]=b
 contrasts={}
 for a,b in [('v2_parameter','v1_parameter'),('v2_parameter_real','real_only')]:
  delta=draws[a]-draws[b];s=summarize(summary);contrasts[a+' minus '+b]={'observed_difference':s[a]['macro_f1']['mean']-s[b]['macro_f1']['mean'],
    'paired_fixed_prediction_conditional95':np.quantile(delta,[.025,.975]).tolist()}
 write_json('results/E7_uncertainty.json',{'models':bands,'contrasts':contrasts,'scope':'post-primary exploratory development; fixed-prediction bands not full training uncertainty'})
 # Controlled holdout is distinct from real student evaluation. Never report in-sample real scores.
 p2,cal=calibrated_v2(real,20260930);diagnostics={}
 for variant,corpus in [('v2_parameter',p2),('v2_parameter_real',p2+real)]:
  m=Classifier().fit([r['prompt_text'] for r in corpus],[r['final_level'] for r in corpus]);diagnostics[variant]=metrics([r['final_level'] for r in test],m.probs([r['prompt_text'] for r in test]))
 write_json('results/E7_controlled_holdout.json',{'test_n':len(test),'calibration':cal,'comparisons':diagnostics,'scope':'engineering candidates; no independent human or external validation'})
 print('E7 coverage supplement finished. All results retained; runtime default unchanged.')
if __name__=='__main__':run()
