我正在使用实现计划格式整理。当前 `StrategyProposalAgent` 确实是一次 LLM 调用生成四个完整 `StrategySpec`，任何一个候选格式错误都会导致整批失败。
现有上下文已经提供完整 Baseline 和允许修改路径，因此适合改成“意图规划 + 独立 Patch + 确定性组装”。
完整 `StrategySpec` 继续由现有领域模型承载，最终仍经过现有严格候选集合校验。 

下面内容可直接发送给 Codex。

````text
# Phase 9C Strategy Proposal 两阶段重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 使用
> superpowers:executing-plans 和 superpowers:test-driven-development，
> 按任务顺序逐项实施。每个生产修改前必须先写失败测试。

## Goal

将当前“一次 LLM 生成四个完整 StrategySpec”的高失败率流程重构为：

StrategyProposalContext
→ CandidateIntentPlanner：一次生成四个结构化候选意图
→ CandidatePatchGenerator：按顺序独立生成四个 StrategyPatch
→ StrategyPatchAssembler：基于 Baseline 确定性构造完整 StrategySpec
→ CandidateSetValidator
→ CandidateNoveltyValidator
→ FrozenCandidateSet

重构后，LLM 不再复制完整 StrategySpec，不再生成 scenario_id、
candidate_id、intended_difference 或稳定结构字段。

## Architecture

第一阶段由 LLM 统一规划四个候选分别要验证什么，保证角色和战术维度具有
整体多样性。

第二阶段按 candidate_00 → candidate_03 顺序独立生成 Patch。后生成的候选
只能看到此前已接受候选的压缩差异摘要，不能看到完整候选 StrategySpec。

系统基于同一 Baseline 应用 Patch，生成完整 StrategySpec，并继续使用现有
StrategyValidator、CandidateSetValidator 和 CandidateNoveltyValidator。

对外接口保持：

StrategyProposalAgent.propose(
    context: StrategyProposalContext
) -> tuple[StrategyCandidate, ...]

Phase 6、Phase 9C Preview 和其他调用方不需要了解内部有五次 LLM 调用。

## Tech Stack

- Python 3.13
- frozen dataclass
- JSON Pointer
- 现有 StrategySpec / StrategyCandidate
- 现有 CandidateSetValidator
- pytest
- 现有 complete_json(system, prompt) 客户端

## Global Constraints

1. 不运行真实 CMO。
2. 未经用户明确允许，不调用当前 DeepSeek 自定义端点。
3. 不降低 CandidateSetValidator 或 CandidateNoveltyValidator 门槛。
4. 不允许 LLM 输出完整 StrategySpec。
5. 不允许 LLM 输出 candidate_id、scenario_id、稳定 ID 或实际 diff。
6. 完整 StrategySpec 必须由系统基于 Baseline 确定性构造。
7. 每个候选最多一次初始 Patch 调用和一次局部修复调用。
8. 不允许失败后重新生成整批四候选。
9. 所有真实 LLM 请求，包括非法 JSON 和验证失败响应，都必须计入预算。
10. Preview 成功后执行阶段不得再次调用 Proposal LLM。
11. 保持 StrategyProposalAgent.propose() 的公共返回类型不变。
12. 不恢复旧的完整 StrategySpec Prompt，不增加容错猜测或字段自动补全。
13. 所有测试先失败，再写最小实现。
14. 每完成一个独立任务提交一次 Git。

---

# 一、文件结构

## 新增

src/cmo_lua_agent/optimization/proposal_models.py

职责：
- CandidateIntent
- StrategyPatchOperation
- CandidatePatch
- AcceptedCandidateSummary
- StrategyProposalUsage
- 结构化错误类型

src/cmo_lua_agent/optimization/strategy_patch.py

职责：
- 枚举 Baseline 中允许修改的具体标量叶子
- 验证 JSON Pointer
- 应用 StrategyPatch
- 生成完整 StrategySpec
- 计算真实 changed_paths
- 拒绝稳定字段、非法类型、空修改和结构变化

src/cmo_lua_agent/agents/candidate_intent_planner.py

职责：
- 一次 LLM 调用生成四个结构化 CandidateIntent
- 系统确定 candidate_id、role、最小/最大修改数量
- LLM 只生成 objective 和 strategy_dimensions

src/cmo_lua_agent/agents/candidate_patch_generator.py

