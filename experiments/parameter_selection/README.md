# 参数补充实验

先看[实验结论与发布决定](../../docs/parameter_validation_20261118.md)。本目录保存研究实现，不含真实学生原文、模型或调用日志。

先按项目README恢复固定版本的私有共享包。识别、生成和状态实验不需API。系统实测还需恢复`私有复现补充20261118.zip`：

```powershell
python -s -X utf8 scripts/restore_experiment_data.py --archive "私有复现补充20261118.zip"
```

按顺序运行：

```powershell
python -s -X utf8 run.py study selection --smoke
python -s -X utf8 run.py study selection
python -s -X utf8 run.py study summarize
python -s -X utf8 run.py study ablation
python -s -X utf8 run.py study state
python -s -X utf8 run.py study system
```

输出在`.private/workspace/参数完善实验20261118_复现`。`--smoke`跑第一个完整外层切分；完整运行可接续该检查点。独立重跑可用`--name 新目录名`，各阶段须用同一名称。源码或输入变化时已有选择检查点拒绝复用，不能改源后冒充原运行。

| 脚本 | 输入 | 输出 |
|---|---|---|
| run_selection.py | 配对快照、学生切分、训练侧四维均值与行为类型 | 20个外层切分的候选、参数、留出预测、隔离记录 |
| summarize_and_fit.py | 外层结果与同一训练内程序 | 汇总、新候选模型及门槛；不替换网页 |
| analyze_results.py | 留出预测与门槛结果 | 分母及按学生整组重抽的条件区间 |
| generator_variants.py / run_generation_ablation.py | 同类配置池、四维评分 | ALSP/ALP/均匀及双评分者敏感性 |
| run_state_sensitivity.py / state_response_analysis.py | 预设工程信号与噪声 | 状态误差、错误限制、切换、延迟及未恢复次数 |
| run_system_validation.py | 24条工程输入、同一识别器和状态 | 六组回复与资源、空评分表和独立映射 |
| run_continuity_replay.py | 4段15轮工程脚本及归档前缀 | 同历史回复回放，不代表学生对新回复作反应 |

需要真实资源实测时先配置本机密钥，显式运行：

```powershell
python -s -X utf8 run.py study system --real
python -s -X utf8 run.py study continuity --real
```

系统实验每条每组一次、不自动重试，共144条回复，另有9个温度/长度设置检查。连续回放先核对输入等于工程脚本、历史等于该脚本既有生成记录。不要直接用真实学生原文替换工程实测输入。

独立评价单位仍是47名学生；后续四类含确认/非提问，接纳覆盖分母只含有等级表达。质量表未填分时程序不生成质量优势结论。参数搜索的负结果也须保留。完整候选和规则见[执行协议](protocol.md)。
