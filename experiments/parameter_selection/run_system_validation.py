"""Paired support/resource validation; fixed archived engineering inputs, no student-effect claim."""
import sys,json,time,os,hashlib,random,csv
from pathlib import Path
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
REPO=Path(os.environ['MATH_CODE_REPOSITORY'])
sys.path[:0]=[str(REPO/'src'),str(REPO/'src/support_versions')]
import latest_runtime as latest
import midterm_support as b
import support_v2 as v
from cloud_client import CloudGateway,CloudConfig

def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 real='--real' in sys.argv
 source=ROOT/'队友优化验收20261115/交接原包/EduTrace_midterm_handoff/final_results/main_records_final.json'
 inputs=[r for r in json.loads(source.read_text(encoding='utf-8')) if r['version']=='B3']
 assert len(inputs)==24
 protocol={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'cases':[r['case_id'] for r in inputs],
   'arms':['edge','cloud_direct','cloud_constrained','B2','B3','revision'],'order_seed':20261118,'repeats':1,'maximum_calls':120,
   'model':'deepseek-flash','temperature':.2,'max_tokens':768,'scope':'engineering development replay, not independent student evaluation',
   'quality':'C/T/A/H/E/R blank until independent review; no automatic quality superiority',
   'extra_settings':{'case':'MT001','temperatures':[0,.2,.5],'max_tokens':[384,768,1536]}}
 dest=OUT/'results'/('system_real' if real else 'system_dry');dest.mkdir(exist_ok=True)
 pp=dest/'protocol.json'
 if pp.exists():assert json.loads(pp.read_text(encoding='utf-8'))==protocol
 else:save(pp,protocol)
 if real and not os.environ.get('MATH_DEEPSEEK_API_KEY'):
  kp=REPO/'.private/deepseek_api_key.txt'
  if kp.is_file():os.environ['MATH_DEEPSEEK_API_KEY']=kp.read_text(encoding='utf-8-sig').strip()
 if real and not os.environ.get('MATH_DEEPSEEK_API_KEY'):raise RuntimeError('Configure local API first')
 existing=[json.loads(p.read_text(encoding='utf-8')) for pattern in ['MT*.json','setting_*.json'] for p in dest.glob(pattern)]
 used=[sum(r['support'].get('external_cloud_attempts',0) for r in existing)]
 class BudgetGateway(CloudGateway):
  def request(self,messages):
   if real:
    if used[0]>=protocol['maximum_calls']:raise RuntimeError('Frozen call budget exhausted; no request sent')
    used[0]+=1
   return super().request(messages)
 gateway=BudgetGateway(CloudConfig(api_key=os.environ.get('MATH_DEEPSEEK_API_KEY','') if real else '',model=protocol['model']))
 runtime,Service=latest.bootstrap('B3')
 from state_v5 import State,advance
 from common import LAB,ACK
 service=Service(dest/'engineering_only.sqlite3',engineering=not real,gateway=gateway)
 rows=[];rng=random.Random(20261118)
 for item in inputs:
  state=State();analysis=None
  seq=[{'text':h['text'],'support':h.get('support',{})} for h in item['history']]+[{'text':item['prompt_text']}]
  for index,h in enumerate(seq):
   model=service.models['first' if index==0 else 'following'];labels=LAB if index==0 else LAB+[ACK]
   probabilities=model.probs([h['text']],labels)[0]
   analysis=advance(state,h['text'],dict(zip(labels,map(float,probabilities))),service.state_config,seq[index-1].get('support',{}).get('text') if index else None)
  ah=hashlib.sha256(json.dumps(analysis,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
  ctx=b.build_task_context(item['task_id'],item['question'],item['history'])
  arms=list(protocol['arms']);rng.shuffle(arms)
  for arm in arms:
   path=dest/(item['case_id']+'_'+arm+'.json')
   if path.exists():r=json.loads(path.read_text(encoding='utf-8'));assert r['analysis_sha256']==ah
   else:
    t=time.perf_counter()
    if arm=='revision':support=v.execute(item['prompt_text'],analysis,ctx,gateway)
    else:support=b.execute_optimized_support(item['prompt_text'],analysis,ctx,gateway,'B2' if arm=='B2' else 'B3',forced_route={'edge':'edge_fixed','cloud_direct':'cloud_direct','cloud_constrained':'cloud_constrained'}.get(arm))
    r={'case_id':item['case_id'],'arm':arm,'question':item['question'],'prompt':item['prompt_text'],'history':item['history'],
       'analysis':analysis,'analysis_sha256':ah,'support':support,'elapsed_ms':(time.perf_counter()-t)*1000,'source':'archived_engineering_input'}
    save(path,r)
   rows.append(r)
  print(item['case_id'],'complete',flush=True)
 summary={}
 for arm in protocol['arms']:
  group=[r for r in rows if r['arm']==arm];supports=[r['support'] for r in group]
  summary[arm]={'n_inputs':len(group),'calls':sum(r.get('external_cloud_attempts',0) for r in supports),'successes':sum(r.get('external_cloud_successes',0) for r in supports),
    'tokens':sum((r.get('usage') or {}).get('total_tokens',0) for r in supports),'truncated':sum(r.get('finish_reason')=='length' for r in supports),
    'failures':sum(r['status'] not in ['success','local_success'] for r in supports) if real else None,'mean_ms':sum(r['elapsed_ms'] for r in group)/len(group) if real else None,'real_execution':real,
    'planned_cloud_calls':sum(r.get('route_requested') in ['cloud_direct','cloud_constrained'] for r in supports),
    'quality_status':'awaiting_independent_scoring','cost_cny':None}
 save(dest/'summary.json',summary)
 # Separate nine-setting check; never folded into arm resources or used to select quality.
 item=inputs[0];ctx=b.build_task_context(item['task_id'],item['question'],item['history'])
 for temperature in [0,.2,.5]:
  for budget in [384,768,1536]:
   path=dest/f'setting_{temperature}_{budget}.json'
   if path.exists():continue
   g=BudgetGateway(CloudConfig(api_key=gateway.config.api_key,model=protocol['model'],temperature=temperature,max_tokens=budget))
   support=g.request(v.build_messages(ctx,item['prompt_text'],1))
   save(path,dict(temperature=temperature,max_tokens=budget,support=support))
 # Opaque shuffled review sheet; mapping stays in a separate file.
 shuffled=rows.copy();random.Random(1811).shuffle(shuffled);mapping=[]
 with (dest/'独立评分_空表.csv').open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=['review_id','题目','已有历史','学生本轮表达','系统回复','C','T','A','H','E','R','依据']);writer.writeheader()
  for i,r in enumerate(shuffled,1):
   rid=f'R{i:03d}';mapping.append(dict(review_id=rid,case_id=r['case_id'],arm=r['arm']))
   writer.writerow(dict(review_id=rid,题目=r['question'],已有历史=json.dumps(r['history'],ensure_ascii=False),学生本轮表达=r['prompt'],系统回复=r['support']['text']))
 save(dest/'负责人保留_盲审映射.json',mapping)
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
