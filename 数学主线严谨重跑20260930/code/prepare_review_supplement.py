"""Create unfilled quality-review sheets without replacing any reviewer work."""
from common import *
def run():
 for label,source in [('训练148条','data/E7_v2训练候选.csv'),('受控留出50条','data/E7_v2受控留出候选.csv')]:
  target='data/v2_'+label+'_人工质量审核.csv'
  if (OUT/target).exists():continue
  rr=list(csv.DictReader((OUT/source).open(encoding='utf-8-sig')))
  write_csv(target,[{'candidate_id':f'V2_{label}_{i+1:03d}','原文':r['prompt_text'],'模板家族':r['template_family'],'题目编号':r['task_id'],
   '工程参考等级':r['final_level'],'数学是否正确':'','语言是否自然':'','是否可判定等级':'','人工等级':'','是否通过':'','依据与修改建议':''} for i,r in enumerate(rr)])
 allrows=list(csv.DictReader((OUT/'results/E10_rule_predictions.csv').open(encoding='utf-8-sig')))
 real,_,_,r3=load();diag=[]
 for r in r3:
  rr=[x for x in allrows if x['policy']=='behavior_hybrid_v3' and x['stage']=='R3' and x['sample_id']==r['sample_id']]
  assert len(rr)==5
  n=sum(x['eligible']=='True' for x in rr)
  diag.append({'student_id':r['student_id'],'sample_id':r['sample_id'],'原始R3文本':r['prompt_text'],'旧标注_仅诊断':r['final_level'],
   '五次折外可判断次数':n,'五次正确次数':sum(x['eligible']=='True' and x['current_behavior_prediction']==x['truth'] for x in rr),
   '五次规则使用次数':sum(x['decision_basis']=='behavior_rule' for x in rr),'规则线索':rr[0]['rule_matches'],
   '备注':'工程诊断；盲法复核成员提交前不得查看；不自动改标'})
 write_csv('results/R3瓶颈分层清单_非盲法审核材料.csv',diag)
 print('Review sheets preserved/created; diagnostic list is separate; human review still pending.')
if __name__=='__main__':run()
