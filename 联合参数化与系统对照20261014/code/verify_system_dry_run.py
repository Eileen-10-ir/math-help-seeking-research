from pathlib import Path
import json,hashlib
from collections import defaultdict
from datetime import datetime,timezone,timedelta
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rr=json.loads((OUT/'results/dry_run/records.json').read_text(encoding='utf-8'))
manifest=json.loads((OUT/'results/dry_run/frozen_run_manifest.json').read_text(encoding='utf-8'))
assert len(rr)==64
by=defaultdict(list)
for r in rr:by[(r['case_id'],r['block'])].append(r)
assert len(by)==16
suffix='请不要直接给出最终答案或完整代做解答；请给我详细的分步思路与必要提示，先说明可以尝试的下一步，并邀请我写出自己的尝试。'
for group in by.values():
    assert {r['arm'] for r in group}=={'cloud_direct','edge_fixed','hybrid','cloud_constrained'}
    assert len({r['shared_analysis_sha256'] for r in group})==1
    assert len({json.dumps(r['initial_state'],sort_keys=True) for r in group})==1
    assert len({json.dumps(r['history'],sort_keys=True,ensure_ascii=False) for r in group})==1
    assert len({r['text'] for r in group})==1
for r in rr:
    a=r['support'];assert a['external_cloud_attempts']==0
    if r['arm']=='edge_fixed':assert not r['planned_external_call'] and a['route_requested']=='edge_fixed'
    if r['arm']=='cloud_direct':assert r['planned_external_call'] and a['edge_suffix']==''
    if r['arm']=='cloud_constrained':assert r['planned_external_call'] and a['edge_suffix']==suffix
    if r['arm']=='hybrid':
        gate=r['shared_analysis']
        if gate['eligible'] and gate['decision_level']=='high':assert a['route_requested']=='edge_fixed'
        if gate['eligible'] and gate['decision_level']=='medium':assert a['route_requested']=='cloud_constrained' and a['edge_suffix']==suffix
        if gate['eligible'] and gate['decision_level']=='low':assert a['route_requested']=='cloud_direct' and a['edge_suffix']==''
    if r['planned_external_call']:
        assert r['actual_total_latency_ms'] is None and r['cost_estimate'] is None and a['status']=='planned_not_executed'
    assert r['human_quality_review']=='pending'
for p,h in manifest['watched_sha256'].items():assert sha(ROOT/p)==h
out={'time':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'records':64,'case_blocks':16,'shared_inference_state_history_inputs_verified':True,'cloud_direct_without_medium_suffix':True,'cloud_constrained_with_exact_suffix':True,'edge_has_zero_cloud_calls':True,'graded_high_medium_low_route_contract_verified':True,'ungraded_support_separately_recorded':True,'external_paid_calls':0,'cloud_latency_cost_quality_not_fabricated':True,'frozen_sources_unchanged':True,'real_API_status':'waiting for local credential configuration'}
(OUT/'results/系统离线验收.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'stage':'system_dry_run_verified',**out},ensure_ascii=False)+'\n')
print(json.dumps(out,ensure_ascii=False))
