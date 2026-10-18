from common import *
import sys
from math_state import State,update,ANCHORS
def state_pressure():
    scenarios={'sudden_high':['low']*8+['high']*24,'persistent_low':['low']*32,
               'recovery':['high']*8+['low']*24,'ack_after_high':['high']*4+['ack']*6+['high']*22}
    result=[];example=[]
    for regime in ['independent','bursts']:
     for noise in [.1,.25]:
      for name,seq in scenarios.items():
       observations=[]
       for rep in range(250):
        rng=np.random.default_rng(20261000+rep+1000*list(scenarios).index(name)+10000*int(noise*100)+100000*(regime=='bursts'))
        # In bursts, stationary marginal error probability=noise; P(error persists)=.75.
        err=bool(rng.random()<noise) if regime=='bursts' else False;obs=[]
        for event in seq:
          if regime=='independent':err=rng.random()<noise
          else:err=rng.random() < (.75 if err else noise*.25/(1-noise))
          label=event if event=='ack' or not err else str(rng.choice([k for k in LAB if k!=event]))
          uncertain=rng.random()<.15
          p={k:(.4 if k==label else .3) if uncertain else (.8 if k==label else .1) for k in LAB}
          obs.append((event,label,p))
        observations.append(obs)
       for mu in [.2,.5,.8,1.]:
        for policy in ['current','ewma','joint','joint_gate']:
         values=[]
         for rep,obs in enumerate(observations):
          risks=[];decisions=[];review=0;state=State();risk=None
          for event,label,p in obs:
           if policy=='joint_gate':
            d=update(state,'好的' if event=='ack' else '数学任务求助',None if event=='ack' else p,followup=event=='ack',mu=mu)
            risk=d['risk'];decision=d['decision_level'];review+=int(d['route'] in ['edge_verify','hybrid_review'])
           else:
            pp={k:float(k=='low') for k in LAB} if event=='ack' else p
            single=sum(pp[k]*ANCHORS[k] for k in LAB);level=max(pp,key=pp.get)
            risk=single if risk is None else mu*single+(1-mu)*risk
            high=single>=.65 or level=='high' if policy=='current' else (risk>=.65 if policy=='ewma' else (level=='high' or single>=.65 or risk>=.65 and single>=.52))
            decision='high' if high else ('medium' if (single if policy=='current' else risk)>=.4 else 'low')
           risks.append(single if policy=='current' else risk);decisions.append(decision)
          lows=[i for i,x in enumerate(seq) if x=='low'];highs=[i for i,x in enumerate(seq) if x=='high']
          values.append({'high_response':sum(decisions[i]=='high' for i in highs)/len(highs) if highs else None,
                         'false_high':sum(decisions[i]=='high' for i in lows)/len(lows) if lows else None,
                         'delay':next((i-8 for i in range(8,32) if decisions[i]=='high'),24) if name=='sudden_high' else None,
                         'ack_drift':risks[9]-risks[3] if name=='ack_after_high' else None,'review_fraction':review/len(seq)})
          if rep==0 and name=='ack_after_high' and regime=='bursts' and noise==.25 and mu==.5:
            example.extend({'policy':policy,'turn':i+1,'event':seq[i],'risk':v,'decision':decisions[i]} for i,v in enumerate(risks))
         r={'regime':regime,'noise':noise,'scenario':name,'mu':mu,'policy':policy,'replicates':250}
         for metric in values[0]:
           a=np.array([v[metric] for v in values if v[metric] is not None])
           r[metric+'_mean']=float(a.mean()) if len(a) else None
           r[metric+'_mcse']=float(a.std(ddof=1)/np.sqrt(len(a))) if len(a)>1 else None
         result.append(r)
    write_csv('results/E5_correlated_pressure.csv',result);write_csv('results/E5_example_trajectory.csv',example)
    write_json('results/E5_metadata.json',{'configurations':len(result),'replicates':250,'low_confidence_rate_assumption':.15,
      'error_burst_persistence':.75,'limits':['标签级工程压力测试，非学生语言轨迹','澄清包含ACK追问与低置信度核实','高等级决策与实际云调用不同','Monte Carlo SE只反映模拟重复误差']})
    print('E5 correlated-error and uncertainty pressure complete.',flush=True)
