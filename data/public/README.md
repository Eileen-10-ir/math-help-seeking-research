# 公开数据说明

本目录提供原研究数据库的空结构和真实标签的汇总计数，不提供逐条学生数据。

- `schema_only.db`：可直接用SQLite查看，三张研究表均为空。
- `schema.sql`：等价建表语句，不包含INSERT。
- `schema_dictionary.json`：字段名、类型及解释。
- `real_aggregate_counts.json`：47名学生两次表达的标签和评分覆盖汇总。

这是格式与汇总公开，不是完整数据集。复现训练和指标仍需课题组授权的私有研究包。
原数据库、原问卷和带内容标注表没有上传；详见[数据访问范围](../../docs/data_access.md)。
