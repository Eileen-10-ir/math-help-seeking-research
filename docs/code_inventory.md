# 共用源码清单

本清单只列共用流程实现。内部兼容层保留来源文件名，统一入口为根目录run.py。交接包制作和临时报告脚本不在本清单。

|源文件|职责（原始模块说明）|
|---|---|
|[bounded_mask.py](../src/frozen_core/数学主线严谨重跑20260930/code/bounded_mask.py)|有限数学内容遮罩|
|[cloud_gateway.py](../src/frozen_core/数学主线严谨重跑20260930/code/cloud_gateway.py)|Bounded DeepSeek Chat Completions adapter. Secret is never in public records.|
|[common.py](../src/frozen_core/数学主线严谨重跑20260930/code/common.py)|字符TF-IDF/LR、数据读取及共享标签|
|[controlled_text.py](../src/frozen_core/数学主线严谨重跑20260930/code/controlled_text.py)|Frozen engineering grammar; labels are candidate specifications, not human validation.|
|[evidence_runtime.py](../src/frozen_core/数学主线严谨重跑20260930/code/evidence_runtime.py)|Versioned evidence gate shared by live service and supplementary evaluations.|
|[legacy_features.py](../src/frozen_core/数学主线严谨重跑20260930/code/legacy_features.py)|文本标准化及兼容特征|
|[math_state.py](../src/frozen_core/数学主线严谨重跑20260930/code/math_state.py)|Evidence-aware mathematics state engine. Scores and thresholds are engineering priors.|
|[routing_v4.py](../src/frozen_core/数学主线严谨重跑20260930/code/routing_v4.py)|User-defined edge / constrained-cloud / direct-cloud policy.|
|[runtime_server.py](../src/frozen_core/数学主线严谨重跑20260930/code/runtime_server.py)|Loopback UI, local classification and auditable DeepSeek three-path support.|
|[runtime_state_v4.py](../src/frozen_core/数学主线严谨重跑20260930/code/runtime_state_v4.py)|v4 high-signal EWMA; old v3 module and E10 remain immutable.|
|[routing_v5.py](../src/frozen_core/云边教学与成本复核20261001/code/routing_v5.py)|Separate uncertainty in state measurement from access to bounded method hints.|
|[runtime_server_v5.py](../src/frozen_core/云边教学与成本复核20261001/code/runtime_server_v5.py)|v5 review prototype; frozen v4 data/state/code preserved. Keys remain memory-only.|
|[routing_v6.py](../src/frozen_core/数学交互与论文初稿20261009/code/routing_v6.py)|Conversation support v6; frozen classifiers and state update remain unchanged.|
|[routing_v7.py](../src/frozen_core/数学交互与论文初稿20261009/code/routing_v7.py)|Local support corrections only; v6 inference, state and three grade routes retained.|
|[runtime_server_v6.py](../src/frozen_core/数学交互与论文初稿20261009/code/runtime_server_v6.py)|Independent v6 operator service; does not mutate v5 or its E13 protocol.|
|[check_contract.py](../src/frozen_core/数学共同主线定版20261018/code/check_contract.py)|Portable hash and chain identity verification.|
|[freeze_contract.py](../src/frozen_core/数学共同主线定版20261018/code/freeze_contract.py)|Capture the selected working point after documents and checks exist.|
|[prepare_response_review.py](../src/frozen_core/数学共同主线定版20261018/code/prepare_response_review.py)|Source-hidden independent response forms, only for actual executed batches.|
|[prepare_runtime.py](../src/frozen_core/数学共同主线定版20261018/code/prepare_runtime.py)|Freeze selected trained objects/config/frontend, preserving the prior chain.|
|[route_models.py](../src/frozen_core/数学共同主线定版20261018/code/route_models.py)|Auditable local text classifiers / real-crossfit calibrated lexical retrieval.|
|[routing_v4.py](../src/frozen_core/数学共同主线定版20261018/code/routing_v4.py)|User-defined edge / constrained-cloud / direct-cloud policy.|
|[run_mainline.py](../src/frozen_core/数学共同主线定版20261018/code/run_mainline.py)|Canonical current check / serve / compare; all new runs in fresh output directories.|
|[run_recognition.py](../src/frozen_core/数学共同主线定版20261018/code/run_recognition.py)|Shared outer students, regenerated inner synthetics, frozen route comparison.|
|[run_state_review.py](../src/frozen_core/数学共同主线定版20261018/code/run_state_review.py)|Gate OOF review -> history controls -> alpha controls; outcomes kept separate.|
|[run_system_current.py](../src/frozen_core/数学共同主线定版20261018/code/run_system_current.py)|Shared frozen analysis for four arms; no stale hard-coded API prices.|
|[runtime_current.py](../src/frozen_core/数学共同主线定版20261018/code/runtime_current.py)|One isolated current process; historical runtime sources are preserved.|
|[state_v5.py](../src/frozen_core/数学共同主线定版20261018/code/state_v5.py)|Stage-specific acceptance and evidence-aware release, no hidden risk resets.|
|[verify_http.py](../src/frozen_core/数学共同主线定版20261018/code/verify_http.py)|Actual loopback HTTP and route checks; isolated mock cannot spend API credits.|
|[verify_results.py](../src/frozen_core/数学共同主线定版20261018/code/verify_results.py)|Independent metric/count/lineage/model equivalence checks for the release.|
|[g1_generator.py](../src/frozen_core/G0_G1严谨对照20261014/code/g1_generator.py)|Empirical joint ALSP-conditioned semantic grammar. All scores are prototypes,|
|[joint_renderer.py](../src/frozen_core/统一数据与交接准备20261014/code/joint_renderer.py)|Parameter spec -> versioned expression. No original student text enters render().|
|[independent_contract_check.py](../src/frozen_core/统一数据与交接准备20261014/code/independent_contract_check.py)|Parse actual evidence and arithmetic; do not import the renderer or its phrase bank.|
|[prepare_data.py](../src/frozen_core/统一数据与交接准备20261014/code/prepare_data.py)|Build traceable joint-expression candidates and a read-only research export.|
|[prepare_blind_review.py](../src/frozen_core/统一数据与交接准备20261014/code/prepare_blind_review.py)|Small coverage-first blind sheet for joint-expression v2, not a population sample.|
|[run_system_comparison.py](../src/frozen_core/系统支持修正v7_20261014/code/run_system_comparison.py)|Same frozen inference, context and cases; local routing check or bounded real API.|
|[run_budget.py](../src/frozen_core/合成数量学习曲线20261018/code/run_budget.py)|Nested real-student budget curve, per-class nested synthetic prefixes.|
|[check_capacity.py](../src/frozen_core/合成数量学习曲线20261018/code/check_capacity.py)|Structural feasibility before comparing scores; first counterexample suffices.|
# 审核回交工具补充

`scripts/review_tools.py`输入私有审核表契约及一份/两份独立Excel或CSV回交，输出字段与来源完整性校验、有效配对数、原始一致率及适用κ。0分按NA排除，评分不完整不冒充完成，裁决不覆盖原独立分；不调用API、不自动打分、不修改真实标签。运行方式见[回交流程](review_return_workflow.md)。

