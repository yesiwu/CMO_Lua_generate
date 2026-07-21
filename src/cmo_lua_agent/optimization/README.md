# optimization

## 1. 目录定位

`optimization` 管理多候选策略的比较、选择、收敛和经验蒸馏，不参与单次 Chat 工具执行。

## 2. 核心职责

根据候选评分维护状态，选择精英方案，判断是否收敛，并把可复用经验写入 memory 或 trajectory。

## 3. 输入与输出

输入是 StrategySpec、候选运行结果、CombatMetrics、RewardBreakdown 和历史经验。输出是候选排名、精英集合、收敛状态和蒸馏经验。

## 4. 主要文件

`candidate_selector.py`、`convergence.py`、`experience_distiller.py`、`optimization_state.py`。

## 5. 依赖关系

依赖 generation、evaluation、memory、trajectory；由 optimization workflow 编排。

## 6. 禁止职责

不得绕过 contract 生成未校验候选，不得直接修改 CMO 配置，不得让优化循环替代人工审批。

## 7. 典型调用链

`CandidateGenerator` -> 多次 `ScenarioWorkflow` -> `Evaluation` -> `CandidateSelector` -> `ConvergenceChecker`。

## 8. 测试要求

覆盖排序稳定性、重复候选、收敛阈值和失败候选隔离；使用确定性随机种子。

## 9. 当前开发状态

部分实现。基础选择和状态存在，多候选真实 CMO 编排计划实现。
