# JSON → Lua 双模式接入实施计划

> **执行要求：** 按任务顺序实施；每个任务使用 TDD：先写失败测试、确认失败、实现最小代码、确认测试通过，再提交。
>
> **计划位置：** `docs/plans/json-to-lua-mvp-plan.md`

**目标：** 在不重写 `CMOLua-main`、不引入修复/评分/多候选/强化学习的前提下，打通一条可信的“标准 JSON → 校验与数据库补全 → Lua → Preflight → 可选 CMO 执行 → Run 产物”链路，并同时服务 Chat 与 CLI Run 两种入口。

**架构：** `CMOLua-main` 作为项目内冻结、只读的外部领域能力。当前系统通过三个薄适配层调用其生成器、数据库查询和 Skill 文档。所有 JSON→Lua 业务逻辑集中在 `ScenarioWorkflow`，Chat 与 CLI 只负责构造请求、选择执行策略和展示结果。

**技术栈：** Python 3.13、标准库 `dataclasses/json/pathlib/importlib/sqlite3`、pytest、现有 Tool/Hook/CMO BatchRunner 基础设施。

## 全局约束

1. 不实现 `version_manifest`。
2. 不实现数据库 Schema 探查脚本。
3. 不重写内部 Lua Renderer；首版复用 `CMOLua-main/tools/json_to_lua.py::generate_cmo_lua()`。
4. 不启动 MCP Server；直接复用 `CMOLua-main/mcp/query.py` 的 Python 查询能力。
5. 不实现 Lua 自动修复、战斗评分、多候选、经验记忆、轨迹、SFT 或 GRPO。
6. `CMOLua-main` 在本阶段视为冻结依赖；业务代码不得修改其文件。
7. 所有数据库访问必须只读。
8. Chat 模式只生成和检查 Lua，不自动执行 CMO。
9. CLI Run 模式由命令本身授权执行；运行期间不得调用 `input()`。
10. 舰载机有合法 `base` 时，描述性坐标规范化为 `positionMode="inherit_base"`。
11. 缺少 `weaponDbid` 时，只允许数据库精确名称唯一命中后补齐；零命中或多命中均阻断。
12. 单位引用、目标引用、DBID、Loadout、弹药超量、非法坐标相关问题为 error；推荐写法等非关键问题为 warning。
13. 不覆盖已有 Lua，不允许输出路径越过项目工作区。
14. 所有阶段产物写入独立 `runs/run_<timestamp>_<suffix>/`；首版不创建 `repair/` 目录。

---

## 一、最终激活的目录与文件

```text
src/cmo_lua_agent/
├── ingest/
│   ├── json_loader.py
│   └── json_profiler.py
├── contract/
│   ├── models.py
│   ├── scenario_schema_validator.py
│   ├── scenario_semantic_validator.py
│   ├── ir_builder.py
│   ├── ir_validator.py
│   ├── database_resolver.py
│   └── manifest_builder.py
├── integrations/cmolua/
│   ├── config.py
│   ├── generator_adapter.py
│   ├── database_repository.py
│   └── skill_repository.py
├── generation/
│   ├── models.py
│   ├── lua_generation_service.py
│   └── lua_preflight_validator.py
├── artifacts/
│   ├── serializers.py
│   └── run_artifact_store.py
├── orchestration/
│   ├── execution_policy.py
│   ├── workflow_context.py
│   ├── workflow_state.py
│   └── scenario_workflow.py
├── tools/
│   ├── factory.py
│   ├── generate_cmo_lua_tool.py
│   ├── search_cmo_skill_tool.py
│   └── read_cmo_skill_tool.py
├── cli/
│   └── run_scenario.py
└── main.py
```

当前不删除但不注册、不导入、不继续开发：

```text
repair/
evaluation/
optimization/
memory/
trajectory/
training/
generation/strategy_*.py
generation/candidate_generator.py
orchestration/lua_repair_workflow.py
orchestration/optimization_workflow.py
orchestration/training_workflow.py
```

---

# MVP 0：CMOLua 外部适配与 Golden

## Task 0.1：复核并固定集成配置

**文件：**
- 已有：`src/cmo_lua_agent/integrations/cmolua/config.py`
- 修改：`src/cmo_lua_agent/integrations/cmolua/__init__.py`
- 测试：`tests/integrations/cmolua/test_config.py`

**接口：**

```python
@dataclass(frozen=True, slots=True)
class CmoLuaIntegrationConfig:
    skill_root: Path
    generator_path: Path
    database_path: Path
    outputs_dir: Path
    generator_function: str = "generate_cmo_lua"

    @classmethod
    def from_project_root(
        cls,
        project_root: Path,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "CmoLuaIntegrationConfig": ...

    def validate(self) -> "CmoLuaIntegrationConfig": ...
```

**实施步骤：**

- [ ] 检查现有测试是否覆盖默认路径、环境变量覆盖、相对路径解析和缺失依赖。
- [ ] 删除任何 `version_manifest` 导入或调用。
- [ ] 确认 `validate()` 只检查路径，不读取数据库、不导入生成器、不创建目录。
- [ ] 运行：

