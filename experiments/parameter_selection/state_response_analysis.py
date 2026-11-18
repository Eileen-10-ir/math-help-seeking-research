"""Response delay / errors on constructed signals, complementing mean error."""
import run_state_sensitivity as s
import numpy as np,json,itertools
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
def detail(scene,a,t,k,e):
 risk=None;streak=0;dec=[];truth=[]
 for i in range(scene['length']):
  if not scene['accepted'][i]:continue
  level=int(scene['observed'][i]);explicit=scene['explicit'][i]
  x=level if e=='binary' or explicit else scene['scores'][i]
  risk=x if risk is None else a*x+(1-a)*risk;streak=0 if level else streak+1
  dec.append(int(level or (risk>=t and not explicit and streak<k)));truth.append(int(scene['target'][i]))
 dec=np.array(dec);truth=np.array(truth);wrong=dec!=truth;longest=0;run=0
 for error in wrong:run=run+1 if error else 0;longest=max(longest,run)
 delays=[];censored=0
 transitions=np.where(np.diff(truth)!=0)[0]+1
 for start in transitions:
  end=next((j for j in transitions if j>start),len(truth));matches=np.where(dec[start:end]==truth[start])[0]
  if len(matches):delays.append(int(matches[0]))
  else:censored+=1
 return dict(error=float(wrong.mean()),longest_wrong_run=longest,delay_sum=sum(delays),resolved=len(delays),censored=censored,transitions=len(transitions))
def main():
 rows=[]
 for split,seeds in [('development',[111,222,333]),('held_variants',[444,555,666])]:
  for a,t,k,e in itertools.product([.2,.4,.5,.65,.8,1.],[.3,.5,.7],[1,2,3],['hybrid','binary']):
   for noise in [0.,.1,.2]:
    rr=[detail(scene,a,t,k,e) for seed in seeds for scene in s.scenarios(seed) if scene['noise']==noise]
    n=sum(r['resolved'] for r in rr)
    rows.append(dict(split=split,alpha=a,threshold=t,streak=k,encoding=e,noise=noise,
      mean_error=float(np.mean([r['error'] for r in rr])),mean_longest_wrong_run=float(np.mean([r['longest_wrong_run'] for r in rr])),
      response_delay_valid_updates=sum(r['delay_sum'] for r in rr)/n if n else None,resolved_transitions=n,
      censored_transitions=sum(r['censored'] for r in rr)))
 (OUT/'results/state_response_sensitivity.json').write_text(json.dumps({'rows':rows,'delay_definition':'first correct decision after constructed regime change, measured in accepted updates; censored separately','scope':'engineering target only'},ensure_ascii=False,indent=2),encoding='utf-8')
 print('response groups',len(rows))
if __name__=='__main__':main()