职责：
- 针对单个 CandidateIntent 调用一次 LLM
- 输出一个 StrategyPatch
- 支持一次带结构化错误的局部修复调用

## 修改

src/cmo_lua_agent/agents/strategy_proposal_agent.py

职责变化：
- 从“单次完整对象解析器”改为两阶段 Coordinator
- 保留 propose(context) 公共接口
- 顺序协调 Planner、四个 Patch Generator、Assembler 和本地校验
- 记录实际 LLM 调用次数

src/cmo_lua_agent/optimization/phase6_models.py

仅更新：
- StrategyCandidate.intended_difference 的注释和语义
- 明确该字段由系统真实 diff 生成，不再来自 LLM

src/cmo_lua_agent/optimization/candidate_set_validator.py

仅增加：
- intended_difference 与实际 changed_paths 一致性检查
- 不修改现有严格校验规则

src/cmo_lua_agent/evolution/production_preview_builder.py

修改：
- 正确统计多次 Proposal LLM 调用
- 提案失败时不留下半完成 Preview
- FrozenCandidateSet 仍是唯一执行输入
- 幂等读取成功 Preview 时不调用 LLM

## 新增测试

src/cmo_lua_agent/tests/optimization/test_strategy_patch.py
src/cmo_lua_agent/tests/optimization/test_candidate_intent_planner.py
src/cmo_lua_agent/tests/optimization/test_candidate_patch_generator.py
src/cmo_lua_agent/tests/optimization/test_strategy_proposal_agent_two_stage.py
src/cmo_lua_agent/tests/evolution/test_phase9c_two_stage_preview.py

---

# Task 1：冻结现有外部接口并建立失败回归测试

## Files

- Test:
  src/cmo_lua_agent/tests/optimization/test_strategy_proposal_agent_two_stage.py
- Read:
  src/cmo_lua_agent/agents/strategy_proposal_agent.py
- Read:
  src/cmo_lua_agent/optimization/phase6_models.py

## Interfaces

保持：

StrategyProposalAgent.propose(
    context: StrategyProposalContext
) -> tuple[StrategyCandidate, ...]

## Steps

- [ ] 1. 写测试，确认调用方仍只调用一次 propose()

测试最终应断言：

```python
candidates = agent.propose(context)

assert len(candidates) == 4
assert [item.candidate_id for item in candidates] == [
    "candidate_00",
    "candidate_01",
    "candidate_02",
    "candidate_03",
]
assert all(
    item.strategy_spec.scenario_id == context.baseline.scenario_id
    for item in candidates
)
````

* [ ] 2. 写测试，确认 StrategyCandidate 的公共序列化格式保持兼容

必须继续包含：

```text
candidate_id
strategy
proposal_summary
intended_difference
strategy_checksum
```

* [ ] 3. 写失败测试，模拟当前 DeepSeek 风格的不完整 StrategySpec

测试输入缺少 scenario_id，证明旧实现失败，并记录该问题将由新 Patch 架构消除。

* [ ] 4. 运行测试并确认 RED

```powershell
$env:PYTHONPATH="$PWD\src"
python -m pytest `
  src\cmo_lua_agent\tests\optimization\test_strategy_proposal_agent_two_stage.py `
  -q
```

预期：
新两阶段接口尚不存在，测试失败。

* [ ] 5. 不修改生产代码，提交测试基线

```text
test(proposal): define two-stage proposal compatibility contract
```

---

# Task 2：实现不可变 Proposal 领域模型

## Files

* Create:
  src/cmo_lua_agent/optimization/proposal_models.py
* Test:
  src/cmo_lua_agent/tests/optimization/test_strategy_patch.py
  src/cmo_lua_agent/tests/optimization/test_candidate_intent_planner.py

## Interfaces

实现：

```python
class ProposalContractError(ValueError):
    code: str

@dataclass(frozen=True, slots=True)
class CandidateIntent:
    candidate_id: str
    role: str
    objective: str
    strategy_dimensions: tuple[str, ...]
    minimum_changed_leaves: int
    maximum_changed_leaves: int
    required_failure_indicators: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class StrategyPatchOperation:
    path: str
    value: str | int | float | bool

@dataclass(frozen=True, slots=True)
class CandidatePatch:
    proposal_summary: str
    operations: tuple[StrategyPatchOperation, ...]

