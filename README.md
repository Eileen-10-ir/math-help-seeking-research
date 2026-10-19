# 中小学生数学AI求助研究

面向中小学生数学求助，研究真实特征校准的受控文本生成、单轮求助识别、动态状态更新，以及分级云边支持。当前已完成工程闭环，正在开展生成语义独立审核和正式回复质量—资源对照。

**第一次了解项目，可以先看[各阶段流程总表：输入—方法—输出—参数—验证状态]了解各阶段输入输出熟悉项目 **(docs/pipeline_overview.md)。**再按[源码地图](docs/architecture.md)查实现。**

## 项目结构

```text
run.py                    统一运行入口
src/frozen_core/          共用算法与流程实现
web/                      当前唯一一套交互页面及本地依赖
scripts/restore_private.py 私有数据/模型恢复工具
docs/                     方法、参数、指标、生成句库与审核协议
requirements.txt          固定科学计算依赖
project_manifest.json     共用源码位置及hash
.private/                 本机私有材料与运行结果，Git忽略
```

`src/frozen_core`内部保留来源目录，用于兼容已有模型反序列化与研究契约；对外统一用`run.py`，不必在日期目录中寻找入口。仓库不保存成员任务包制作、Word制作、材料打包、临时汇总脚本或多套旧网页。

## 快速开始

要求Python3.13独立环境。私有数据包从小组另行取得，不进入Git。

```powershell
python -m pip install -r requirements.txt
python -s -X utf8 scripts/restore_private.py --archive "共享可复现数据.zip的实际位置"
python -s -X utf8 run.py check
python -s -X utf8 run.py serve --port 8771
```

网页为`http://127.0.0.1:8771/`。`check`使用假API，包含契约核验、识别指标复算、状态与连续HTTP、四组离线比较；不产生付费调用。私有ZIP中的历史材料只在`.private/workspace`还原，不作为Git共用源码。

## 流程命令

|命令|用途|
|---|---|
|`python -s -X utf8 run.py generate`|在新目录复现联合表达生成、溯源与结构核验|
|`python -s -X utf8 run.py train`|在新目录复现当前识别方法比较/拟合，不自动替换网页模型|
|`python -s -X utf8 run.py budget`|先检查表达池容量，再做0/45/91数量实验；已有结果拒绝覆盖|
|`python -s -X utf8 run.py compare`|同输入的四组离线路由检查|
|`python -s -X utf8 run.py compare --real`|按既有固定病例执行真实API对照；先冻结正式协议和预算|

结果写到`.private/workspace/交付结果`，生成器数量实验在相应私有实验目录。原标签、数据和归档结果保留。真实API密钥只放本机`MATH_DEEPSEEK_API_KEY`环境变量；实际模型、usage、失败和费用依据必须保存。

小组可以向队友提供授权共享的API密钥用于测试，通过私密渠道交付、在各自本机配置。也可运行`python -s -X utf8 scripts/configure_api.py`交互式保存到Git忽略目录，随后网页和真实对照入口会自动读取。[API配置和一次连通性检查](docs/api_access.md)说明了具体步骤，仓库不保存真实密钥。

## 方法与证据

- [流程与源码地图](docs/architecture.md)：生成→识别→证据接纳→EWMA→画像→连续对话→三路支持。
- [参数来源](docs/parameters.md)：数据校准、训练内选择和固定工程参数分别说明。
- [文本生成与实际句库](docs/text_generation.md)：参数到底控制什么、句子从哪里来。
- [语言部件来源与AI辅助说明](docs/phrase_bank_provenance.md)：区分队友原交接、我们本地设计和运行时生成。
- [ALSP部分审核](docs/semantic_review.md)与[数字锚点表](docs/semantic_score_anchors.md)：记录语义及0代码＋1—5分，不重新划分真实整体标签。
- [系统比较协议](docs/system_comparison.md)、[质量评分规程](docs/response_quality.md)、[指标口径](docs/metrics.md)。
- [当前结果](docs/results.md)、[合成数量比较](docs/synthetic_budget.md)。

真实数据47名学生、两次表达共94条；整体标签保留，ALSP均值用于生成校准，线上未自动逐项打分。当前共同版首轮混合文本LR内部宏F1约0.678、准确率79.6%；后续四类宏F1约0.599。新数量实验固定tau1时，仅真实0.734强于加45/91条的0.702/0.679，不宣称合成增强已胜出。重复切分仍是47名独立学生。

三路按最终档位执行：低直接云、中附限制后云、高本地固定提示；本轮等级、历史保护后档位及实际路径分别记录，未知/确认单列。工程跑通不等于回复质量优势或真实学生行为改善。