```powershell
$env:PYTHONPATH="$PWD\src"
pytest tests\integrations\cmolua\test_config.py -q
```

预期：全部通过。

**验收：** `CmoLuaIntegrationConfig.from_project_root(project_root)` 能得到四个稳定路径和生成器函数名。

---

## Task 0.2：实现 `CmoLuaGeneratorAdapter`

**文件：**
- 创建：`src/cmo_lua_agent/integrations/cmolua/generator_adapter.py`
- 修改：`src/cmo_lua_agent/integrations/cmolua/__init__.py`
- 测试：`tests/integrations/cmolua/test_generator_adapter.py`

**职责：** 动态加载外部 `json_to_lua.py`，取得 `generate_cmo_lua`，调用后返回 Lua 文本。Adapter 不做 Schema、DB、Preflight、保存或执行。

**接口：**

```python
class CmoLuaGeneratorImportError(RuntimeError): ...
class CmoLuaGenerationError(RuntimeError): ...

@dataclass(frozen=True, slots=True)
class GeneratorRawResult:
    lua_text: str
    warnings: tuple[str, ...]

class CmoLuaGeneratorAdapter:
    def __init__(self, config: CmoLuaIntegrationConfig) -> None: ...

    def generate(self, manifest_path: Path) -> GeneratorRawResult: ...
```

**关键实现规则：**

```python
spec = importlib.util.spec_from_file_location(
    "_cmo_lua_external_generator",
    config.generator_path,
)
```

- 导入失败 → `CmoLuaGeneratorImportError`
- 函数不存在或不可调用 → `CmoLuaGeneratorImportError`
- 生成函数抛异常 → `CmoLuaGenerationError`
- 返回值不是非空字符串 → `CmoLuaGenerationError`
- 捕获 `stderr` 中以 `[warn]` 开头的行，转换为 `warnings`
- 不修改 `sys.path`
- 不依赖当前工作目录
- 每个 Adapter 实例只加载一次模块

**测试顺序：**

- [ ] 写测试：临时生成器正常返回 Lua。
- [ ] 运行测试，确认因模块不存在而失败。
- [ ] 实现最小动态导入。
- [ ] 写测试：函数缺失、导入语法错误、执行异常、空返回值。
- [ ] 写测试：捕获 `[warn]`，且不会打印到终端。
- [ ] 运行：

```powershell
pytest tests\integrations\cmolua\test_generator_adapter.py -q
```

**验收：** 可稳定调用真实 `generate_cmo_lua(path)`，上层只收到结构化结果。

---

## Task 0.3：实现只读 `CmoDatabaseRepository`

**文件：**
- 创建：`src/cmo_lua_agent/integrations/cmolua/database_repository.py`
- 修改：`src/cmo_lua_agent/integrations/cmolua/__init__.py`
- 测试：`tests/integrations/cmolua/test_database_repository.py`

**职责：** 直接加载 `CMOLua-main/mcp/query.py`，将其查询能力包装成当前项目稳定接口。Repository 不决定业务规则，不写 Manifest，不保存报告。

**模型与接口：**

```python
@dataclass(frozen=True, slots=True)
class CmoDatabaseRecord:
    dbid: int
    name: str
    category: str
    raw: Mapping[str, Any]

class CmoDatabaseRepository:
    def find_weapon_exact(self, name: str) -> tuple[CmoDatabaseRecord, ...]: ...
    def get_platform(self, dbid: int) -> CmoDatabaseRecord | None: ...
    def get_loadout(self, loadout_id: int) -> CmoDatabaseRecord | None: ...
    def loadout_belongs_to_aircraft(
        self,
        *,
        aircraft_dbid: int,
        loadout_id: int,
    ) -> bool: ...
```

**实现策略：**

- 使用 `query.py` 公开的 `read_query()` 等现有函数。
- SQL 文本由 Repository 内部固定生成，不接受用户 SQL。
- 精确名称查询使用 `WHERE Name = ?`，禁止自动模糊匹配。
- 所有结果映射为 `CmoDatabaseRecord`。
- 数据库不存在、查询模块导入失败、Schema 不兼容时抛：

```python
class CmoDatabaseInfrastructureError(RuntimeError): ...
```

**测试顺序：**

- [ ] 使用临时 `query.py` Stub 验证调用和结果转换。
- [ ] 验证名称参数按参数化查询传递，不拼接进 SQL。
- [ ] 验证零命中、唯一命中、多命中均原样返回。
- [ ] 验证 Repository 没有写数据库接口。
- [ ] 运行：

```powershell
pytest tests\integrations\cmolua\test_database_repository.py -q
```

**验收：** 上层无需了解 `query.py` 的模块路径、返回格式或缓存实现。

---

## Task 0.4：实现 `CmoSkillRepository`

**文件：**
- 创建：`src/cmo_lua_agent/integrations/cmolua/skill_repository.py`
- 测试：`tests/integrations/cmolua/test_skill_repository.py`

**接口：**

