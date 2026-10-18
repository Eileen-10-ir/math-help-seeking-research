from pathlib import Path
import csv,json,hashlib
from datetime import datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
font=next((p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('C:/Windows/Fonts/simsun.ttc')] if p.exists()),None)
if font:
    font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
s=json.loads((OUT/'results/summary.json').read_text(encoding='utf-8'));m=s['metrics']
rr=list(csv.DictReader((OUT/'results/repeat_metrics.csv').open(encoding='utf-8-sig')))
names={'G0_synth':'G0：模板增强','G1_ALSP_synth':'G1：四维校准','G1_bank_uniform_synth':'同库不校准','G1_AP_synth':'同库仅AP校准','real_only':'仅真实训练','G0_mixed':'G0＋真实','G1_ALSP_mixed':'G1＋真实','G1_bank_uniform_mixed':'同库不校准＋真实','G1_AP_mixed':'同库仅AP＋真实','G1_raterA_synth':'四维：评分者A','G1_raterB_synth':'四维：评分者B'}
(OUT/'figures').mkdir(exist_ok=True)
fig,axs=plt.subplots(1,2,figsize=(11.8,4.8))
groups=[['G0_synth','G1_bank_uniform_synth','G1_AP_synth','G1_ALSP_synth'],['G0_mixed','G1_ALSP_mixed','real_only']]
colors=['#64748b','#9aa6a6','#83aaa4','#177b72']
for ai,(ax,keys) in enumerate(zip(axs,groups)):
    x=np.arange(len(keys));vals=[m[k]['macro_f1'] for k in keys]
    ax.bar(x,vals,color=colors[:len(keys)],width=.6,alpha=.85)
    for i,k in enumerate(keys):
        dots=[float(r['macro_f1']) for r in rr if r['variant']==k]
        ax.scatter(np.full(5,i)+np.linspace(-.16,.16,5),dots,color='#1e293b',s=19,zorder=3)
        ax.text(i,max(dots)+.024,f'{vals[i]:.3f}',ha='center',fontweight='bold')
    ax.set_xticks(x,[names[k].replace('：','\n') for k in keys]);ax.set_ylim(0,1)
    ax.set_ylabel('宏平均 F1');ax.grid(axis='y',alpha=.17);ax.set_axisbelow(True)
    ax.set_title(['主实验：仅合成文本训练','辅助实验：加入真实训练文本'][ai],pad=15)
fig.suptitle('G0 / G1 单轮识别对照',fontsize=16,fontweight='bold',y=1.01)
fig.text(.5,.015,'47名学生；相同学生切分与合成数量。柱为五次重复均值，点为各重复结果（不是置信区间）。\n回顾性内部评价；生成文本的独立人工语义审核待完成。',ha='center',fontsize=9,color='#475569')
fig.tight_layout(rect=(0,.11,1,.97))
for ext in ['png','pdf']:fig.savefig(OUT/f'figures/G0_G1识别比较.{ext}',dpi=180,bbox_inches='tight')
plt.close(fig)

