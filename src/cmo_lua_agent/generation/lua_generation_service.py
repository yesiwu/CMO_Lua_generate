"""Lua 生成计算服务。

这个版本和上面被注释掉的旧版本有一个重要区别：

旧版本：
    LuaGenerationService 自己负责：
    - 保存 Manifest
    - 调生成器
    - 预检
    - 保存 Lua

新版本：
    LuaGenerationService 只负责：
    - 读取已经保存好的 Manifest
    - 调用 Lua 生成器
    - 做 Lua 预检
    - 返回生成结果

真正的文件保存统一交给 RunArtifactStore。

也就是说：

    RunArtifactStore
        ↓ 保存 Manifest

    LuaGenerationService
        ↓ 读取 Manifest
        ↓ 调生成器
        ↓ 预检 Lua
        ↓ 返回候选结果

    RunArtifactStore
        ↓ 决定是否保存 Lua

这样“计算逻辑”和“文件持久化”被拆开。
"""

from __future__ import annotations

from pathlib import Path

from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ScenarioContract,
)

from cmo_lua_agent.generation.lua_preflight_validator import (
    LuaPreflightValidator,
)

from cmo_lua_agent.generation.models import (
    LuaGenerationResult,
)

from cmo_lua_agent.integrations.cmolua.generator_adapter import (
    CmoLuaGeneratorAdapter,
)


class LuaGenerationService:
    """根据已经保存好的 Manifest 生成 Lua，并执行生成前后的完整性检查。

    注意：
    这个 Service 不负责写文件。

    它只负责“生成 + 校验”。

    Manifest 和 Lua 最终保存在哪里，由外层 Workflow / RunArtifactStore 决定。
    """

    def __init__(
        self,
        *,
        adapter: CmoLuaGeneratorAdapter,
        preflight_validator: LuaPreflightValidator,
        workspace_root: Path,
    ) -> None:

        # adapter 负责真正调用外部 JSON→Lua 生成器。
        self._adapter = adapter

        # preflight_validator 负责检查生成出来的 Lua 是否满足基本要求。
        self._preflight_validator = preflight_validator

        # 工作区根目录。
        # Lua 预检时需要用它判断输出路径是否合理、安全。
        self._workspace_root = _normalize_path(
            workspace_root,
            field_name="workspace_root",
        )

    def generate(
        self,
        *,
        manifest: ResolvedScenarioManifest,
        contract: ScenarioContract,
        manifest_path: Path,
        output_path: Path,
    ) -> LuaGenerationResult:
        """执行一次：

        Manifest
            ↓
        外部 Lua 生成器
            ↓
        Lua 候选代码
            ↓
        Preflight 预检
            ↓
        LuaGenerationResult

        注意：
        output_path 这里只表示“如果通过预检，未来应该保存到哪里”。

        本方法不会真的创建这个文件。
        """

        # 保证上游传入的是已经数据库解析完成的标准 Manifest。
        if not isinstance(
            manifest,
            ResolvedScenarioManifest,
        ):
            raise TypeError(
                "manifest 必须是 ResolvedScenarioManifest"
            )

        # contract 用于预检时核对单位、射手、目标等场景资源。
        if not isinstance(
            contract,
            ScenarioContract,
        ):
            raise TypeError(
                "contract 必须是 ScenarioContract"
            )

        # Lua 生成器读取的是已经真正落盘的 Manifest 文件。
        #
        # 所以这里要求：
        # manifest_path 必须真实存在，而且必须是普通文件。
        resolved_manifest_path = _require_existing_file(
            manifest_path,
            field_name="manifest_path",
        )

        # output_path 只是预期输出位置。
        # 此时还不会真正写入 Lua。
        resolved_output_path = _normalize_path(
            output_path,
            field_name="output_path",
        )

        # 真正调用外部 CMO Lua 生成器。
        #
        # 输入：
        #   resolved_manifest.json
        #
        # 输出一般包含：
        #   lua_text
        #   warnings
        raw_result = self._adapter.generate(
            resolved_manifest_path
        )

        # 对生成出来的 Lua 做预检。
        #
        # 这里不是执行 CMO，
        # 而是先检查 Lua 是否具备进入下一阶段的基本条件。
        preflight = self._preflight_validator.validate(
            raw_result.lua_text,

            # 用 Manifest 检查生成结果是否和场景数据一致
            manifest=manifest,

            # 用 Contract 检查单位、射手、目标等引用
            contract=contract,

            # 告诉预检器未来 Lua 应该保存到哪里
            output_path=resolved_output_path,

            # 用于路径安全检查
            workspace_root=self._workspace_root,

            # 生成器本身产生的 warning 也一起进入预检结果
            generator_warnings=raw_result.warnings,
        )

        # 无论预检成功还是失败，
        # 都统一返回 LuaGenerationResult。
        #
        # 如果通过：
        #   success=True
        #   output_path=预期Lua路径
        #
        # 如果失败：
        #   success=False
        #   output_path=None
        #
        # 但 lua_text 仍然保留，
        # 外层可以把失败 Lua 保存成 rejected Lua，方便调试。
        return LuaGenerationResult(
            success=preflight.valid,

            lua_text=raw_result.lua_text,

            output_path=(
                resolved_output_path
                if preflight.valid
                else None
            ),

            generator_warnings=raw_result.warnings,

            preflight=preflight,
        )


def _require_existing_file(
    value: Path,
    *,
    field_name: str,
) -> Path:
    """要求某个路径必须已经存在，而且必须是普通文件。

    当前主要用于 manifest_path。

    因为 Manifest 应该由前面的 ArtifactStore 先保存好，
    LuaGenerationService 这里只负责读取它。
    """

    path = _normalize_path(
        value,
        field_name=field_name,
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"Manifest 文件不存在或不是普通文件：{path}"
        )

    return path


def _normalize_path(
    value: Path,
    *,
    field_name: str,
) -> Path:
    """把输入路径转换成统一的绝对路径。

    主要处理：
    - ~ 用户目录
    - 相对路径
    - Path 对象标准化
    """

    try:
        return (
            Path(value)
            .expanduser()
            .resolve(strict=False)
        )

    except TypeError as exc:
        raise TypeError(
            f"{field_name} 必须是合法路径"
        ) from exc