```python
SkillArea = Literal[
    "skill",
    "templates",
    "references",
    "errors",
    "examples",
]

@dataclass(frozen=True, slots=True)
class SkillSearchHit:
    relative_path: str
    area: str
    line_number: int
    snippet: str

@dataclass(frozen=True, slots=True)
class SkillReadResult:
    relative_path: str
    start_line: int
    end_line: int
    text: str
    truncated: bool

class CmoSkillRepository:
    def search(
        self,
        query: str,
        *,
        area: SkillArea | None = None,
        limit: int = 10,
    ) -> tuple[SkillSearchHit, ...]: ...

    def read(
        self,
        relative_path: str,
        *,
        start_line: int = 1,
        limit: int = 200,
    ) -> SkillReadResult: ...
```

**允许范围：**

```text
SKILL.md
templates/
references/
errors/
examples/
```

**禁止范围：**

```text
mcp/
db/
outputs/
_archive/
.git/
*.db
*.db3
*.zip
图片和二进制文件
```

**测试顺序：**

- [ ] 中文关键词可命中。
- [ ] `area` 过滤生效。
- [ ] `limit` 和行范围生效。
- [ ] `../`、绝对路径、符号链接越界被拒绝。
- [ ] 数据库、归档和历史输出不能读取。
- [ ] 运行：

```powershell
pytest tests\integrations\cmolua\test_skill_repository.py -q
```

**验收：** Chat 可以按需读取小块文档，不能一次加载整套 Skill。

---

## Task 0.5：建立 Golden 回归基线

**文件：**
- 创建：`tests/fixtures/cmolua/golden/source.json`
- 创建：`tests/fixtures/cmolua/golden/expected_assertions.json`
- 可选保存：`tests/fixtures/cmolua/golden/expected.lua`
- 创建：`tests/integrations/cmolua/test_golden_generation.py`

**原则：** 首版不做全文逐字符比较，优先比较稳定语义断言，避免注释或空白变化导致无意义失败。

`expected_assertions.json` 至少记录：

```json
{
  "required_fragments": [
    "红方",
    "蓝方",
    "function main",
    "function clear",
    "function reload"
  ],
  "required_unit_names": [],
  "forbidden_fragments": [
    "DumpAmmo",
    "remove_weapon"
  ],
  "minimum_length": 1000
}
```

**测试：**

- [ ] 真实 Adapter 生成非空 Lua。
- [ ] 所有关键单位名、阵营名、DBID 和五个主要作战段存在。
- [ ] 禁止 API 不存在。
- [ ] 同一 JSON 连续生成两次，语义断言一致。
- [ ] 测试默认标记为 `integration`，未提供真实 CMOLua 目录时跳过，而不是失败。

**验收：** 当前标准 JSON 可以稳定生成一份可回归检查的 Lua。

---

# MVP 1：JSON 契约与 Manifest

## Task 1.1：定义公共模型和校验结果

**文件：**
- 创建或重写：`src/cmo_lua_agent/contract/models.py`
- 创建：`tests/contract/test_models.py`

**模型：**

```python
class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"

@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    path: str
    severity: ValidationSeverity

@dataclass(frozen=True, slots=True)
class ValidationResult:
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(
            item.severity is ValidationSeverity.ERROR
            for item in self.issues
        )
```

再定义：

```python
@dataclass(frozen=True, slots=True)
class ScenarioInput:
    source_path: Path
    raw: Mapping[str, Any]

@dataclass(frozen=True, slots=True)
class ScenarioIR:
    data: Mapping[str, Any]

@dataclass(frozen=True, slots=True)
class ScenarioContract:
    scenario_id: str
    unit_ids: tuple[str, ...]
    unit_names: tuple[str, ...]
    shooter_ids: tuple[str, ...]
    target_ids: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class ResolvedScenarioManifest:
    data: Mapping[str, Any]
```

**要求：**

- 模型可转换为 JSON。
- 不在 dataclass 构造器中访问文件、数据库或生成器。
- `ValidationIssue.code` 使用稳定机器码，如 `schema.missing_field`。

**验收命令：**

```powershell
pytest tests\contract\test_models.py -q
```

---

## Task 1.2：实现安全 `JsonLoader`

**文件：**
- 修改：`src/cmo_lua_agent/ingest/json_loader.py`
- 测试：`tests/ingest/test_json_loader.py`

**接口：**

```python
class JsonLoadError(ValueError): ...

class JsonLoader:
    def load(self, path: Path) -> ScenarioInput: ...
```

**行为：**

- 只接受存在的普通 `.json` 文件。
- 使用 `utf-8-sig`，兼容 BOM。
- 顶层必须是对象。
- 不修改原始 JSON。
- 解析失败错误中包含文件路径和行列号。

**验收：**

```powershell
pytest tests\ingest\test_json_loader.py -q
```

---

## Task 1.3：实现结构校验器

**文件：**
- 创建或修改：`src/cmo_lua_agent/contract/scenario_schema_validator.py`
- 测试：`tests/contract/test_scenario_schema_validator.py`
- 文档：`docs/contracts/scenario-json-v1.md`

**接口：**

```python
class ScenarioSchemaValidator:
    def validate(self, scenario: ScenarioInput) -> ValidationResult: ...
```

**首版结构规则：**