@dataclass(frozen=True, slots=True)
class AcceptedCandidateSummary:
    candidate_id: str
    strategy_dimensions: tuple[str, ...]
    changed_paths: tuple[str, ...]
    strategy_checksum: str

@dataclass(frozen=True, slots=True)
class StrategyProposalUsage:
    intent_planning_calls: int
    patch_generation_calls: int
    patch_repair_calls: int

    @property
    def total_calls(self) -> int: ...
```

## Candidate 角色规则

由系统固定，不允许 LLM 修改：

```text
candidate_00:
role = exploit
minimum_changed_leaves = 1
maximum_changed_leaves = 2

candidate_01:
role = repair 或 conservative_risk_reduction
minimum_changed_leaves = 1
maximum_changed_leaves = 2

candidate_02:
role = explore
minimum_changed_leaves = 2
maximum_changed_leaves = 3

candidate_03:
role = conservative_control
minimum_changed_leaves = 1
maximum_changed_leaves = 1
```

## Steps

* [ ] 1. 为所有 dataclass 写构造校验失败测试

覆盖：

```text
candidate_id 非法
未知 role
objective 为空
strategy_dimensions 为空
minimum > maximum
Patch path 不是 JSON Pointer
Patch value 是 dict/list/null
重复 Patch path
Usage 出现负数
```

* [ ] 2. 运行并确认 RED

* [ ] 3. 实现最小不可变模型和 ProposalContractError

错误码至少包括：

```text
INVALID_INTENT
INVALID_INTENT_ROLE
INVALID_INTENT_DIMENSION
INVALID_PATCH_PATH
INVALID_PATCH_VALUE
DUPLICATE_PATCH_PATH
INVALID_PROPOSAL_RESPONSE
```

* [ ] 4. 运行模型测试并确认 GREEN

* [ ] 5. 提交

```text
feat(proposal): add immutable intent and patch contracts
```

---

# Task 3：实现 StrategyPatchAssembler

## Files

* Create:
  src/cmo_lua_agent/optimization/strategy_patch.py
* Test:
  src/cmo_lua_agent/tests/optimization/test_strategy_patch.py
* Reuse:
  src/cmo_lua_agent/contract/strategy_models.py
  src/cmo_lua_agent/optimization/candidate_set_validator.py

## Interfaces

实现：

```python
def build_patchable_leaf_catalog(
    *,
    baseline: StrategySpec,
    allowed_paths: tuple[str, ...],
) -> tuple[dict[str, object], ...]: ...

def apply_strategy_patch(
    *,
    baseline: StrategySpec,
    patch: CandidatePatch,
    allowed_paths: tuple[str, ...],
) -> tuple[StrategySpec, tuple[str, ...]]: ...
```

`build_patchable_leaf_catalog()` 每项只返回：

```json
{
  "path": "/attacks/0/fire_quantity",
  "current_value": 2,
  "value_type": "integer"
}
```

不得返回完整场景或完整 StrategySpec。

## 禁止修改字段

即使错误地出现在 allowed paths 中，也必须拒绝：

```text
scenario_id
attack_id
shooter_id
weapon_dbid
sortie_id
aircraft_id
base_unit_id
```

## Steps

* [ ] 1. 写成功测试

覆盖：

```text
修改 /attacks/0/fire_quantity
修改 /attacks/0/target_ids/0
修改 /sorties/0/fire_delay_seconds
修改 /sorties/0/route/0/latitude
```

断言：

```text
scenario_id 自动继承
攻击数量不变
出击数量不变
所有稳定 ID 不变
只有声明路径发生变化
```

* [ ] 2. 写失败测试

覆盖：

```text
不存在的路径
禁止路径
稳定字段
整个 attacks 数组
整个 target_ids 数组
类型不匹配
负数数量
no-op Patch
同一路径重复修改
Patch 声明路径与实际 diff 不一致
```

* [ ] 3. 运行并确认 RED

* [ ] 4. 实现叶子枚举、JSON Pointer 读取和写入

只允许替换现有标量叶子，不允许：

```text
add
remove
append
reorder
rename
```

* [ ] 5. 应用 Patch 后调用：

```python
strategy_spec_from_dict(payload)
strategy_leaf_diff(baseline, strategy, allowed_paths)
```

* [ ] 6. 确认实际 diff 集合与 Patch path 完全相同

* [ ] 7. 运行测试并确认 GREEN

* [ ] 8. 提交

```text
feat(proposal): build complete strategies from bounded patches
```

---

# Task 4：实现 CandidateIntentPlanner

## Files

* Create:
  src/cmo_lua_agent/agents/candidate_intent_planner.py
* Test:
  src/cmo_lua_agent/tests/optimization/test_candidate_intent_planner.py

## Interfaces

```python
class CandidateIntentPlanner:
    def __init__(self, client: StrategyProposalJsonClient) -> None: ...

    def plan(
        self,
        context: StrategyProposalContext,
    ) -> tuple[CandidateIntent, ...]: ...
