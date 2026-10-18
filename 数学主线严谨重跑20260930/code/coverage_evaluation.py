"""Fixed OOF scores: report abstention coverage jointly with observed error."""
from common import *
from evidence_runtime import assess
def run():
 real,eedi,llm,r3=load();text={r['sample_id']:r['prompt_text'] for r in real+r3}
 predictions=list(csv.DictReader((OUT/'results/recognition_predictions.csv').open(encoding='utf-8-sig')))
 selected=[r for r in predictions if (r['experiment']=='E2_student_crossfit' and r['variant']=='parameter_real') or (r['experiment']=='E3_r3_crossfit' and r['variant']=='r3_only')]
 details=[];summaries=[]
 for stage,experiment in [('R1','E2_student_crossfit'),('R3','E3_r3_crossfit')]:
  labels=LAB if stage=='R1' else LAB+[ACK]
  for policy,ev,conf in [('no_gate',False,False),('events_only',True,False),('confidence_only',False,True),('events_and_confidence',True,True)]:
   for cutoff in [.5,.6,.7,.8]:
    for seed in SEEDS:
     current=[]
     for p in [r for r in selected if r['experiment']==experiment and int(r['seed'])==seed]:
      scores={k:float(p['p_'+k]) for k in labels};g=assess(text[p['sample_id']],scores,cutoff,events=ev,confidence=conf)
      row={'stage':stage,'policy':policy,'cutoff':cutoff,'seed':seed,'sample_id':p['sample_id'],'student_id':p['student_id'],
        'truth':p['truth'],'model_prediction':p['prediction'],'eligible':g['eligible'],'event':g['observed_event'],
        'max_model_score':g['max_model_score'],'reason':'；'.join(g['hold_reasons'])}
      current.append(row);details.append(row)
     accepted=[r for r in current if r['eligible']];high=[r for r in current if r['truth']=='high'];ack=[r for r in current if r['truth']==ACK];graded=[r for r in current if r['truth'] in LAB]
     accepted_true_graded=[r for r in accepted if r['truth'] in LAB]
     def fraction(rows,predicate):return sum(predicate(r) for r in rows)/len(rows) if rows else None
     summaries.append({'stage':stage,'policy':policy,'cutoff':cutoff,'seed':seed,'n':47,'accepted_n':len(accepted),'coverage':len(accepted)/47,
       'accepted_accuracy_all':fraction(accepted,lambda r:r['model_prediction']==r['truth']),
       'accepted_accuracy_non_ack':fraction(accepted_true_graded,lambda r:r['model_prediction']==r['truth']),
       'non_ack_coverage':fraction(graded,lambda r:r['eligible']),
       'high_correct_decision_rate_all_high':fraction(high,lambda r:r['eligible'] and r['model_prediction']=='high'),
       'high_review_rate':fraction(high,lambda r:not r['eligible']),
       'ack_wrong_state_update_rate':fraction(ack,lambda r:r['eligible']),
       **{k+'_coverage':fraction([r for r in current if r['truth']==k],lambda r:r['eligible']) for k in labels}})
 write_csv('results/E8_coverage_predictions.csv',details);write_csv('results/E8_coverage_repeat_metrics.csv',summaries)
 aggregate=[]
 for stage in ['R1','R3']:
  for policy in ['no_gate','events_only','confidence_only','events_and_confidence']:
   for cutoff in [.5,.6,.7,.8]:
    rr=[r for r in summaries if r['stage']==stage and r['policy']==policy and r['cutoff']==cutoff]
    row={'stage':stage,'policy':policy,'cutoff':cutoff,'students_per_repeat':47,'repeats':5}
    for key in rr[0]:
     if key not in ['stage','policy','cutoff','seed','n']:
      values=[r[key] for r in rr if r[key] is not None];row[key+'_mean']=float(np.mean(values)) if values else None
    aggregate.append(row)
 write_csv('results/E8_coverage_summary.csv',aggregate)
 write_json('results/E8_metadata.json',{'protocol_sha256':sha(OUT/'实时闭环与补充实验协议.md'),'thresholds':[.5,.6,.7,.8],'runtime_cutoff':.6,
  'caveats':['Fixed previous OOF scores; no retraining','Labels are historical task annotation','Accuracy on accepted subset is not whole-population accuracy',
   'ACK candidate is always excluded from dependency updates, even in no_gate baseline','Class-specific coverage can be severely unbalanced','No theoretical selective-risk guarantee or calibrated confidence']})
 print('E8 all thresholds and class-specific coverage saved; no cutoff tuning.')
if __name__=='__main__':run()