1. 顶层必须有 `scenario`、`sides`、`strikePlan`。
2. `sides.red`、`sides.blue` 必须存在且含 `name`、`units`。
3. 每个单位至少有 `id`、`name`、`dbid`、`type`。
4. 固定部署单位经纬度必须为数字。
5. 舰载机存在字符串坐标时，必须有非空 `base`；后续语义阶段规范化。
6. `strikePlan` 每项必须有 `shooter` 或 `shooters`，必须有非空 `targets`。
7. `loaded`、`fired` 必须是非负整数。
8. `weaponDbid` 可以缺失，但存在时必须是正整数。
9. Schema 阶段不访问数据库、不验证引用是否存在。

**错误码示例：**

```text
schema.missing_field
schema.invalid_type
schema.invalid_coordinate
schema.invalid_quantity
schema.invalid_shooter_shape
```

**验收：** 标准 JSON 通过；缺字段和类型错误失败。

---

## Task 1.4：实现语义校验与规范化

**文件：**
- 创建或修改：`src/cmo_lua_agent/contract/scenario_semantic_validator.py`
- 测试：`tests/contract/test_scenario_semantic_validator.py`

**接口：**

```python
@dataclass(frozen=True, slots=True)
class SemanticValidationOutput:
    normalized: Mapping[str, Any]
    validation: ValidationResult

class ScenarioSemanticValidator:
    def validate_and_normalize(
        self,
        scenario: ScenarioInput,
    ) -> SemanticValidationOutput: ...
```

**规范化规则：**

```text
shooter: "id"
→ shooters: ["id"]

舰载机有合法 base 且坐标为描述字符串或缺失
→ positionMode: "inherit_base"
→ 删除描述性 latitude/longitude/heading/speed
```

**语义规则：**

- 单位 ID 全局唯一。
- 单位名全局唯一。
- `base` 和 `aircraftCarried` 引用存在。
- 舰载机 `base` 属于同一阵营。
- shooter 引用存在。
- target 引用存在且属于敌方。
- `loaded >= fired >= 0`。
- `strikePlan.fired` 不超过对应射手同武器可用量。
- 发现重复或错误引用时不继续猜测。

**错误码示例：**

```text
semantic.duplicate_unit_id
semantic.duplicate_unit_name
semantic.unknown_base
semantic.unknown_shooter
semantic.unknown_target
semantic.friendly_target
semantic.ammo_exceeded
```

**验收：** 重复 ID、错误引用、弹药超量被阻断；舰载机继承母舰位置被规范化。

---

## Task 1.5：实现 IR Builder 与 IR Validator

**文件：**
- 修改：`src/cmo_lua_agent/contract/ir_builder.py`
- 修改：`src/cmo_lua_agent/contract/ir_validator.py`
- 测试：`tests/contract/test_ir_builder.py`
- 测试：`tests/contract/test_ir_validator.py`

**接口：**

```python
class IRBuilder:
    def build(
        self,
        normalized: Mapping[str, Any],
    ) -> ScenarioIR: ...

class IRValidator:
    def validate(self, ir: ScenarioIR) -> ValidationResult: ...
```

**IR 只做确定性整理：**

- 建立 `unit_by_id`。
- 为单位增加 `side_key`。
- shooter 统一为数组。
- 保留原始业务字段。
- 记录 `positionMode`。
- 不查询数据库、不生成 Lua。

**验收：** 同一输入重复构建完全一致；IR 中不存在 `shooter` 单数形式。

---

## Task 1.6：实现数据库补全与校验

**文件：**
- 创建或修改：`src/cmo_lua_agent/contract/database_resolver.py`
- 测试：`tests/contract/test_database_resolver.py`

**接口：**

```python
@dataclass(frozen=True, slots=True)
class DatabaseResolutionOutput:
    resolved_ir: ScenarioIR
    validation: ValidationResult
    report: Mapping[str, Any]

class DatabaseResolver:
    def __init__(
        self,
        repository: CmoDatabaseRepository,
    ) -> None: ...

    def resolve(
        self,
        ir: ScenarioIR,
    ) -> DatabaseResolutionOutput: ...
```

**规则：**

- 显式平台 `dbid` 必须存在。
- 舰载机 `loadoutId` 必须存在并属于该飞机。
- 武器有 `weaponDbid`：验证 ID 存在且名称一致。
- 武器缺 `weaponDbid`：按名称精确查询。
- 唯一命中：补齐并记录 `resolutionSource="database_exact_name"`。
- 零命中：`database.weapon_not_found`。
- 多命中：`database.weapon_ambiguous`。
- 禁止调用 generator 的兜底 DBID 表。

**验收：** 未知 DBID、Loadout 不匹配、武器零命中和多命中均失败。

---

## Task 1.7：实现 Manifest Builder

**文件：**
- 创建或修改：`src/cmo_lua_agent/contract/manifest_builder.py`
- 测试：`tests/contract/test_manifest_builder.py`
- 文档：`docs/contracts/resolved-manifest-v1.md`

**接口：**

```python
@dataclass(frozen=True, slots=True)
class ManifestBuildOutput:
    manifest: ResolvedScenarioManifest
    contract: ScenarioContract
    validation: ValidationResult

class ManifestBuilder:
    def build(
        self,
        resolved_ir: ScenarioIR,
    ) -> ManifestBuildOutput: ...
```

