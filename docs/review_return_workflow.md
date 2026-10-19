# 独立审核回交与汇总

本轮每位评审76行：44条合成表达、16条真实首轮分项抽核、16条引导后回应。两份内容相同、顺序不同；不是分成互不重叠的两半。评分先按[精简参考](review_quick_reference.md)，完整锚点见[分项表](semantic_score_anchors.md)。

真实审核表与对应契约随私有包提供，不在公开Git。只填审核字段；原始表达、实际引导和ID不改。Excel与三份CSV二选一回交，不需重复填写两套。AI可校验格式、整理引用，不能代填独立人工分数。

## 校验

将私有表及审核表契约放到本机.private/review/A、B。下面以A为例；输出路径已有文件时程序停止，换新文件名以保留历史。

```powershell
python -s -X utf8 scripts/review_tools.py validate --contract ".private/review/A/审核表契约.json" --input ".private/review/A/审核表.xlsx" --allow-incomplete --out ".private/review/A/初验.json"
python -s -X utf8 scripts/review_tools.py validate --contract ".private/review/A/审核表契约.json" --input ".private/review/A/审核表.xlsx" --out ".private/review/A/回交校验.json"
```

初验允许尚未评分，但仍检查原文、ID、字段和填写代码；它通过不表示审核完成。最终校验要求必填项完整，0分须写NA原因。也可把--input指向只含同名三份CSV的目录。

## 锁定和计算

负责人收齐两个独立版本，记录回交时间和文件SHA256，确认均通过最终校验后，才开放目标与旧评分核对。不要覆盖原始独立分；讨论裁决另列。

```powershell
python -s -X utf8 scripts/review_tools.py agreement --contract ".private/review/A/审核表契约.json" --input ".private/review/A/审核表.xlsx" --other ".private/review/B/审核表.xlsx" --out ".private/review/独立一致性.json"
```

数字1—5用线性加权κ，0是NA，排除但报告排除数；名义类别用普通κ并报告未知/NA。双方均为同一唯一类别或没有有效配对时κ记不可定义，不填1。程序同时给有效配对数和原始一致率。

首轮新审核分与旧评分不是严格等值量表，不能把两种版本的分歧直接称标注质量升降。合成审核分也不要求数值等于工程锚点：对照实际行为语义，分别记录匹配、错配或不明确。

本轮按类别、分歧和行为覆盖选样，缺陷占比不能当总体发生率。后续回应建议是新侧表，不自动覆盖旧整体标签，也不作为真实依赖改善率。系统回复质量评分另用[共同回复规程](response_quality.md)，不混入此76行的一致性统计。
