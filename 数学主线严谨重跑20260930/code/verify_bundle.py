"""Check scientific bookkeeping and reproducible outputs, without changing labels."""
from common import *
from controlled_text import pool
from collections import defaultdict
import platform,scipy,sklearn

def run():
 checks={};real,eedi,llm,r3=load()
 assert [len(x) for x in [real,eedi,llm,r3]]==[47,247,16,47]
 assert len({r['student_id'] for r in real})==47
 checks['snapshot_counts_and_student_uniqueness']=True
 manifest=json.loads((OUT/'data/input_manifest.json').read_text(encoding='utf-8'))
 assert manifest['protocol_sha256']==sha(OUT/'冻结重跑协议.md')
 for p,h in manifest['sources'].items():
  if Path(p).exists():assert sha(p)==h,f'Original source changed: {p}'
 checks['available_original_hashes_unchanged']=True
 splits=json.loads((OUT/'data/E2_family_calibration_splits.json').read_text(encoding='utf-8'))
 parents={r['sample_id']:r['parent_id'] for r in llm};allreal={r['sample_id'] for r in real}
 held=defaultdict(list)
 for s in splits:
  tr=set(s['training_real_ids']);te=set(s['heldout_real_ids'])
  assert not tr&te and tr|te==allreal
  assert set(s['parameter_calibration']['calibration_ids'])==tr
  assert all(parents[x] in tr for x in s['allowed_llm_ids'])
  assert all(parents[x] in te for x in s['excluded_llm_ids'])
  assert set(s['allowed_llm_ids'])|set(s['excluded_llm_ids'])==set(parents)
  held[s['seed']].extend(te)
 assert len(splits)==20 and all(len(x)==47 and set(x)==allreal for x in held.values())
 checks['student_family_and_calibration_isolation']=True
 choices=json.loads((OUT/'data/E3b_inner_selection.json').read_text(encoding='utf-8'))
 for s in choices:
  assert not set(s['training_students'])&set(s['heldout_students'])
  assert s['chosen_weight']==max(s['inner_candidates'],key=lambda x:x['inner_macro_f1'])['weight']
 checks['nested_selection_uses_training_students']=True
 _,train=pool();_,test=pool('test')
 assert len(train)==120 and len(test)==40
 for k in ['template_family','task_id','feature_key']:assert not {r[k] for r in train}&{r[k] for r in test}
 checks['controlled_templates_tasks_masked_text_disjoint']=True
 pred=list(csv.DictReader((OUT/'results/recognition_predictions.csv').open(encoding='utf-8-sig')))
 grouped=defaultdict(list)
 for r in pred:
  labs=LAB+[ACK] if r['experiment']=='E3_r3_crossfit' else LAB
  p=np.array([float(r['p_'+x]) for x in labs]);assert np.isfinite(p).all() and np.all(p>=0) and np.isclose(p.sum(),1)
  assert r['prediction']==labs[int(p.argmax())]
  grouped[(r['experiment'],r['variant'],r['seed'])].append(r)
 for (exp,var,seed),rr in grouped.items():
  assert len(rr)==(247 if exp=='E1_public_oof' else 47)
  assert len({r['sample_id'] for r in rr})==len(rr)
 checks['prediction_scores_labels_and_repeat_counts']=True
 for exp in ['E2_student_crossfit','E3_r3_crossfit']:
  expected=json.loads((OUT/('results/E2_summary.json' if exp.startswith('E2') else 'results/E3_summary.json')).read_text(encoding='utf-8'))
  for variant,summary in expected.items():
   measured=[]
   for seed in SEEDS:
    rr=grouped[(exp,variant,str(seed))];labs=LAB+[ACK] if exp.startswith('E3') else LAB
    measured.append(metrics([r['truth'] for r in rr],[[float(r['p_'+x]) for x in labs] for r in rr],labs)['macro_f1'])
   assert np.isclose(np.mean(measured),summary['macro_f1']['mean'])
 checks['summaries_recomputed_from_sample_predictions']=True
 state=list(csv.DictReader((OUT/'results/E5_correlated_pressure.csv').open(encoding='utf-8-sig')))
 assert len(state)==256
 gates=[r for r in state if r['scenario']=='ack_after_high' and r['policy']=='joint_gate']
 assert gates and all(float(r['ack_drift_mean'])==0 for r in gates)
 for r in state:
  for k,v in r.items():
   if k.endswith('_mcse') and v:assert np.isfinite(float(v)) and float(v)>=0
 checks['ack_gate_preserves_state_and_mcse_valid']=True
 trajectories=list(csv.DictReader((OUT/'results/E6_trajectories.csv').open(encoding='utf-8-sig')))
 null=defaultdict(list)
 for r in trajectories:
  if r['scenario']=='zero_extra_effect':null[r['turn']].append((r['low_fraction'],r['high_fraction']))
 assert len(null)==8 and all(len(x)==3 and len(set(x))==1 for x in null.values())
 checks['zero_action_effect_has_equal_aggregate_trajectories']=True
 endpoints=list(csv.DictReader((OUT/'results/E6_replicate_endpoints.csv').open(encoding='utf-8-sig')))
 assert len(endpoints)==12000
 import ast
 summary=list(csv.DictReader((OUT/'results/E6_action_scenarios.csv').open(encoding='utf-8-sig')))
 for r in summary:
  rr=sorted([x for x in endpoints if x['scenario']==r['scenario'] and x['policy']==r['policy']],key=lambda x:int(x['rep']))
  base=sorted([x for x in endpoints if x['scenario']==r['scenario'] and x['policy']=='no_added_action'],key=lambda x:int(x['rep']))
  delta=np.array([float(a['end_low'])-float(b['end_low']) for a,b in zip(rr,base)])
  assert len(rr)==1000 and np.isclose(delta.mean(),float(r['low_difference_vs_baseline_mean']))
  assert np.allclose(np.quantile(delta,[.025,.975]),ast.literal_eval(r['low_difference_scenario95']))
 checks['action_summaries_recomputed_from_12000_endpoints']=True
 profiles=json.loads((OUT/'data/validated_replay_profiles.json').read_text(encoding='utf-8'))
 assert len(profiles['real'])==47 and len(profiles['synthetic'])==300
 assert all(len(d['steps'])==2 for d in profiles['real']) and all(len(d['steps'])==8 for d in profiles['synthetic'])
 for d in profiles['real']:
  for s in d['steps']:assert np.isclose(sum(s['probabilities'].values()),1)
 checks['profile_sources_turns_and_scores']=True
 # One independent diagnostic refit checks local copied feature code against saved output.
 model=Classifier().fit([r['prompt_text'] for r in eedi],[r['final_level'] for r in eedi])
 f1=metrics([r['final_level'] for r in real],model.probs([r['prompt_text'] for r in real]))['macro_f1']
 assert np.isclose(f1,json.loads((OUT/'results/E2_summary.json').read_text(encoding='utf-8'))['eedi_only']['macro_f1']['mean'])
 checks['portable_local_feature_refit_matches_saved_diagnostic']=True
 qa=OUT/'qa/中期页面检查.json'
 if qa.exists():
  q=json.loads(qa.read_text(encoding='utf-8'));assert q['allRecordsRendered'] and not q['scriptErrors'] and not q['mobileHorizontalOverflow']
  checks['browser_rendering_all_records']=True
 write_json('results/交付一致性检查.json',{'passed':True,'checks':checks,'human_review_completed':False,'external_validation':False,
   'runtime':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__}})
 print(f'{len(checks)} checks passed; human review remains pending.')
if __name__=='__main__':run()
