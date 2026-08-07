"""
自动化推演 CLI：直接在终端运行，不走 AgentLoop。

用法：
  python -m cmo_lua_agent.scripts.run_auto_evolution start --campaign-id test001 --scenario red_blue_6v4_liaoning_v1 --experiences 100 --mode FAKE_FIXTURE
  python -m cmo_lua_agent.scripts.run_auto_evolution status --campaign-id test001
  python -m cmo_lua_agent.scripts.run_auto_evolution stop --campaign-id test001

前置：conda activate py313
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保 src 在 path 中
_SRC = Path(__file__).parents[2] / "src"
sys.path.insert(0, str(_SRC))

from cmo_lua_agent.evolution.auto_campaign_tools import (
    StartAutoEvolutionCampaignTool,
    StopAutoEvolutionCampaignTool,
    StatusAutoEvolutionCampaignTool,
)
from cmo_lua_agent.tools.tool_base.context import ToolContext


def _ctx() -> ToolContext:
    """伪造 ToolContext（CLI 环境没有真正的 progress 回调）"""
    return ToolContext(
        session_id="cli",
        conversation_id="cli",
        message_id="cli",
        requested_approval=None,
    )


def cmd_start(args: argparse.Namespace) -> int:
    tool = StartAutoEvolutionCampaignTool()
    result = tool.execute({
        "campaign_id": args.campaign_id,
        "scenario_package_id": args.scenario,
        "target_experiences": args.experiences,
        "max_generations": args.max_generations,
        "max_cmo_runs": args.max_cmo_runs,
        "max_repair_attempts": args.max_repair_attempts,
        "execution_mode": args.mode,
        "generation_objective": args.objective or "Improve red-side score through multi-candidate generation, experience accumulation, and skill evolution.",
        "minimum_improvement_delta": args.min_improvement_delta or 1,
        "no_improvement_patience": args.patience or 3,
    }, context=_ctx())
    print(result.content)
    return 0 if not result.is_error else 1


def cmd_status(args: argparse.Namespace) -> int:
    tool = StatusAutoEvolutionCampaignTool()
    result = tool.execute({"campaign_id": args.campaign_id}, context=_ctx())
    data = json.loads(result.content)

    print(f"\n{'='*50}")
    print(f"Campaign: {data['campaign_id']}")
    print(f"状态:     {data['status']}")
    print(f"代数:     {data['completed_generations']}")
    print(f"经验:     {data['total_experiences']}")
    print(f"运行中:   {'是' if data['is_running'] else '否'}")
    if data.get("errors"):
        print(f"错误:     {data['errors']}")
    if data.get("lineage"):
        print(f"\n最近 5 代:")
        for entry in data["lineage"]:
            print(f"  gen {entry.get('generation_index', '?')}: "
                  f"score={entry.get('selected_score', '?')} "
                  f"champion={entry.get('selected_champion_id', '?')[:40]}")
    print(f"{'='*50}\n")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    tool = StopAutoEvolutionCampaignTool()
    result = tool.execute({"campaign_id": args.campaign_id}, context=_ctx())
    print(result.content)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_auto_evolution", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="启动自动化推演")
    start.add_argument("--campaign-id", required=True, help="推演任务唯一 ID（幂等键）")
    start.add_argument("--scenario", default="red_blue_6v4_liaoning_v1", help="场景包 ID")
    start.add_argument("--experiences", type=int, default=100, help="经验目标（默认 100）")
    start.add_argument("--max-generations", dest="max_generations", type=int, default=20)
    start.add_argument("--max-cmo-runs", dest="max_cmo_runs", type=int, default=200)
    start.add_argument("--max-repair-attempts", dest="max_repair_attempts", type=int, default=3)
    start.add_argument("--mode", choices=["PRODUCTION_CMO", "FAKE_FIXTURE"], default="FAKE_FIXTURE")
    start.add_argument("--objective", help="推演目标描述（可选）")
    start.add_argument("--min-improvement-delta", dest="min_improvement_delta", type=int, default=1)
    start.add_argument("--patience", type=int, default=3)

    sub.add_parser("status", help="查看推演进度").add_argument("--campaign-id", required=True)
    sub.add_parser("stop", help="停止推演").add_argument("--campaign-id", required=True)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    commands = {"start": cmd_start, "status": cmd_status, "stop": cmd_stop}
    sys.exit(commands[args.command](args))
