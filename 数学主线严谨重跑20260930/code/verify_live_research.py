"""Audit supplement splits, denominators, replay semantics, versions and provenance."""
from common import *
from collections import defaultdict
from evidence_runtime import RULE_VERSION
def read(p):return json.loads((OUT/p).read_text(encoding='utf-8'))
def rows(p):return list(csv.DictReader((OUT/p).open(encoding='utf-8-sig')))
def run():
 checks={};real,_,_,r3=load();ids={r['sample_id'] for r in real}
 splits=read('data/E7_calibration_splits.json');held=defaultdict(list)
 for r in splits:
  tr=set(r['v2_calibration']['calibration_ids']);te=set(r['heldout_ids']);assert not tr&te and tr|te==ids
  held[r['seed']].extend(te)
 assert len(splits)==20 and all(len(x)==47 and set(x)==ids for x in held.values())
 checks['E7_fold_calibration_and_complete_student_holdouts']=True
 train=rows('data/E7_v2训练候选.csv');test=rows('data/E7_v2受控留出候选.csv');assert (len(train),len(test))==(148,50)
 for k in ['template_family','task_id','feature_key']:assert not {r[k] for r in train}&{r[k] for r in test}
 checks['E7_template_task_masked_input_isolation']=True
 original=rows('results/recognition_predictions.csv');lookup={(r['variant'],r['seed'],r['sample_id']):r for r in original if r['experiment']=='E2_student_crossfit'}
 pred=rows('results/E7_predictions.csv');group=defaultdict(list);summary=read('results/E7_summary.json')
 for r in pred:
  p=np.array([float(r['p_'+k]) for k in LAB]);assert np.isfinite(p).all() and (p>=0).all() and np.isclose(sum(p),1)
  assert r['prediction']==LAB[p.argmax()];group[r['variant'],r['seed']].append(r)
  if r['variant'] in ['v1_parameter','real_only']:
   old=lookup['parameter_primary' if r['variant']=='v1_parameter' else 'real_only',r['seed'],r['sample_id']]
   assert old['fold']==r['fold'] and np.allclose(p,[float(old['p_'+k]) for k in LAB],atol=1e-12)
 for v in summary:
  m=[]
  for seed in SEEDS:
   rr=group[v,str(seed)];assert len(rr)==47 and {r['sample_id'] for r in rr}==ids
   m.append(metrics([r['truth'] for r in rr],[[float(r['p_'+k]) for k in LAB] for r in rr])['macro_f1'])
  assert np.isclose(np.mean(m),summary[v]['macro_f1']['mean'])
 checks['E7_old_controls_identical_and_metrics_recomputed']=True
 details=rows('results/E8_coverage_predictions.csv');repeat=rows('results/E8_coverage_repeat_metrics.csv');e8group=defaultdict(list)
 for r in details:e8group[r['stage'],r['policy'],r['cutoff'],r['seed']].append(r)
 for r in repeat:
  rr=e8group[r['stage'],r['policy'],r['cutoff'],r['seed']];accepted=[x for x in rr if x['eligible']=='True'];assert len(rr)==47 and len({x['sample_id'] for x in rr})==47
  assert int(r['accepted_n'])==len(accepted) and np.isclose(float(r['coverage']),len(accepted)/47)
  if accepted:assert np.isclose(float(r['accepted_accuracy_all']),np.mean([x['truth']==x['model_prediction'] for x in accepted]))
  else:assert r['accepted_accuracy_all']==''
 checks['E8_rejection_denominators_and_empty_accuracy_not_perfect']=True
 e10=rows('results/E10_rule_predictions.csv');e10repeat=rows('results/E10_rule_repeat_metrics.csv');e10summary=rows('results/E10_rule_summary.csv');g=defaultdict(list)
 for r in e10:g[r['policy'],r['stage'],r['seed']].append(r)
 for r in e10repeat:
  rr=g[r['policy'],r['stage'],r['seed']];accepted=[x for x in rr if x['eligible']=='True'];high=[x for x in rr if x['truth']=='high'];assert len(rr)==47 and len({x['sample_id'] for x in rr})==47
  assert np.isclose(float(r['coverage']),len(accepted)/47)
  if accepted:assert np.isclose(float(r['accepted_accuracy']),np.mean([x['truth']==x['current_behavior_prediction'] for x in accepted]))
  else:assert not r['accepted_accuracy']
  assert np.isclose(float(r['high_correct_rate_all_high']),sum(x['eligible']=='True' and x['current_behavior_prediction']=='high' for x in high)/len(high))
 for r in e10summary:
  rr=[x for x in e10repeat if x['policy']==r['policy'] and x['stage']==r['stage']]
  assert len(rr)==5
  for k in ['coverage','accepted_accuracy','high_correct_rate_all_high','rules_fraction_all']:
   values=[float(x[k]) for x in rr if x[k]]
   assert np.isclose(float(r[k+'_mean']),np.mean(values))
 checks['E10_coverage_accuracy_high_rates_recomputed']=True
 replay=read('data/E10_真实两点统一回放.json');assert len(replay)==235
 for seed in SEEDS:assert len({r['student_id'] for r in replay if r['seed']==seed})==47
 for r in replay:
  a,b=r['r1_analysis'],r['r3_analysis'];assert b['previous_risk']==a['risk']
  if not b['eligible']:assert b['risk']==a['risk'] and not b['risk_updated']
  assert r['source']=='original_vignette_prompts_with_oof_scores'
  for d in [a,b]:
   assert np.isclose(sum(d['model_scores'].values()),1)
   if d['decision_basis']=='behavior_rule':assert d['current_behavior_level'] in LAB and sum(d['state_update_weights'].values())==1
 checks['E10_47_pairs_not_235_people_and_holds_preserved']=True
 meta=read('results/E10_metadata.json');assert meta['rule_version']==RULE_VERSION and meta['rule_code_sha256']==sha(OUT/'code/evidence_runtime.py')
 assert meta['protocol_sha256']==sha(OUT/'实时行为规则修正协议_v3.md') and meta['truth_is_input'] is False
 checks['E10_rule_protocol_and_code_version_consistent']=True
 e9=rows('results/E9_unified_state_pressure.csv');assert len(e9)==64 and all(int(r['replicates'])==250 for r in e9)
 ack=[r for r in e9 if r['scenario']=='ack_after_high'];assert ack and all(float(r['ack_drift_mean'])==0 for r in ack)
 checks['E9_configuration_count_and_ACK_state_hold']=True
 archive='history/runtime_v3_20260930/'
 card=read(archive+'data/runtime_model_card.json');assert card['rule_version']==RULE_VERSION and card['artifact_sha256']==sha(OUT/(archive+'data/runtime_models_v1.joblib'))
 assert card['snapshot_sha256']==sha(OUT/'data/anonymous_samples_snapshot.json');assert (card['first_train_rows'],card['following_train_rows'])==(138,47)
 checks['runtime_artifact_snapshot_and_rule_match']=True
 http=read(archive+'results/实时HTTP工程检查.json');ui=read(archive+'results/实时前端检查.json');assert http['passed'] and all(http['checks'].values()) and ui['passed']
 assert http['provenance']=='automated_engineering_check' and http['new_real_students']==0 and ui['realStudentCount']==0 and ui['mobileHorizontalOverflow'] is False and not ui['scriptErrors']
 checks['HTTP_browser_and_zero_new_student_provenance']=True
 for path,h in read('data/input_manifest.json')['sources'].items():
  if Path(path).exists():assert sha(path)==h
 checks['original_materials_unchanged']=True
 write_json('results/实时补充一致性检查.json',{'passed':True,'checks':checks,'rule_version':RULE_VERSION,'new_real_students':0,'human_review':'pending'})
 files=['实时闭环与补充实验协议.md','实时行为规则修正协议_v3.md','data/anonymous_samples_snapshot.json',archive+'data/runtime_model_card.json',
   'code/evidence_runtime.py',archive+'code/runtime_server.py','code/parameter_v2.py','code/parameter_v2_experiment.py','code/coverage_evaluation.py','code/behavior_rule_evaluation.py','code/unified_state_pressure.py',
   'results/E7_summary.json','results/E8_coverage_summary.csv','results/E9_unified_state_pressure.csv','results/E10_rule_summary.csv']
 write_json('data/live_research_manifest.json',{'date':'2026-09-30','scope':'development supplement; not independent preregistration','rule_version':RULE_VERSION,
  'new_real_students':0,'paid_calls':0,'human_review':'pending','files':{p:sha(OUT/p) for p in files}})
 print(f'{len(checks)} supplementary audit checks passed.')
if __name__=='__main__':run()
