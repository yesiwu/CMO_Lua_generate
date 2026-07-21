"""单次工作流运行的文件持久化边界层

本存储类全权管理固定目录结构，是整条流水线唯一允许写入运行产出文件的组件。
1. 不可变更的阶段中间产物：采用独占创建模式，一旦生成绝不允许覆盖；
2. 工作流最终结果文件：采用原子替换写入，更新状态时不会暴露半截损坏的JSON。
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 通用序列化工具：JSON/文本标准化转换
from cmo_lua_agent.artifacts.serializers import (
    ArtifactSerializationError,
    serialize_json,
    serialize_text,
)
# 全链路业务模型
from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ScenarioContract,
    ScenarioIR,
    ScenarioInput,
)

# RunID 合法正则规则：大小写字母、数字、._-，总长最多128字符
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
# 校验阶段名称 → 对应报告文件名映射
_VALIDATION_STAGES = {
    "schema": "schema_report",
    "semantic": "semantic_report",
    "ir": "ir_report",
    "database": "database_report",
    "manifest": "manifest_report",
    "lua_preflight": "lua_preflight_report",
}


# 持久化通用异常：序列化失败、文件写入失败抛出
class ArtifactPersistenceError(RuntimeError):
    """产出物序列化或安全持久化失败"""


# 不可变文件/运行目录已存在异常：禁止重复创建
class ArtifactAlreadyExistsError(ArtifactPersistenceError):
    """不可变运行产物或运行根目录已存在，禁止覆盖/复用"""


# 路径非法异常：绝对路径、跳出运行目录沙箱
class ArtifactPathError(ValueError):
    """产出路径是绝对路径，或路径会跳出当前run沙箱目录"""


@dataclass(frozen=True, slots=True)
class RunArtifactPaths:
    """单次流水线全量产出文件标准路径集合，固定目录结构"""
    run_id: str
    run_root: Path

    # 五大固定子目录
    @property
    def input_dir(self) -> Path:
        """原始输入目录"""
        return self.run_root / "input"

    @property
    def validation_dir(self) -> Path:
        """各阶段校验报告目录"""
        return self.run_root / "validation"

    @property
    def contract_dir(self) -> Path:
        """IR、契约、解析完成清单目录"""
        return self.run_root / "contract"

    @property
    def generation_dir(self) -> Path:
        """Lua脚本生成产物目录"""
        return self.run_root / "generation"

    @property
    def result_dir(self) -> Path:
        """工作流最终汇总结果目录"""
        return self.run_root / "result"

    # 具体文件路径定义
    @property
    def source_json(self) -> Path:
        """用户原始输入作战JSON"""
        return self.input_dir / "source.json"

    @property
    def schema_report(self) -> Path:
        """Schema语法校验报告"""
        return self.validation_dir / "schema_report.json"

    @property
    def semantic_report(self) -> Path:
        """语义逻辑校验报告"""
        return self.validation_dir / "semantic_report.json"

    @property
    def ir_report(self) -> Path:
        """IR中间表示校验报告"""
        return self.validation_dir / "ir_report.json"

    @property
    def database_report(self) -> Path:
        """CMO数据库DBID解析校验报告"""
        return self.validation_dir / "database_report.json"

    @property
    def manifest_report(self) -> Path:
        """Manifest construction validation report."""
        return self.validation_dir / "manifest_report.json"

    @property
    def lua_preflight_report(self) -> Path:
        """Lua生成前预检报告"""
        return self.validation_dir / "lua_preflight_report.json"

    @property
    def scenario_ir(self) -> Path:
        """标准化IR中间模型文件"""
        return self.contract_dir / "scenario_ir.json"

    @property
    def scenario_contract(self) -> Path:
        """全局资源契约文件"""
        return self.contract_dir / "scenario_contract.json"

    @property
    def resolved_manifest(self) -> Path:
        """数据库解析完成后的标准场景清单"""
        return self.contract_dir / "resolved_manifest.json"

    @property
    def original_lua(self) -> Path:
        """预检通过、正式可用的Lua脚本"""
        return self.generation_dir / "original.lua"

    @property
    def rejected_lua(self) -> Path:
        """预检失败、被拦截丢弃的半成品Lua"""
        return self.generation_dir / "rejected.lua"

    @property
    def workflow_result(self) -> Path:
        """整条流水线最终汇总结果（唯一允许原子覆盖的文件）"""
        return self.result_dir / "workflow_result.json"

    def to_dict(self) -> dict[str, str]:
        """路径集合序列化，用于日志、报表输出"""
        return {
            "run_id": self.run_id,
            "run_root": str(self.run_root),
            "input_dir": str(self.input_dir),
            "validation_dir": str(self.validation_dir),
            "contract_dir": str(self.contract_dir),
            "generation_dir": str(self.generation_dir),
            "result_dir": str(self.result_dir),
            "source_json": str(self.source_json),
            "schema_report": str(self.schema_report),
            "semantic_report": str(self.semantic_report),
            "ir_report": str(self.ir_report),
            "database_report": str(self.database_report),
            "manifest_report": str(self.manifest_report),
            "lua_preflight_report": str(self.lua_preflight_report),
            "scenario_ir": str(self.scenario_ir),
            "scenario_contract": str(self.scenario_contract),
            "resolved_manifest": str(self.resolved_manifest),
            "original_lua": str(self.original_lua),
            "rejected_lua": str(self.rejected_lua),
            "workflow_result": str(self.workflow_result),
        }


class RunArtifactStore:
    """单次流水线运行的产物持久化存储器，负责创建目录、写入所有不可变中间文件"""
    def __init__(self, paths: RunArtifactPaths) -> None:
        if not isinstance(paths, RunArtifactPaths):
            raise TypeError("paths 必须是 RunArtifactPaths 实例")
        self._paths = paths

    @classmethod
    def create(
        cls,
        runs_root: Path,
        *,
        run_id: str | None = None,
    ) -> "RunArtifactStore":
        """创建全新的运行根目录与全套子文件夹
        运行目录独占分配，历史运行目录绝不复用、覆盖。
        - 手动指定run_id：直接校验合法性并创建；
        - 不指定run_id：自动生成20次随机ID，直到分配到未占用目录。
        """
        root = _normalize_path(runs_root, field_name="runs_root")
        root.mkdir(parents=True, exist_ok=True)

        if run_id is not None:
            normalized_run_id = _normalize_run_id(run_id)
            return cls._create_once(root, normalized_run_id)

        # 自动生成随机run_id，最多重试20次
        for _ in range(20):
            generated = _generate_run_id()
            try:
                return cls._create_once(root, generated)
            except ArtifactAlreadyExistsError:
                continue

        raise ArtifactPersistenceError(
            f"无法在运行根目录分配唯一 run_id：{root}"
        )

    @classmethod
    def _create_once(
        cls,
        runs_root: Path,
        run_id: str,
    ) -> "RunArtifactStore":
        """原子创建单次运行完整目录树，失败则自动清理空目录"""
        run_root = (runs_root / run_id).resolve(strict=False)
        # 独占创建顶层run目录，exist_ok=False防止重复
        try:
            run_root.mkdir(parents=False, exist_ok=False)
        except FileExistsError as exc:
            raise ArtifactAlreadyExistsError(
                f"Run 运行目录已存在，禁止复用：{run_root}"
            ) from exc
        except OSError as exc:
            raise ArtifactPersistenceError(
                f"无法创建 Run 顶层目录：{run_root}：{exc}"
            ) from exc

        paths = RunArtifactPaths(run_id=run_id, run_root=run_root)
        # 批量创建5个子目录，任一失败则整体删除run根目录回滚
        try:
            for directory in (
                paths.input_dir,
                paths.validation_dir,
                paths.contract_dir,
                paths.generation_dir,
                paths.result_dir,
            ):
                directory.mkdir(exist_ok=False)
        except OSError as exc:
            shutil.rmtree(run_root, ignore_errors=True)
            raise ArtifactPersistenceError(
                f"初始化Run子目录失败，已回滚清空：{run_root}：{exc}"
            ) from exc

        return cls(paths)

    @property
    def paths(self) -> RunArtifactPaths:
        """获取当前运行所有标准路径对象"""
        return self._paths

    @property
    def run_id(self) -> str:
        return self._paths.run_id

    @property
    def run_root(self) -> Path:
        return self._paths.run_root

    def save_source(
        self,
        source: ScenarioInput | Mapping[str, Any],
    ) -> Path:
        """保存用户原始输入JSON"""
        if isinstance(source, ScenarioInput):
            value: Any = source.raw
        elif isinstance(source, Mapping):
            value = source
        else:
            raise TypeError(
                "source 必须为 ScenarioInput 或字典映射"
            )
        return self.write_json("input/source.json", value)

    def save_validation(self, stage: str, value: Any) -> Path:
        """保存指定阶段校验报告，仅允许预设5个校验阶段"""
        if not isinstance(stage, str):
            raise TypeError("validation stage 必须是字符串")
        normalized = stage.strip().lower()
        attribute = _VALIDATION_STAGES.get(normalized)
        if attribute is None:
            allowed = ", ".join(sorted(_VALIDATION_STAGES))
            raise ValueError(
                "Unknown validation stage；允许值："
                f"{allowed}"
            )
        target = getattr(self.paths, attribute)
        return self.write_json(target.relative_to(self.run_root), value)

    def save_ir(self, value: ScenarioIR) -> Path:
        """保存IR中间表示模型文件"""
        if not isinstance(value, ScenarioIR):
            raise TypeError("value 必须是 ScenarioIR 实例")
        return self.write_json("contract/scenario_ir.json", value)

    def save_contract(self, value: ScenarioContract) -> Path:
        """保存全局资源契约"""
        if not isinstance(value, ScenarioContract):
            raise TypeError("value 必须是 ScenarioContract 实例")
        return self.write_json(
            "contract/scenario_contract.json",
            value,
        )

    def save_manifest(
        self,
        value: ResolvedScenarioManifest,
    ) -> Path:
        """保存数据库解析完成的标准场景清单"""
        if not isinstance(value, ResolvedScenarioManifest):
            raise TypeError(
                "value 必须是 ResolvedScenarioManifest 实例"
            )
        return self.write_json(
            "contract/resolved_manifest.json",
            value,
        )

    def save_original_lua(self, text: str) -> Path:
        """保存预检通过、正式可用Lua（独占写入，不可覆盖）"""
        return self.write_text("generation/original.lua", text)

    def save_rejected_lua(self, text: str) -> Path:
        """保存预检失败被拦截的半成品Lua（独占写入）"""
        return self.write_text("generation/rejected.lua", text)

    def save_final_result(self, value: Any) -> Path:
        """保存整条工作流最终汇总结果，唯一允许原子覆盖更新的文件"""
        return self.write_json(
            "result/workflow_result.json",
            value,
            replace=True,
        )

    def write_json(
        self,
        relative_path: str | Path,
        value: Any,
        *,
        replace: bool = False,
    ) -> Path:
        """通用JSON写入入口：自动序列化+持久化
        replace=False：独占新建，禁止覆盖（中间产物默认）
        replace=True：原子替换覆盖（仅最终结果文件使用）
        """
        target = self._resolve_target(relative_path)
        try:
            text = serialize_json(value)
        except (ArtifactSerializationError, TypeError, ValueError) as exc:
            raise ArtifactPersistenceError(
                f"JSON产物序列化失败 {target}：{exc}"
            ) from exc
        self._persist_text(target, text, replace=replace)
        return target

    def write_text(
        self,
        relative_path: str | Path,
        text: str,
        *,
        replace: bool = False,
    ) -> Path:
        """通用纯文本写入入口（Lua脚本），自动标准化换行符"""
        target = self._resolve_target(relative_path)
        try:
            normalized = serialize_text(text)
        except TypeError as exc:
            raise ArtifactPersistenceError(
                f"文本产物序列化失败 {target}：{exc}"
            ) from exc
        self._persist_text(target, normalized, replace=replace)
        return target

    def _resolve_target(self, relative_path: str | Path) -> Path:
        """路径安全沙箱校验：
        1. 禁止绝对路径；
        2. 解析后不能跳出run_root沙箱目录；
        3. 不能等于根目录，必须指向文件。
        """
        try:
            candidate = Path(relative_path)
        except TypeError as exc:
            raise ArtifactPathError(
                "产物路径必须为合法路径类型"
            ) from exc

        if candidate.is_absolute():
            raise ArtifactPathError(
                f"产物路径必须是相对于run根目录的相对路径：{candidate}"
            )

        target = (self.run_root / candidate).resolve(strict=False)
        if not target.is_relative_to(self.run_root):
            raise ArtifactPathError(
                f"路径逃逸run沙箱目录：{candidate}"
            )
        if target == self.run_root:
            raise ArtifactPathError(
                "路径必须指向具体文件，不能为目录根"
            )
        return target

    @staticmethod
    def _persist_text(
        target: Path,
        text: str,
        *,
        replace: bool,
    ) -> None:
        """分发写入逻辑：区分独占新建 / 原子替换覆盖"""
        if not isinstance(replace, bool):
            raise TypeError("replace 必须为布尔值")
        if replace:
            _write_atomic_replace(target, text)
        else:
            _write_exclusive(target, text)


def _write_exclusive(path: Path, text: str) -> None:
    """独占创建写入：O_EXCL模式，文件存在直接报错，用于所有不可变中间产物
    特点：一旦生成永久不可修改、覆盖，保证中间快照唯一不变。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        # 底层系统调用：仅新建，存在即抛异常
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o644,
        )
        created = True
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ArtifactAlreadyExistsError(
            f"文件已存在，禁止覆盖：{path}"
        ) from exc
    except OSError as exc:
        # 创建成功但写入失败，删除残缺文件
        if created:
            _remove_file(path)
        raise ArtifactPersistenceError(
            f"独占写入文件失败：{path}：{exc}"
        ) from exc