**要求：**

- 输出结构仍兼容 `generate_cmo_lua()` 需要的 `scenario/sides/strikePlan`。
- 所有 `weaponDbid` 已显式补齐。
- 所有 shooter 统一为 `shooters`；若外部生成器仍需单数，则 Adapter 前建立兼容视图，不污染 IR。
- 生成 `ScenarioContract`，记录单位 ID/名称、射手、目标、DBID 和 Loadout 的允许集合。
- Manifest 不包含运行目录、日志路径或 CMO 执行状态。

**验收：** 相同 IR 生成相同 Manifest；Manifest 可 JSON 序列化并可交给 Adapter。

---

# MVP 2：Lua 生成服务与 Preflight

## Task 2.1：定义生成模型

**文件：**
- 修改：`src/cmo_lua_agent/generation/models.py`
- 测试：`tests/generation/test_models.py`

**接口：**

```python
@dataclass(frozen=True, slots=True)
class LuaGenerationRequest:
    manifest: ResolvedScenarioManifest
    manifest_path: Path
    output_path: Path

@dataclass(frozen=True, slots=True)
class LuaPreflightReport:
    validation: ValidationResult

@dataclass(frozen=True, slots=True)
class LuaGenerationResult:
    success: bool
    lua_text: str | None
    output_path: Path | None
    generator_warnings: tuple[str, ...]
    preflight: LuaPreflightReport
```

**验收：** 模型 JSON 序列化稳定，不包含外部模块对象或异常对象。

---

## Task 2.2：实现 `LuaPreflightValidator`

**文件：**
- 创建或修改：`src/cmo_lua_agent/generation/lua_preflight_validator.py`
- 测试：`tests/generation/test_lua_preflight_validator.py`

**接口：**

```python
class LuaPreflightValidator:
    def validate(
        self,
        lua_text: str,
        *,
        manifest: ResolvedScenarioManifest,
        contract: ScenarioContract,
        output_path: Path,
        workspace_root: Path,
    ) -> LuaPreflightReport: ...
```

**阻断项：**

- Lua 为空或缺少关键主体结构。
- 出现禁止 API：`DumpAmmo`、`remove_weapon` 及明确列入红线的调用。
- Lua 中阵营名、单位名、目标名不在 Contract。
- DBID 或 Loadout 与 Manifest 不一致。
- 输出路径不在工作区。
- 输出文件已存在。
- 关键 Generator warning 属于单位引用、目标引用、DBID、Loadout、弹药、非法坐标。

**警告项：**

- 推荐 `pcall` 模式缺失。
- 命名或注释不符合模板建议。
- 可疑但无法确定的重复事件名。

**注意：** 该组件不是完整 Lua 解析器；只做有限、可解释的 CMO 规则检查。

**验收：** 禁止 API、名称错位、Loadout 错位和越界输出被阻断。

---

## Task 2.3：实现 `LuaGenerationService`

**文件：**
- 创建或修改：`src/cmo_lua_agent/generation/lua_generation_service.py`
- 测试：`tests/generation/test_lua_generation_service.py`

**接口：**

```python
class LuaGenerationService:
    def __init__(
        self,
        *,
        adapter: CmoLuaGeneratorAdapter,
        preflight_validator: LuaPreflightValidator,
        workspace_root: Path,
    ) -> None: ...

    def generate(
        self,
        *,
        manifest: ResolvedScenarioManifest,
        contract: ScenarioContract,
        manifest_path: Path,
        output_path: Path,
    ) -> LuaGenerationResult: ...
```

**固定顺序：**

```text
将 Manifest 写入 manifest_path
→ Adapter.generate(manifest_path)
→ Preflight
→ 只有 Preflight 无 error 才写 output_path
→ 返回 LuaGenerationResult
```

**安全规则：**

- 使用独占创建模式 `open("x")`，不覆盖已有 Lua。
- 输出路径必须经 Preflight 通过。
- Adapter 异常结构化转换，不直接打印。
- 生成器 warning 统一进入 Preflight 分级。

**验收：** Chat 和 CLI 后续只调用 Service，不直接调用 Adapter。

---

# MVP 3：RunArtifactStore 与共享 Workflow

> 这里提前建立 `ScenarioWorkflow`，因为 Chat 与 CLI 都必须复用同一条主链路。否则 MVP 4 和 MVP 5 会产生两套实现。

## Task 3.1：实现序列化器

**文件：**
- 创建或修改：`src/cmo_lua_agent/artifacts/serializers.py`
- 测试：`tests/artifacts/test_serializers.py`

**接口：**

```python
def to_jsonable(value: Any) -> Any: ...
def write_json_atomic(path: Path, value: Any) -> None: ...
def write_text_exclusive(path: Path, text: str) -> None: ...
```

**规则：**

- 支持 dataclass、Enum、Path、tuple、Mapping。
- JSON 使用 UTF-8、`ensure_ascii=False`、稳定缩进。
- JSON 原子写入；Lua 独占写入。
- 不自动创建工作区外目录。

