"""Engineering sensitivity of state controls, with disjoint random realizations.
Constructed targets are NOT student dependency ground truth. No model retraining.
"""
from pathlib import Path
import itertools,json,csv,math
import numpy as np
OUT=Path(__file__).resolve().parents[1]
def scenarios(seed):
 rng=np.random.default_rng(seed)
 for length in [8,16,24]:
  for kind in ['high','nonhigh','up','down','alternating']:
   target=np.ones(length) if kind=='high' else np.zeros(length) if kind=='nonhigh' else np.r_[np.zeros(length//2),np.ones(length-length//2)] if kind=='up' else np.r_[np.ones(length//2),np.zeros(length-length//2)] if kind=='down' else np.arange(length)%2
   for noise in [0.,.1,.2]:
    observed=np.logical_xor(target,rng.random(length)<noise).astype(int)
    strength=rng.uniform(.55,.95,length)
    scores=np.where(observed,strength,1-strength)
    accepted=rng.random(length)>.15;accepted[0]=True
    explicit=rng.random(length)<.2
    yield dict(kind=kind,length=length,noise=noise,target=target,observed=observed,scores=scores,accepted=accepted,explicit=explicit)
def replay(s,alpha,threshold,streak_limit,encoding,protect=True):
 r=None;streak=0;pred=[];values=[];held=0
 for t in range(s['length']):
  if not s['accepted'][t]:held+=1;continue
  level=int(s['observed'][t]);explicit=bool(s['explicit'][t])
  x=float(level) if encoding=='binary' or explicit else float(s['scores'][t])
  r=x if r is None else alpha*x+(1-alpha)*r
  streak=0 if level else streak+1
  hist=protect and not level and r>=threshold and not explicit and streak<streak_limit
  pred.append(int(level or hist));values.append((r-s['target'][t])**2)
 y=s['target'][s['accepted']]
 p=np.array(pred)
 return dict(error=float(np.mean(p!=y)),false_restriction=float(np.sum((p==1)&(y==0))/max(1,sum(y==0))),
             missed_high=float(np.sum((p==0)&(y==1))/max(1,sum(y==1))),
             switches=int(np.sum(np.diff(p)!=0)),target_switches=int(np.sum(np.diff(y)!=0)),
             constructed_mse=float(np.mean(values)),valid=len(y),held=held)
def main():
 rows=[]
 configs=[dict(alpha=a,threshold=t,streak=k,encoding=e,protect=True) for a,t,k,e in itertools.product([.2,.4,.5,.65,.8,1.],[.3,.5,.7],[1,2,3],['hybrid','binary'])]
 configs += [dict(alpha=.65,threshold=.5,streak=2,encoding=e,protect=False) for e in ['hybrid','binary']]
 for split,seeds in [('development',[111,222,333]),('held_variants',[444,555,666])]:
  for seed in seeds:
   for s in scenarios(seed):
    for c in configs:
     result=replay(s,c['alpha'],c['threshold'],c['streak'],c['encoding'],c['protect'])
     rows.append(dict(split=split,seed=seed,kind=s['kind'],length=s['length'],noise=s['noise'],**c,**result))
 p=OUT/'results/state_sensitivity.csv'
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 import pandas as pd
 df=pd.DataFrame(rows);keys=['split','alpha','threshold','streak','encoding','protect']
 summary=df.groupby(keys)[['error','false_restriction','missed_high','switches','constructed_mse']].mean().reset_index()
 summary.to_csv(OUT/'results/state_summary.csv',index=False,encoding='utf-8-sig')
 baseline=summary[(summary.alpha==.65)&(summary.threshold==.5)&(summary.streak==2)&(summary.encoding=='hybrid')&summary.protect]
 report={'scope':'constructed engineering signals, not real longitudinal students','rows':len(rows),'configurations':len(configs),
         'unchanged_runtime':True,'baseline':baseline.to_dict('records'),
         'decision':'No automatic parameter promotion from constructed targets. Report error tradeoffs and validate on context cases.',
         'ewma_properties':{'weights':'alpha*(1-alpha)^k','constant_input_error':'(1-alpha)^k * initial_error','alpha_065_half_life_valid_updates':math.log(.5)/math.log(.35)}}
 (OUT/'results/state_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
