from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from pathlib import Path
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams['font.family']=font.get_name();plt.rcParams['axes.unicode_minus']=False
def J(name):return json.loads((OUT/'results'/name).read_text(encoding='utf-8'))
def C(name):return list(csv.DictReader((OUT/'results'/name).open(encoding='utf-8-sig')))
def names():return {'majority':'多数类','eedi_only':'Eedi辅助','real_only':'真实训练','eedi_real_llm':'Eedi＋真实＋允许改写',
 'parameter_primary':'参数主体','parameter_real':'参数＋真实','parameter_eedi_real_llm':'参数＋Eedi＋真实＋允许改写',
 'full':'融合','no_intent':'无意图特征','no_mask':'无遮蔽','no_balance':'无平衡','old_mask':'旧遮蔽',
 'r3_only':'仅当前R3','context':'直接拼接R1历史','context_guide':'拼接历史及回复类型','nested_context':'分块＋内折选历史权重'}
def run():
 n=names();e1=J('E1_summary.json');e2=J('E2_summary.json');e3=J('E3_summary.json');e3b=J('E3b_summary.json');u=J('prediction_uncertainty.json');e4=J('E4_observational.json');runtime=J('local_runtime.json')
 fig,axs=plt.subplots(1,2,figsize=(13,5.5))
 for ax,models,title,key,uscope in [(axs[0],e2,'R1：学生及后代隔离','macro_f1','E2_student_crossfit'),(axs[1],{**e3,**e3b['metrics']},'R3：四类回应识别','macro_f1','E3_r3_crossfit')]:
   ks=list(models);ys=np.arange(len(ks));means=[models[k][key]['mean'] for k in ks]
   intervals=[u['models'][uscope+'/'+k]['macro_f1_conditional95'] if k!='nested_context' else J('E3b_uncertainty.json')['model']['macro_f1_conditional95'] for k in ks]
   ax.errorbar(means,ys,xerr=np.array([[max(0,m-b[0]),max(0,b[1]-m)] for m,b in zip(means,intervals)]).T,fmt='o',capsize=3,color='#456fa8')
   ax.set_yticks(ys,[n[k] for k in ks]);ax.invert_yaxis();ax.set_xlim(0,1);ax.set_xlabel('Macro-F1');ax.set_title(title);ax.grid(axis='x',alpha=.18)
 fig.suptitle('数学识别重跑：每次仍为47名真实学生',fontsize=16)
 fig.text(.5,.01,'点为5次折外指标均值；线为固定预测、类别分层的学生重采样带，不覆盖完整拟合与历史选型不确定性。',ha='center',fontsize=9)
 fig.tight_layout(rect=(0,.04,1,.94));fig.savefig(OUT/'figures/识别重跑与条件不确定性.png',dpi=170);plt.close(fig)
 actions=C('E6_action_scenarios.csv');fig,axs=plt.subplots(1,4,figsize=(14,4.5),sharey=True)
 scenario_names={'zero_extra_effect':'无额外效果','uniform_benefit':'统一有益','matched_benefit':'匹配有益','mismatched_harm':'错配有害'}
 for ax,(sc,title) in zip(axs,scenario_names.items()):
   rr=[r for r in actions if r['scenario']==sc and r['policy']!='no_added_action'];ys=[float(r['low_difference_vs_baseline_mean'])*100 for r in rr];bs=[json.loads(r['low_difference_scenario95']) for r in rr]
   ax.bar([0,1],ys,color=['#456fa8','#9c7eaf'],width=.55);ax.errorbar([0,1],ys,yerr=np.array([[max(0,y-b[0]*100),max(0,b[1]*100-y)] for y,b in zip(ys,bs)]).T,fmt='none',color='#33415a',capsize=4)
   ax.set_xticks([0,1],['统一支持','分级支持']);ax.set_title(title);ax.axhline(0,color='#888',lw=.8);ax.grid(axis='y',alpha=.15)
 axs[0].set_ylabel('第8次low比例相对仿真基准差（百分点）')
 fig.suptitle('动作响应情景：分级支持的优势取决于假设和目标',fontsize=16)
 fig.text(.5,.01,'1000组转移抽样×1000模拟用户；响应参数为工程假设，基底来自历史混合引导，不是随机教育效果。',ha='center',fontsize=9)
 fig.tight_layout(rect=(0,.04,1,.94));fig.savefig(OUT/'figures/动作响应情景比较.png',dpi=170);plt.close(fig)
 lines=['# 数学主线严谨重跑结果总报告','',
 '2026-09-30。全部比较使用现有材料，无新增被试或付费云调用。原库与人标不变。协议在主实验运行前保存；上下文分块为看到拼接负结果后另行登记的补充。',
 '', '## 结论先读','',
 '数学主线可以继续形成方法与工程初稿。参数文本应作为真实校准的补充；简单增加数量或历史文本并不保证提高识别。回应证据门控有独立价值。教学分级在给定响应假设下才出现差异，现有问卷没有教育因果证据。','',
 '本轮真实47仍是回顾性开发资源，重新划分不能抹去历史看过标签和选型的事实。所有表中五次重复的有效学生数仍为47；R1低类4、R3高类7，罕见类结论尤需谨慎。',
 '', '## E1 组件与辅助来源','', '| 配置 | Eedi折外F1均值 | high召回 | 准确率 | 真实47诊断F1 |','|---|---:|---:|---:|---:|']
 for k,r in e1['public_oof'].items():lines.append(f"| {n[k]} | {r['macro_f1']['mean']:.3f} | {r['high_recall']['mean']:.3f} | {r['accuracy']['mean']:.3f} | {e1['real47_development'][k]['macro_f1']:.3f} |")
 lines+=['','类别平衡对高类召回和宏平均表现重要，但不保证准确率或Brier同时最优。意图特征的平均增量较小；不写完全冗余。公开池只有可追溯规范化文本组，原用户/题目关系缺失，不能声称已排除所有公开同源。',
 '', '## E2 真实学生及改写后代隔离','', '| 来源 | F1均值 | 种子范围 | high召回 | high→low |','|---|---:|---|---:|---:|']
 for k,r in e2.items():lines.append(f"| {n[k]} | {r['macro_f1']['mean']:.3f} | {r['macro_f1']['min']:.3f}—{r['macro_f1']['max']:.3f} | {r['high_recall']['mean']:.3f} | {r['high_to_low']['mean']:.3f} |")
 delta=u['contrasts']['E2_student_crossfit: parameter_real minus real_only']
 lines+=['',f"参数＋真实相对真实训练的F1增量为{delta['observed_mean_difference']:.3f}，学生配对条件重采样带[{delta['conditional95'][0]:.3f},{delta['conditional95'][1]:.3f}]，跨过0。参数主体提高某些高类召回，但总体F1仅{e2['parameter_primary']['macro_f1']['mean']:.3f}，不能取代真实校准。",
 '本轮参数初始比例只用训练折标签；没有用验证学生的R1、R3或后代标定。固定语法864行在有界遮蔽后仅120种独立表达，先去重再抽样；全量真实标定的演示训练采用91种参数表达＋47真实，共138条。工程标签待人工审核。',
 '', '## E3 后续回应与上下文','', '| 识别输入 | 四类F1均值 | high召回 | 种子范围 |','|---|---:|---:|---|']
 for k,r in {**e3,**e3b['metrics']}.items():lines.append(f"| {n[k]} | {r['macro_f1']['mean']:.3f} | {r['high_recall']['mean']:.3f} | {r['macro_f1']['min']:.3f}—{r['macro_f1']['max']:.3f} |")
 lines+=['','直接拼接历史损害当前R3识别；分块及内折选权重减少损失，仍未超过仅R3。20个外训练折中10次选择历史权重0。R1/R3字符长度中位数17/9提供输入占比线索，未证明唯一损害机制。',
 '仅R3的高类召回约0.314，说明总体F1不足以支持安全自动处理所有高依赖回应。R3四类标签沿用历史人标；短答案能否证明自主推理，需要独立语境复核。',
 '', '## E4 观察性标签变化','',
 '旧下降定义为24/47；接受类别暂不计改善后为10/47。匹配4/24、错配6/23，Fisher p=.494。按起点标准化后的下降记录比例约14.6%和27.7%，只是描述；自报选择与话术信息量等因素仍无法分离。',
 '排除14条接受/非提问后的敏感性口径为10/33；匹配4/18、错配6/15，Fisher p=.448。该排除依据引导后的回应，可能引入选择偏差，仅作为描述性敏感性分析。',
 '不按礼貌应答给心理依赖定级，不由错配结果推断人格，也不使用旧R3作为新路由的反事实效果。接受类别、只给答案、展示新推理、信息不足应分开。',
 '', '## E5 状态稳健性','',
 '保留此前240配置独立噪声实验，新增256配置：独立/成串误判、10%/25%噪声、4种序列、4个μ、4种规则，每配置250重复，另设15%低置信度。成串误判过程按平稳边际初始化，记录模拟标准误。',
 '在确认序列中，证据门控保持历史风险并请求更多信息；当前或无门控平滑方案会将确认当low下调。平滑能减少部分误触发，却增加突变响应延迟。当前明确high仍可能来自误判，门控不能替代识别质量。高等级判断与澄清请求分开计数，均不冒充实际云调用。',
 '低置信度与事件门控须区分：通用状态引擎对低置信度提问触发核实，但仍可更新状态；真实R3回放另加模型弱证据保持状态的处理。当前尚未形成实时各回合统一的弱证据更新规则，不声称所有低置信度回合都已暂停状态更新。',
 '', '## E6 动作真正进入转移','',
 '四种响应情景、每种1000个转移后验抽样、每抽样1000模拟用户、8次交互。动作按所假设响应改变转移概率，共同随机初始与扰动支持配对比较。',
 '| 响应假设 | 统一支持low差值（百分点） | 分级支持low差值（百分点） |','|---|---:|---:|']
 for sc,title in scenario_names.items():
    rr={r['policy']:r for r in actions if r['scenario']==sc};lines.append(f"| {title} | {float(rr['uniform_support']['low_difference_vs_baseline_mean'])*100:.2f} | {float(rr['graded_support']['low_difference_vs_baseline_mean'])*100:.2f} |")
 lines+=['','零额外效果下三个策略的逐用户轨迹完全相同，断言通过。统一有效情景中统一与分级同样改善。匹配有益时分级也不必在终点low比例上优于统一支持；在错配有害情景中差异由人工响应参数产生。基底为历史混合引导转移，仿真基准不能叫实测无引导自然过程。',
 '', '## 本地工程表现','',f"实际暖启动单条识别中位数{runtime['single_ms']['median']:.2f}ms，P95 {runtime['single_ms']['p95']:.2f}ms；模型包{runtime['model_bytes']/1024:.1f}KiB。是本机运行记录，不包含云通信、生成、冷启动或云边优越性验证。",
 '', '## 画像与论文可用范围','',
 '保留任务内依赖风险代理、事件与证据量、词句线索和支持建议；两点真实记录不判长期趋势。真实个案用于描述，受控八轮用于工程回放。R1/R3分数没有独立概率校准，不画成心理依赖百分比。',
 '本轮可直接写入初稿的是数据来源与同源处理、参数文本的补充效用及失败、历史输入表示的负结果、证据门控的状态取舍和动作情景敏感性。外测、长期效果、真实云边性能仍无相应数据。',
 '', '## 证据与待人工工作','',
 '全部逐样本预测、分折、内折选型、标定ID、语法去重、压力配置和情景轨迹在data/results；配对区间为固定预测条件重采样带。方法依据见可靠文献与项目应用。',
 '待成员独立填写：data/R3独立证据复核_A.csv及_B.csv（分别提供，隐藏旧等级和模型预测）；data/受控语法120条_人工审核.csv。生成审核表不等于人工审核已完成。新语法审核和R3证据裁定后需要保留版本，再执行受影响实验。']
 (OUT/'report/严谨重跑结果总报告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print('Built result report and two scientific figures.')
if __name__=='__main__':run()