---

## Task 3.2：实现 `RunArtifactStore`

**文件：**
- 创建或修改：`src/cmo_lua_agent/artifacts/run_artifact_store.py`
- 测试：`tests/artifacts/test_run_artifact_store.py`

**接口：**

```python
@dataclass(frozen=True, slots=True)
class RunPaths:
    root: Path
    source_json: Path
    source_reference: Path
    schema_report: Path
    semantic_report: Path
    database_report: Path
    manifest_report: Path
    lua_preflight_report: Path
    scenario_ir: Path
    scenario_contract: Path
    resolved_manifest: Path
    original_lua: Path
    cmo_output: Path
    execution_result: Path
    workflow_state: Path
    workflow_result: Path

class RunArtifactStore:
    def create_run(self) -> RunPaths: ...
    def copy_source(self, source: Path, paths: RunPaths) -> None: ...
    def save_json(self, path: Path, value: Any) -> None: ...
    def save_text(self, path: Path, text: str) -> None: ...
```

**目录：**

```text
runs/run_<YYYYMMDD_HHMMSS>_<6chars>/
├── input/
├── validation/
├── contract/
├── generation/
├── execution/        # 仅执行时写文件
├── workflow_state.json
└── workflow_result.json
```

**验收：** 两次运行目录不冲突；所有写入路径均位于该 Run 根目录；不创建 `repair/`。

---

## Task 3.3：定义 Workflow 状态和结果

**文件：**
- 修改：`src/cmo_lua_agent/orchestration/workflow_state.py`
- 修改：`src/cmo_lua_agent/orchestration/workflow_context.py`
- 测试：`tests/orchestration/test_workflow_state.py`

**状态枚举：**

```python
class ScenarioStage(str, Enum):
    STARTED = "started"
    INPUT_LOADED = "input_loaded"
    SCHEMA_VALIDATED = "schema_validated"
    SEMANTIC_VALIDATED = "semantic_validated"
    IR_BUILT = "ir_built"
    DATABASE_RESOLVED = "database_resolved"
    MANIFEST_BUILT = "manifest_built"
    LUA_GENERATED = "lua_generated"
    PREFLIGHT_VALIDATED = "preflight_validated"
    CMO_EXECUTED = "cmo_executed"
    COMPLETED = "completed"
    FAILED = "failed"
```

**失败原因：**

```python
class ScenarioFailureReason(str, Enum):
    INVALID_INPUT = "invalid_input"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    SEMANTIC_VALIDATION_FAILED = "semantic_validation_failed"
    DATABASE_VALIDATION_FAILED = "database_validation_failed"
    MANIFEST_FAILED = "manifest_failed"
    GENERATION_FAILED = "generation_failed"
    PREFLIGHT_FAILED = "preflight_failed"
    CMO_EXECUTION_FAILED = "cmo_execution_failed"
    INFRASTRUCTURE_FAILED = "infrastructure_failed"
    CANCELLED = "cancelled"
```

**验收：** 所有状态可序列化；失败必须同时带 `stage` 和 `reason`。

---

## Task 3.4：实现共享 `ScenarioWorkflow`

**文件：**
- 创建或修改：`src/cmo_lua_agent/orchestration/scenario_workflow.py`
- 测试：`tests/orchestration/test_scenario_workflow.py`

**请求与结果：**

```python
@dataclass(frozen=True, slots=True)
class ScenarioRunRequest:
    json_path: Path
    output_path: Path | None = None
    execute: bool = False
    job_index: int = 0
    timeout_seconds: int = 600

@dataclass(frozen=True, slots=True)
class ScenarioRunResult:
    success: bool
    run_id: str
    run_root: Path
    stage: ScenarioStage
    failure_reason: ScenarioFailureReason | None
    lua_path: Path | None
    execution_result: Mapping[str, Any] | None
    issues: tuple[ValidationIssue, ...]
```

**依赖注入：**

```python
class ScenarioWorkflow:
    def __init__(
        self,
        *,
        json_loader: JsonLoader,
        schema_validator: ScenarioSchemaValidator,
        semantic_validator: ScenarioSemanticValidator,
        ir_builder: IRBuilder,
        ir_validator: IRValidator,
        database_resolver: DatabaseResolver,
        manifest_builder: ManifestBuilder,
        generation_service: LuaGenerationService,
        artifact_store: RunArtifactStore,
        cmo_runner: CmoRunner | None,
    ) -> None: ...
```

**固定流程：**

```text
create_run
→ copy source
→ load
→ schema
→ semantic + normalize
→ build/validate IR
→ database resolve
→ build manifest/contract
→ generate + preflight
→ execute（仅 request.execute=True）
→ save workflow_result
```

**失败策略：**

- 每个阶段结束立即保存对应报告和 `workflow_state.json`。
- 任一 error 立即停止，不进入后续阶段。
- 失败也必须保存 `workflow_result.json`。
- `execute=False` 时不要求注入 `CmoRunner`。
- Workflow 不调用 `input()`、不打印 Rich、不直接 import 外部 CMOLua。

**验收：** 一条 Stub 链路可完整通过；每个阶段失败都准确停止并保留已有产物。