lines=['# G0 / G1 生成器对照实验报告','', '日期：2026-10-14。状态：候选生成器与数值对照已完成；独立人工语义审核待完成。原有学生整体标签、数据库、网页模型及G0历史结果未改。','',
'## 一、先看结论','',
'1. **G1已把逐条四维均值用于选择文本语义配置。**它是基于经验特征的条件语法生成候选，已超出只调类别数量的G0；还不是经独立验证的学生心理/行为变化模型。',
'2. **仅合成训练时，G1宏F1从G0的0.460提高到0.574，准确率从49.8%提高到70.6%。**五次划分中宏F1均高于G0，但配对条件区间较宽，不能宣布总体上已经稳定优越。',
'3. **新增表达库本身贡献明显，四维校准的额外收益尚不稳。**同库不看四维的对照宏F1为0.555；G1比它高0.019，不能将相对G0的全部提升归因于四维校准。',
'4. **加入真实训练文本后，G1没有整体替代G0的证据。**两者宏F1约0.654与0.655，G1准确率更低，但高类和低类召回更高，形成错误类型上的权衡。',
'5. **保留G1候选，不替换现行模型。**下一步优先审查语义配置与低类覆盖，尤其是明确自主声明、方法线索及自主陈述。不能为提高成绩改变原标签。','',
'![G0/G1对照图](figures/G0_G1识别比较.png)','',
'## 二、完成了用户要求的哪些工作','',
'| 要求 | 完成内容 | 证据 |','|---|---|---|',
'| G0正式作为模板增强baseline | 原代码及历史结果按哈希归档，旧指标精确复现 | archive/；data/frozen_manifest.json |',
'| 四维均值建立G1候选 | 逐条联合向量→兼容语义配置→文本；原学生等级不变 | code/g1_generator.py；data/generated_outer_corpora.csv |',
'| 合成主训练对照 | G0与G1只用合成文本拟合分类器，训练真实部分仅校准和内层选择 | results/summary.json；data/fold_audit.json |',
'| 真实混合辅助 | 相同合成文本加入该折真实训练文本，并设仅真实组 | results/predictions.csv |',
'| 实时记录 | 开始、预检查、每折、每次重复、完成与复核均追加记录 | events.jsonl |','',
'## 三、方法与可复现设计','',
'真实R1为47名学生，每人一条，最终高/中/低为12/31/4。沿用既有五种子×四折学生切分。G1的距离带宽tau候选0.5/1/2，在外层训练部分再分三折，以仅合成训练的内层宏F1选择；外层只评价，不参与校准、词表拟合或选择。混合和AP消融沿用这个tau。',
'本轮“真实仅校准”具体指：均值、等级用于拟合生成条件分布；内层验证真实文本用于选tau，但不作为主线分类器拟合样本。它不是完全不利用真实文本信息的无监督模拟；真实外层严格留出。',
'每折各生成方案都生成高36、中36、低19，共91条遮罩后不重复文本；混合组再加35或36条真实训练文本。对照均用同一字符TF-IDF＋意图特征LR。原G0上限仅作为匹配训练预算，不宣称此比例复现真实人群。',
'G1先从同类训练学生抽一个完整四维向量，再按exp(−四维平方距离/(2tau²))在兼容配置中抽样，最后选一个未使用的表达。均匀对照在同一库中均匀抽配置，不参考四维；AP只使用A/P距离。训练候选库含1536种遮罩后表达（高576、中576、低384），词面/任务留出池与训练池不重叠，后者只做实现检查，未用来挑优。',
'A/L/S/P各自控制求助范围、学习诉求、信息呈现、尝试证据。配置分是旧细则的工程锚点，不是生成文本的人工评分。兼容配置造成的偏差被保留记录；缺少可达配置时不改真实分数。低类至少含方法线索这一结构限制也正是待改进的覆盖问题。',
'带宽较大意味着更宽松匹配，较小意味着更贴近目标配置。它经过内层比较，不因外层成绩再修改。五次划分、400次拟合；每折所有后代绑定训练学生。三类标签测试只看当前文本，不看测试学生四维人标。','',
'## 四、主实验与必要归因对照','',
'| 仅合成训练方案 | 宏F1 | 准确率 | 高类召回 | 中类召回 | 低类召回 |','|---|---:|---:|---:|---:|---:|']
for k in ['G0_synth','G1_bank_uniform_synth','G1_AP_synth','G1_ALSP_synth']:
    a=m[k];lines.append(f"|{names[k]}|{a['macro_f1']:.3f}|{a['accuracy']:.1%}|{a['recall_by_class']['high']:.1%}|{a['recall_by_class']['medium']:.1%}|{a['recall_by_class']['low']:.1%}|")
lines+=['','G1主要改善了中类识别；低类召回从40%下降到25%，不能用总体准确率掩盖这一点。低类只有4位，均值对个体非常敏感。',
'','| 主要差值 | 宏F1差 | 条件95%区间 |','|---|---:|---:|']
for r in s['comparisons'][:3]:
    a,b=r['comparison'].split(' minus ');lines.append(f"|{names[a]} − {names[b]}|{r['delta_macro_f1']:+.3f}|[{r['conditional_95_lo']:.3f}, {r['conditional_95_hi']:.3f}]|")
