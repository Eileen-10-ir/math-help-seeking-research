"""Generate v4 report/figure from E11/E12 and engineering acceptance records."""
from common import *
from routing_v4 import HIGH_REPLY,MEDIUM_SUFFIX
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

def read(p):return json.loads((OUT/p).read_text(encoding='utf-8'))
def rows(p):return list(csv.DictReader((OUT/p).open(encoding='utf-8-sig')))

def run():
 cfg=read('data/runtime_state_config_v4.json');e11=rows('results/E11_ewma_summary.csv');e12=rows('results/E12_real_sensitivity_summary.csv');qa=read('results/v4_HTTP云边验收.json')
 dev=[r for r in e11 if r['split']=='development'];held=[r for r in e11 if r['split']=='heldout'];font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
 fig,axes=plt.subplots(1,2,figsize=(12,4.8));x=[float(r['lambda']) for r in dev]
 for rr,label,color in [(dev,'开发配置','#367d89'),(held,'留出配置','#b56835')]:
  axes[0].errorbar(x,[float(r['filter_mse_mean']) for r in rr],yerr=[1.96*float(r['filter_mse_mcse']) for r in rr],fmt='o-',label=label,color=color,capsize=3)
 axes[0].set_ylabel('过滤 MSE（构造高类指示信号）',fontproperties=font);axes[0].set_title('选择只用开发配置，留出配置用于检查',fontproperties=font);axes[0].legend(prop=font)
 axes[1].plot(x,[100*float(r['persistent_low_false_high_mean']) for r in held],'o-',color='#367d89');axes[1].set_ylabel('持续低类场景误高率（%）',fontproperties=font,color='#367d89')
 twin=axes[1].twinx();twin.plot(x,[float(r['sudden_high_delay_mean']) for r in held],'s--',color='#b56835');twin.set_ylabel('突变判高延迟（输入轮次）',fontproperties=font,color='#b56835');axes[1].set_title('留出配置：抗噪声与突变响应的取舍',fontproperties=font)
 for ax in axes:ax.set_xlabel('EWMA 更新系数 λ',fontproperties=font);ax.set_xticks(x);ax.grid(alpha=.15)
 fig.text(.5,.01,'工程模拟，非真实学生；误差线仅为模拟均值的 ±1.96 MCSE，非教育效果置信区间',ha='center',fontproperties=font,fontsize=10)
 fig.tight_layout(rect=[0,.065,1,1]);fig.savefig(OUT/'figures/E11_EWMA系数依据与取舍.png',dpi=170);plt.close(fig)
 table='| λ | 开发过滤MSE | 留出过滤MSE | 留出持续低类误高率 | 留出突变判高延迟 |\n|---:|---:|---:|---:|---:|\n'
 for a,b in zip(dev,held):table+=f"| {float(a['lambda']):g} | {float(a['filter_mse_mean']):.6f} | {float(b['filter_mse_mean']):.6f} | {float(b['persistent_low_false_high_mean']):.2%} | {float(b['sudden_high_delay_mean']):.2f} |\n"
 selected=next(r for r in held if float(r['lambda'])==cfg['lambda']);baseline=next(r for r in held if float(r['lambda'])==1);gain=1-float(selected['filter_mse_mean'])/float(baseline['filter_mse_mean'])
 sensitivity='| λ | R3可更新覆盖 | 历史高档保护触发比例 | 已判断子集路由准确率 | ACK更新次数 | 有状态者平均R3状态 |\n|---:|---:|---:|---:|---:|---:|\n'
 for r in e12:sensitivity+=f"| {float(r['lambda']):g} | {float(r['r3_update_fraction']):.1%} | {float(r['history_high_protection_fraction']):.1%} | {float(r['accepted_route_accuracy']):.1%} | {int(r['ACK_update_count'])} | {float(r['mean_state_after_R3']):.3f} |\n"
 report=f'''# 云边机制与EWMA参数依据 v4

日期：2026-09-30。实际运行规则：{cfg['rule_version']}。此报告更新v3原型的反馈路径与状态标尺；原始数据、人标及旧实验保留。没有新增学生或真实付费API调用。

## 1. 本轮修正后的机制

| 可判定回合的综合等级 | 边缘端动作 | 云端动作 |
|---|---|---|
| 低 | 保留学生原prompt | 直接调用同一DeepSeek API |
| 中 | 在原prompt后追加本地限制模板 | 将附加后的prompt调用同一DeepSeek API |
| 高 | 返回固定引导 | 零云端请求 |
| 证据不足、ACK、只有答案/算式 | 补充证据或确认，保持状态 | 零云端请求 |

中档模板原文：

> {MEDIUM_SUFFIX}

高档固定回答原文：

> {HIGH_REPLY}

数学题型、是否可检查算式都不能绕过高档固定路径。中档保留学生原文并追加模板，低档不追加该模板。共同云端数学教师system提示及实际前序支持用于上下文，不构成中档限制。默认自由数学任务，固定例题只用于验收示例，题型不决定依赖路由。

当前判高立即走本地。当前非高但更新后的历史高信号达到阈值，也保守维持高档；页面同时展示“当前求助行为”与“综合分流等级”。例如高规则输入使D=1，随后两条有明确尝试的非高表达使D依次变为0.5、0.25；阈值0.5时第一条仍走本地，第二条解除保护。确认/纯答案不推进这个过程。

## 2. 云端是谁、什么已经验收

用户愿意购买DeepSeek V4.1 Flash。依据[DeepSeek官方更新记录](https://api-docs.deepseek.com/updates/)，当前请求模型名配置为`deepseek-flash`，接口为`https://api.deepseek.com/chat/completions`；参考[Chat Completions接口](https://api-docs.deepseek.com/api/create-chat-completion/)与[多轮对话说明](https://api-docs.deepseek.com/guides/multi_round_chat/)。本机stdlib适配器发送非流式请求，thinking disabled、temperature=0.2、max_tokens=768、30秒超时；这些是费用与响应时长的工程上限，不是研究效度参数。

记录请求模型与服务实际返回模型、原始prompt、限制模板、发出的messages、实际路线、调用尝试/成功次数、时长、token用量及错误状态。密钥只从进程环境读取，不进入SQLite、导出或成果包；第三方转售接口尚未核验，当前只接官方HTTPS地址。

截至交付：真实DeepSeek未配置、未实测，真实外部付费请求=0。{len(qa['checks'])}项本机HTTP验收和实际Edge浏览器验收已通过，采用隔离数据库与本机HTTP假API，检验真实请求构造、三路分流、上下文、超时/429、重复提交幂等、状态保持、恢复、导出和页面输入处理。它们不能证明真实模型遵守中档限制，不能证明API密钥有效，不能证明教学效果。未配置/失败的回合明确显示没有云端回答，不用本地题解冒充。

## 3. EWMA信号和旧系数哪里需要纠正

交接1以p_high作为连续信号。v4采用原始模型high分数x_t；R3四类模型的ACK分数不被删去再归一。明确行为规则路径使用高=1、非高=0的`rule_binary_proxy`并单独记录；规则值不是模型概率。当前中/低类由规则或分类器确定，不由状态曲线的中点确定。

有效证据回合：D_t=λx_t+(1−λ)D_{{t−1}}；首个有效回合D=x。ACK、证据不足、纯答案或冲突表达保持状态，首次没有有效证据时状态为未知。画像描述会话内求助方式与历史高信号，不显示“心理依赖百分比”。

旧0.78/0.52/0.28来自`7月数据/参数化标定/calibrate_parametric.py`的固定latent字典，旧0.65/0.40是这些值的中点，并非从真实数据估计。v4移除它们在现场状态与分流中的用途。旧报告/静态页面保留为历史标尺，不能与v4曲线混算，也不能以历史高档阈值0.65解释v4。

“模型分数+规则二值”是透明工程代理，尚非经校准概率或心理量表。R1三类与R3四类模型可能存在分数分布差异，不能把同一阈值的跨模型适用性当成已验证结论。

## 4. E11：系数现在有什么依据

计算前登记[修正协议](../云边机制与EWMA修正协议_v4.md)，候选λ=0.2、0.35、0.5、0.65、0.8、1。构造突变高、持续低、高后恢复及高后ACK四类场景，独立或成串误差，15%弱证据保持。开发误差率0.10/0.25、成串持续率0.75；留出误差率0.05/0.15/0.30、成串持续率0.60/0.85，种子另设。

每配置400重复，开发16配置、留出36配置；每个λ分别6400/14400个配置重复记录，共124800行。全体开发配置等权，以更新后状态对构造高类指示信号的过滤MSE最小选系数。留出结果不参与选择。这不是未来预测MSE，也不是儿童真实依赖潜变量。

{table}
选择λ={cfg['lambda']:g}。相对不平滑λ=1，留出过滤MSE下降{gain:.1%}；λ=0.35与0.5的差距很小，不能宣称0.5独一无二。更大的系数响应更快，也增加持续低类误高。这里的0.5诊断判高阈值用于模拟取舍，部署阈值另行标定。无触发的突变延迟记为24，延迟从突变首轮0计，包含弱证据保持轮。ACK区间状态漂移为0；λ=0.5使旧状态权重每一个**有效更新**减半，不是每发一条消息减半。

![工程系数比较](../figures/E11_EWMA系数依据与取舍.png)

[NIST EWMA说明](https://www.itl.nist.gov/div898/handbook/mpc/section2/mpc2211.htm)支持指数加权和平滑/漂移响应的机制，但其工业过程经验值不能直接证明儿童参数。[Hyndman与Athanasopoulos《Forecasting: Principles and Practice》](https://otexts.com/fpp3/ses.html)说明指数平滑权重与预测误差参数估计；本项目E11采用过滤MSE，不能借用预测最优结论。λ=0.5目前是有记录、有候选比较的工程选择，真实纵向效度未验证。

## 5. 阈值与真实两点数据的验证边界

历史高档阈值候选0.3—0.8步长0.1，按R1训练折内三折OOF high-vs-rest平衡准确率选择；20个外折均保留内折训练、验证和参数标定ID，外折学生及R3人标不参与阈值选择。运行全量阈值使用每名R1学生已有五次OOF分数的均值，选择θ={cfg['history_high_threshold']:g}。这属于开发标定，不能作为独立部署校准或改善准确率的证据。

E12使用47名真实学生的R1/R3原始情境表达及折外分数，五次切分、六个系数共1410条回放记录。仍只有47人，每人两点；人标只用于后续诊断，不直接更新状态，也不选择λ或θ。

{sensitivity}
所有系数的R3分流结果一致，历史高档保护均未触发。已判断子集100%准确只覆盖平均4.8/47条，其余多为保持或补充证据；不能报告全体准确100%。状态均值虽不同，**现有真实数据没有显示EWMA改善实际分流**。第一点D1=x1与λ无关，因此两点数据无法为下一轮预测识别最优λ；用更新后D2拟合x2会偏好λ=1，不能包装成预测验证。

分类器与透明规则候选沿用原开发路线，仍保留参数化语法未独立审核、R3证据覆盖低、标签历史暴露及小样本稀有类瓶颈。本轮修正没有把这些问题消除。

## 6. 本机使用与下一步

无密钥版：双击`启动数学实时系统.cmd`，浏览器打开http://127.0.0.1:8765/。高档和证据提示可直接展示，中/低档显示API未配置。

有官方密钥后：双击`启动DeepSeek云边系统.cmd`，在本机隐藏输入提示中输入密钥。若8765已有服务，启动8767并使用独立会话库；以终端显示地址为准。保持终端打开，Ctrl+C结束。不会将密钥保存到磁盘。启动“已配置”只表示存在密钥，不表示已验证连接；中/低回合会产生实际请求费用。

先以少量明确高/中/低输入实测：高档应零调用，中档核对发出的限制模板并人工检查是否泄露答案，低档核对原prompt与真实返回。导出请求/返回模型、用量、时长和路线；失败记录保留。费用、模型服从和数学质量只用实际返回说明。人工复核仍须完成R1/R3独立边界表与参数语法表，不能自动伪造人工结果。

v4离线复现：从成果目录运行`python -X utf8 code/run_v4.py`，执行E11/E12→运行候选→隔离HTTP/浏览器验收→报告→一致性审计。复现前停止现场服务，不写原研究数据库或操作者会话库。v3/E7—E10由原补充脚本单独复现，v3原型归档在history，禁止把旧标尺的图与v4混用。

可以向中期报告提供真实两点个案、原始表达与人标、折外识别比较、低覆盖负结果，以及现场三路原型和工程压力测试。不能据此提供儿童心理依赖诊断或降低依赖的因果结论。
'''
 (OUT/'report/云边机制与EWMA参数依据_v4.md').write_text(report,encoding='utf-8')
 paper=(OUT/'report/论文工作稿_v2_含实时闭环与覆盖分析.md').read_text(encoding='utf-8')
 paper=paper.replace('# 小样本数学情境下参数化求助识别与证据约束状态原型','# 小样本数学情境下参数化求助识别、证据约束状态与云边协同原型')
 start=paper.index('论文工作稿v2');end=paper.index('## 摘要')
 paper=paper[:start]+'论文工作稿v3，2026-09-30。开发性研究；人工复核与独立外部验证未完成。保留E1—E10负结果，更新三路云边机制、连续信号与E11/E12依据。真实DeepSeek连接与回答服从待密钥实测。完整协议与新增结果见《云边机制与EWMA参数依据 v4》。\n\n'+paper[end:]
 paper=paper.replace('系统接通实际输入、有限数学反馈、证据保持、状态与画像导出。','系统接通实际输入、三路云边分流、证据保持、状态与画像导出。六候选工程比较支持λ=0.5；真实两点敏感性中各系数分流相同，尚无纵向改善证据。')
 start=paper.index('状态采用固定工程锚点');end=paper.index('## 结果',start)
 paper=paper[:start]+'''状态用原始模型p_high作工程代理，明确规则用高=1、非高=0并记录来源，不重新归一R3的ACK概率。确认、仅答案、弱证据、冲突表达及逐字复述前条支持保持状态，首次不足证据为未知。有效回合D_t=λx_t+(1−λ)D_{t−1}，首个有效回合初始化为x。规则沿用回顾性透明候选，原分数保留；旧手工锚点不再用于现场状态。

E11计算前固定六候选，开发16配置与留出36配置，每配置400重复，构造二值高信号及独立/成串误差和弱证据保持。仅以开发配置等权过滤MSE选λ，留出配置检查；不是心理参数估计或预测误差最优。E12每个外训练折重新做三折R1 OOF，选择历史高保护阈值，真实R3标签只用于诊断；运行阈值使用每名R1学生五次OOF均值开发标定。

当前高类或历史高信号达到保护阈值时使用固定边缘引导，零云请求；中类在学生原prompt之后追加不给最终答案、提供分步思路的模板，再调用同一云端；低类直接云调用。证据不足回合只请求补充证据。默认自由数学，题型不改变高档机制；对话历史使用实际提供的支持，下一条输入来自操作者。DeepSeek官方模型请求名deepseek-flash，密钥只用本机进程环境；未配置或失败时明确记录没有云回答。模板发送与模型服从分别验证。

'''+paper[end:]
 old='实际本机HTTP、持久化和浏览器验收通过。四种固定数学情境可反馈步骤，自由情境仅分析求助。工程输入与操作者记录分开保存；云调用0、新学生0。本机热请求性能只能作为实现证据。'
 new=f'''v4通过{len(qa['checks'])}项隔离本机HTTP检查及实际Edge浏览器检查，覆盖三路请求构造、错误/超时、幂等、防重复云调用、状态保护、持久化与导出。采用本机HTTP假API，真实外部调用0、新学生0；未验证真实云连接、限制服从、数学质量或教学效果。

E11开发过滤MSE最小候选λ=0.5，留出MSE={float(selected['filter_mse_mean']):.6f}，相对λ=1下降{gain:.1%}；λ=0.35差距很小。较大系数响应快，持续低类误高更多；ACK漂移0。模拟检验是对登记生成假设的工程取舍，不是儿童纵向效度。

E12真实47人×五次切分×六候选形成1410条敏感性记录，仍只有47人两点。各系数R3可判断覆盖10.2%、已判断子集准确100%，历史保护均未触发，分流结果完全相同。状态数值改变未转化为真实分流收益。D1与λ无关，两点不能识别下一轮预测最优λ。完整逐配置/逐学生结果及内折选择记录保留。'''
 assert old in paper;paper=paper.replace(old,new).replace('未校准分数、先验锚点、未完成人工复核','未校准分数、跨模型状态标尺差异、工程生成假设、未完成人工复核')
 paper+='\n\nEWMA机制参考：[NIST EWMA说明](https://www.itl.nist.gov/div898/handbook/mpc/section2/mpc2211.htm)；Hyndman & Athanasopoulos，[简单指数平滑](https://otexts.com/fpp3/ses.html)。工业过程经验与预测SSE估计不能直接证明本项目过滤MSE选择的儿童效度。API配置依据[DeepSeek官方更新记录](https://api-docs.deepseek.com/updates/)，实际返回型号与用量须在连接后记录。\n'
 (OUT/'report/论文工作稿_v3_含云边机制与EWMA依据.md').write_text(paper,encoding='utf-8')
 print('v4 report and engineering tradeoff figure written.',flush=True)
if __name__=='__main__':run()