---

# MVP 4：Chat Skill 工具

## Task 4.1：实现 `GenerateCmoLuaTool`

**文件：**
- 创建或修改：`src/cmo_lua_agent/tools/generate_cmo_lua_tool.py`
- 测试：`tests/tools/test_generate_cmo_lua_tool.py`

**输入：**

```json
{
  "json_path": "inputs/scenario.json",
  "output_path": "可选"
}
```

**行为：**

```python
request = ScenarioRunRequest(
    json_path=resolved_json_path,
    output_path=resolved_output_path,
    execute=False,
)
result = workflow.run(request)
```

**输出：**

```json
{
  "success": true,
  "run_id": "...",
  "run_root": "...",
  "lua_path": "...",
  "issues": []
}
```

**要求：**

- 永远传 `execute=False`。
- 通过 `ToolContext.progress` 报告阶段。
- 输入和输出路径使用现有工作区权限校验。
- 不注册或调用 `execute_cmo`。

---

## Task 4.2：实现 Skill 搜索与读取工具

**文件：**
- 创建或修改：`src/cmo_lua_agent/tools/search_cmo_skill_tool.py`
- 创建或修改：`src/cmo_lua_agent/tools/read_cmo_skill_tool.py`
- 测试：`tests/tools/test_search_cmo_skill_tool.py`
- 测试：`tests/tools/test_read_cmo_skill_tool.py`

**要求：**

- 工具只是 Repository 的薄包装。
- Search 返回相对路径、area、行号、摘要。
- Read 支持起始行和最大行数。
- 路径越界返回结构化失败，不抛到 AgentLoop。
- 单次响应限制长度。

---

## Task 4.3：注册工具和精简 System Prompt

**文件：**
- 修改：`src/cmo_lua_agent/tools/factory.py`
- 修改：`src/cmo_lua_agent/bootstrap/app_factory.py`
- 修改：`src/cmo_lua_agent/llm/prompts.py`
- 测试：`tests/tools/test_factory.py`

**注册：**

```text
generate_cmo_lua
search_cmo_skill
read_cmo_skill
```

**System Prompt 只加入四条：**

```text
生成 CMO Lua 时优先调用 generate_cmo_lua。
需要规则、模板或错误资料时先 search，再按行 read。
禁止编造 DBID、weaponDbid 和 loadoutId。
Chat 中生成 Lua 后不得自动执行 CMO。
```

**验收：** 三个工具可发现；远期 repair/optimization/training 工具未注册。

---

# MVP 5：CLI Run 双模式接入

## Task 5.1：完善 `ExecutionPolicy`

**文件：**
- 修改：`src/cmo_lua_agent/orchestration/execution_policy.py`
- 测试：`tests/orchestration/test_execution_policy.py`

**接口：**

```python
class ExecutionMode(str, Enum):
    CHAT = "chat"
    RUN = "run"

@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    mode: ExecutionMode
    allow_cmo_execution: bool
    require_approval: bool

    @classmethod
    def chat(cls) -> "ExecutionPolicy": ...
    @classmethod
    def run(cls, *, no_execute: bool) -> "ExecutionPolicy": ...
```

**规则：**

```text
chat:
allow_cmo_execution=False
require_approval=True（仅单独 execute_cmo 工具时使用）

run --no-execute:
allow_cmo_execution=False
require_approval=False

run:
allow_cmo_execution=True
require_approval=False
```

自动 Run 模式中任何 ASK 都视为配置错误，启动前失败。

---

## Task 5.2：实现 `run_scenario.py`

**文件：**
- 创建或修改：`src/cmo_lua_agent/cli/run_scenario.py`
- 测试：`tests/cli/test_run_scenario.py`

**参数：**

```text
scenario_json
--output PATH
--job-index INTEGER        默认 0
--timeout-seconds INTEGER  默认 600
--no-execute
```

**CLI 逻辑：**

```python
request = ScenarioRunRequest(
    json_path=args.scenario_json,
    output_path=args.output,
    execute=not args.no_execute,
    job_index=args.job_index,
    timeout_seconds=args.timeout_seconds,
)
result = workflow.run(request)
```

**退出码：**

```text
0   成功；或 --no-execute 下生成成功
2   输入、Schema、语义、数据库、Manifest、Preflight 失败
3   Lua 已生成但 CMO 执行失败
4   外部生成器、数据库、文件系统或 CMO 基础设施错误
130 用户中断
```

**要求：**

- 不调用 `input()`。
- 不依赖 Chat AgentLoop。
- 输出简短摘要：run 目录、Lua 路径、执行结果、失败阶段。
- `--output` 必须位于工作区且不得覆盖。

---

## Task 5.3：接入 `main.py`

**文件：**
- 修改：`src/cmo_lua_agent/main.py`
- 测试：`tests/cli/test_main.py`

**命令：**

```powershell
python -m cmo_lua_agent.main chat
python -m cmo_lua_agent.main run inputs\scenario.json
python -m cmo_lua_agent.main run inputs\scenario.json --no-execute
```

**要求：**