```

## LLM 输出契约

LLM 只允许输出：

```json
{
  "intents": [
    {
      "objective": "提高首轮水面打击火力",
      "strategy_dimensions": ["fire_quantity"]
    },
    {
      "objective": "降低舰载机过早损失风险",
      "strategy_dimensions": ["attack_timing", "air_route"]
    },
    {
      "objective": "探索目标分配与攻击时机协同",
      "strategy_dimensions": ["target_assignment", "attack_timing"]
    },
    {
      "objective": "执行一项低风险局部调整",
      "strategy_dimensions": ["ammunition_reserve"]
    }
  ]
}
```

LLM 不得输出：

```text
candidate_id
role
minimum_changed_leaves
maximum_changed_leaves
scenario_id
StrategySpec
Patch
Lua
分数预测
```

## 系统补充规则

系统根据索引生成：

```text
candidate_00～candidate_03
role
min/max changed leaves
required failure indicators
```

`candidate_01`：

```text
存在 BaselineFailureProfile
→ role=repair
→ required_failure_indicators 来自冻结 Profile

不存在可信 Profile
→ role=conservative_risk_reduction
→ required_failure_indicators=()
```

## Steps

* [ ] 1. 写四条合法 Intent 解析测试

* [ ] 2. 写错误测试

覆盖：

```text
不是 exactly four
多余字段
objective 非字符串
dimensions 非字符串数组
未知 dimension
四个 Intent 全部选择同一 dimension
repair 未覆盖对应 failure indicator 可映射维度
```

允许 dimension：

```text
target_assignment
attack_timing
fire_quantity
ammunition_reserve
air_route
risk_policy
```

* [ ] 3. 运行并确认 RED

* [ ] 4. 编写简短 System Prompt

不得在 Planner Prompt 中要求复制 Baseline。

* [ ] 5. 实现严格解析和系统字段补充

* [ ] 6. 验证四个 Intent 整体至少覆盖两个维度

* [ ] 7. 运行测试并确认 GREEN

* [ ] 8. 提交

```text
feat(proposal): plan four bounded candidate intents
```

---

# Task 5：实现 CandidatePatchGenerator

## Files

* Create:
  src/cmo_lua_agent/agents/candidate_patch_generator.py
* Test:
  src/cmo_lua_agent/tests/optimization/test_candidate_patch_generator.py

## Interfaces

```python
class CandidatePatchGenerator:
    def __init__(self, client: StrategyProposalJsonClient) -> None: ...

    def generate(
        self,
        *,
        context: StrategyProposalContext,
        intent: CandidateIntent,
        patchable_leaves: tuple[dict[str, object], ...],
        accepted_candidates: tuple[AcceptedCandidateSummary, ...],
        previous_error: dict[str, object] | None = None,
    ) -> CandidatePatch: ...
