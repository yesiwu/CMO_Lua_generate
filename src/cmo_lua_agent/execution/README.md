# execution

## 1. 目录定位

`execution` 是 CMO BatchRunner 的进程边界，负责把已生成 Lua 交给 CMO 批处理程序，并可靠返回日志、结果目录和部分失败状态。

## 2. 核心职责

配置临时替换和恢复，启动 BatchRunner，使用主 PID 等待，轮询 runner.log 进度，解析 CMO 错误和成功/失败汇总。

## 3. 输入与输出

输入是 Lua 路径、job index、超时时间、BatchRunner 路径和工作目录。输出是 CmoProcessResult、CmoRunResult、日志路径、结果目录和结构化错误。

## 4. 主要文件

`cmo_job_config.py`、`cmo_process_runner.py`、`cmo_runner.py`、`cmo_progress_parser.py`、`cmo_error_parser.py`、`models.py`。

## 5. 依赖关系

依赖 artifacts、文件系统和 subprocess；被工具和 orchestration 调用，不依赖终端绘制。

## 6. 禁止职责

不得调用 LLM、猜测修复方案、绕过审批或把子进程退出码当成唯一业务成功条件。

## 7. 典型调用链

`ExecuteCmoTool` -> `CmoRunner` -> `CmoJobConfig` + `CmoProcessRunner` -> `CmoErrorParser` -> `RunArtifactStore`。

## 8. 测试要求

覆盖子进程继承输出、超时清理、日志增量、部分失败、结果目录锁定和配置恢复；默认使用 fake process。

## 9. 当前开发状态

已实现。真实 CMO 仍需人工验证环境路径和数据库版本。
