"""E10 post-E8 registered retrospective hybrid-rule evaluation and paired replay."""
from common import *
from evidence_runtime import assess,advance,behavioral_evidence,State,RULE_VERSION
def run():
 real,eedi,llm,r3=load();original=list(csv.DictReader((OUT/'results/recognition_predictions.csv').open(encoding='utf-8-sig')))
 by={(r['experiment'],r['variant'],int(r['seed']),r['sample_id']):r for r in original}
 rows=[];summaries=[];replays=[]
 def get_scores(r,seed,stage):
  exp,var,labels=('E2_student_crossfit','parameter_real',LAB) if stage=='R1' else ('E3_r3_crossfit','r3_only',LAB+[ACK])
  rr=by[exp,var,seed,r['sample_id']];return {k:float(rr['p_'+k]) for k in labels}
 for policy in ['events_confidence_v2','events_only','behavior_hybrid_v3']:
  for seed in SEEDS:
   for stage,data in [('R1',real),('R3',r3)]:
    current=[]
    for r in data:
     scores=get_scores(r,seed,stage);state=State()
     if policy=='behavior_hybrid_v3':
      decision=advance(state,r['prompt_text'],scores);eligible=decision['eligible'];pred=decision['current_behavior_level'];basis=decision['decision_basis'];review=decision['review_required']
     else:
      gate=assess(r['prompt_text'],scores,.6,events=True,confidence=policy!='events_only');eligible=gate['eligible'];pred=gate['candidate_level'] if eligible else None;basis='model' if eligible else 'hold';review=False
     row={'policy':policy,'seed':seed,'stage':stage,'sample_id':r['sample_id'],'student_id':r['student_id'],'truth':r['final_level'],
       'eligible':eligible,'current_behavior_prediction':pred,'decision_basis':basis,'review_flag':review,'text':r['prompt_text'],
       'rule_matches':json.dumps(behavioral_evidence(r['prompt_text']),ensure_ascii=False)}
     rows.append(row);current.append(row)
    accepted=[r for r in current if r['eligible']];high=[r for r in current if r['truth']=='high'];ack=[r for r in current if r['truth']==ACK]
    def frac(group,p):return sum(p(r) for r in group)/len(group) if group else None
    summaries.append({'policy':policy,'stage':stage,'seed':seed,'n':47,'coverage':len(accepted)/47,'accepted_accuracy':frac(accepted,lambda r:r['truth']==r['current_behavior_prediction']),
      'high_correct_rate_all_high':frac(high,lambda r:r['eligible'] and r['current_behavior_prediction']=='high'),'high_review_rate':frac(high,lambda r:not r['eligible']),
      'ack_update_rate':frac(ack,lambda r:r['eligible']),'rules_fraction_all':frac(current,lambda r:r['decision_basis']=='behavior_rule'),
      'rule_model_disagreement_fraction_all':frac(current,lambda r:r['review_flag']),
      **{k+'_coverage':frac([r for r in current if r['truth']==k],lambda r:r['eligible']) for k in LAB+[ACK]}})
 # Each student's R1 and R3 use that same repeat's held-out scores; truth never enters advance.
 parent={r['sample_id']:r for r in real}
 for seed in SEEDS:
  for r in r3:
   p=parent[r['pair_id']];state=State();a=advance(state,p['prompt_text'],get_scores(p,seed,'R1'));b=advance(state,r['prompt_text'],get_scores(r,seed,'R3'))
   replays.append({'student_id':r['student_id'],'seed':seed,'source':'original_vignette_prompts_with_oof_scores','r1_id':p['sample_id'],'r3_id':r['sample_id'],
     'r1_text':p['prompt_text'],'r3_text':r['prompt_text'],'r1_analysis':a,'r3_analysis':b,
     'note':'R3 followed historical questionnaire guidance, not current generated support; two-point state replay not educational effect'})
 aggregate=[]
 for policy in ['events_confidence_v2','events_only','behavior_hybrid_v3']:
  for stage in ['R1','R3']:
   rr=[r for r in summaries if r['policy']==policy and r['stage']==stage];row={'policy':policy,'stage':stage,'students_per_repeat':47,'repeats':5}
   for key in rr[0]:
    if key not in ['policy','stage','seed','n']:
     vv=[r[key] for r in rr if r[key] is not None];row[key+'_mean']=float(np.mean(vv)) if vv else None
   aggregate.append(row)
 write_csv('results/E10_rule_predictions.csv',rows);write_csv('results/E10_rule_repeat_metrics.csv',summaries);write_csv('results/E10_rule_summary.csv',aggregate)
 write_json('data/E10_真实两点统一回放.json',replays)
 write_json('results/E10_metadata.json',{'protocol_sha256':sha(OUT/'实时行为规则修正协议_v3.md'),'rule_version':RULE_VERSION,'rule_code_sha256':sha(OUT/'code/evidence_runtime.py'),
  'scope':'Post-E8 retrospective rule development, fixed OOF base scores; no independent external validation','truth_is_input':False,'new_real_students':0,
  'limitations':['Rules authored after historical data exposure','Accepted accuracy can increase by selecting easier examples','Grade semantics require independent human review',
   'Displayed formula does not establish authorship or independent thinking','Two-point replay did not execute new support before historical R3']})
 print('E10 all hybrid comparisons and paired OOF state replays saved.')
if __name__=='__main__':run()
