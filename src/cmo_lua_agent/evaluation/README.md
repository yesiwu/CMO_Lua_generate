# evaluation

## 1. 目录定位

`evaluation` 在 CMO 执行后解析战斗结果，计算指标和奖励，并判断最终策略是否偏离原始契约。

## 2. 核心职责

解析结果目录、统计目标完成、己方损失、弹药消耗和时间效率，输出 CombatMetrics、RewardBreakdown 与 StrategyAlignmentReport。

## 3. 输入与输出

输入是 CMO 结果目录、runner.log、原始 Manifest 和执行轨迹。输出是指标、评分、奖励和对齐报告。

## 4. 主要文件

`combat_metrics.py`、`combat_result_parser.py`、`combat_scorer.py`、`reward.py`。`strategy_alignment_validator.py` 计划增加。

## 5. 依赖关系

依赖 execution 结果和 contract；被 optimization、memory 和 training 消费。

## 6. 禁止职责

不得生成 Lua、修复代码、控制终端或把缺失结果伪造成成功。

## 7. 典型调用链

`CmoRunResult` -> `CombatResultParser` -> `CombatMetrics` -> `CombatScorer` -> `RewardComputer`。

## 8. 测试要求

使用固定日志、SQLite fixture 和失败批次，验证指标可重复；不调用真实 CMO。

## 9. 当前开发状态

部分实现。基础指标和奖励存在，策略对齐和完整结果 schema 计划实现。
