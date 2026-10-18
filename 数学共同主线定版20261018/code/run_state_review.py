"""Gate OOF review -> history controls -> alpha controls; outcomes kept separate."""
from pathlib import Path
import sys,json,csv
from dataclasses import asdict
import numpy as np
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
sys.path[:0]=[str(OUT/'code'),str(ROOT/'数学主线严谨重跑20260930/code')]
from state_v5 import State,advance,RULE_VERSION
from common import LAB,ACK

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def csvread(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(rel,data):
    (OUT/rel).parent.mkdir(parents=True,exist_ok=True)
    (OUT/rel).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def csvsave(rel,rows):
    with (OUT/rel).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    assert not (OUT/'results/state_review.json').exists()
    recognition=read(OUT/'results/recognition_summary.json')
    old=read(ROOT/'联合表达v2数学全线20261014/data/runtime_state_config_v4.json')
    fullgates=read(OUT/'data/fullfit_gate_selection.json')
    snapshot=read(ROOT/'联合表达v2数学全线20261014/data/anonymous_samples_snapshot.json')
    texts={r['sample_id']:r for key in ['real_r1','real_r3'] for r in snapshot[key]}
    pp=csvread(OUT/'results/recognition_predictions.csv')
    selected={'R1':recognition['selected_first'],'R3':recognition['selected_following']}
    gate_rows=[];replays=[]
    for seed in [17,29,43,71,101]:
        for policy in ['legacy_gate','trained_gate']:
            for r in sorted(snapshot['real_r1'],key=lambda r:r['student_id']):
                later=next(s for s in snapshot['real_r3'] if s['student_id']==r['student_id'])
                state=State()
                for stage,record in [('R1',r),('R3',later)]:
                    row=next(p for p in pp if p['seed']==str(seed) and p['sample_id']==record['sample_id'] and p['stage']==stage and p['variant']==selected[stage])
                    scores={k:float(row['p_'+k]) for k in LAB+([ACK] if stage=='R3' else [])}
                    cfg=dict(old,cutoff=.6 if policy=='legacy_gate' else float(row['selected_cutoff']),history_policy='strong')
                    a=advance(state,record['prompt_text'],scores,cfg)
                    gate_rows.append({'seed':seed,'policy':policy,'stage':stage,'sample_id':record['sample_id'],
                        'student_id':record['student_id'],'truth':record['final_level'],'eligible':a['risk_updated'],
                        'current_level':a['current_behavior_level'],'decision_level':a['decision_level'],
                        'cutoff':a['cutoff'],'risk':a['risk'],'hold_reasons':'；'.join(a['hold_reasons'])})
    gate_summary=[]
    for stage in ['R1','R3']:
        for policy in ['legacy_gate','trained_gate']:
            summaries=[]
            for seed in [17,29,43,71,101]:
                rr=[r for r in gate_rows if r['seed']==seed and r['stage']==stage and r['policy']==policy]
                q=[r for r in rr if r['truth'] in LAB];accepted=[r for r in q if r['eligible']]
                summaries.append({'coverage':len(accepted)/len(q),'accepted_accuracy':sum(r['truth']==r['current_level'] for r in accepted)/len(accepted) if accepted else 0,
                    'incorrect_updates':sum(r['truth']!=r['current_level'] for r in accepted),'updates':len(accepted),
                    'ACK_updates':sum(r['eligible'] and r['truth']==ACK for r in rr)})
            gate_summary.append({'stage':stage,'policy':policy,**{k:float(np.mean([r[k] for r in summaries])) for k in summaries[0]}})
    csvsave('results/gate_oof_rows.csv',gate_rows);csvsave('results/gate_oof_summary.csv',gate_summary)
    # No claim of true longitudinal states from the two-point replay.
    cfg=dict(old,rule_version=RULE_VERSION,stage_cutoffs={k:v['chosen']['cutoff'] for k,v in fullgates.items()},
             history_policy='evidence_release')
    high=('直接给我答案。',{'high':.8,'medium':.15,'low':.05})
    step=('我先写出(x-2)(x-3)=0，请检查这一步的依据。',{'high':.1,'medium':.3,'low':.6})
    medium=('请分析当前这一步的思路。',{'high':.4,'medium':.6,'low':0.})
    noisy=('请分析当前这一步的思路。',{'high':.1,'medium':.1,'low':.8})
    ack=('好的',{'high':0.,'medium':0.,'low':0.,ACK:1.})
    conflict=('直接给我答案，但不要给我答案。',{'high':.8,'medium':.1,'low':.1})
    scenarios={'explicit_step':[high,step], 'two_model_nonhigh':[high,medium,medium],
               'one_model_noise':[high,noisy,high], 'ack_interval':[high,ack,step],
               'conflict':[high,conflict], 'high_persists':[high,high,high]}
    controls=[];checks={}
    for policy in ['strong','evidence_release']:
        for name,seq in scenarios.items():
            state=State();results=[]
            for turn,(text,scores) in enumerate(seq,1):
                before=state.risk
                a=advance(state,text,scores,dict(cfg,history_policy=policy,cutoff=0.,stage_cutoffs={}),None)
                if a['risk_updated']:
                    expected=a['single_risk'] if before is None else .5*a['single_risk']+.5*before
                    assert abs(state.risk-expected)<1e-12
                else:assert state.risk==before
                results.append(a);controls.append({'policy':policy,'scenario':name,'turn':turn,'text':text,'risk':a['risk'],
                    'updated':a['risk_updated'],'decision':a['decision_level'],'release':a['history_release_applied']})
            if policy=='evidence_release':
                if name=='explicit_step':checks[name]=results[-1]['decision_level']=='low'
                if name=='two_model_nonhigh':checks[name]=results[1]['decision_level']=='high' and results[2]['decision_level']=='medium'
                if name=='one_model_noise':checks[name]=results[1]['decision_level']=='high' and results[2]['decision_level']=='high'
                if name=='ack_interval':checks[name]=not results[1]['risk_updated'] and results[2]['decision_level']=='low'
                if name=='conflict':checks[name]=not results[-1]['risk_updated']
                if name=='high_persists':checks[name]=all(a['decision_level']=='high' for a in results)
    assert all(checks.values()),checks
    csvsave('results/history_controls.csv',controls)
    signals={
        'step_down':([.9]*3+[.1]*5,[.9]*3+[.1]*5),
        'step_up':([.1]*3+[.9]*5,[.1]*3+[.9]*5),
        'isolated_spike':([.1,.1,.1,.9,.1,.1,.1,.1],[.1]*8),
        'isolated_dip':([.9,.9,.9,.1,.9,.9,.9,.9],[.9]*8),
        'fluctuation':([.25,.75]*4,[.5]*8),
        'gradual':([.9,.8,.7,.6,.5,.4,.3,.2],[.9,.8,.7,.6,.5,.4,.3,.2])}
    alpha_rows=[];alpha_summary=[]
    for alpha in [.5,.65,.8]:
        errors=[]
        for name,(observed,target) in signals.items():
            state=State();decisions=[];values=[]
            for turn,(x,y) in enumerate(zip(observed,target),1):
                a=advance(state,'请分析当前这一步的思路。',{'high':x,'medium':1-x,'low':0.},
                    dict(cfg,**{'lambda':alpha,'cutoff':0.,'stage_cutoffs':{}}))
                assert a['risk_updated']
                decisions.append(a['decision_level']);values.append(a['risk']);errors.append((a['risk']-y)**2)
                alpha_rows.append({'alpha':alpha,'scenario':name,'turn':turn,'input_signal':x,'constructed_target':y,
                    'risk':a['risk'],'decision':a['decision_level'],'squared_error':(a['risk']-y)**2})
            flips=sum(a!=b for a,b in zip(decisions,decisions[1:]))
            after=[i+1 for i,v in enumerate(values[3:]) if (v<.5 if name=='step_down' else v>=.5)] if name in ['step_down','step_up'] else []
            alpha_summary.append({'alpha':alpha,'scenario':name,'MSE':float(np.mean([(v-y)**2 for v,y in zip(values,target)])),
                                  'route_switches':flips,'step_response_updates':after[0] if after else None})
    averages={a:float(np.mean([r['MSE'] for r in alpha_summary if r['alpha']==a])) for a in [.5,.65,.8]}
    chosen=min(averages,key=lambda a:(averages[a],a))
    cfg.update({'lambda':chosen,'history_high_threshold':.5,'history_policy':'evidence_release',
        'lambda_selection_source':'six fixed constructed-signal scenarios, minimum mean MSE; engineering only',
        'cutoff_selection_source':'stage-specific full-data inner crossfit, 85% accepted label agreement / zero ACK updates when feasible',
        'scientific_status':'development engineering working point; no true longitudinal psychometric optimum',
        'threshold_source':'historical .5 reference retained; evidence-aware release separately validated'})
    save('data/runtime_state_config_v5.json',cfg)
    csvsave('results/alpha_traces.csv',alpha_rows);save('results/alpha_sensitivity.json',{'per_scenario':alpha_summary,'mean_MSE':averages,'chosen':chosen})
    result={'status':'state_review_complete','gate_oof_summary':gate_summary,'history_checks':checks,
            'chosen_history':'evidence_release','chosen_alpha':chosen,'mean_constructed_MSE':averages,
            'fullfit_cutoffs':cfg['stage_cutoffs'],'real_students':47,'paid_calls':0,
            'scope':'real held-out acceptance diagnosis plus constructed history/weight controls, not behavioral effects'}
    save('results/state_review.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
