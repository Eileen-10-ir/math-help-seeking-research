"""Freeze one explicit new-method research contract without retraining or altering data."""
import json, hashlib, csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
card=json.loads((OUT/'data/runtime_model_card.json').read_text(encoding='utf-8'))
cfg=json.loads((OUT/'data/runtime_state_config_v4.json').read_text(encoding='utf-8'))
full=json.loads((OUT/'results/新版本全线验收.json').read_text(encoding='utf-8'))
assert full['status']=='new_joint_version_chain_completed'
paths=[OUT/'data/runtime_models_joint_v2.joblib',OUT/'data/runtime_models_v1.joblib',OUT/'data/runtime_model_card.json',
       OUT/'data/runtime_state_config_v4.json',OUT/'data/runtime_joint_specs_and_texts.json',OUT/'data/anonymous_samples_snapshot.json',
       OUT/'data/fold_audit.json',OUT/'results/predictions.csv',OUT/'results/summary.json',OUT/'results/real_two_point_profiles.json',
       ROOT/'统一数据与交接准备20261014/data/数学真实94条_研究只读导出.sqlite3',
       ROOT/'统一数据与交接准备20261014/data/联合表达v2_全部折候选.csv',
       ROOT/'统一数据与交接准备20261014/data/参数说明_联合表达v2.json',
       ROOT/'统一数据与交接准备20261014/code/joint_renderer.py',
       ROOT/'统一数据与交接准备20261014/code/independent_contract_check.py',
       ROOT/'数学主线严谨重跑20260930/code/common.py',ROOT/'数学主线严谨重跑20260930/code/legacy_features.py',
       ROOT/'数学主线严谨重跑20260930/code/bounded_mask.py',ROOT/'数学主线严谨重跑20260930/code/runtime_state_v4.py',
       ROOT/'数学主线严谨重跑20260930/code/evidence_runtime.py',ROOT/'数学主线严谨重跑20260930/code/cloud_gateway.py',
       ROOT/'数学主线严谨重跑20260930/code/runtime_server.py',ROOT/'数学主线严谨重跑20260930/code/routing_v4.py',
       ROOT/'数学交互与论文初稿20261009/code/routing_v6.py',ROOT/'数学交互与论文初稿20261009/code/routing_v7.py',
       ROOT/'数学交互与论文初稿20261009/code/runtime_server_v6.py',
       ROOT/'云边教学与成本复核20261001/code/runtime_server_v5.py',ROOT/'云边教学与成本复核20261001/code/routing_v5.py',
       ROOT/'云边教学与成本复核20261001/data/E13_cost_guidance_protocol_v2.json',
       ROOT/'系统支持修正v7_20261014/code/run_system_comparison.py',
       OUT/'code/runtime_joint.py',OUT/'code/run_system_new_model.py',OUT/'code/run_mainline.py',
       OUT/'code/verify_training_results.py',OUT/'code/verify_new_mainline.py',OUT/'code/check_handoff_contract.py',
       OUT/'code/check_environment.py',OUT/'code/reproduce_training.py',
       OUT/'code/select_runtime_text.py',OUT/'data/state_parameter_review_20261015.json',
       OUT/'01_执行前协议.md',OUT/'02_固定输入系统对照协议.md',OUT/'00_统一主线交接说明.md']
paths += [p for p in (OUT/'app').rglob('*') if p.is_file()]
contract={'version':'math-joint-v2-handoff-20261015-r3','frozen_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'environment':{'python_minor':'3.13','numpy':'2.1.3','scipy':'1.15.3','sklearn':'1.6.1','joblib':'1.4.2'},
    'primary_model':card['model_version'],'primary_variant':card['active_variant'],
    'runtime_selection':'post-development operational selection; not independent confirmation',
    'generator':'joint-expression-v2-20261014','support':'conversation-support-v7-20261014',
    'state_rule':cfg['rule_version'],'lambda':cfg['lambda'],'history_high_threshold':cfg['history_high_threshold'],
    'state_threshold_origin':'engineering reference retained; active text classifier proxy review in state_parameter_review_20261015.json; not cumulative-state optimum',
    'runtime_first_training':{'real':47,'joint_synthetic':91,'total':138,'seed':20261014,'tau':1.0},
    'runtime_following_training':{'real':47,'synthetic':0,'reused_unchanged':True},
    'evaluation':{'students':47,'repeats':5,'outer_folds':20,'new_variants':4,'new_predictions':940,
                  'scope':'internal retrospective; no untouched external test','tau':'inherited fold training-inner choice'},
    'route_policy':{'low':'cloud_direct','medium':'cloud_constrained','high':'edge_fixed',
                    'unknown':'separate verify or bounded hint; state not updated','ACK':'separate; state not updated'},
    'cloud_request':{'provider':'official DeepSeek','alias':'deepseek-flash','temperature':.2,
                     'thinking':'disabled','max_tokens':768,'timeout_seconds':30,'max_requests_per_initial_batch':48},
    'system_cases_source':'same 8-case protocol from support v7; 2 blocks; 4 arms',
    'system_cases_model_version':card['model_version'],
    'metrics_denominators':{'recognition':'47 held-out students per repeat; do not count 235 unique students',
         'cloud_rate':'all executed case-turns in each arm; failed requests counted',
         'cloud_success':'actual external attempts','response_quality':'independently scored applicable outputs; NA and coverage reported',
         'answer_leakage':'applicable restricted medium/high turns; disclosure and policy violation separated',
         'latency':'actual execution only; failures and completed outputs separately reported',
         'cost':'actual usage and contemporaneous official rates; missing usage unknown'},
    'completed_by_project_lead':['shared new data','initial training and held-out evaluation','new runtime model',
          'two-point OOF profiles','continuous mainline integration','system offline checks','portable package'],
    'team_next_work':['formal paired system baseline comparison','independent generated-text and response review',
           'necessary ablation and error diagnosis','quality-cost analysis and report evidence'],
    'pending_evidence':['independent generated semantics','new-model real API and response quality',
           'state threshold transfer evaluation','original full ALSP/M/H risk formula','real behavioral improvement'],
    'watched_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}}
target=OUT/'data/统一主线交接契约.json'
target.write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'contract':str(target),'watched_files':len(contract['watched_sha256']),'model':card['model_version']},ensure_ascii=False))
