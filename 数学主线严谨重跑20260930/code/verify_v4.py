"""Recompute results and audit student isolation, provenance, and v4 versions."""
from common import *
from collections import defaultdict
from ewma_validation_v4 import LAMBDAS,threshold,observation,PROTOCOL,RULE_VERSION

def read(p):return json.loads((OUT/p).read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader((OUT/p).open(encoding='utf-8-sig')))
def flag(r,k):return r[k]=='True'
def number(r,k):return None if r[k]=='' else float(r[k])
def same(a,b):assert (a is None and b is None) or (a is not None and b is not None and np.isclose(a,b,rtol=1e-10,atol=1e-12)),(a,b)

def run():
 checks={};cfg=read('data/runtime_state_config_v4.json');card=read('data/runtime_model_card.json');meta=read('results/E11_metadata.json')
 assert cfg['rule_version']==card['rule_version']==RULE_VERSION and cfg['protocol_sha256']==meta['protocol_sha256']==sha(OUT/PROTOCOL)
 assert card['state_config_sha256']==sha(OUT/'data/runtime_state_config_v4.json') and card['artifact_sha256']==sha(OUT/'data/runtime_models_v1.joblib')
 assert card['snapshot_sha256']==sha(OUT/'data/anonymous_samples_snapshot.json');assert (card['first_train_rows'],card['following_train_rows'])==(138,47)
 checks['protocol_config_model_snapshot_versions']=True
 original=read('data/input_manifest.json')
 for p,h in original['sources'].items():
  if Path(p).exists():assert sha(p)==h
 assert sha(OUT/'data/anonymous_samples_snapshot.json')==original['anonymous_snapshot_sha256']
 checks['original_database_annotation_proposal_and_snapshot_unchanged']=True
 e11=rows('results/E11_ewma_replicates.csv');summary=rows('results/E11_ewma_summary.csv');group=defaultdict(list);paired=defaultdict(list)
 assert len(e11)==124800 and len(summary)==12 and meta['is_real_student_validation'] is False
 for r in e11:
  group[r['split'],float(r['lambda'])].append(r)
  paired[tuple(r[k] for k in ['split','regime','noise','persistence','scenario','rep'])].append(r)
  assert 0<=float(r['filter_mse'])<=1 and 0<=float(r['known_fraction'])<=1
  if r['scenario']=='ack_after_high' and r['ack_drift']!='':same(float(r['ack_drift']),0)
 assert all(sorted(float(r['lambda']) for r in rr)==LAMBDAS for rr in paired.values())
 for s in summary:
  rr=group[s['split'],float(s['lambda'])];assert len(rr)==(6400 if s['split']=='development' else 14400)
  cohorts=defaultdict(list)
  for r in rr:cohorts[tuple(r[k] for k in ['regime','noise','persistence','scenario'])].append(r)
  assert len(cohorts)==(16 if s['split']=='development' else 36) and all(len(v)==400 and len({r['rep'] for r in v})==400 for v in cohorts.values())
  for metric in ['filter_mse','known_fraction','low_time_false_high','sudden_high_delay','ack_drift']:
   values=[[float(r[metric]) for r in cc if r[metric]!=''] for cc in cohorts.values()];values=[v for v in values if v]
   same(number(s,metric+'_mean'),float(np.mean([np.mean(v) for v in values])) if values else None)
   same(number(s,metric+'_mcse'),float(np.sqrt(sum(np.var(v,ddof=1)/len(v) for v in values))/len(values)) if values else None)
  same(float(s['persistent_low_false_high_mean']),float(np.mean([float(r['low_time_false_high']) for r in rr if r['scenario']=='persistent_low'])))
 best=min([s for s in summary if s['split']=='development'],key=lambda s:(float(s['filter_mse_mean']),float(s['lambda'])))
 assert cfg['lambda']==meta['selected_lambda']==float(best['lambda'])==.5
 checks['E11_candidate_pairing_counts_ACK_and_all_summary_metrics']=True
 checks['E11_lambda_selected_from_development_only_not_psychometric']=True
 real,_,_,r3=load();by1={r['sample_id']:r for r in real};by3={r['sample_id']:r for r in r3};ids=set(by1)
 audit=read('data/E12_threshold_inner_audit.json');held=defaultdict(list);thresholds={}
 assert len(audit)==20
 for a in audit:
  tr=set(a['training_ids']);te=set(a['heldout_ids']);assert not tr&te and tr|te==ids;held[a['seed']].extend(te)
  validation=[]
  for inner in a['inner_splits']:
   it=set(inner['training_ids']);iv=set(inner['validation_ids']);assert not it&iv and it|iv==tr and set(inner['parameter_calibration_ids'])==it;validation.extend(iv)
  assert len(validation)==len(tr) and set(validation)==tr
  scores=a['inner_oof_high_scores'];assert len(scores)==len(tr) and {r['sample_id'] for r in scores}==tr
  t,candidates=threshold([by1[r['sample_id']]['final_level'] for r in scores],[r['p_high'] for r in scores])
  assert t==a['chosen_threshold']
  for p,q in zip(candidates,a['candidates']):same(p['balanced_accuracy'],q['balanced_accuracy']);same(p['threshold'],q['threshold'])
  thresholds[a['seed'],a['fold']]=t
 assert set(held)==set(SEEDS) and all(len(v)==47 and set(v)==ids for v in held.values())
 checks['E12_nested_training_only_thresholds_recomputed_and_no_student_overlap']=True
 preds=rows('results/recognition_predictions.csv');lookup={(r['experiment'],r['variant'],int(r['seed']),r['sample_id']):r for r in preds}
 pfull=[np.mean([float(lookup['E2_student_crossfit','parameter_real',s,r['sample_id']]['p_high']) for s in SEEDS]) for r in real]
 t,candidates=threshold([r['final_level'] for r in real],pfull);assert t==cfg['history_high_threshold']
 for p,q in zip(candidates,cfg['threshold_candidates']):same(p['balanced_accuracy'],q['balanced_accuracy'])
 checks['runtime_threshold_one_mean_OOF_score_per_47_R1_students']=True
 e12=rows('results/E12_real_two_point_sensitivity.csv');assert len(e12)==1410 and len({r['student_id'] for r in e12})==47;repeat=defaultdict(list)
 for r in e12:
  seed=int(r['seed']);fold=int(r['fold']);lam=float(r['lambda']);a=by1[r['r1_id']];b=by3[r['r3_id']]
  assert b['pair_id']==a['sample_id'] and r['student_id']==a['student_id'] and r['r3_annotation_for_evaluation_only']==b['final_level']
  q1=lookup['E2_student_crossfit','parameter_real',seed,a['sample_id']];q3=lookup['E3_r3_crossfit','r3_only',seed,b['sample_id']]
  p1={k:float(q1['p_'+k]) for k in LAB};p3={k:float(q3['p_'+k]) for k in LAB+[ACK]}
  ok1,x1,l1=observation(a['prompt_text'],p1);ok3,x3,l3=observation(b['prompt_text'],p3)
  assert ok1==flag(r,'r1_eligible') and ok3==flag(r,'r3_eligible');same(float(r['r1_model_p_high']),p1['high']);same(float(r['r3_model_p_high']),p3['high'])
  d1=x1 if ok1 else None;d3=(x3 if d1 is None else lam*x3+(1-lam)*d1) if ok3 else d1;t=thresholds[seed,fold]
  same(number(r,'x1'),x1 if ok1 else None);same(number(r,'x3'),x3 if ok3 else None);same(number(r,'state_before_R3'),d1);same(number(r,'state_after_R3'),d3);same(float(r['threshold']),t)
  guard=ok3 and l3!='high' and d3 is not None and d3>=t;route=('high' if l3=='high' or guard else l3) if ok3 else 'verify'
  assert guard==flag(r,'history_high_protection') and route==r['route_grade']
  if b['final_level']==ACK:assert not ok3
  repeat[r['r1_id'],seed].append(r)
 assert len(repeat)==235
 for rr in repeat.values():
  assert sorted(float(r['lambda']) for r in rr)==LAMBDAS and len({r['state_before_R3'] for r in rr})==1
  assert len({r['route_grade'] for r in rr})==1
 checks['E12_scores_trace_to_frozen_OOF_no_truth_update_and_holds_recomputed']=True
 checks['E12_47_people_two_points_lambda_independent_first_state_and_unchanged_routes']=True
 for s in rows('results/E12_real_sensitivity_summary.csv'):
  rr=[r for r in e12 if float(r['lambda'])==float(s['lambda'])];valid=[r for r in rr if flag(r,'r3_eligible')]
  assert len(rr)==235 and int(s['unique_students'])==47
  same(float(s['r3_update_fraction']),len(valid)/235);same(float(s['history_high_protection_fraction']),sum(flag(r,'history_high_protection') for r in rr)/235)
  same(float(s['route_matches_annotation_all']),np.mean([r['route_grade']==r['r3_annotation_for_evaluation_only'] for r in rr]))
  same(number(s,'accepted_route_accuracy'),float(np.mean([r['route_grade']==r['r3_annotation_for_evaluation_only'] for r in valid])) if valid else None)
  same(float(s['mean_state_after_R3']),np.mean([float(r['state_after_R3']) for r in rr if r['state_after_R3']!='']))
  assert int(s['ACK_update_count'])==sum(flag(r,'r3_eligible') for r in rr if r['r3_annotation_for_evaluation_only']==ACK)==0
 checks['E12_summary_denominators_and_negative_result_recomputed']=True
 http=read('results/v4_HTTP云边验收.json');ui=read('results/v4_前端验收.json');launcher=read('results/v4_启动器语法检查.json')
 assert http['passed'] and all(http['checks'].values()) and len(http['checks'])==17 and http['external_paid_calls']==http['new_real_students']==0
 assert http['cloud_instruction_compliance_validated'] is False and ui['passed'] and ui['externalPaidCalls']==ui['realStudents']==0 and not ui['overflow'] and not ui['errors']
 assert launcher['passed'] and launcher['parse_only'] and not launcher['errors']
 assert ui['mediumConstrainedCloudRequest'] and ui['highLocalOnly'] and ui['lowCloudRequest']
 checks['17_HTTP_checks_browser_three_routes_mock_only_and_launcher_parse']=True
 legacy=read('results/E10_metadata.json');assert legacy['rule_code_sha256']==sha(OUT/'code/evidence_runtime.py')
 checks['legacy_E10_rule_code_hash_preserved']=True
 write_json('results/v4_一致性检查.json',{'passed':True,'checks':checks,'rule_version':RULE_VERSION,'new_real_students':0,'external_paid_calls':0,
  'real_API_connection_verified':False,'real_longitudinal_EWMA_validated':False,'human_review':'pending'})
 files=[PROTOCOL,'data/anonymous_samples_snapshot.json','data/runtime_state_config_v4.json','data/runtime_model_card.json','data/E12_threshold_inner_audit.json',
  'code/ewma_validation_v4.py','code/runtime_state_v4.py','code/runtime_server.py','code/cloud_gateway.py','code/routing_v4.py','code/test_runtime_v4.py','code/qa_runtime_v4.cjs','code/verify_v4.py','code/build_v4_report.py',
  'results/E11_metadata.json','results/E11_ewma_summary.csv','results/E11_ewma_replicates.csv','results/E12_metadata.json','results/E12_real_two_point_sensitivity.csv','results/E12_real_sensitivity_summary.csv',
  'results/v4_HTTP云边验收.json','results/v4_前端验收.json','results/v4_启动器语法检查.json','report/云边机制与EWMA参数依据_v4.md','report/论文工作稿_v3_含云边机制与EWMA依据.md','app/app.js','app/index.html','启动DeepSeek云边系统.ps1']
 write_json('data/v4_input_output_manifest.json',{'date':'2026-09-30','scope':'engineering parameter selection and retrospective two-point sensitivity; not independent longitudinal validation',
  'rule_version':RULE_VERSION,'new_real_students':0,'external_paid_calls':0,'files':{p:sha(OUT/p) for p in files}})
 print(f'{len(checks)} v4 consistency audit checks passed.',flush=True)
if __name__=='__main__':run()