lines+=['','区间按47名学生配对bootstrap 2000次，每次抽取学生时携带其所有重复预测；仅反映已拟合折外预测的条件不确定性，不涵盖重训或历史开发的全部影响。三项区间均跨0，不声称独立贡献已确证，也不将五次重复当成五组新学生。','',
'## 五、混合训练辅助结果','',
'| 方案 | 宏F1 | 准确率 | 高类召回 | 低类召回 |','|---|---:|---:|---:|---:|']
for k in ['real_only','G0_mixed','G1_ALSP_mixed','G1_bank_uniform_mixed','G1_AP_mixed']:
    a=m[k];lines.append(f"|{names[k]}|{a['macro_f1']:.3f}|{a['accuracy']:.1%}|{a['high_recall']:.1%}|{a['recall_by_class']['low']:.1%}|")
lines+=['', '加入真实文本，G0宏F1增加0.195（条件区间0.052～0.329），G1增加0.081（−0.038～0.226）。这是各自训练方案内的比较，不证明真实数据可省略。G1混合相对G0混合的宏F1差约−0.001，准确率更低；低类召回更高，但低→高误分也从10%升至20%。不能只择一项指标宣称整体获胜。','',
'## 六、评分者与参数匹配敏感性','',
f"仅合成训练，用评分者A、两人均值、评分者B校准的宏F1分别为{m['G1_raterA_synth']['macro_f1']:.3f}、{m['G1_ALSP_synth']['macro_f1']:.3f}、{m['G1_raterB_synth']['macro_f1']:.3f}。三者都高于G0的本轮点估计，但仍不能证明L/S已可靠。没有根据较高成绩选择某位评分者来替代均值。",
f"20折选择tau的次数：{s['selected_tau_counts']}。说明没有一个在所有划分上占优的带宽。AP未单独重新选tau，因此消融解释限于共同带宽设置。",
'G1工程配置与目标均值的平均绝对距离约为A0.504、L0.724、S0.636、P0.459；同库均匀对照分别为0.611、1.408、1.527、0.884。它证明程序更接近目标配置，不能证明真人会给生成文本这些分数。按类别的完整诊断见profile_fidelity_by_class.csv。','',
'## 七、真实低类错例（原文与原标签保持）','']
cases=json.loads((OUT/'results/low_class_case_audit.json').read_text(encoding='utf-8'))
notes={'S0013':'最终low。G0与G1仅合成训练均未在五次留出中正确识别。G1低类语法主要要求过程线索，未覆盖这种直接声明自主学习的形式；旧G0也存在相似措辞的medium模板。这里只诊断生成器覆盖，不改真实结论。',
       'S0049':'最终low。G0仅合成五次均识别low，G1五次均识别medium。这说明G1并非普遍改善，方法线索与实际步骤之间的表述迁移仍有问题；这是待验证解释，不是已经定位到单一原因。',
       'S0053':'最终low。G1仅合成五次均正确，G0三次正确。与S0049内容相近但行为不同，说明对词面变化仍敏感。',
       'S0071':'最终low。两者仅合成五次均误判high；现有G1库没有自主陈述程序。其P均值为5不意味着必须把它生成成带实际演算的请求，这暴露了“只用四维分数不能唯一还原表达行为”的限制。'}
for c in cases:
    lines += [f"### {c['sample_id']}",'', '> '+c['prompt_text'],'',notes[c['sample_id']], '']
