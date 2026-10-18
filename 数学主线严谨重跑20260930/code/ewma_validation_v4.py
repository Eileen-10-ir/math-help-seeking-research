"""Registered E11 engineering selection, E12 nested threshold/two-point sensitivity."""
from common import *
from sklearn.model_selection import StratifiedKFold
from controlled_text import calibrated
from evidence_runtime import assess,behavioral_evidence
from collections import defaultdict

LAMBDAS=[.2,.35,.5,.65,.8,1.]
RULE_VERSION='math-cloudedge-v4-20260930'
PROTOCOL='云边机制与EWMA修正协议_v4.md'
SCENARIOS={'sudden_high':['low']*8+['high']*24,'persistent_low':['low']*32,'recovery':['high']*8+['low']*24,'ack_after_high':['high']*4+['ack']*6+['high']*22}

def observation(text,scores):
 g=assess(text,scores);cue=behavioral_evidence(text) if g['observed_event']=='question' else None
 eligible=g['eligible']
 if cue:eligible=not cue.get('conflict',False)
 return eligible,(float(cue['level']=='high') if cue and eligible else float(scores['high'])),(cue['level'] if cue and eligible else g['candidate_level'])

def engineering():
 rows=[]
 for split,noises,persists in [('development',[.1,.25],[.75]),('heldout',[.05,.15,.30],[.60,.85])]:
  for regime in ['independent','bursts']:
   for noise in noises:
    for persist in ([.75] if regime=='independent' else persists):
     for name,seq in SCENARIOS.items():
      for rep in range(400):
       rng=np.random.default_rng(202611000+rep+1000*list(SCENARIOS).index(name)+10000*int(noise*100)+100000*(regime=='bursts')+1000000*(split=='heldout')+100*int(persist*100))
       err=bool(rng.random()<noise) if regime=='bursts' else False;observations=[]
       for event in seq:
        err=rng.random()<noise if regime=='independent' else rng.random()<(persist if err else noise*(1-persist)/(1-noise))
        label=event if event=='ack' or not err else str(rng.choice([k for k in LAB if k!=event]));weak=rng.random()<.15
        p={k:(.4 if k==label else .3) if weak else (.8 if k==label else .1) for k in LAB}
        observations.append((event,p['high'] if event!='ack' else None,not weak and event!='ack'))
       for lam in LAMBDAS:
        state=None;truth=None;sse=[];risk=[];known=0;false=[]
        for event,x,valid in observations:
         if event!='ack':truth=float(event=='high')
         if valid:state=x if state is None else lam*x+(1-lam)*state
         risk.append(state)
         if event!='ack' and state is not None:
          sse.append((state-truth)**2);known+=1
          if event=='low':false.append(state>=.5)
        delay=next((i-8 for i in range(8,32) if risk[i] is not None and risk[i]>=.5),24) if name=='sudden_high' else None
        rows.append({'split':split,'regime':regime,'noise':noise,'persistence':persist,'scenario':name,'rep':rep,'lambda':lam,
         'filter_mse':float(np.mean(sse)),'known_fraction':known/sum(x!='ack' for x in seq),'high_threshold_for_diagnostic_only':.5,
         'low_time_false_high':float(np.mean(false)) if false else None,'sudden_high_delay':delay,
         'ack_drift':risk[9]-risk[3] if name=='ack_after_high' and risk[3] is not None else None})
 summary=[]
 for split in ['development','heldout']:
  for lam in LAMBDAS:
   rr=[r for r in rows if r['split']==split and r['lambda']==lam];out={'split':split,'lambda':lam,'replicate_config_rows':len(rr)}
   for metric in ['filter_mse','known_fraction','low_time_false_high','sudden_high_delay','ack_drift']:
    # Each configuration has exactly 400 reps; equal row weighting equals equal configuration weighting.
    group=defaultdict(list)
    for r in rr:
     if r[metric] is not None:group[r['regime'],r['noise'],r['persistence'],r['scenario']].append(r[metric])
    means=[np.mean(a) for a in group.values()];out[metric+'_mean']=float(np.mean(means)) if means else None
    out[metric+'_mcse']=float(np.sqrt(sum(np.var(a,ddof=1)/len(a) for a in group.values()))/len(group)) if group else None
   stable=[r['low_time_false_high'] for r in rr if r['scenario']=='persistent_low']
   out['persistent_low_false_high_mean']=float(np.mean(stable))
   summary.append(out)
 chosen=min([r for r in summary if r['split']=='development'],key=lambda r:(r['filter_mse_mean'],r['lambda']))['lambda']
 write_csv('results/E11_ewma_replicates.csv',rows);write_csv('results/E11_ewma_summary.csv',summary)
 write_json('results/E11_metadata.json',{'protocol_sha256':sha(OUT/PROTOCOL),'candidates':LAMBDAS,'selected_lambda':chosen,
  'selection':'minimum development equal-configuration filtering MSE; heldout not used','source':'constructed binary high indicator and E5-style noisy scores',
  'is_real_student_validation':False,'replicates_per_configuration':400,'threshold_.5':'only engineering diagnostic; deployment threshold separately nested-calibrated',
  'limitations':['Engineering optimum conditional on generator and equal scenario weighting','Not forecasting MSE','Not latent psychology parameter estimation']})
 print('E11 selected lambda from development only:',chosen,flush=True)
 return chosen

