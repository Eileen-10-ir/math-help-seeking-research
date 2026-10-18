import json
import argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parents[1]
old = json.loads((ROOT / '联合参数化与系统对照20261014/results/dry_run/records.json').read_text(encoding='utf-8'))
parser = argparse.ArgumentParser()
parser.add_argument('--records-dir', type=Path)
args = parser.parse_args()
dest = args.records_dir.resolve() if args.records_dir else OUT / 'results/dry_run'
new = json.loads((dest / 'records.json').read_text(encoding='utf-8'))
key = lambda r: (r['block'], r['case_id'], r['arm'])
by = {key(r): r for r in old}
assert len(by) == len(new) == 64
changed = []
for r in new:
    before = by[key(r)]
    assert r['shared_analysis'] == before['shared_analysis']
    assert r['initial_state'] == before['initial_state'] and r['history'] == before['history']
    assert r['support']['route_requested'] == before['support']['route_requested']
    assert r['support']['external_cloud_attempts'] == 0
    if r['support']['route_requested'] in ('cloud_direct', 'cloud_constrained'):
        assert r['support']['messages_sent'] == before['support']['messages_sent']
    if r['support']['text'] != before['support']['text']:
        changed.append({'block': r['block'], 'case_id': r['case_id'], 'arm': r['arm'],
                        'before': before['support']['text'], 'after': r['support']['text']})
    if r['case_id'] == 'L_answer' and r['arm'] == 'hybrid':
        assert '因数对' not in r['support']['text'] and '减4' in r['support']['text']
    if r['case_id'] == 'T_concept' and r['arm'] == 'edge_fixed':
        assert '垂直距离' in r['support']['text'] and '延长线' in r['support']['text']
result = {'records': 64, 'same_model_state_inference_routes': True, 'cloud_messages_unchanged': True,
          'local_only_dry_run_no_API': True, 'local_replies_changed': changed,
          'actual_API_status': 'pending_separate_v7_run', 'human_quality_status': 'pending'}
(dest / 'v7_离线修正核验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'local_replies_changed'}, ensure_ascii=False))
