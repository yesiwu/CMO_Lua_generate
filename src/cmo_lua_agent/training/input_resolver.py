"""把用户提供的 ScenarioIR 解析为可重启 Campaign 引用。

训练请求只保存路径与场景标识，而不复制或改写输入 JSON；Runner 恢复时重新解析同一
来源，从而既保留用户的原始文件所有权，也让不兼容输入在启动阶段被明确拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder


@dataclass(frozen=True, slots=True)
class ResolvedScenarioInput:
    """写入 Training 请求、且已通过校验的 ScenarioIR 身份信息。"""

    reference: str
    absolute_path: Path
    scenario_id: str


class ScenarioInputResolver:
    """校验兼容的 ScenarioIR 输入，不复制也不修改原文件。"""

    def __init__(self, project_root: Path) -> None:
        self._project_root = Path(project_root).resolve()

    def resolve(self, path: str | Path) -> ResolvedScenarioInput:
        """解析路径、校验 ScenarioIR 可构建性，并返回可跨进程保存的引用。

        项目目录内的文件以相对路径保存以便迁移；外部文件保留绝对路径。无论哪种情况，
        本方法都不复制输入，也不改变用户提供的 JSON。
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self._project_root / candidate
        candidate = candidate.resolve()
        if not candidate.is_file():
            raise ValueError("scenario_ir_not_found")
        if candidate.suffix.lower() != ".json":
            raise ValueError("scenario_ir_json_required")
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError("scenario_ir_invalid_json") from exc
        if not isinstance(payload, dict):
            raise ValueError("scenario_ir_json_object_required")
        try:
            derived = BaselineStrategyBuilder().build(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("scenario_ir_incompatible") from exc
        try:
            reference = candidate.relative_to(self._project_root).as_posix()
        except ValueError:
            reference = str(candidate)
        return ResolvedScenarioInput(
            reference=reference,
            absolute_path=candidate,
            scenario_id=str(derived.scenario.scenario_id),
        )
