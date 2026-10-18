"""Capture the selected working point after documents and checks exist."""
from pathlib import Path
import json,hashlib
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if __name__=='__main__':
    card=read(OUT/'data/runtime_model_card.json');cfg=read(OUT/'data/runtime_state_config_v5.json')
    original=read(ROOT/'联合表达v2数学全线20261014/data/统一主线交接契约.json')
    paths={ROOT/p for p in original['watched_sha256']}
    paths.update(p for d in ['code','app','data'] for p in (OUT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts
                 and p.name!='统一主线交接契约.json')
    paths.update(OUT.glob('*.md'))
    paths.update(p for p in (OUT/'review').rglob('*') if p.is_file())
    for rel in ['results/recognition_predictions.csv','results/recognition_metrics.csv','results/recognition_repeats.csv',
                'results/recognition_summary.json','results/gate_selection.json','results/gate_oof_rows.csv','results/gate_oof_summary.csv',
                'results/history_controls.csv','results/alpha_traces.csv','results/alpha_sensitivity.json','results/state_review.json',
                'results/system_dry_run02/records.json','results/system_dry_run02/summary.json','results/system_dry_run02/frozen_run_manifest.json']:
        paths.add(OUT/rel)
    for folder in ['G0_G1严谨对照20261014/code','统一数据与交接准备20261014/code']:
        paths.update((ROOT/folder).glob('*.py'))
    paths.update([ROOT/'参数验证与生成器比较20261014/四维均值_真实R1_47条.csv',
        ROOT/'统一数据与交接准备20261014/data/真实行为类型解释_机器候选.csv'])
    contract={'version':'math-shared-handoff-20261018-r1','primary_model':card['model_version'],
        'first_variant':card['active_variant'],'following_variant':card['following_variant'],'generator':'joint-expression-v2-20261014',
        'state_rule':cfg['rule_version'],'stage_cutoffs':cfg['stage_cutoffs'],'alpha':cfg['lambda'],
        'history_policy':cfg['history_policy'],'history_high_threshold':.5,'support':'conversation-support-v7-20261014',
        'environment':original['environment'],'data':{'real_students':47,'expressions':94,'fold_synthetics':1820,
            'outer_repeats':5,'outer_folds_per_repeat':4,'runtime_first_training':138,'runtime_following_training':47},
        'evaluation':'internal retrospective development; common student outer folds; no untouched external test',
        'route_policy':original['route_policy'],'cloud_request':original['cloud_request'],
        'metrics_denominators_file':'04_数据与指标统一口径.md','quality_rules_file':'05_共同回复评分规程.md',
        'pending':['independent semantics','formal current-version real API quality/resource comparison','real student effects'],
        'state_warning':'held-out subsequent accepted label agreement ~80.2%; 85% was inner target, not achieved outer guarantee',
        'watched_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)}}
    (OUT/'data/统一主线交接契约.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'contract':contract['version'],'watched_files':len(paths),'model':card['model_version']},ensure_ascii=False))