- 保留现有 Chat 启动行为。
- `run` 子命令不初始化交互审批器。
- Bootstrap 统一创建依赖，Chat 与 Run 共用同一 `ScenarioWorkflow` 实例构造逻辑。
- `bootstrap/tool_factory.py` 若与 `tools/factory.py` 重复，停用前者，只保留一个工具注册入口。

---

## Task 5.4：端到端回归测试

**文件：**
- 创建：`tests/orchestration/test_json_to_lua_e2e.py`
- 创建：`tests/fixtures/scenarios/valid_carrier_scenario.json`
- 创建：`tests/fixtures/scenarios/invalid_reference.json`
- 创建：`tests/fixtures/scenarios/missing_weapon_dbid.json`

**测试矩阵：**

1. 标准 JSON → Manifest → Lua → Preflight → 成功。
2. 舰载机描述坐标 + 合法 base → `inherit_base`。
3. 缺 `weaponDbid` + 数据库唯一命中 → 补齐成功。
4. 缺 `weaponDbid` + 零命中 → 生成前失败。
5. 缺 `weaponDbid` + 多命中 → 生成前失败。
6. 重复 ID → 语义阶段失败。
7. shooter/target 错误引用 → 语义阶段失败。
8. 弹药超量 → 语义阶段失败。
9. Generator 输出禁止 API → Preflight 失败且不写 Lua。
10. Chat 工具 → 生成成功但不调用 CMO。
11. CLI `--no-execute` → 生成成功但不调用 CMO。
12. CLI 默认 Run → 调用 CMO Runner 一次。
13. CMO 失败 → Lua 和日志保留，退出码 3。
14. 任一失败 → `workflow_result.json` 仍存在。
15. 同名输出已存在 → 拒绝覆盖。

**全量验证：**

```powershell
$env:PYTHONPATH="$PWD\src"
pytest -q
python -m compileall src\cmo_lua_agent
```

真实集成测试：

```powershell
pytest -m integration tests\integrations\cmolua -q

python -m cmo_lua_agent.main run `
  tests\fixtures\cmolua\golden\source.json `
  --no-execute
```

最终真实 CMO 联调：

```powershell
python -m cmo_lua_agent.main run `
  inputs\scenario.json `
  --job-index 0 `
  --timeout-seconds 600
```

---

# 里程碑与停止线

## 里程碑 A：外部能力可用

完成 Task 0.1—0.5。

通过标准：

```text
Generator 可导入
数据库可只读查询
Skill 可搜索/读取
Golden JSON 可生成稳定 Lua
```

在此之前，不写 Schema/Workflow。

## 里程碑 B：JSON 能可靠变成 Manifest

完成 Task 1.1—1.7。

通过标准：

```text
标准 JSON 通过
缺字段、类型错误、重复 ID、错误引用、弹药超量失败
未知 DBID、Loadout 不匹配失败
武器缺 ID 时只允许唯一精确匹配
```

在此之前，不接 Chat/CLI。

## 里程碑 C：Manifest 能安全生成 Lua

完成 Task 2.1—2.3。

通过标准：

```text
不覆盖文件
不越过工作区
禁止 API、名称错位和 Loadout 错位被拦截
```

## 里程碑 D：共享 Workflow 和产物完整

完成 Task 3.1—3.4。

通过标准：

```text
每一步有报告
失败时可定位阶段和原因
Chat 与 CLI 不需要各写一套流程
```

## 里程碑 E：双模式完成

完成 Task 4.1—5.4。

通过标准：

```text
Chat 只生成，不自动执行
CLI Run 自动执行且不调用 input()
--no-execute 生效
完整 runs 产物可复现
```

---

# 推荐执行顺序

```text
0.1 配置复核
→ 0.2 Generator Adapter
→ 0.3 Database Repository
→ 0.4 Skill Repository
→ 0.5 Golden
→ 1.1 公共模型
→ 1.2 JsonLoader
→ 1.3 Schema
→ 1.4 Semantic
→ 1.5 IR
→ 1.6 DatabaseResolver
→ 1.7 Manifest
→ 2.1 生成模型
→ 2.2 Preflight
→ 2.3 GenerationService
→ 3.1 Serializer
→ 3.2 ArtifactStore
→ 3.3 WorkflowState
→ 3.4 ScenarioWorkflow
→ 4.1 Generate Tool
→ 4.2 Skill Tools
→ 4.3 Tool 注册
→ 5.1 ExecutionPolicy
→ 5.2 CLI Run
→ 5.3 main.py
→ 5.4 E2E
```

# 当前第一项代码任务

从 `Task 0.2：CmoLuaGeneratorAdapter` 开始。`config.py` 已存在并有测试，不再围绕版本清单或数据库探查继续扩展。

第一批只改三个文件：

```text
src/cmo_lua_agent/integrations/cmolua/generator_adapter.py
src/cmo_lua_agent/integrations/cmolua/__init__.py
tests/integrations/cmolua/test_generator_adapter.py
```

第一批验收仅要求：

```text
能够从配置路径导入 generate_cmo_lua
能够返回非空 Lua
能够捕获 warning
导入和执行异常结构化
不打印、不保存、不执行 CMO
```
