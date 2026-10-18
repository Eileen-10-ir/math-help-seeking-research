"""New joint-expression training and candidate runtime; frozen sources stay intact."""
import os
for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[key] = '1'
import sys, csv, json, hashlib, shutil, platform
from pathlib import Path
from collections import Counter
from datetime import datetime
import numpy as np
import sklearn, joblib
from sklearn.metrics import confusion_matrix, f1_score, accuracy_score

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parent
OLD = ROOT / '数学主线严谨重跑20260930'
sys.path[:0] = [str(OLD / 'code'), str(ROOT / '统一数据与交接准备20261014/code')]
from common import Classifier, LAB, SEEDS, load, F, B, metrics
from joint_renderer import sample_and_render, VERSION
from independent_contract_check import check_contract
from runtime_state_v4 import State, advance, RULE_VERSION
for folder in ['data', 'results', 'app']:
    (OUT / folder).mkdir(exist_ok=True)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readcsv(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def save(rel, data):
    (OUT / rel).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
def csvsave(rel, rows):
    with (OUT / rel).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def event(stage, **kw):
    data = {'time': datetime.now().astimezone().isoformat(), 'stage': stage, **kw}
    with (OUT / 'events.jsonl').open('a', encoding='utf-8') as f: f.write(json.dumps(data, ensure_ascii=False) + '\n')
    print(json.dumps(data, ensure_ascii=False), flush=True)
def metric_pred(truth, pred):
    cm = confusion_matrix(truth, pred, labels=LAB)
    return {'macro_f1': float(f1_score(truth, pred, labels=LAB, average='macro', zero_division=0)),
        'accuracy': float(accuracy_score(truth, pred)),
        'recall_by_class': {k: float(cm[i, i] / cm[i].sum()) for i, k in enumerate(LAB)},
        'high_to_low': float(cm[0, 2] / cm[0].sum()), 'low_to_high': float(cm[2, 0] / cm[2].sum()),
        'confusion_matrix': cm.tolist()}

def main():
    assert not (OUT / 'results/summary.json').exists(), 'Version already trained; preserve it and create a new output version.'
    sources = [ROOT / '统一数据与交接准备20261014/data/联合表达v2_全部折候选.csv',
        ROOT / '统一数据与交接准备20261014/data/参数说明_联合表达v2.json',
        ROOT / '统一数据与交接准备20261014/data/真实行为类型解释_机器候选.csv',
        ROOT / 'G0_G1严谨对照20261014/data/fold_audit.json',
        ROOT / '参数验证与生成器比较20261014/四维均值_真实R1_47条.csv',
        OLD / 'data/anonymous_samples_snapshot.json', OLD / 'data/runtime_models_v1.joblib',
        OLD / 'data/runtime_state_config_v4.json', OLD / 'results/recognition_predictions.csv',
        ROOT / 'G0_G1严谨对照20261014/results/predictions.csv',
        ROOT / 'G0_G1_融合候选20261014/results/predictions.csv',
        ROOT / '科研工作流与基线补强20261011/results/识别基线逐学生预测.csv',
        OUT / '01_执行前协议.md', Path(__file__),
        ROOT / '统一数据与交接准备20261014/code/joint_renderer.py',
        ROOT / '统一数据与交接准备20261014/code/independent_contract_check.py',
        OLD / 'code/common.py', OLD / 'code/runtime_state_v4.py',
        ROOT / '数学交互与论文初稿20261009/code/routing_v7.py']
    protected = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    save('data/input_hashes.json', protected)
    real, _, _, following = load()
    assert len(real) == len(following) == 47
    byid = {r['sample_id']: r for r in real}; ordered = [r['sample_id'] for r in real]
    joint = readcsv(sources[0]); specs = {r['candidate_id']: r for r in json.loads(sources[1].read_text(encoding='utf-8'))}
    assert len(joint) == 1820 and len(specs) == 1820
    folds = json.loads(sources[3].read_text(encoding='utf-8'))
    foldmap = {(r['seed'], r['fold']): r for r in folds}
    variants = [('joint_synth_intent', False, True), ('joint_mixed_intent', True, True),
                ('joint_synth_text', False, False), ('joint_mixed_text', True, False)]
    preds, audits, repeat = [], [], []
    event('training_start',variants=[r[0] for r in variants],real_students=47,protocol_sha256=sha(sources[12]))
    for fold in folds:
        seed, index = fold['seed'], fold['fold']
        tr = [r for r in real if r['sample_id'] in fold['train_ids']]
        te = [r for r in real if r['sample_id'] in fold['heldout_ids']]
        syn = [r for r in joint if int(r['seed']) == seed and int(r['fold']) == index]
        assert len(syn) == 91 and Counter(r['final_level'] for r in syn) == Counter(fold['quotas'])
        assert not {r['student_id'] for r in tr} & {r['student_id'] for r in te}
        assert len({B.safe_mask(F.normalize_prompt(r['prompt_text'])) for r in syn}) == 91
        for r in syn:
            spec = specs[r['candidate_id']]
            assert r['parent_id'] in fold['train_ids'] and r['parent_id'] not in fold['heldout_ids']
            assert float(spec['tau']) == float(fold['selected_tau'])
            assert check_contract(spec, r['prompt_text'], r['question'])['status'] == 'pass'
        for name, mixed, intent in variants:
            corpus = syn + tr if mixed else syn
            model = Classifier(intent=intent).fit([r['prompt_text'] for r in corpus], [r['final_level'] for r in corpus])
            p = model.probs([r['prompt_text'] for r in te])
            for r, prob in zip(te, p):
                preds.append({'variant': name, 'seed': seed, 'fold': index, 'sample_id': r['sample_id'],
                    'student_id': r['student_id'], 'truth': r['final_level'], 'prediction': LAB[int(prob.argmax())],
                    **{'p_' + k: float(prob[j]) for j, k in enumerate(LAB)}})
        audits.append({'seed': seed, 'fold': index, 'train_ids': fold['train_ids'], 'heldout_ids': fold['heldout_ids'],
            'joint_ids': [r['candidate_id'] for r in syn], 'synthetic_rows': len(syn), 'real_training_rows': len(tr),
            'quotas': fold['quotas'], 'inherited_tau': fold['selected_tau'], 'parent_isolation': True, 'text_contract': True})
        csvsave('results/predictions.csv', preds); save('data/fold_audit.json', audits)
        event('training_fold_complete',seed=seed,fold=index,fits_so_far=len(audits)*len(variants))
    # Reuse archived predictions only when their held-out students and labels match this protocol.
    references = []
    def reuse(path, mapping):
        for r in readcsv(path):
            if r['variant'] not in mapping: continue
            row = {**r, 'variant': mapping[r['variant']]}
            assert r['sample_id'] in foldmap[int(r['seed']), int(r['fold'])]['heldout_ids']
            assert r['truth'] == byid[r['sample_id']]['final_level']
            references.append(row)
    reuse(sources[9], {'G0_synth':'old_G0_synth', 'G0_mixed':'old_G0_mixed', 'G1_ALSP_synth':'old_G1_synth', 'G1_ALSP_mixed':'old_G1_mixed'})
    reuse(sources[10], {'fusion_equal_mixed':'old_fusion_equal_mixed'})
    reuse(sources[11], {'text_lr_real':'real_text_LR'})
    allrows = preds + references
    names = sorted({r['variant'] for r in allrows}); matrices = {}
    summaries = {}
    for name in names:
        matrix = []
        for seed in SEEDS:
            rr = {r['sample_id']: r for r in allrows if r['variant'] == name and int(r['seed']) == seed}
            assert len(rr) == 47 and set(rr) == set(ordered)
            pp = [rr[s]['prediction'] for s in ordered]; matrix.append([LAB.index(v) for v in pp])
            m = metric_pred([byid[s]['final_level'] for s in ordered], pp)
            if name.startswith('joint_'):
                probs = np.array([[float(rr[s]['p_' + k]) for k in LAB] for s in ordered])
                m['brier_multiclass'] = metrics([byid[s]['final_level'] for s in ordered], probs)['brier_multiclass']
            repeat.append({'variant': name, 'seed': seed, **m})
        matrices[name] = np.array(matrix)
        mm = [m for m in repeat if m['variant'] == name]
        summaries[name] = {k: float(np.mean([m[k] for m in mm])) for k in ['macro_f1','accuracy','high_to_low','low_to_high']}
        summaries[name]['recall_by_class'] = {k: float(np.mean([m['recall_by_class'][k] for m in mm])) for k in LAB}
        summaries[name]['confusion_matrix_sum_repeats'] = np.sum([m['confusion_matrix'] for m in mm], axis=0).tolist()
        if name.startswith('joint_'): summaries[name]['brier_multiclass'] = float(np.mean([m['brier_multiclass'] for m in mm]))
    save('results/repeat_metrics.json', repeat)
    csvsave('results/metrics_summary.csv', [{'variant': n, **{k:v for k,v in m.items() if not isinstance(v,(dict,list))},
        **{k+'_recall':m['recall_by_class'][k] for k in LAB}} for n,m in summaries.items()])
    yi = np.array([LAB.index(byid[s]['final_level']) for s in ordered]); rng = np.random.default_rng(20261014)
    def fastscore(p, ix):
        vals=[]
        for v in p:
            cm=np.bincount(yi[ix]*3+v[ix],minlength=9).reshape(3,3);den=cm.sum(0)+cm.sum(1)
            vals.append(np.divide(2*np.diag(cm),den,out=np.zeros(3),where=den>0).mean())
        return np.mean(vals)
    pairs=[('joint_synth_intent','old_G0_synth'),('joint_mixed_intent','old_G0_mixed'),
        ('joint_mixed_intent','old_fusion_equal_mixed'),('joint_mixed_intent','joint_synth_intent'),
        ('joint_mixed_text','real_text_LR'),('joint_mixed_text','joint_mixed_intent')]
    bootstrap={n:[] for n in names}
    for _ in range(1000):
        ix=rng.integers(0,47,47)
        for n in names:bootstrap[n].append(fastscore(matrices[n],ix))
    comparisons=[]
    for a,b in pairs:
        d=np.array(bootstrap[a])-np.array(bootstrap[b])
        comparisons.append({'candidate':a,'reference':b,'delta_macro_f1':summaries[a]['macro_f1']-summaries[b]['macro_f1'],
            'conditional_95_lo':float(np.quantile(d,.025)),'conditional_95_hi':float(np.quantile(d,.975))})
    csvsave('results/comparisons.csv',comparisons)
    # Full-fit candidate is chosen in the protocol before observing these scores.
    scores = readcsv(sources[4]); cal=[]
    for r in scores:
        cal.append({k:(float(v) if k.endswith(('_mean','_rater_A','_rater_B')) else v) for k,v in r.items()
                    if k in ['sample_id','student_id','final_level'] or k.endswith(('_mean','_rater_A','_rater_B'))})
    kinds={r['sample_id']:r['behavior_type'] for r in readcsv(sources[2])}
    fresh=sample_and_render(cal,kinds,{'high':36,'medium':36,'low':19},20261014,tau=1.0)
    for r in fresh: assert check_contract(r['spec'],r['prompt_text'],r['question'])['status']=='pass'
    save('data/runtime_joint_specs_and_texts.json',fresh)
    first=Classifier(intent=True).fit([r['prompt_text'] for r in fresh+real],
        [r['spec']['final_level_candidate'] if 'spec' in r else r['final_level'] for r in fresh+real])
    oldmodels=joblib.load(sources[6]); second=oldmodels['following']
    stage2texts=[r['prompt_text'] for r in following]
    before=second.probs(stage2texts,LAB+['接受引导/非提问'])
    artifact=OUT/'data/runtime_models_joint_v2.joblib'
    joblib.dump({'first':first,'following':second},artifact)
    # Legacy service resolves this compatibility filename within the new version only.
    shutil.copy2(artifact,OUT/'data/runtime_models_v1.joblib')
    after=joblib.load(artifact)['following'].probs(stage2texts,LAB+['接受引导/非提问'])
    assert np.array_equal(before,after)
    for name in ['anonymous_samples_snapshot.json','runtime_state_config_v4.json']:
        shutil.copy2(OLD/'data'/name,OUT/'data'/name)
    reference=summaries['joint_mixed_intent']
    card={'model_version':'math-joint-expression-v2-20261014','rule_version':RULE_VERSION,
        'artifact_sha256':sha(artifact),'snapshot_sha256':sha(OUT/'data/anonymous_samples_snapshot.json'),
        'state_config_sha256':sha(OUT/'data/runtime_state_config_v4.json'),'first_train_rows':138,'following_train_rows':47,
        'first_real_ids':ordered,'following_real_ids':[r['sample_id'] for r in following],
        'parameter_calibration':{'generator':VERSION,'seed':20261014,'tau':1.0,'quotas':{'high':36,'medium':36,'low':19},
            'calibration_ids':ordered,'raw_prompt_not_generator_input':True,'score_type':'double_rater_mean'},
        'first_candidate':'joint_mixed_intent_prespecified_for_integration_not_best_score_selection',
        'first_oof_reference':reference,'fullfit_tau_differs_from_fold_inherited_tau':True,
        'following_reused_unchanged':True,'following_oof_reference':'historical E3 r3_only macroF1 ~0.611',
        'state_config_reused_not_new_model_calibrated':True,'support_version':'conversation-support-v7-20261014',
        'runtime':{'python':platform.python_version(),'sklearn':sklearn.__version__},
        'limits':['internal post-development candidate evaluation','independent semantic review pending',
                  'no fullfit training accuracy reported','p_high uncalibrated','historical threshold not validated for new model',
                  'no new student behavioral effectiveness evidence']}
    save('data/runtime_model_card.json',card)
    # Real two-point OOF replay: predicted signals only, labels saved for display.
    historical=readcsv(sources[8]); cfg=json.loads(sources[7].read_text(encoding='utf-8')); replay=[]
    for later in following:
        r=byid[later['pair_id']]; state=State()
        first_rows=[p for p in preds if p['variant']=='joint_mixed_intent' and p['sample_id']==r['sample_id']]
        second_rows=[p for p in historical if p['experiment']=='E3_r3_crossfit' and p['variant']=='r3_only' and p['sample_id']==later['sample_id']]
        assert len(first_rows)==len(second_rows)==5
        p1={k:float(np.mean([float(p['p_'+k]) for p in first_rows])) for k in LAB}
        p2={k:float(np.mean([float(p['p_'+k]) for p in second_rows])) for k in LAB+['接受引导/非提问']}
        a=advance(state,r['prompt_text'],p1,cfg); b=advance(state,later['prompt_text'],p2,cfg)
        replay.append({'student_id':r['student_id'],'source':'real_vignette_two_texts_OOF_system_replay_not_intervention',
            'r1_text':r['prompt_text'],'r3_text':later['prompt_text'],'original_labels':[r['final_level'],later['final_level']],
            'r1_analysis':a,'r3_analysis':b,'state':vars(state)})
    save('results/real_two_point_profiles.json',replay)
    shutil.copytree(ROOT/'数学交互与论文初稿20261009/app',OUT/'app',dirs_exist_ok=True)
    html=(OUT/'app/index.html').read_text(encoding='utf-8')
    html=html.replace('历史47名学生的初次提问Macro-F1约0.655',f"联合表达v2候选：历史47名学生内部首轮Macro-F1约{reference['macro_f1']:.3f}，准确率约{reference['accuracy']*100:.1f}%")
    html=html.replace('数学求助 · 连续交流与画像','数学求助 · 联合表达v2连续交流')
    (OUT/'app/index.html').write_text(html,encoding='utf-8')
    assert all(sha(ROOT/p)==h for p,h in protected.items())
    outcome={'status':'new_joint_training_and_runtime_complete_integration_pending','new_variants':[r[0] for r in variants],
        'real_students':47,'repeats':5,'folds':20,'new_fits':80,'predictions':len(preds),'metrics':summaries,
        'comparisons':comparisons,'runtime_prespecified_variant':'joint_mixed_intent','runtime_model_sha256':sha(artifact),
        'runtime_training_rows':138,'following_reused_unchanged':True,'real_two_point_profiles':len(replay),
        'source_hashes_unchanged':True,'paid_calls':0,'independent_human_review':'pending'}
    save('results/summary.json',outcome)
    event('training_complete',metrics={k:{m:round(v[m],4) for m in ['macro_f1','accuracy','low_to_high']} for k,v in summaries.items()},runtime_model=card['model_version'])

if __name__=='__main__':main()
