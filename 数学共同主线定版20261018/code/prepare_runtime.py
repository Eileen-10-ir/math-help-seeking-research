"""Freeze selected trained objects/config/frontend, preserving the prior chain."""
from pathlib import Path
import sys,json,hashlib,shutil,math
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
sys.path.insert(0,str(OUT/'code'))
from state_v5 import RULE_VERSION
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

if __name__=='__main__':
    base=ROOT/'联合表达v2数学全线20261014'
    cfg=read(OUT/'data/runtime_state_config_v5.json')
    # Historical metadata must not appear to be a newly validated current setting.
    save(OUT/'data/state_stage_output_before_metadata_cleanup.json',cfg)
    cfg['legacy_threshold_reference']={'source':cfg.get('threshold_source'),'grid':cfg.pop('threshold_candidates',[])}
    cfg.pop('protocol_sha256',None)
    cfg['lambda_half_life_in_valid_updates']=math.log(.5)/math.log(1-cfg['lambda'])
    cfg['protocol_sha256']=sha(OUT/'01_执行前协议.md')
    for name in ['runtime_state_config_v5.json','runtime_state_config_v4.json']:save(OUT/'data'/name,cfg)
    for name in ['anonymous_samples_snapshot.json','runtime_joint_specs_and_texts.json','fold_audit.json']:
        shutil.copy2(base/'data'/name,OUT/'data'/name)
    recognition=read(OUT/'results/recognition_summary.json');card=read(base/'data/runtime_model_card.json')
    card.update(model_version='math-joint-v2-state5-20261018',rule_version=RULE_VERSION,
        artifact_sha256=sha(OUT/'data/runtime_models_v1.joblib'),snapshot_sha256=sha(OUT/'data/anonymous_samples_snapshot.json'),
        state_config_sha256=sha(OUT/'data/runtime_state_config_v4.json'),active_variant=recognition['selected_first'],
        following_variant=recognition['selected_following'],cloud_alias='deepseek-flash',
        first_oof_reference=next(r for r in recognition['metrics'] if r['variant']==recognition['selected_first']),
        following_oof_reference=next(r for r in recognition['metrics'] if r['variant']==recognition['selected_following']),
        state_config_reused_not_new_model_calibrated=False,stage_cutoffs=cfg['stage_cutoffs'],
        selection_is_post_development=True,independent_selection_confirmation=False,
        following_reused_unchanged=False,following_status='same LR settings/full real data refitted; common student folds newly evaluated',
        state_status='training-inner gate workpoint; history and alpha engineering controls, not longitudinal validation')
    card['limits']=['internal post-development evaluation','independent generated semantic review pending',
        'R3 held-out acceptance agreement ~80%, below training design target; errors retained',
        'classifier scores not independently calibrated probabilities','no new student behavioral effect',
        'new version real API quality and resource comparison pending']
    save(OUT/'data/runtime_model_card.json',card)
    shutil.copytree(base/'app',OUT/'app',dirs_exist_ok=True)
    path=OUT/'app/index.html';html=path.read_text(encoding='utf-8')
    html=html.replace('联合表达v2连续交流','联合参数化 · 动态证据更新')
    html=html.replace('后续四类约0.611，高类召回约0.314','后续共同学生切分四类约0.599，高类召回约0.286')
    html=html.replace('后续自动判断覆盖有限','后续门槛已有训练内选择，仍需核验误更新')
    path.write_text(html,encoding='utf-8')
    path=OUT/'app/app.js';js=path.read_text(encoding='utf-8')
    start=js.index("$('coefficient-source').textContent=")
    end=js.index(';const previous=',start)
    replacement="$('coefficient-source').textContent=`本轮接纳门槛：首轮 ${config.state_config.stage_cutoffs.R1}，后续 ${config.state_config.stage_cutoffs.R3}；由训练内预测选择。λ=${config.state_config.lambda}来自固定工程信号比较；明确新证据及连续非高证据可解除历史保护。累计风险保持实际EWMA，不因换路清零。`"
    js=js[:start]+replacement+js[end:]
    js=js.replace("localStorage.getItem('math-live-session')","localStorage.getItem('math-current-state5-session')").replace("localStorage.setItem('math-live-session'","localStorage.setItem('math-current-state5-session'")
    path.write_text(js,encoding='utf-8')
    print(json.dumps({'model':card['model_version'],'cutoffs':cfg['stage_cutoffs'],'alpha':cfg['lambda'],'runtime_prepared':True},ensure_ascii=False))
