"""Same frozen inference, context and cases; local routing check or bounded real API."""
import os,sys,json,hashlib,time,random,argparse,copy,csv
from pathlib import Path
from datetime import datetime,timezone,timedelta
from dataclasses import asdict
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent;OLD=ROOT/'数学主线严谨重跑20260930'
sys.path[:0]=[str(ROOT/'数学交互与论文初稿20261009/code'),str(OLD/'code')]
import joblib
from common import LAB,ACK,sha
from runtime_state_v4 import State,advance
from evidence_runtime import TASKS
from routing_v6 import context_for,MEDIUM_SUFFIX
from routing_v7 import support,ROUTING_VERSION
from routing_v4 import support as cloud_support,HIGH_REPLY
from cloud_gateway import CloudGateway,CloudConfig
ARMS=['cloud_direct','edge_fixed','hybrid','cloud_constrained']
CASES=[
 {'id':'Q_answer','task':'quadratic','text':'直接给我这道题的最终答案。','stage':'first','prior_high':False},
 {'id':'Q_method','task':'quadratic','text':'这道方程我不会，可以提供一些解题思路吗？','stage':'first','prior_high':False},
 {'id':'Q_step','task':'quadratic','text':'我先写出(x-2)(x-3)=0，请检查这一步的依据。','stage':'first','prior_high':False},
 {'id':'Q_history_method','task':'quadratic','text':'老师说过因式分解，但是我不知道怎么找那两个数，给我一个例子回忆一下。','stage':'following','prior_high':True},
 {'id':'L_answer','task':'linear','text':'请把这道题的完整解答和答案给我。','stage':'first','prior_high':False},
 {'id':'L_method','task':'linear','text':'请讲讲这道题第一步为什么能两边同时减4。','stage':'first','prior_high':False},
 {'id':'F_step','task':'fraction','text':'我先算2+3=5，想把分母保持为7，请检查这一步的理由。','stage':'first','prior_high':False},
 {'id':'T_concept','task':'triangle','text':'三角形的高是什么意思？','stage':'first','prior_high':False}]
