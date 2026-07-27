"""
Phase8 运行时技能的显式人工审核命令行工具。
提供命令行入口，供运维/研发人员执行技能审核操作：查看待审核包、审批通过、驳回技能包，
对接 SkillAssetStore 完整生命周期接口，作为人工干预流水线的标准入口。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .assets import SkillAssetStore
from .config import SkillStorageConfig


def _parser() -> argparse.ArgumentParser:
    """
    构建命令行参数解析器
    支持三条子命令：review（预览审核信息）、approve（审批通过）、reject（驳回）
    """
    parser = argparse.ArgumentParser(prog="manage-phase8-skill")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 批量创建三个子命令
    for command in ("review", "approve", "reject"):
        sub = subparsers.add_parser(command)
        # 公共必选参数：技能ID、兼容分组ID、版本号
        sub.add_argument("--skill-id", required=True)
        sub.add_argument("--cohort-id", required=True)
        sub.add_argument("--version", required=True)
        # 审批/驳回额外需要：校验和、操作人、操作理由
        if command in {"approve", "reject"}:
            sub.add_argument("--expected-checksum", required=True)
            sub.add_argument("--actor", required=True)
            sub.add_argument("--reason", required=True)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    store: SkillAssetStore | None = None,
) -> int:
    """
    命令行主逻辑
    :param argv: 外部传入命令行参数；None 则使用系统默认命令行参数
    :param store: 仅供测试注入的显式 Store；正式 CLI 固定使用项目 data/skills
    :return: 进程退出码，0代表正常执行
    """
    args = _parser().parse_args(argv)
    # 确定技能存储根目录
    if store is None:
        project_root = Path(__file__).resolve().parents[4]
        store = SkillAssetStore(
            SkillStorageConfig.production(project_root)
        )
    # 组装技能唯一标识三元组
    identity = {
        "skill_id": args.skill_id,
        "cohort_id": args.cohort_id,
        "version": args.version,
    }

    if args.command == "review":
        # 预览待审核技能元数据
        result = store.review(**identity)
    else:
        # 动态调用 approve / reject 方法
        result = getattr(store, args.command)(
            **identity,
            expected_checksum=args.expected_checksum,
            actor=args.actor,
            reason=args.reason,
        )
    # 标准输出JSON结果，方便脚本捕获、日志记录
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    # 启动入口，执行主函数并设置进程退出码
    raise SystemExit(main())