def action_simulation():
    real,eedi,llm,r3=load();by={r['sample_id']:r for r in real}
    counts=np.array([[sum(by[r['pair_id']]['final_level']==a and r['final_level']==b for r in r3) for b in LAB+[ACK]] for a in LAB])
    initial=np.array([sum(r['final_level']==a for r in real)/47 for a in LAB]);summary=[];trajectory=[];all_draws=[]
    for scenario in ['zero_extra_effect','uniform_benefit','matched_benefit','mismatched_harm']:
     draws=[]
     for rep in range(1000):
      rng=np.random.default_rng(20260930+rep);n=1000
      P=np.vstack([rng.dirichlet(row+.5) for row in counts]);init=np.searchsorted(initial.cumsum(),rng.random(n))
      u=rng.random((7,n));noise=rng.random((8,n));wrong=rng.integers(1,3,(8,n));hist={}
      for policy in ['no_added_action','uniform_support','graded_support']:
       state=init.copy();ack=np.zeros(n,bool);series=[state.copy()];acts=[]
       for t in range(7):
        observed=(state+wrong[t])%3;observed=np.where(noise[t]<.1,observed,state)
        target=np.ones(n,int) if policy=='uniform_support' else observed
        effective=np.zeros(n)
        if policy!='no_added_action':
          if scenario=='uniform_benefit':effective[:]=.04
          elif scenario=='matched_benefit':effective=np.where(target==state,.06,0.)
          elif scenario=='mismatched_harm':effective=np.where(target==state,.04,-.06)
        q=P[state].copy()
        # Positive engineering response transfers mass toward lower dependency; negative toward higher.
        for level in range(3):
          ix=np.where(state==level)[0];positive=ix[effective[ix]>0];negative=ix[effective[ix]<0]
          if level<2:
            shift=np.minimum(q[positive,level],effective[positive]);q[positive,level]-=shift;q[positive,level+1]+=shift
          if level>0:
            shift=np.minimum(q[negative,level],-effective[negative]);q[negative,level]-=shift;q[negative,level-1]+=shift
        assert np.allclose(q.sum(axis=1),1) and (q>=0).all()
        outcome=(u[t,:,None]>q.cumsum(axis=1)).sum(axis=1)
        state=np.where(outcome==3,state,outcome);series.append(state.copy());acts.append(effective.copy())
       hist[policy]=np.array(series)
       draws.append({'scenario':scenario,'policy':policy,'rep':rep,'end_low':float(np.mean(state==2)),'end_high':float(np.mean(state==0)),
                     'average_engineering_risk':float(np.mean(np.array([.78,.52,.28])[state]))})
       if rep==0:trajectory.extend({'scenario':scenario,'policy':policy,'turn':t+1,'low_fraction':float(np.mean(s==2)),'high_fraction':float(np.mean(s==0))} for t,s in enumerate(series))
      if scenario=='zero_extra_effect':assert all(np.array_equal(hist['no_added_action'],hist[p]) for p in hist)
     all_draws.extend(draws)
     for policy in ['no_added_action','uniform_support','graded_support']:
      rr=[r for r in draws if r['policy']==policy];base=[r for r in draws if r['policy']=='no_added_action']
      delta=np.array([r['end_low']-b['end_low'] for r,b in zip(rr,base)])
      summary.append({'scenario':scenario,'policy':policy,'replicates':1000,'users_per_replicate':1000,
                      'end_low_mean':float(np.mean([r['end_low'] for r in rr])),'end_high_mean':float(np.mean([r['end_high'] for r in rr])),
                      'low_difference_vs_baseline_mean':float(delta.mean()),'low_difference_mcse':float(delta.std(ddof=1)/np.sqrt(len(delta))),
                      'low_difference_scenario95':np.quantile(delta,[.025,.975]).tolist()})
    write_csv('results/E6_replicate_endpoints.csv',all_draws)
    write_csv('results/E6_action_scenarios.csv',summary);write_csv('results/E6_trajectories.csv',trajectory)
    write_json('results/E6_metadata.json',{'observed_mixed_guidance_counts':counts.tolist(),'prior':'Dirichlet(.5,.5,.5,.5)',
      'replicates':1000,'simulated_users_per_replicate':1000,'turns':8,'action_noise':.1,
      'parameters':{'uniform_benefit':.04,'matched_benefit':.06,'mismatched_harm':-.06},
      'null_assertion':'zero-extra-effect policies produce exactly equal trajectories under common random numbers',
      'limits':['动作响应参数为人为假设，非真实因果估计','基底是历史混合引导下观察转移，未加动作不等于无引导自然转移',
                '模拟潜状态只是工程定义','95区间包含转移抽样与Monte Carlo变异，不是教学效应置信区间','未用语义模型模拟学生或真实云边调用']})
    print('E6 action enters transition; zero-effect invariance verified; conditional scenarios complete.',flush=True)
if __name__=='__main__':
 if '--action-only' not in sys.argv:state_pressure()
 if '--state-only' not in sys.argv:action_simulation()
