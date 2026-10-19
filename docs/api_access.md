# 小组API配置与测试

可以由项目提供授权共享的DeepSeek密钥，方便成员测试网页与找问题。通过小组私密渠道交付，每台机器只配置一次；不需要把真实密钥写入Git，也不要求每人重复购买。

在项目根目录运行：

```powershell
python -s -X utf8 scripts/configure_api.py
python -s -X utf8 scripts/check_api.py
```

第一条交互式输入不回显，保存在`.private/deepseek_api_key.txt`；第二条只检查配置，不发送请求、不打印密钥。已有`MATH_DEEPSEEK_API_KEY`环境变量时优先使用。网页与真实对照入口会自动读取本机配置。

实际连通性检查须显式运行：

```powershell
python -s -X utf8 scripts/check_api.py --probe
```

最多一次简单数学请求，不自动重试；实际模型、usage、时延和状态保存在`.private/api_checks/`。“已配置”不等于“已连通”。它不是学生样本或教学效果实验。

模型别名从已恢复的私有模型卡读取，未恢复时使用代码默认值；以实际响应核实底座。需要换模型时统一修改研究版本，不能各成员悄悄用不同模型。

恢复私有数据后运行`python -s -X utf8 run.py serve --port 8771`。`compare`默认离线，`compare --real`才发送真实请求；正式比较先冻结病例和预算。共享密钥的总账单不能直接当每个实验成本，分别保存usage和批次。回交问题时提供输入、版本、路径和现象，不在聊天/截图中包含密钥。
