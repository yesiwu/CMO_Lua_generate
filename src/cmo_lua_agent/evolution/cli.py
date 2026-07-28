"""
Phase9 推演任务显式命令行入口定义。正式环境运行时需要外部注入运行时实例。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器，注册所有Phase9顶层子命令"""
    parser = argparse.ArgumentParser(prog="phase9-evolution")
    # 注册子命令容器，command字段用于区分执行动作
    commands = parser.add_subparsers(dest="command", required=True)

    # start：新建并启动一套演化推演任务
    start = commands.add_parser("start")
    # 传入推演规约文件路径（EvolutionCampaignSpec配置文件）
    start.add_argument("campaign_spec", type=Path)
    # 推演全流程硬性算力、次数、超时约束，全部必填整数参数
    limit_names = (
        "max-generations",                  # 最大迭代世代总数
        "max-cmo-runs",                     # 全局最大CMO仿真总次数
        "max-cmo-attempts-per-candidate",   # 单条候选策略最大仿真尝试次数
        "max-cmo-attempts-for-baseline",    # 基线策略最大仿真尝试次数
        "max-repair-attempts-per-candidate",# 单条策略Lua修复最大重试次数
        "max-failed-runs",                  # 允许的最大仿真失败次数
        "max-llm-total-calls",              # LLM总调用次数上限
        "max-strategy-proposal-calls",      # 策略生成LLM调用上限
        "max-lua-generation-calls",         # Lua脚本生成调用上限
        "max-lua-repair-calls",             # Lua脚本修复调用上限
        "max-comparative-learning-calls",   # 对比学习调用上限
        "max-skill-author-calls",           # 技能编排调用上限
        "max-wall-clock-seconds",           # 推演全局总墙钟时长上限
        "per-generation-timeout-seconds",   # 单个世代执行超时时间
        "per-candidate-timeout-seconds",    # 单条候选仿真超时时间
    )
    for name in limit_names:
        start.add_argument(f"--{name}", required=True, type=int)

    # resume：恢复已存在的推演任务（断点续跑）
    resume = commands.add_parser("resume")
    resume.add_argument("campaign_id")

    # inspect：查询推演任务当前状态信息
    inspect = commands.add_parser("inspect")
    inspect.add_argument("campaign_id")

    # stop：主动终止正在运行的推演任务
    stop = commands.add_parser("stop")
    stop.add_argument("campaign_id")
    stop.add_argument("--reason", required=True, help="任务终止原因")

    # recover-lock：异常锁恢复，清理僵死占用锁（运维应急命令）
    recover = commands.add_parser("recover-lock")
    recover.add_argument("--reason", required=True, help="执行锁恢复的原因")

    return parser


def main(argv: list[str] | None = None) -> int:
    """
    命令行入口主函数
    职责：仅完成参数解析，不包含任何业务执行逻辑。
    设计意图：本模块只负责命令解析与控制面交互；正式运行时，运行时环境由外部调用方显式构造，
    禁止模块导入时自动创建运行时，避免隐式副作用。
    """
    args = build_parser().parse_args(argv)
    # 输出标准化回执，上层程序拿到解析完成的指令后再启动真实业务逻辑
    print(json.dumps({"command": args.command, "accepted": True}, ensure_ascii=False))
    return 0