```

## LLM 输出契约

```json
{
  "proposal_summary": "增加第一攻击条目的发射数量",
  "changes": [
    {
      "path": "/attacks/0/fire_quantity",
      "value": 4
    }
  ]
}
```

仅允许两个顶层字段：

```text
proposal_summary
changes
```

每项 change 仅允许：

```text
path
value
```

## Prompt 输入压缩

只发送：

```text
CandidateIntent
patchable leaf catalog
与 Patch 选择相关的场景约束摘要
accepted candidate summaries
previous structured error
```

不要额外要求模型输出完整 Baseline。

模型需要知道当前值时，从 `patchable_leaves.current_value` 获取。

## Steps

* [ ] 1. 写合法 Patch 解析测试

* [ ] 2. 写失败测试

覆盖：

```text
额外字段
changes 不是数组
path 不在 leaf catalog
value 类型不匹配
修改数量小于 Intent minimum
修改数量大于 Intent maximum
candidate_03 修改两个叶子
candidate_02 只修改一个维度
与已接受候选 changed_paths 和值完全重复
```

* [ ] 3. 运行并确认 RED

* [ ] 4. 实现严格 JSON 解析

* [ ] 5. 不在 Generator 中构造完整 StrategySpec

Generator 只返回 CandidatePatch。

* [ ] 6. previous_error 存在时使用局部修复 Prompt

错误结构：

```json
{
  "code": "PATCH_PATH_NOT_ALLOWED",
  "detail": "/attacks/99/fire_quantity"
}
```

* [ ] 7. 运行测试并确认 GREEN

* [ ] 8. 提交

```text
feat(proposal): generate one bounded strategy patch per candidate
```

---

# Task 6：将 StrategyProposalAgent 重构为 Coordinator

## Files

* Modify:
  src/cmo_lua_agent/agents/strategy_proposal_agent.py
* Modify:
  src/cmo_lua_agent/agents/**init**.py
* Test:
  src/cmo_lua_agent/tests/optimization/test_strategy_proposal_agent_two_stage.py

## Public Interface

必须保持：

```python
class StrategyProposalAgent:
    def propose(
        self,
        context: StrategyProposalContext,
    ) -> tuple[StrategyCandidate, ...]: ...
```

新增只读属性：

```python
@property
def last_usage(self) -> StrategyProposalUsage: ...

@property
def total_client_calls(self) -> int: ...
```

## 正常调用流程

```text
1 次 CandidateIntentPlanner
1 次 candidate_00 Patch
1 次 candidate_01 Patch
1 次 candidate_02 Patch
1 次 candidate_03 Patch
```

正常：

```text
5 次 LLM 调用
```

每个 Patch 最多局部修复一次：

```text
最多 4 次 Patch Repair
```

最坏：

```text
9 次 LLM 调用
```

## 顺序生成

必须按：

```text
candidate_00
→ candidate_01
→ candidate_02
→ candidate_03
```

每个候选成功后生成：

```python
AcceptedCandidateSummary(
    candidate_id=...,
    strategy_dimensions=...,
    changed_paths=...,
    strategy_checksum=...,
)
```

只把该摘要传给后续 Patch Generator。

## 单候选流程

```text
生成 Patch
→ Assembler
→ StrategyValidator
→ 与已接受候选 checksum 比较
→ Role 规则校验
→ 成功后接受
```

首次失败：

```text
记录结构化错误
→ 只重试当前 Candidate 一次
```

第二次失败：

```text
抛出 CandidateProposalFailed
```

不得重跑 Planner 或已成功候选。

## Steps

* [ ] 1. 写正常五次调用测试

断言：

```text
intent calls = 1
patch calls = 4
repair calls = 0
total = 5
```

* [ ] 2. 写 candidate_02 首次失败、局部重试成功测试

断言：

```text
candidate_00/01 不重复调用
candidate_02 调用两次
candidate_03 调用一次
total = 6
```

* [ ] 3. 写第二次仍失败的终止测试

断言未调用后续 candidate。

* [ ] 4. 写候选重复时只修复当前候选测试

* [ ] 5. 写每个最终 StrategySpec 完整性测试

断言：

```text
scenario_id 存在
attacks/sorties 结构完整
稳定 ID 与 Baseline 一致
intended_difference 等于真实 changed_paths
```

* [ ] 6. 运行并确认 RED

* [ ] 7. 重写 StrategyProposalAgent 为 Coordinator

删除旧完整 StrategySpec Prompt 和：

```python
strategy_spec_from_dict(dict(row["strategy"]))
```

* [ ] 8. 运行专项测试并确认 GREEN

* [ ] 9. 提交

```text
refactor(proposal): coordinate intent planning and isolated patches
```

---

# Task 7：保留并加强最终批次校验

## Files

* Modify:
  src/cmo_lua_agent/optimization/candidate_set_validator.py
* Test:
  src/cmo_lua_agent/tests/optimization/test_strategy_proposal_agent_two_stage.py

## Steps

* [ ] 1. 写失败测试

人为构造：

```text
StrategyCandidate.intended_difference
与真实 changed_paths 不一致
```

预期：

```text
candidate_XX:declared_diff_mismatch
```

* [ ] 2. 运行并确认 RED

* [ ] 3. 在 Validator 中加入一致性检查

```python
actual_paths = tuple(changed_paths)

