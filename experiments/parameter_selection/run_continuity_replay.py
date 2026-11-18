"""Same archived history for both support versions; no generated-student behavior claim."""
from pathlib import Path
import os,sys,json,time,hashlib
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
REPO=Path(os.environ['MATH_CODE_REPOSITORY'])
sys.path[:0]=[str(REPO/'src/support_versions')]
import midterm_support as b
import support_v2 as v
from cloud_client import CloudGateway,CloudConfig
def main():
 key=os.environ.get('MATH_DEEPSEEK_API_KEY','')
 if not key:key=(REPO/'.private/deepseek_api_key.txt').read_text(encoding='utf-8-sig').strip()
 gateway=CloudGateway(CloudConfig(api_key=key,model='deepseek-flash'))
 raw=json.loads((ROOT/'队友优化验收20261115/交接原包/EduTrace_midterm_handoff/final_results/multiturn_records_final.json').read_text(encoding='utf-8'))
 source=[r for r in raw if r['version']=='B3'];assert len(source)==15
 config_path=ROOT/'队友优化验收20261115/交接原包/EduTrace_midterm_handoff/configs/midterm_multiturn_v1.json'
 cfg=json.loads(config_path.read_text(encoding='utf-8'))
 assert cfg['scope']=='Four scripted engineering dialogues; not real student evidence'
 script={(d['dialogue_id'],i):t for d in cfg['dialogues'] for i,t in enumerate(d['turns'],1)}
 for r in source:
  assert r['source_group']=='scripted_engineering_multiturn'
  expected=script[(r['dialogue_id'],r['turn_id'])]
  assert all(r[k]==expected[k] for k in ['task_id','question','prompt_text'])
  preceding=[x for x in source if x['dialogue_id']==r['dialogue_id'] and x['turn_id']<r['turn_id']]
  for h in r['history']:
   assert any(h['text']==p['prompt_text'] and h['support']['text']==p['support']['text'] for p in preceding)
 proof={'all_15_utterances_equal_engineering_configuration':True,'history_matches_prior_generated_support':True,
        'config_scope':cfg['scope'],'config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),'real_student_rows_sent':0}
 (OUT/'results/continuity_source_check.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
 if '--check-source-only' in sys.argv:print(json.dumps(proof));return
 dest=OUT/'results/continuity_real';dest.mkdir(exist_ok=True);rows=[]
 for r in source:
  ctx=b.build_task_context(r['task_id'],r['question'],r['history'])
  for arm in ['B3','revision']:
   path=dest/(r['case_id']+'_'+arm+'.json')
   if path.exists():result=json.loads(path.read_text(encoding='utf-8'))
   else:
    t=time.perf_counter()
    support=b.execute_optimized_support(r['prompt_text'],r['shared_analysis'],ctx,gateway,'B3') if arm=='B3' else v.execute(r['prompt_text'],r['shared_analysis'],ctx,gateway)
    result={'case_id':r['case_id'],'arm':arm,'question':r['question'],'prompt':r['prompt_text'],'history':r['history'],
      'analysis':r['shared_analysis'],'support':support,'elapsed_ms':(time.perf_counter()-t)*1000}
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
   rows.append(result)
  print(r['case_id'],flush=True)
 summary={}
 for arm in ['B3','revision']:
  rr=[r for r in rows if r['arm']==arm];ss=[r['support'] for r in rr]
  summary[arm]={'n_turns':len(rr),'n_dialogues':4,'calls':sum(r.get('external_cloud_attempts',0) for r in ss),
    'tokens':sum((r.get('usage') or {}).get('total_tokens',0) for r in ss),'failures':sum(r['status'] not in ['success','local_success'] for r in ss),
    'scope':'paired prefix replay; fixed supplied histories, not autonomous rollout or learning outcome','H_scoring':'pending'}
 (dest/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