def threshold(y,p):
 rr=[];y=np.asarray(y)=='high'
 for t in [.3,.4,.5,.6,.7,.8]:
  pred=np.asarray(p)>=t;bac=.5*(pred[y].mean()+(~pred[~y]).mean());rr.append({'threshold':t,'balanced_accuracy':float(bac)})
 return max(rr,key=lambda r:(r['balanced_accuracy'],r['threshold']))['threshold'],rr

def inner_scores(training,seed):
 y=np.array([r['final_level'] for r in training]);p=np.zeros(len(training));splits=[]
 for f,(tr,te) in enumerate(StratifiedKFold(3,shuffle=True,random_state=seed).split(np.zeros(len(y)),y)):
  realtrain=[training[i] for i in tr];param,cal=calibrated(realtrain,seed*100+f);m=Classifier().fit([r['prompt_text'] for r in realtrain+param],[r['final_level'] for r in realtrain+param]);p[te]=m.probs([training[i]['prompt_text'] for i in te])[:,0]
  splits.append({'training_ids':[training[i]['sample_id'] for i in tr],'validation_ids':[training[i]['sample_id'] for i in te],'parameter_calibration_ids':cal['calibration_ids']})
 return p,splits

def real_sensitivity(chosen):
 real,_,_,r3=load();by1={r['sample_id']:r for r in real};pair={r['pair_id']:r for r in r3}
 allpred=list(csv.DictReader((OUT/'results/recognition_predictions.csv').open(encoding='utf-8-sig')))
 pred={(r['experiment'],r['variant'],int(r['seed']),r['sample_id']):r for r in allpred};audits=[];rows=[]
 for split in json.loads((OUT/'data/E2_family_calibration_splits.json').read_text(encoding='utf-8')):
  seed,fold=split['seed'],split['fold'];training=[by1[i] for i in split['training_real_ids']];p,inside=inner_scores(training,seed*100+fold)
  t,candidates=threshold([r['final_level'] for r in training],p);audits.append({'seed':seed,'fold':fold,'training_ids':split['training_real_ids'],'heldout_ids':split['heldout_real_ids'],'chosen_threshold':t,'candidates':candidates,'inner_splits':inside,
   'inner_oof_high_scores':[{'sample_id':r['sample_id'],'p_high':float(v)} for r,v in zip(training,p)]})
  for sid in split['heldout_real_ids']:
   a=by1[sid];b=pair[sid];q1=pred['E2_student_crossfit','parameter_real',seed,sid];q3=pred['E3_r3_crossfit','r3_only',seed,b['sample_id']]
   p1={k:float(q1['p_'+k]) for k in LAB};p3={k:float(q3['p_'+k]) for k in LAB+[ACK]};ok1,x1,l1=observation(a['prompt_text'],p1);ok3,x3,l3=observation(b['prompt_text'],p3)
   for lam in LAMBDAS:
    d1=x1 if ok1 else None;d3=(x3 if d1 is None else lam*x3+(1-lam)*d1) if ok3 else d1
    history=ok3 and l3!='high' and d3 is not None and d3>=t
    route=('high' if l3=='high' or history else l3) if ok3 else 'verify'
    rows.append({'student_id':a['student_id'],'seed':seed,'fold':fold,'lambda':lam,'threshold':t,'r1_id':sid,'r3_id':b['sample_id'],
     'r1_eligible':ok1,'r3_eligible':ok3,'r1_model_p_high':p1['high'],'r3_model_p_high':p3['high'],'x1':x1 if ok1 else None,'x3':x3 if ok3 else None,'state_before_R3':d1,'state_after_R3':d3,
     'history_high_protection':history,'route_grade':route,'r3_annotation_for_evaluation_only':b['final_level'],
     'note':'two-point historical sensitivity, not actual new support effect or future prediction'})
 # Deployment calibration uses all R1 OOF means, one score per student (not 235 independent people).
 pfull=[np.mean([float(pred['E2_student_crossfit','parameter_real',s,r['sample_id']]['p_high']) for s in SEEDS]) for r in real]
 deployed,candidates=threshold([r['final_level'] for r in real],pfull)
 write_json('data/E12_threshold_inner_audit.json',audits);write_csv('results/E12_real_two_point_sensitivity.csv',rows)
 summary=[]
 for lam in LAMBDAS:
  rr=[r for r in rows if r['lambda']==lam];valid=[r for r in rr if r['r3_eligible']];ack=[r for r in rr if r['r3_annotation_for_evaluation_only']==ACK]
  summary.append({'lambda':lam,'student_repeats':235,'unique_students':47,'r3_update_fraction':len(valid)/235,'history_high_protection_fraction':sum(r['history_high_protection'] for r in rr)/235,
   'route_matches_annotation_all':sum(r['route_grade']==r['r3_annotation_for_evaluation_only'] for r in rr)/235,
   'accepted_route_accuracy':np.mean([r['route_grade']==r['r3_annotation_for_evaluation_only'] for r in valid]) if valid else None,
   'ACK_update_count':sum(r['r3_eligible'] for r in ack),'mean_state_after_R3':np.mean([r['state_after_R3'] for r in rr if r['state_after_R3'] is not None])})
 write_csv('results/E12_real_sensitivity_summary.csv',summary)
 for (sid,seed),rr in __import__('itertools').groupby(sorted(rows,key=lambda r:(r['r1_id'],r['seed'])),lambda r:(r['r1_id'],r['seed'])):
  values=[r['state_before_R3'] for r in rr];assert all(v==values[0] for v in values)
 write_json('data/runtime_state_config_v4.json',{'rule_version':RULE_VERSION,'risk_proxy':'model_raw_p_high_or_explicit_rule_binary','lambda':chosen,
  'lambda_selection_source':'E11 development constructed-signal MSE; engineering only','lambda_half_life_in_valid_updates':float(np.log(.5)/np.log(1-chosen)) if chosen<1 else 0.,
  'history_high_threshold':deployed,'threshold_source':'existing R1 4-fold x 5 OOF scores averaged per student; high-v-rest balanced accuracy; development calibration only',
  'threshold_candidates':candidates,'cutoff':.6,'protocol_sha256':sha(OUT/PROTOCOL),'scientific_status':'no real longitudinal or psychometric coefficient validation',
  'legacy_anchors_origin':'hardcoded latent means in 7月数据/参数化标定/calibrate_parametric.py; not data-estimated; excluded from v4 state'})
 write_json('results/E12_metadata.json',{'protocol_sha256':sha(OUT/PROTOCOL),'unique_students':47,'R1_R3_points_per_student':2,'outer_repeats':5,'inner_splits':3,
  'lambda_not_identified_for_next_turn_forecasting':True,'selection_used_R3_labels':False,'threshold_calibration':'nested R1 only; full R1 OOF for runtime','new_real_students':0})
 print('E12 nested threshold audits and all real two-point sensitivity outputs saved.',flush=True)
if __name__=='__main__':real_sensitivity(engineering())
