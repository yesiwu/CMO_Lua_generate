# Lua 生成能力扩展设计

## 1. 目的与范围

当前项目有两条 Lua 生成入口：

1. 旧场景入口：`ScenarioWorkflow` 将受约束的场景 JSON 解析为
   `ResolvedScenarioManifest`，再调用 `CMOLua-main/tools/json_to_lua.py`。
2. 受控策略入口：`ScenarioDefinition + StrategySpec` 经
   `ExecutionPlanCompiler`、`CapabilityValidator`、`LuaRenderer` 或
   `ScoredLuaAssemblyService` 生成候选或 Baseline Lua。

本设计只重构这两条**生成链的能力扩展边界**。它不重构、替换或重新编排
Phase 3-9 的评分、执行结果、候选比较、经验、Skill 晋升、Campaign 或 Chat
控制面。那些阶段继续消费“已生成 Lua、ExecutionPlan、Source Map、运行结果”这类
现有稳定产物。

目标是同时满足两件事：

- 已支持的海空反舰场景保持确定性、可比较和可追溯；
- 对潜艇、巡逻、反潜或新的任务细节，允许 LLM 在严格边界内辅助实现 Lua 能力，
  而不是每次把整个系统改为自由 Lua 生成。

## 2. 现状与问题

### 2.1 当前确定性边界

`DatabaseResolver` 已能够识别 `aircraft`、`ship`、`submarine` 和 `facility`
等平台类别。但当前 Phase 2 Runtime Primitive 只覆盖海空反舰的有限集合，例如
阵营初始化、舰艇/飞机创建、目标 Contact、舰艇攻击、飞机起飞、航路、攻击和返航。
`ExecutionPlanCompiler` 对潜艇操作会明确返回 `CapabilityGap`。

`CMOLua-main/SKILL.md` 和 `CMOLua-main/templates/` 已积累大量 CMO 知识，包括
舰船、飞机、潜艇、巡逻和任务模板；但它们是大篇幅参考资料，不是可按能力版本化、
可执行验证的 Runtime 接口。

### 2.2 当前失败模式

Lua 预检通过，只能说明文本具备有限的语法和静态 API 合规性。它不能证明：

- 飞机实际完成起飞；
- 飞机已进入飞行状态、正确设置航路并进入攻击距离；
- 攻击命令真正提交、武器真正发射；
- 单位的阵营、基地、Loadout、Contact 或目标关系在 CMO 中实际可用；
- 新任务能力在真实 CMO Runtime 中有效。

因此会出现“Lua 无错误，但舰载机停留在舰上”的假成功。此类结果不能作为有效
候选或可信战术证据。

### 2.3 不采用自由 Lua 的原因

以下做法不在本设计范围内：

```text
JSON -> LLM -> complete arbitrary Lua
```

它会让模型直接控制 DBID、Loadout、阵营、评分规则、事件名称和运行时 API 调用。
这会破坏单位稳定 ID、评分片段保护、StrategyDiff、Source Map、候选可比较性、
Phase 7 的 planned-versus-actual 以及 Phase 9 的契约冻结和恢复。

## 3. 设计原则

1. **事实、策略、实现分层。** 场景事实不由 LLM 改写；策略以结构化模型表达；
   Lua 细节以受限能力实现表达。
2. **既有能力确定性优先。** 已验证 Primitive 只能由 Renderer 生成，不重新让
   LLM 编写同类 Lua。
3. **新能力由 LLM 提案，不由 LLM 直接发布。** LLM 的 Lua 只能成为待验证的
   `PrimitiveImplementationProposal`，不能直接成为候选最终 Lua。
4. **运行行为是生成验收的一部分。** 对飞机、潜艇、巡逻等任务必须验证任务活性，
   而不仅是语法或进程退出码。
5. **评分是系统 instrumentation。** 任何能力提案都不能新增、删除、重排或修改
   原生评分 Trigger、Action、Event、评分侧或积分。
6. **能力按版本演进。** 通过验证的能力才会成为可注册的 Runtime Primitive；
   旧 Runtime/Renderer 版本和已有 Golden 不被覆盖。

## 4. 推荐架构

```text
Scenario JSON / ScenarioDefinition
      |                         |
      |                         +--> locked facts:
      |                              unit_id, side_id, DBID, loadout,
      |                              coordinates, score contract
      v
ScenarioContract / StrategySpec
      v
ExecutionPlanCompiler
      v
CapabilityResolutionService
      |
      +--> registered primitive
      |      -> deterministic LuaRenderer
      |
      +--> registered template binding
      |      -> deterministic template renderer
      |
      +--> missing capability
             -> LLM PrimitiveImplementationProposal
             -> PrimitiveSafetyGate
             -> isolated CMO capability smoke
             -> MissionLivenessValidator
             -> human review and versioned registration
             -> deterministic LuaRenderer
      v
ScoredLuaAssemblyService
      v
final Lua + Source Map + generation manifest
```

