# 共用流程与源码地图

研究代码保持算法内容不变，只整理目录与运行入口。内部来源目录用于兼容现有模型与冻结契约，不代表多个默认版本。完整源码清单见[code_inventory.md](code_inventory.md)。

|环节|实现|入口|输入|输出|
|---|---|---|---|---|
|真实训练特征→配置抽样|[g1_generator.py](../src/frozen_core/G0_G1严谨对照20261014/code/g1_generator.py)|generate|ALSP均值、原标签、配额、tau/seed|供体与离散行为配置|
|配置→生成文本|[joint_renderer.py](../src/frozen_core/统一数据与交接准备20261014/code/joint_renderer.py)|make_spec / render / sample_and_render|spec、数学题型、语言风格|可追溯prompt/题目/去重键|
|文本结构核验|[independent_contract_check.py](../src/frozen_core/统一数据与交接准备20261014/code/independent_contract_check.py)|check_contract|实际文本、题目、spec|语义契约/数学结构检查|
|文本识别|[common.py](../src/frozen_core/数学主线严谨重跑20260930/code/common.py)|Classifier|当前表达、训练侧文本与标签|TF-IDF/LR类别分数|
|候选识别比较|[route_models.py](../src/frozen_core/数学共同主线定版20261018/code/route_models.py)|BM25 / CalibratedBM25 / fit_lr|同一训练侧数据与内层映射|LR与检索候选分数|
|新证据接纳|[evidence_runtime.py](../src/frozen_core/数学主线严谨重跑20260930/code/evidence_runtime.py)|assess / behavioral_evidence|当前表达、分数、前次支持|事件/行为/接纳或保持理由|
|状态/画像|[state_v5.py](../src/frozen_core/数学共同主线定版20261018/code/state_v5.py)|advance / State|旧状态、有效证据、参数|EWMA、最终档位、历史解除/趋势|
|连续交互|[runtime_current.py](../src/frozen_core/数学共同主线定版20261018/code/runtime_current.py)|ConversationService|题目、当前输入、实际历史|会话/SQLite记录/连续回复|
|三路支持|[routing_v7.py](../src/frozen_core/数学交互与论文初稿20261009/code/routing_v7.py)|support|最终档位、题目/历史、网关|直接云/受限云/固定本地|
|系统正式对照|[run_system_current.py](../src/frozen_core/数学共同主线定版20261018/code/run_system_current.py)|run|固定病例与一次共同分析|四组实际输出或离线路由记录|
|独立回复评分材料|[prepare_response_review.py](../src/frozen_core/数学共同主线定版20261018/code/prepare_response_review.py)|main|真实API记录|隐藏策略标签的双人空表，不自动打分|

网页只保留[web](../web)当前一套；历史数据与兼容材料只在.private/workspace还原，不出现在Git中。单轮→状态→画像→连续交互→三路支持由run.py check统一验收。

当前分层按最终档位，历史覆盖与unknown单列，详见[routing_policy.md](routing_policy.md)。真实数据未提供时，代码可查阅，模型服务需恢复私有包后才能运行。
