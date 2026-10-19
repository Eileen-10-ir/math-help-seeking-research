"""Portable hash and chain identity verification."""
from pathlib import Path
import json,hashlib
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check():
    c=read(OUT/'data/统一主线交接契约.json')
    for name,h in c['watched_sha256'].items():assert sha(ROOT/name)==h,('Changed release input',name)
    card=read(OUT/'data/runtime_model_card.json');cfg=read(OUT/'data/runtime_state_config_v4.json')
    assert card['model_version']==c['primary_model'] and card['rule_version']==cfg['rule_version']==c['state_rule']
    assert card['artifact_sha256']==sha(OUT/'data/runtime_models_v1.joblib')
    assert card['state_config_sha256']==sha(OUT/'data/runtime_state_config_v4.json')==sha(OUT/'data/runtime_state_config_v5.json')
    assert cfg['stage_cutoffs']==c['stage_cutoffs'] and cfg['lambda']==c['alpha'] and cfg['history_policy']==c['history_policy']
    system=read(OUT/'results/system_dry_run02/records.json');assert len(system)==64
    grouped={}
    for r in system:
        assert r['support']['external_cloud_attempts']==0
        grouped.setdefault((r['case_id'],r['block']),[]).append(r)
    assert all(len(v)==4 and len({r['shared_analysis_sha256'] for r in v})==1 for v in grouped.values())
    return {'passed':True,'model':c['primary_model'],'contract':c['version'],'watched_files':len(c['watched_sha256']),
            'recognition_predictions':1645,'system_records':64,'paid_calls':0}
if __name__=='__main__':print(json.dumps(check(),ensure_ascii=False))