`CapabilityResolutionService` 是新边界。它只回答某个 Operation 是否由已注册
Primitive、已注册模板或待验证能力提案处理；它不执行 CMO，不负责候选评估，也不
改变评分规则。

## 5. 三种生成模式

### 5.1 已注册 Primitive

适用范围：当前已有的舰船攻击、飞机起飞、航路、攻击、返航和其他已通过 Runtime
验证的能力。

输入为不可变 `Operation` 参数，输出只来自当前版本的 `LuaRenderer`。LLM 不参与
代码生成；它至多通过受限 `StrategyPatch` 调整合法策略参数。

### 5.2 已注册模板绑定

适用范围：已有被审核模板能够表达的新任务细节，例如已验证的潜艇部署或巡逻模板。

模板不是把 `CMOLua-main/templates/` 中的任意文件直接拼入最终 Lua。每个模板须先
登记为 `CapabilityTemplate`，声明：

- `capability_id`、版本和适用平台类别；
- 输入参数 Schema；
- 允许的 CMO API；
- 必需的 Runtime Helper；
- 任务活性断言；
- 禁止触及的评分区段；
- 对应的 Source Map 范围。

渲染时只做确定性占位符绑定。模板参数只能来自已校验的事实和 StrategySpec。

### 5.3 新 Primitive 实现提案

适用范围：没有已注册 Primitive 或模板的新能力，例如首次引入潜艇反舰、反潜、巡逻
区、电子战等。

LLM 可以依据经裁剪的 Skill Pack 和已验证模板，返回
`PrimitiveImplementationProposal`。该提案不是最终 Lua，最小模型为：

```text
capability_id
primitive_type
runtime_version_target
parameter_schema
lua_helper_body
declared_cmo_apis
required_runtime_helpers
expected_telemetry_events
liveness_assertions
source_skill_refs
```

其中 `lua_helper_body` 只能使用显式参数名和允许的 Helper；它不能包含具体单位
名称、DBID、Loadout ID、阵营名称、评分对象、文件路径、Shell 命令或任意 Lua
拼接入口。

## 6. LLM 与 Skill Pack 的边界

不将完整 `CMOLua-main/SKILL.md` 发送给模型。应将其迁移为按能力延迟加载的
小型 Skill Pack，例如：

```text
cmo-aircraft-launch
cmo-aircraft-strike
cmo-contact-acquisition
cmo-aircraft-return
cmo-submarine-operations
cmo-patrol-mission
cmo-native-scoring-boundaries
```

每个 Pack 只包含：已核验 CMO API 约束、参数表、失败模式、模板引用、任务活性
要求和少量反例。数据库事实仍通过 `query_cmo_database` / `DatabaseResolver` 取得，
不能由 Skill 或 LLM 猜测。

LLM 输入必须是：

```text
CapabilityRequest
+ permitted Skill Pack excerpts
+ allowed API catalog
+ parameter schema
+ required telemetry and liveness assertions
+ protected score boundary notice
```

LLM 不接收完整评分片段、本地路径、CMO 配置、未过滤数据库、候选排行榜或历史
运行日志。

## 7. 任务活性契约

为每类可行动任务定义 `MissionLivenessContract`。它绑定 Operation ID、预期事件、
超时和失败分类，并由 Phase 3 已有执行摘要/时间线消费，而不是引入第二套结果解析。

舰载机打击的最低链路：

```text
launch_requested
-> airborne_confirmed
-> route_applied
-> attack_range_reached
-> attack_command_submitted
-> weapon_fired or explicit_attack_result
-> return_started
```

潜艇反舰和巡逻也必须提供等价的启动、状态转换、任务提交和结果节点。只有
`execution_success` 不足以满足契约。

若 Lua 成功运行但缺少必要节点，结果必须保留官方原生分数，但标记：

```text
execution_success = true
semantic_valid = false
mission_liveness = failed
ranking_eligible = false
```

不得通过猜测事件、修改评分或重算战果来掩盖任务未执行。

## 8. 安全门与能力晋升

`PrimitiveSafetyGate` 在任何新提案进入 CMO 前执行以下确定性校验：

1. 仅使用登记过的 API 和 Runtime Helper；
2. 参数 Schema、Primitive 类型和能力版本一致；
3. 没有硬编码单位、DBID、Loadout、side、路径或 Shell 内容；
4. 不写入 `system.native_score` 或评分 Lua Source Map 区段；
5. 所有外部引用都指向受信任 Skill Pack 和模板版本；
6. 有完整 Source Map、遥测声明和活性断言；
7. 生成文本可稳定规范化和校验和化。

通过静态门后，提案仅能在隔离 CMO capability fixture 中运行。fixture 必须证明
声明的任务活性事件实际出现，且没有评分区段修改、未捕获 Runtime 异常或越权 API。
人工审核后才可将其登记为新的版本化 Runtime Primitive 或 CapabilityTemplate。

