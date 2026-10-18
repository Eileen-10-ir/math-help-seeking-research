"""Validate model, data, state, support and evaluation refer to the same frozen chain."""
import argparse, json, hashlib, csv
from pathlib import Path
from collections import Counter
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def csvread(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def check():
    contract=json.loads((OUT/'data/统一主线交接契约.json').read_text(encoding='utf-8'))
    for name,expected in contract['watched_sha256'].items():
        assert sha(ROOT/name)==expected, ('Contract source changed',name)
    card=json.loads((OUT/'data/runtime_model_card.json').read_text(encoding='utf-8'))
    cfg=json.loads((OUT/'data/runtime_state_config_v4.json').read_text(encoding='utf-8'))
    assert card['model_version']==contract['primary_model']
    assert card['support_version']==contract['support']
    assert card['rule_version']==cfg['rule_version']==contract['state_rule']
    assert card['artifact_sha256']==sha(OUT/'data/runtime_models_joint_v2.joblib')==sha(OUT/'data/runtime_models_v1.joblib')
    assert card['state_config_sha256']==sha(OUT/'data/runtime_state_config_v4.json')
    assert cfg['lambda']==contract['lambda'] and cfg['history_high_threshold']==contract['history_high_threshold']
    assert card['first_train_rows']==138 and card['following_train_rows']==47 and card['following_reused_unchanged']
    p=card['parameter_calibration'];assert p['generator']==contract['generator'] and p['seed']==20261014 and p['tau']==1.0
    syn=csvread(ROOT/'统一数据与交接准备20261014/data/联合表达v2_全部折候选.csv')
    folds=json.loads((OUT/'data/fold_audit.json').read_text(encoding='utf-8'))
    assert len(syn)==1820 and len(folds)==20
    for f in folds:
        rr=[r for r in syn if int(r['seed'])==f['seed'] and int(r['fold'])==f['fold']]
        assert len(rr)==91 and Counter(r['final_level'] for r in rr)==Counter(f['quotas'])
        assert not set(f['train_ids'])&set(f['heldout_ids'])
        assert all(r['parent_id'] in f['train_ids'] for r in rr)
    rows=csvread(OUT/'results/predictions.csv');assert len(rows)==940
    summary=json.loads((OUT/'results/summary.json').read_text(encoding='utf-8'))
    assert summary['runtime_active_variant']==card['active_variant']==contract['primary_variant']
    assert summary['runtime_prespecified_variant']=='joint_mixed_intent'
    assert card['selection_is_post_development'] and not card['independent_selection_confirmation']
    assert card['first_oof_reference']==summary['metrics'][contract['primary_variant']]
    manifest=json.loads((OUT/'results/system_dry_run/frozen_run_manifest.json').read_text(encoding='utf-8'))
    assert manifest['model_version']==contract['primary_model'] and manifest['support_version']==contract['support']
    records=json.loads((OUT/'results/system_dry_run/records.json').read_text(encoding='utf-8'))
    assert len(records)==64 and all(r['support']['external_cloud_attempts']==0 for r in records)
    grouped={}
    for r in records:grouped.setdefault((r['case_id'],r['block']),[]).append(r)
    assert all(len(g)==4 and len({r['shared_analysis_sha256'] for r in g})==1 for g in grouped.values())
    assert len(json.loads((OUT/'results/real_two_point_profiles.json').read_text(encoding='utf-8')))==47
    return {'passed':True,'contract_version':contract['version'],'model':contract['primary_model'],
       'watched_files':len(contract['watched_sha256']),'shared_data_rows':1820,'predictions':940,
       'system_records':64,'same_primary_chain':True,'API_calls':0}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path);args=p.parse_args();proof=check()
    if args.output_dir:
        args.output_dir.mkdir(parents=True,exist_ok=True)
        (args.output_dir/'统一契约核验.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(proof,ensure_ascii=False))
