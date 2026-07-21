# training

## 1. 目录定位

`training` 是可选的离线训练层，消费 trajectory 构建 SFT/GRPO 数据，不控制生产 ScenarioWorkflow。

## 2. 核心职责

转换轨迹、生成训练样本、封装 SFT/GRPO 训练入口，并提供环境与数据校验。

## 3. 输入与输出

输入是已脱敏、已评估的 Trajectory。输出是数据集、训练日志、模型检查点和统计信息；不会修改 CMO 场景。

## 4. 主要文件

`dataset_builder.py`、`sft_trainer.py`、`grpo_environment.py`、`grpo_trainer.py`。旧 `rl/` 路径只作兼容。

## 5. 依赖关系

依赖 trajectory、evaluation 和 memory；不得反向依赖 CLI 或生产工具审批。

## 6. 禁止职责

不得在训练进程中直接启动未经授权的 CMO，不得把训练失败当作业务执行失败。

## 7. 典型调用链

`TrajectoryStore` -> `DatasetBuilder` -> `SFT/GRPO Trainer`；训练结果另由人工部署。

## 8. 测试要求

只测试数据转换、环境协议和 checkpoint 恢复；真实 GPU/大模型测试单独标记。

## 9. 当前开发状态

后期创建。兼容代码已迁移到本目录，但尚未接入生产工作流。