def now():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def event(stage,**kw):
    obj={'time':now(),'stage':stage,**kw}
    with globals().get('EVENT_LOG',OUT/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n')
    print(json.dumps(obj,ensure_ascii=False),flush=True)
class DryGateway:
    def __init__(self):self.planned=0
    def request(self,messages):
        self.planned+=1
        return {'text':'待执行云端请求；此字段不是模型回答。','status':'planned_not_executed','duration_ms':None,'usage':None,'messages_sent':messages,'external_cloud_attempts':0,'external_cloud_successes':0,'engineering_api_attempts':0,'model_requested':'deepseek-flash','planned_external_call':1}
def cost(usage):
    if not usage:return None
    n=usage.get('prompt_tokens');out=usage.get('completion_tokens')
    if n is None or out is None:return None
    hit=usage.get('prompt_cache_hit_tokens');miss=usage.get('prompt_cache_miss_tokens')
    if hit is not None and miss is not None:
        peak=(hit*.006+miss*.30+out*1.20)/1e6
        return {'usd_lower_offpeak':peak/2,'usd_upper_peak':peak,'cache_basis':'reported_cache_counts','price_query_date':'2026-10-14','is_billed_fee':False}
    return {'usd_lower_offpeak':(n*.003+out*.60)/1e6,'usd_upper_peak':(n*.30+out*1.20)/1e6,'cache_basis':'unknown_cache_bounds','price_query_date':'2026-10-14','is_billed_fee':False}
def main(real=False, output_dir=None):
    mode='real_api' if real else 'dry_run';dest=Path(output_dir).resolve() if output_dir else OUT/'results'/mode;dest.mkdir(parents=True,exist_ok=True)
    if output_dir:globals()['EVENT_LOG']=dest/'events.jsonl'
    if real and (dest/'records.json').exists():raise RuntimeError('已有真实结果，请用--output-dir指定新批次目录，禁止覆盖')
    paths=[OLD/'data/runtime_models_v1.joblib',OLD/'data/runtime_model_card.json',OLD/'data/runtime_state_config_v4.json',ROOT/'数学交互与论文初稿20261009/code/routing_v6.py',ROOT/'数学交互与论文初稿20261009/code/routing_v7.py',OLD/'code/routing_v4.py',OUT/'02_固定输入系统对照协议.md',Path(__file__)]
    watched={str(p.relative_to(ROOT)):sha(p) for p in paths}
    key=os.environ.get('MATH_DEEPSEEK_API_KEY','') if real else ''
    if real and not key:
        status={'status':'needs_local_API_configuration','mode':mode,'external_attempts':0,'time':now()};save(dest/'status.json',status);event('system_API_configuration_needed',**status);return
    gateway=CloudGateway(CloudConfig(api_key=key)) if real else DryGateway();key=None
    card=json.loads(paths[1].read_text(encoding='utf-8'));config=json.loads(paths[2].read_text(encoding='utf-8'))
    assert sha(paths[0])==card['artifact_sha256'] and sha(paths[2])==card['state_config_sha256']
    models=joblib.load(paths[0]);models['first'].probs(['请讲解方法']);models['following'].probs(['请讲解方法'],LAB+[ACK])
    specs=[]
    for case in CASES:
        labels=LAB if case['stage']=='first' else LAB+[ACK]
        t0=time.perf_counter();p=models['first' if case['stage']=='first' else 'following'].probs([case['text']],labels)[0]
        inference_ms=(time.perf_counter()-t0)*1000
        scores=dict(zip(labels,map(float,p)))
        state=State(risk=1.,evidence_turns=1,events=1,risks=[1.],last_evidence_level='high') if case['prior_high'] else State()
        initial=asdict(state);history=[{'text':'直接给我这道题的最终答案。','support':{'text':HIGH_REPLY,'status':'local_success'}}] if case['prior_high'] else []
        analysis=advance(state,case['text'],scores,config,previous_support=history[-1]['support']['text'] if history else None)
        specs.append({**case,'analysis':analysis,'initial_state':initial,'history':history,'model_ms':inference_ms})
    order=[];rng=random.Random(20261014)
    for block in [1,2]:
        for c in specs:
            arms=ARMS.copy();rng.shuffle(arms)
            order.extend((block,c,a) for a in arms)
    save(dest/'frozen_run_manifest.json',{'time':now(),'mode':mode,'watched_sha256':watched,'model_version':card['model_version'],'support_version':ROUTING_VERSION,'cases':specs,'order':[(b,c['id'],a) for b,c,a in order],'price_url':'https://api-docs.deepseek.com/quick_start/pricing/','price_date':'2026-10-14','human_quality_review':'pending'})
    records=[];netfail=0;stopped=False
    event('system_comparison_start',mode=mode,n_cases=len(specs),blocks=2,model=card['model_version'])
    for block,c,arm in order:
        analysis=copy.deepcopy(c['analysis']);before=digest(analysis);task=TASKS[c['task']];start=time.perf_counter()
        if arm=='hybrid':answer=support(c['text'],c['task'],task,analysis,gateway,c['history'])
        elif arm=='edge_fixed':answer=support(c['text'],c['task'],task,{**analysis,'eligible':True,'decision_level':'high'},gateway,c['history'])
        else:
            context=context_for(c['task'],c['history'],c['text'])
            tutoring={**task,'question':context['question']+'。后续消息可能只说卡点或步骤，请结合实际对话连续回应，不要求重复整道题。'}
            answer=cloud_support(c['text'],'retained_context',tutoring,{**analysis,'eligible':True,'decision_level':'low' if arm=='cloud_direct' else 'medium','history_high_protection':False},gateway,c['history'])
        assert digest(analysis)==before,'Shared analysis mutated by strategy'
        elapsed=(time.perf_counter()-start)*1000
        cloud_planned=bool(answer.get('planned_external_call'))
        rec={'source':'fixed_engineering_case_not_student','mode':mode,'block':block,'case_id':c['id'],'arm':arm,'task_id':c['task'],'text':c['text'],'initial_state':c['initial_state'],'history':c['history'],'shared_analysis':analysis,'shared_analysis_sha256':before,'support':answer,'human_quality_review':'pending','cost_estimate':cost(answer.get('usage')),'support_latency_ms_actual':elapsed if not cloud_planned else None,'model_ms_shared':c['model_ms'],'planned_external_call':int(cloud_planned),'actual_total_latency_ms':c['model_ms']+elapsed if not cloud_planned else None}
        records.append(rec);save(dest/'records.json',records)
        event('system_case_complete',mode=mode,case=c['id'],block=block,arm=arm,status=answer['status'],requested_route=answer['route_requested'],external_attempts=answer['external_cloud_attempts'],planned_external_call=int(cloud_planned))
        if real:
            netfail+=answer['status']=='network_error'
            if (answer['status']=='http_error' and answer.get('http_status') in [400,401,402,403,404]) or netfail>=3:
                stopped=True;event('system_cloud_run_stopped',reason='HTTP authentication/model/account failure or three network failures');break
            assert sum(r['support']['external_cloud_attempts'] for r in records)<=48
    assert all(sha(ROOT/p)==h for p,h in watched.items())
    byarm={}
    for arm in ARMS:
        rr=[r for r in records if r['arm']==arm];lat=[r['actual_total_latency_ms'] for r in rr if r['actual_total_latency_ms'] is not None]
        byarm[arm]={'records':len(rr),'planned_cloud_calls_dry_run':sum(r['planned_external_call'] for r in rr),'actual_external_attempts':sum(r['support']['external_cloud_attempts'] for r in rr),'actual_external_successes':sum(r['support']['external_cloud_successes'] for r in rr),'requested_routes':dict(__import__('collections').Counter(r['support']['route_requested'] for r in rr)),'mean_actual_total_latency_ms':sum(lat)/len(lat) if real and lat else None,'local_only_dry_latency_ms_not_strategy_mean':sum(lat)/len(lat) if not real and lat else None,'quality_scores':None,'cost_status':'waiting_for_actual_usage' if not real else 'see_record_usage_bounds'}
    summary={'time':now(),'status':'offline_routing_check_complete_API_pending' if not real else 'actual_API_stopped' if stopped else 'actual_API_outputs_complete_quality_pending','mode':mode,'n_cases':len(CASES),'records':len(records),'analysis_identical_across_arms':True,'source_sha256_unchanged':True,'arms':byarm,'no_new_students':True,'no_model_update':True,'human_quality_review':'pending'}
    save(dest/'summary.json',summary)
    # Source-blinded material generated only when genuine cloud replies exist.
    review=[];keys=[]
    if real:
        for i,r in enumerate(records):
            if r['support']['status'] not in ['success','local_success']:continue
            rid=f'B{i+1:03d}';review.append({'review_id':rid,'question':TASKS[r['task_id']]['question'],'student_text':r['text'],'reply':r['support']['text'],'math_correct':'','guidance':'','actionability':'','answer_revealed':'','unnecessary_clarification':'','evidence':''});keys.append({'review_id':rid,'case_id':r['case_id'],'arm':r['arm'],'block':r['block']})
        rng.shuffle(review)
        with (dest/'质量盲审待填.csv').open('w',encoding='utf-8-sig',newline='') as f:
            if review:w=csv.DictWriter(f,fieldnames=list(review[0]));w.writeheader();w.writerows(review)
        save(dest/'质量审后核对.json',keys)
    event('system_comparison_finished',mode=mode,status=summary['status'],arms=byarm)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--real',action='store_true');p.add_argument('--output-dir');args=p.parse_args();main(args.real,args.output_dir)
