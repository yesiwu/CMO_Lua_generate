"""JSON → Lua 流水线的应用组装入口。

这个文件只负责“把各个模块接起来”，不真正执行业务。

创建应用时会：
1. 检查配置路径；
2. 创建数据库仓库、Lua 生成器、Skill 仓库；
3. 创建 LuaGenerationService；
4. 创建完整的 ScenarioWorkflow。

注意：
这里只完成依赖组装，不会真的生成 Lua，也不会立即查询数据库。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cmo_lua_agent.contract import (
    DatabaseResolver,
    IRBuilder,
    IRValidator,
    ManifestBuilder,
    ScenarioSchemaValidator,
    ScenarioSemanticValidator,
)
from cmo_lua_agent.generation import (
    LuaGenerationService,
    LuaPreflightValidator,
)
from cmo_lua_agent.ingest import JsonLoader
from cmo_lua_agent.integrations.cmolua import (
    CmoDatabaseRepository,
    CmoLuaGeneratorAdapter,
    CmoLuaIntegrationConfig,
    CmoSkillRepository,
)
from cmo_lua_agent.orchestration import ScenarioWorkflow


@dataclass(frozen=True, slots=True)
class CmoLuaApplication:
    """保存已经组装好的整套应用组件。

    可以把它理解成一个“应用容器”：
    外部只需要拿到这个对象，就可以访问数据库、Lua 生成器和完整工作流。

    frozen=True 表示容器中的依赖创建后不应该随意替换。
    """

    project_root: Path
    config: CmoLuaIntegrationConfig
    database_repository: CmoDatabaseRepository
    generator_adapter: CmoLuaGeneratorAdapter
    skill_repository: CmoSkillRepository
    generation_service: LuaGenerationService
    scenario_workflow: ScenarioWorkflow

    def __post_init__(self) -> None:
        # 统一项目根目录格式，避免后续各模块处理不同形式的路径
        object.__setattr__(
            self,
            "project_root",
            Path(self.project_root).expanduser().resolve(strict=False),
        )

        # 确保组装进来的依赖类型正确，尽早发现错误配置
        _require_instance(
            self.config,
            CmoLuaIntegrationConfig,
            field_name="config",
        )
        _require_instance(
            self.database_repository,
            CmoDatabaseRepository,
            field_name="database_repository",
        )
        _require_instance(
            self.generator_adapter,
            CmoLuaGeneratorAdapter,
            field_name="generator_adapter",
        )
        _require_instance(
            self.skill_repository,
            CmoSkillRepository,
            field_name="skill_repository",
        )
        _require_instance(
            self.generation_service,
            LuaGenerationService,
            field_name="generation_service",
        )
        _require_instance(
            self.scenario_workflow,
            ScenarioWorkflow,
            field_name="scenario_workflow",
        )


def create_application(
    project_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> CmoLuaApplication:
    """创建并连接 JSON → Lua 流水线需要的全部组件。

    这个函数是本文件最核心的地方。

    它负责把：

        配置
          ↓
        数据库 / Lua生成器 / Skill仓库
          ↓
        LuaGenerationService
          ↓
        ScenarioWorkflow

    连接成一个完整应用。

    这里只负责组装，不会真正执行数据库查询或 Lua 生成。
    """

    root = _normalize_project_root(project_root)

    # 根据项目目录和环境变量加载 CMO 集成配置
    config = CmoLuaIntegrationConfig.from_project_root(
        root,
        environ=environ,
    )

    # 底层外部资源访问层
    database_repository = CmoDatabaseRepository(config)
    generator_adapter = CmoLuaGeneratorAdapter(config)
    skill_repository = CmoSkillRepository(config)

    # Lua 生成服务：
    # 对外封装 Lua 生成器，并在生成前执行基本检查
    generation_service = LuaGenerationService(
        adapter=generator_adapter,
        preflight_validator=LuaPreflightValidator(),
        workspace_root=root,
    )

    # 组装完整的 JSON → Lua 业务流水线
    scenario_workflow = ScenarioWorkflow(
        loader=JsonLoader(),

        # 第一层：检查输入 JSON 是否符合结构要求
        schema_validator=ScenarioSchemaValidator(),

        # 第二层：检查数据内容是否合理
        semantic_validator=ScenarioSemanticValidator(),

        # 把原始场景转换为系统内部统一表示 IR
        ir_builder=IRBuilder(),

        # 再检查生成出来的 IR 是否有效
        ir_validator=IRValidator(),

        # 解析平台、DBID 等数据库信息
        database_resolver=DatabaseResolver(
            database_repository
        ),

        # 根据处理后的场景构造生成任务描述
        manifest_builder=ManifestBuilder(),

        # 最终负责 Lua 生成
        generation_service=generation_service,
    )

    # 把所有组装好的对象统一返回
    return CmoLuaApplication(
        project_root=root,
        config=config,
        database_repository=database_repository,
        generator_adapter=generator_adapter,
        skill_repository=skill_repository,
        generation_service=generation_service,
        scenario_workflow=scenario_workflow,
    )


def _normalize_project_root(value: Path) -> Path:
    """统一项目根目录格式。"""

    try:
        return Path(value).expanduser().resolve(strict=False)
    except TypeError as exc:
        raise TypeError("project_root 必须是有效的路径") from exc


def _require_instance(
    value: object,
    expected_type: type[object],
    *,
    field_name: str,
) -> None:
    """检查应用容器中的依赖类型是否正确。"""

    if not isinstance(value, expected_type):
        raise TypeError(
            f"{field_name} 必须是 {expected_type.__name__} 类型"
        )


__all__ = [
    "CmoLuaApplication",
    "create_application",
]