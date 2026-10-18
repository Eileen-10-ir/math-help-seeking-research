"""E9 adds one policy to the identical E5 observation generator."""
from common import *
from evidence_runtime import State,advance
def run():
 scenarios={'sudden_high':['low']*8+['high']*24,'persistent_low':['low']*32,'recovery':['high']*8+['low']*24,'ack_after_high':['high']*4+['ack']*6+['high']*22}
 rows=[]
 for regime in ['independent','bursts']:
  for noise in [.1,.25]:
   for name,seq in scenarios.items():
    observations=[]
    for rep in range(250):
     rng=np.random.default_rng(20261000+rep+1000*list(scenarios).index(name)+10000*int(noise*100)+100000*(regime=='bursts'))
     err=bool(rng.random()<noise) if regime=='bursts' else False;obs=[]
     for event in seq:
      err=rng.random()<noise if regime=='independent' else rng.random()<(.75 if err else noise*.25/(1-noise))
      level=event if event=='ack' or not err else str(rng.choice([k for k in LAB if k!=event]));uncertain=rng.random()<.15
      scores={k:(.4 if k==level else .3) if uncertain else (.8 if k==level else .1) for k in LAB}
      if event=='ack':scores={**{k:0. for k in LAB},ACK:1.}
      obs.append((event,scores))
     observations.append(obs)
    for mu in [.2,.5,.8,1.]:
     values=[]
     for rep,obs in enumerate(observations):
      state=State();risks=[];decisions=[];reviews=0;known=[]
      for event,p in obs:
       d=advance(state,'好的' if event=='ack' else '数学任务求助',p,mu=mu,behavior_rules=False);risks.append(state.risk);decisions.append(d['decision_level']);reviews+=int(not d['eligible']);known.append(state.risk is not None)
      highs=[i for i,x in enumerate(seq) if x=='high'];lows=[i for i,x in enumerate(seq) if x=='low']
      values.append({'high_response':sum(decisions[i]=='high' for i in highs)/len(highs) if highs else None,
       'false_high':sum(decisions[i]=='high' for i in lows)/len(lows) if lows else None,
       'delay':next((i-8 for i in range(8,32) if decisions[i]=='high'),24) if name=='sudden_high' else None,
       'ack_drift':risks[9]-risks[3] if name=='ack_after_high' and risks[3] is not None else None,
       'review_fraction':reviews/32,'state_known_fraction':sum(known)/32})
     row={'regime':regime,'noise':noise,'scenario':name,'mu':mu,'policy':'joint_events_confidence','replicates':250}
     for key in values[0]:
      a=np.array([v[key] for v in values if v[key] is not None]);row[key+'_mean']=float(a.mean()) if len(a) else None;row[key+'_mcse']=float(a.std(ddof=1)/np.sqrt(len(a))) if len(a)>1 else None
     rows.append(row)
 write_csv('results/E9_unified_state_pressure.csv',rows)
 write_json('results/E9_metadata.json',{'configurations':64,'replicates':250,'generator':'identical to E5 including RNG draw order; ACK ignored scores replaced by valid four-class point mass','extra_policy':'event + confidence hold, cutoff=.6',
    'limits':['Engineering labels, not real students','Unknown is never encoded as low','Review is not a high or cloud decision','Delay includes 24 for no high decision','MCSE is simulation repetition error only']})
 print('E9 unified gate 64 configurations finished.')
if __name__=='__main__':run()
