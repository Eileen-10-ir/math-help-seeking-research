# 公开材料和研究数据的访问范围

共用代码、流程表、参数说明、审核规程和汇总统计可以公开查阅。真实学生原文及其可关联记录继续在受控研究材料中使用；API密钥仅保存在各自本机。

|材料|本次处理|说明|
|---|---|---|
|共用代码和方法文档|公开仓库|无需邀请即可浏览、下载和clone；直接写入仍需权限|
|数据库结构|公开空库与SQL|见[data/public](../data/public/README.md)；无学生、样本或标注记录|
|真实标签汇总|公开汇总JSON|不含学生ID、逐条原文、逐条分数或人口属性交叉表|
|原始问卷及处理表|不上传公开仓库|两份表各有52条非空IP记录；原表还含提交时间等信息|
|完整研究数据库、模型和带内容审核表|仍按私有研究包共享|去掉姓名或使用S编号，不自动等于已完成匿名化或取得公开授权|
|API密钥与费用凭据|不公开|本机.private/或环境变量；公开代码不能包含真实密钥|

原问卷告知匿名、仅用于学术研究，当前检查的文件没有提供公开逐条原文的授权。不能把课题组内部分析与向全网开放视为同一范围。原始数据公开前需核对完整告知/授权、移除身份及链接线索、评估自由文本和小样本关联风险，并确认外部语料的再分发权利；这些条件尚未满足。

公开空库用于理解格式和测试建表，不是完整数据集，不可用它复现识别指标。完整复现仍需课题组私有研究包，按README恢复到.private/workspace。本次没有把745文件的旧私有归档整体公开。

若使用私有GitHub仓库，队友需要被邀请并接受，通常完成一次即可，不是每次pull都重新审批。也可在课题组授权范围内，通过私密渠道分发同一研究ZIP；不需要为读取公开代码授予账户权限。私有托管不能替代数据告知、授权和最小必要访问。

依据与定位（网页无固定页码，行号为2026-10-19本次网页提取编号）：

- [GitHub仓库可见性](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)，Changing from private to public，提取64—70行：公开访问、fork及Actions历史可见。
- [GitHub邀请协作者](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository)，Inviting a collaborator第1—8步：邀请及接受后访问。
- [个人信息保护法官方全文](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm)，第二十五条（提取174行）涉及公开个人信息；第二十八—三十一条（181—191行）涉及敏感信息及不满十四周岁未成年人。以上是确定本次公开边界的依据，不将当前数据宣称为已经过法律或匿名化认证。
