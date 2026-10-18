"""Consolidate the completed new-model chain and readable evidence report."""
import json, hashlib, csv
from pathlib import Path
from collections import Counter
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
summary=json.loads((OUT/'results/summary.json').read_text(encoding='utf-8'))
training=json.loads((OUT/'results/训练独立核验.json').read_text(encoding='utf-8'))
proofs=sorted((OUT/'results/mainline_verification').glob('*/核验结果.json'),key=lambda p:p.stat().st_mtime)
mainline=json.loads(proofs[-1].read_text(encoding='utf-8'))
assert mainline['passed'] and mainline['external_paid_calls']==0 and mainline['model_version']=='math-joint-expression-v2-20261014'
records=json.loads((OUT/'results/system_dry_run/records.json').read_text(encoding='utf-8'))
manifest=json.loads((OUT/'results/system_dry_run/frozen_run_manifest.json').read_text(encoding='utf-8'))
assert manifest['model_version']==mainline['model_version']
assert len(records)==64 and Counter(r['arm'] for r in records)==Counter(cloud_direct=16,edge_fixed=16,hybrid=16,cloud_constrained=16)
group={}
for r in records:
    group.setdefault((r['case_id'],r['block']),[]).append(r)
    assert r['support']['external_cloud_attempts']==0
    assert r['support'].get('usage') is None and r['cost_estimate'] is None
for rr in group.values():
    assert len(rr)==4 and len({r['shared_analysis_sha256'] for r in rr})==1
    assert all(r['initial_state']==rr[0]['initial_state'] and r['history']==rr[0]['history'] for r in rr)
replay=json.loads((OUT/'results/real_two_point_profiles.json').read_text(encoding='utf-8'))
assert len(replay)==47 and len({r['student_id'] for r in replay})==47
for r in replay:
    assert r['source']=='real_vignette_two_texts_OOF_system_replay_not_intervention'
    if r['r3_analysis']['observed_event']=='ack': assert not r['r3_analysis']['risk_updated']
card=json.loads((OUT/'data/runtime_model_card.json').read_text(encoding='utf-8'))
assert sha(OUT/'data/runtime_models_joint_v2.joblib')==card['artifact_sha256']
verified={'status':'new_joint_version_chain_completed','model_version':card['model_version'],
    'training_verified':training,'mainline_verified':{k:v for k,v in mainline.items() if k!='session'},
    'system_records':64,'system_shared_analysis_across_arms':True,'system_external_calls':0,
    'real_two_point_profiles':47,'runtime_first_train_rows':138,'following_stage_reused_unchanged':True,
    'independent_semantic_review':'pending','actual_cloud_quality_and_cost_for_new_model':'pending',
    'current_old_running_service_overwritten':False,'source_labels_changed':False}