if tuple(candidate.intended_difference) != actual_paths:
    violations.append(
        f"{candidate.candidate_id}:declared_diff_mismatch"
    )
```

* [ ] 4. 不修改以下现有规则

```text
exactly four
固定 candidate ID
重复 checksum
StrategyValidator
结构不可变
白名单路径
至少两个维度
```

* [ ] 5. 运行 Optimization 测试并确认 GREEN

* [ ] 6. 提交

```text
fix(proposal): verify candidate diff metadata against actual strategy
```

---

# Task 8：接入 ProductionPreviewBuilder

## Files

* Modify:
  src/cmo_lua_agent/evolution/production_preview_builder.py
* Test:
  src/cmo_lua_agent/tests/evolution/test_phase9c_two_stage_preview.py

## 当前必须修复的问题

当前 Builder 只在 propose 成功后增加：

```python
self.proposal_calls += 1
```

非法输出已经发送到模型端，却没有被计入调用数。

## 修改要求

### 调用统计

调用前记录：

```python
before = self._proposal_agent.total_client_calls
```

在 `finally` 中记录：

```python
after = self._proposal_agent.total_client_calls
self.proposal_calls += after - before
```

即使 Planner、Patch 或 Repair 失败，也必须计数。

### Preview 原子目录

不要直接将半成品写入最终 revision 目录。

使用：

```text
revision_000.building/
→ snapshot
→ intent artifacts
→ patch artifacts
→ frozen candidate set
→ strategy diff
→ 全部成功
→ 原子 rename revision_000/
```

失败时：

```text
保留 proposal-failure.json
删除或隔离 building 目录
不生成 FrozenCandidateSet
```

### Proposal 审计产物

在 Preview 目录保存：

```text
candidate-intents.json
candidate-patches.json
proposal-usage.json
proposal-failure.json（仅失败时）
```

不得保存完整 LLM 原始响应中的敏感附加内容。

### 幂等

最终 revision 目录完整且 checksum 正确：

```text
直接读取
0 次 LLM 调用
```

building 目录残留：

```text
视为未完成
不能当作成功 Preview
```

## Steps

* [ ] 1. 写正常 Preview 测试

断言：

```text
proposal_llm_calls = 5
FrozenCandidateSet 完整
未运行 CMO
```

* [ ] 2. 写 Patch 局部修复 Preview 测试

断言：

```text
proposal_llm_calls = 6
```

* [ ] 3. 写失败调用仍计数测试

* [ ] 4. 写失败后不存在成功 FrozenCandidateSet 测试

* [ ] 5. 写幂等 Preview 测试

第二次调用：

```text
proposal_llm_calls = 0
```

* [ ] 6. 运行并确认 RED

* [ ] 7. 实现调用计数和 building 目录原子发布

* [ ] 8. 运行 Evolution 专项测试并确认 GREEN

* [ ] 9. 提交

```text
fix(phase9c): atomically freeze two-stage proposal previews
```

---

# Task 9：预算和错误码接入

## Files

根据现有 Phase 9 预算实现定位后修改：

* Campaign budget model
* Proposal operation ledger
* Preview service

## 新预算字段

第一版至少记录：

```text
max_intent_planning_calls = 1
max_patch_generation_calls = 4
max_patch_repair_calls = 4
max_strategy_proposal_total_calls = 9
```

也可以复用现有总 LLM 预算，但必须分类记录实际用量。

## 预算规则

每次调用 `complete_json()` 之前：

```text
检查剩余预算
→ 原子预留
→ 调用
→ 无论成功或解析失败都计数
```

预算不足时：

```text
不得开始下一次 Patch 或 Repair
```

不得产生半完成 FrozenCandidateSet。

## 错误码

至少包含：

```text
INTENT_RESPONSE_INVALID
INTENT_DIVERSITY_INVALID
PATCH_RESPONSE_INVALID
PATCH_PATH_NOT_ALLOWED
PATCH_TYPE_MISMATCH
PATCH_NO_EFFECT
PATCH_ROLE_CONSTRAINT_FAILED
PATCH_DUPLICATES_EXISTING_CANDIDATE
PATCH_REPAIR_EXHAUSTED
PROPOSAL_BUDGET_EXHAUSTED
CANDIDATE_SET_INVALID
```

## Steps

* [ ] 1. 写预算不足阻止下一次调用测试

* [ ] 2. 写非法 JSON 也消耗预算测试

* [ ] 3. 写局部 Repair 消耗 repair budget 测试

* [ ] 4. 运行并确认 RED

* [ ] 5. 实现最小预算接入

* [ ] 6. 运行并确认 GREEN

* [ ] 7. 提交

```text
feat(proposal): meter multi-call proposal generation
```

---

# Task 10：全量回归与文档收口

## Files

* Modify:
  docs/architecture/current-state.md
* Modify:
  必要的 Phase 9C 状态文档
* Do not modify:
  评分、Renderer、CMO Runner、Phase 7、Phase 8 算法

## 文档更新

明确记录：

```text
StrategyProposalAgent 已从完整 StrategySpec 生成重构为：
CandidateIntentPlanner
→ per-candidate StrategyPatch
→ deterministic StrategySpec assembly。