候选生成过程只能使用已登记能力；它不能在 Phase 5、6 或 9 的运行中临时执行新的
LLM Lua。

## 9. 新能力接入：潜艇示例

潜艇并不要求重写所有生成链，但需要一套明确的能力包：

1. `ScenarioSchema` / IR 接受并校验潜艇所需事实；现有数据库解析已能识别类别，
   但仍需具体字段契约。
2. `StrategySpec` 只增加真正需要的策略语义，例如目标、武器政策、搜索或攻击条件；
   不将 Lua API 细节塞进策略。
3. `ExecutionPlanCompiler` 将这些语义降低为新的潜艇 Operation。
4. 新 Operation 在未注册前返回结构化 `CapabilityGap`，不能降级为自由 Lua。
5. 通过上述提案和 CMO fixture 验证后，注册潜艇 Primitive 并扩展 Renderer。
6. `ScenarioScoreSpec` 以数据方式增加角色/目标计分规则；不能把计分写进策略或
   由能力提案修改。
7. 增加 Golden、任务活性、Phase 5 Candidate 和 Phase 3 证据回归。

该过程会修改“该能力相关”的模型和测试，但不会重构 Phase 3-9 的工作流。

## 10. 两条现有入口的兼容策略

### 10.1 旧 JSON 到 Lua

保留 `ScenarioWorkflow -> CmoLuaGeneratorAdapter` 作为兼容入口。它应新增
`CapabilityRequest` 产物并在 Manifest 中记录所需能力版本。若 JSON 使用未支持
能力，默认行为仍是结构化失败，不隐式调用 LLM。

新能力经过审核注册后，旧入口可由 Capability Resolution 调用已登记模板或
Primitive，而不要求改变用户 JSON 为 Lua。

### 10.2 StrategySpec 到 Lua

保留 `ExecutionPlanCompiler -> CapabilityValidator -> LuaRenderer /
ScoredLuaAssemblyService`。它只渲染已注册能力，保持同输入、同版本得到字节级
一致 Lua 的要求。

新增能力改变 Runtime、Compiler 或 Renderer 后，必须产生新版本、新 generation
manifest 和独立 Golden；不得覆盖既有 Phase 2 或 Phase 3 Golden。

## 11. 迁移阶段

### 阶段 A：可观测性收口

先实现 `MissionLivenessContract`、Operation 到遥测的关联和明确的失败分类。
不改变既有 Renderer 的渲染路径。这一步优先解决“飞机未起飞但 Lua 成功”的问题。

### 阶段 B：能力注册与 Skill 拆分

引入 `CapabilityRequest`、`CapabilityTemplate` 和小型 Skill Pack。将大型
`CMOLua-main/SKILL.md` 中已经验证的知识按能力迁移；原文继续作为 legacy
reference，不强制一次性删改。

### 阶段 C：LLM Primitive Lab

引入 `PrimitiveImplementationProposal`、`PrimitiveSafetyGate`、隔离 CMO fixture
和人工审核。此阶段只允许实验性能力提案，不能影响 Candidate 或 Campaign。

### 阶段 D：受控能力发布

将完成审核的 Primitive 注册为正式 Runtime 版本，接入旧 JSON 和受控策略入口。
为每项能力增加 deterministic render、CMO smoke、任务活性和评分契约回归。

## 12. 非目标

本设计不做以下事情：

- 不让 LLM 生成或修复完整候选 Lua；
- 不在 Candidate、Campaign 或 Chat 中动态安装新 Runtime 能力；
- 不更改 Phase 3 官方分数来源或评分片段所有权；
- 不替换 Phase 5/6 的 CandidateEvaluationWorkflow；
- 不自动批准新 Primitive、Skill 或评分规则；
- 不将 CMO 的任意日志、SQLite 或完整 Lua 直接输入 LLM；
- 不把任务活性失败解释为战术失败或重新计算官方分数。

## 13. 验收标准

该重构完成时，应满足：

1. 已有 6v4 海空反舰 Golden 的 Lua 字节级不变；
2. 飞机任务只有在活性契约满足时才可视为语义有效；
3. 未支持能力返回明确 CapabilityGap，绝不自动回退自由 Lua；
4. LLM 新能力提案无法触及事实、评分或未登记 API；
5. 每个已发布 Primitive 都有 Skill Pack、参数 Schema、Source Map、CMO fixture、
   活性断言和版本校验；
6. 新增潜艇/巡逻能力时，只扩展对应的能力包和契约，不需要改写 Phase 3-9；
7. 同一事实、策略、Runtime 与 Renderer 版本始终生成相同 Lua。

## 14. 推荐决策

采用本设计的“受控能力扩展”路线，而不是立即推倒现有链路或开放 JSON 到自由 Lua。
第一项实施工作应是阶段 A：为飞机、舰船攻击等现有 Operation 增加任务活性契约和
实际执行验证。它能直接发现“飞机未起飞”的假成功，并为潜艇、巡逻等未来能力建立
相同的验收边界。