lines+=['## 八、逻辑验证与质量边界','',
'- 原始数据库、标签来源、G0代码和历史结果哈希未变；G0仅合成、G0混合、仅真实三组旧指标均复现。',
'- 20个外层、60个内层切分隔离通过；所有G1目标向量均可追到该折训练学生；120组外层生成语料的数量与类别配额核验通过。',
'- 所有生成语料与对应留出真实文本的完全重复、数学遮罩后重复均为0；未根据测试文本过滤生成。',
'- G1接口拒收真实原文；固定种子复现、每维扰动改变生成、AP不受L/S扰动影响、均匀对照不受评分扰动影响均通过。',
'- 独立复算程序从逐学生预测重建宏F1与准确率；从实际生成文本解析并检查43条因数组合、22条分数变换、21条一元一次变换和46条乘法陈述，无数值错误。这是自动覆盖到的132条数值断言，不等于全部文本的教学语义已审核。',
'- 共保存10920行跨折合成记录（含多个方案及重复），不是10920名新学生。外层各G1分支合计出现1411种不同遮罩表达。',
'- 已导出98条覆盖已观察语义配置及G0代表表达的盲审材料。生成者AI已阅读代表材料并记录自然度、结构覆盖与边界问题；未获得独立双人评分。所有生成记录仍标human_review=pending，不报告虚构人工通过率或κ。','',
'## 九、现在能说什么、接下来怎么做','',
'可报告：完成了四维联合校准的候选文本生成链，完成合成主训练与真实混合对照；相对旧模板G0，G1在当前内部评价中提高总体点估计，但四维校准本身的额外收益尚不明确，存在低类覆盖与误分权衡。',
'不可报告：完整学生行为模型已经验证；G1显著优于G0；四维评分可靠性已解决；生成轨迹证明学生依赖改善；已完成新的独立外部验证。',
'下一步优先进行生成文本的独立审查；以已有整体标准补足自主声明/自主陈述/方法线索的语义类型。必须新建版本与协议，保留本轮负结果，不按当前测试错例改完再把同一数据当全新验证。若调整涉及行为类型标签，可先小规模核对，不重标原有总体等级。只有语义覆盖与真实留出收益都支持，再考虑升级模型。','',
'## 十、复现与材料导航','',
'在项目根目录分别执行：','', '```powershell',
"& 'D:\\anaconda3\\python.exe' -s -X utf8 'G0_G1严谨对照20261014\\code\\run_comparison.py'",
"& 'D:\\anaconda3\\python.exe' -s -X utf8 'G0_G1严谨对照20261014\\code\\verify_results.py'",
"& 'D:\\anaconda3\\python.exe' -s -X utf8 'G0_G1严谨对照20261014\\code\\build_report.py'",'```','',
'原样重跑会重建结果并追加events日志；修改方法时必须另存新版本，不能覆盖本轮。报告图的点表示重复划分成绩，不是置信区间。',
'01_执行前协议.md：实验矩阵与选择规则。data/frozen_manifest.json：来源、协议和执行代码哈希。results/summary.json：全部指标。results/comparisons.csv：全部配对差值。data/generated_outer_corpora.csv：每折生成文本、目标和实现配置、父ID。review/盲审待填.csv：不含目标信息的审查表；目标与来源另存，审后才核对。events.jsonl：追加式实时记录。']
(OUT/'02_实验报告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
readme='''# 本轮交付导航

已完成G0冻结、G1四维候选、合成主训练比较、混合辅助对照和程序逻辑复核。独立人工语义审核待完成。

先读[实验报告](02_实验报告.md)，其中有结果图、完整对照表、真实错例与下一步取舍。

关键结果：仅合成G0/G1宏F1为0.460/0.574；同库不校准为0.555，四维校准的额外优势尚不明确。混合G0/G1为0.655/0.654。G1纯合成低类召回由40%降至25%，不能只看平均分升级。

- `01_执行前协议.md`：先固定方法再跑结果。
- `02_实验报告.md`：自包含报告。
- `03_生成器边界与审查说明.md`：配置分、原始均值和人工审查的区别。
- `archive/`：原G0代码与旧结果，不覆盖原文件。
- `code/`：生成、训练、交叉核验、报告脚本。
- `data/`：冻结清单、切分、候选库及全部外层生成文本。
- `results/`：逐学生预测、全部候选参数结果、配对比较、误分与核验。
- `review/`：98条盲审材料及审后核对密钥，不冒充已有人审。
- `figures/`：PNG/PDF结果图。
- `events.jsonl`：按阶段、每折追加的实时执行记录。

全部真实标签保留；没有新增学生、没有付费API调用、没有替换网页模型。此文件夹不是成员分工包，尚未对外分发。
'''
(OUT/'README.md').write_text(readme,encoding='utf-8')
event={'time':datetime.now().astimezone().isoformat(),'stage':'report_and_figures_generated','report':'02_实验报告.md','human_semantic_review':'pending'}
with (OUT/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
print(json.dumps(event,ensure_ascii=False))