(OUT/'results/新版本全线验收.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding='utf-8')
text='''# 新联合参数化数据：数学全线运行报告

2026-10-14。新联合表达v2已完成识别训练、真实学生留出评价、全量运行模型、47人真实两点折外状态回放、连续交互与四组离线路由核验。原标签、模型和旧实验保留，付费调用0次。

## 新版本实际使用什么

数据为G1四维均值校准参数＋G0题目/已有语言部件的联合表达v2，不是将旧G0/G1两批文本混合。外层沿用五种子四折，每折仅训练学生校准、91条合成。测试是该折真实留出学生。

新模型的全量接入首轮训练为47真实＋91联合表达＝138条；后续复用47条真实R3训练的模型。后续模型未增加虚构四维人标。网页用新首轮模型、原状态v4和支持v7，支持Markdown/公式与连续题目背景。

## 真实留出结果

| 方案 | 宏F1 | 准确率 | 高类召回 | 低类召回 | 低→高 |
|---|---:|---:|---:|---:|---:|
'''
names=[('joint_synth_intent','联合仅合成＋意图LR'),('joint_mixed_intent','联合＋真实＋意图LR（接入候选）'),
       ('joint_synth_text','联合仅合成＋文本LR'),('joint_mixed_text','联合＋真实＋文本LR'),
       ('old_G0_mixed','旧G0＋真实＋意图LR'),('old_fusion_equal_mixed','旧两份语料等量融合＋真实'),
       ('real_text_LR','仅真实＋文本LR')]
for k,name in names:
    m=summary['metrics'][k]
    text+=f"| {name} | {m['macro_f1']:.3f} | {m['accuracy']*100:.1f}% | {m['recall_by_class']['high']*100:.1f}% | {m['recall_by_class']['low']*100:.1f}% | {m['low_to_high']*100:.1f}% |\n"
text+='''
这些是同47人五次重复的内部回顾性评价；宏F1是每种子汇总47条折外预测后计算，再平均。235次预测不计235名学生。旧结果复用原逐学生预测并检查同折留出和标签一致。

接入候选在结果前选定带意图联合混合模型，宏F1约0.627，不能宣称超过旧G0混合0.655。联合混合仅文本方案约0.678，也未超过真实训练文本LR约0.734。生成路线的解释性与识别收益分别判断；不能用一次最高分宣布新路线最佳。各类混淆、配对差值与条件区间见results。

全量运行生成tau固定1.0；外层评价tau继承旧G1的同折训练内选择。两者属于同一路线的不同拟合设置，模型卡标明差异，折外成绩不当全量模型的独立实测。新表达器自己的内层选参、四维消融和审核后版本可由成员继续完成。

## 主线核验结果

- 80次外层拟合，4个新方案共940条折外预测；分母、概率和混淆矩阵由独立脚本重算通过。
- 新运行模型138条训练，模型哈希、后续模型复用一致性通过。
- 47名学生真实两点使用折外信号回放，保留原文和原标签；不是新系统引导后的反馈。
- 连续4轮本机HTTP工程核验通过：新模型识别、题目保持、实际回复历史、EWMA、确认不更新、三路路由、会话导出及前端关键资源。
- 8案例×2次×4组64条新模型系统离线记录，同病例识别/初始状态/历史一致，外部调用0次。云回复质量和成本没有用离线占位数据计算。

## 使用与下一阶段

新版本已可运行，现有旧服务没有被覆盖。需要查看新模型时按README启动独立端口。首先在新模型上做方法诊断和正式共同协议，再进行扩展系统基线、真实API及独立内容评分；不再把首次训练/接入留作未完成工作。

集中待办：生成文本独立语义审核；新模型后续部署误挡诊断及状态阈值标定；识别方案择优；系统质量/费用比较与真实行为验证。程序核验不替代这些实证。
'''
(OUT/'03_运行报告.md').write_text(text,encoding='utf-8')
readme='''# 联合表达v2数学新版本

主线已用新联合数据完成训练、评价和接入。先读`03_运行报告.md`，验收证据为`results/新版本全线验收.json`。

从研究工作区根目录执行：

```powershell
python -X utf8 联合表达v2数学全线20261014/code/verify_training_results.py
python -X utf8 联合表达v2数学全线20261014/code/verify_new_mainline.py
python -X utf8 联合表达v2数学全线20261014/code/runtime_joint.py --port 8770
```

网页地址`http://127.0.0.1:8770/`，后台明确显示新模型版本。未配置密钥时云端没有实际回答，可检查本地识别与连续交互；真实云请求需本机API。工程核验使用本机假API，不耗真实额度。

完整训练复现写全新目录（目录不能预先存在）：

```powershell
python -X utf8 联合表达v2数学全线20261014/code/reproduce_training.py --output-dir 交付结果/联合v2训练复现01
```

新模型四组对照默认离线：

```powershell
python -X utf8 联合表达v2数学全线20261014/code/run_system_new_model.py --output-dir 交付结果/新模型系统离线01
```

所有运行记录与结果注明模型和支持版本。原网页、模型和旧实验保留。当前模型是开发接入候选，独立语义及回复审核待完成。
'''
(OUT/'README.md').write_text(readme,encoding='utf-8')
print(json.dumps({k:v for k,v in verified.items() if k not in ('training_verified','mainline_verified')},ensure_ascii=False))