def _write_atomic_replace(path: Path, text: str) -> None:
    """原子替换写入：先写临时文件，全部写完再重命名覆盖原文件
    仅用于 workflow_result.json，保证任何时刻读取文件都是完整合法JSON，不会读到半截损坏文件。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        descriptor, raw_temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            text=True,
        )
        temp_path = Path(raw_temp_path)
        # 完整写入并刷盘，确保内容落盘
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        # 原子重命名替换，操作系统保证瞬间切换
        os.replace(temp_path, path)
        temp_path = None
    except OSError as exc:
        raise ArtifactPersistenceError(
            f"原子写入文件失败：{path}：{exc}"
        ) from exc
    finally:
        # 清理临时文件
        if temp_path is not None:
            _remove_file(temp_path)


def _remove_file(path: Path) -> None:
    """容错删除文件，不存在也不抛异常"""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _normalize_path(value: Path, *, field_name: str) -> Path:
    """路径标准化：展开家目录、转为绝对真实路径"""
    try:
        return Path(value).expanduser().resolve(strict=False)
    except TypeError as exc:
        raise TypeError(f"{field_name} 必须是合法路径类型") from exc


def _normalize_run_id(run_id: str) -> str:
    """校验并标准化用户传入的run_id，不符合命名规则直接报错"""
    if not isinstance(run_id, str):
        raise TypeError("run_id 必须是字符串")
    normalized = run_id.strip()
    if not _RUN_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            "run_id 仅允许大小写字母、数字、. _ -，首字符必须为字母/数字，总长不超过128字符"
        )
    return normalized


def _generate_run_id() -> str:
    """自动生成全局唯一run_id：时间戳+4字节随机十六进制，保证几乎无碰撞"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"run-{timestamp}-{secrets.token_hex(4)}"