正常 Preview 使用 5 次 Proposal LLM 调用。
每个 Candidate 最多一次局部 Patch Repair。
执行阶段不再次调用 Proposal LLM。

当前仅完成 Fake Client 和生产 Preview 工程验证。
尚未向 DeepSeek 自定义端点重新发送场景或策略数据。
真实 CMO Smoke 尚未执行。
```

## 最终测试

按顺序运行：

```powershell
$env:PYTHONPATH="$PWD\src"

python -m pytest `
  src\cmo_lua_agent\tests\optimization\test_strategy_patch.py `
  -q

python -m pytest `
  src\cmo_lua_agent\tests\optimization\test_candidate_intent_planner.py `
  -q

python -m pytest `
  src\cmo_lua_agent\tests\optimization\test_candidate_patch_generator.py `
  -q

python -m pytest `
  src\cmo_lua_agent\tests\optimization\test_strategy_proposal_agent_two_stage.py `
  -q

python -m pytest `
  src\cmo_lua_agent\tests\evolution\test_phase9c_two_stage_preview.py `
  -q

python -m pytest `
  src\cmo_lua_agent\tests\optimization `
  -q

python -m pytest `
  src\cmo_lua_agent\tests\evolution `
  -q

python -m pytest `
  src\cmo_lua_agent\tests `
  -q

python -m compileall src\cmo_lua_agent

git diff --check
```

## 最终只读审查

必须确认：

1. LLM 不再输出完整 StrategySpec。
2. candidate_id 由系统生成。
3. scenario_id 从 Baseline 继承。
4. 稳定 ID 不可能被 Patch 修改。
5. intended_difference 由实际 diff 生成。
6. 每个 Candidate 独立失败和独立修复。
7. 一个 Candidate 失败不会重新生成其他已接受候选。
8. 最终仍执行 CandidateSetValidator。
9. 最终仍执行 CandidateNoveltyValidator。
10. Preview 成功后执行阶段不再调用 Proposal LLM。
11. 所有实际 LLM 调用都计入预算。
12. Preview 失败不会生成可执行 FrozenCandidateSet。
13. Fake 测试没有访问真实 DeepSeek、自定义端点或 CMO。
14. 没有修改评分、Phase 7、Phase 8 和 Champion 算法。

Blocking Issue 为零后提交。

建议最终提交信息：

```text
refactor(proposal): generate candidates through intents and bounded patches
```

---

# Acceptance

本重构完成的标准：

```text
Fake Client：
1 次 Intent 调用
+ 4 次独立 Patch 调用
→ 4 个完整合法 StrategySpec
→ CandidateSetValidator 通过
→ CandidateNoveltyValidator 通过
→ FrozenCandidateSet 成功落盘
```

局部失败场景：

```text
candidate_02 首次 Patch 非法
→ 只重试 candidate_02
→ candidate_00、01 不重新调用
→ candidate_03 正常继续
```

真实端点边界：

```text
只有在用户明确允许向当前 DeepSeek 自定义 base_url
发送场景、Baseline、Bootstrap Skill 和候选意图信息后，
才执行一次真实 Preview。

真实 Preview 通过后，才继续 Phase 9C 单代 CMO Smoke。
```

````

这次重构最重要的三条原则是：

```text
先统一规划四种策略意图
每个候选独立生成一个小 Patch
完整 StrategySpec 永远由系统从 Baseline 构造
````

这样既保留了四候选的整体战术多样性，也消除了让模型重复复制完整嵌套对象导致的高失败率。
