---
skill_id: cmo_naval_air_strategy_proposal
version: 1.0.0
status: bootstrap
source: human-authored
evidence_level: none
applicable_scenario_types:
  - naval_air_anti_surface
consumer:
  - StrategyProposalAgent
---

# CMO 舰机协同反舰策略生成指南

## 1. 目标

根据相同的 ScenarioDefinition 和 BaselineStrategy，生成四个合法、
可执行且具有实质战术差异的 StrategySpec。

本 Skill 只指导策略提案，不生成 Lua，不调用 CMO，不预测得分。

## 2. 不可修改内容

候选不得修改：

- 阵营及敌对关系；
- 单位数量、单位 ID、DBID；
- 飞机基地和 Loadout；
- 初始位置、航向和速度；
- 场景武器库存；
- ScenarioScoreSpec；
- CMO Points、Trigger、Action 和 Event；
- RuntimeProfile；
- Renderer；
- 系统评分 instrumentation。

所有候选必须在相同场景事实和相同评分规则下进行比较。

## 3. 可变化的策略维度

候选可以在允许路径内调整：

### 目标优先级

例如：

- 航母优先；
- 护航舰优先；
- 防空能力较强目标优先；
- 分散覆盖多个目标。

### 攻击方与目标分配

例如：

- 舰艇攻击护航舰，舰载机攻击高价值目标；
- 多个攻击方集中攻击一个目标；
- 攻击方之间避免目标重复；
- 一个目标由多个波次连续攻击。

### 攻击时机

例如：

- 舰艇先攻击；
- 舰载机先接近后，舰艇与飞机同步攻击；
- 分波次攻击；
- 根据攻击方能力设置不同延迟。

### 火力分配

例如：

- 高强度集中发射；
- 均衡分配；
- 保留部分弹药；
- 根据目标价值分配不同发射数量。

### 舰载机航路与攻击距离

例如：

- 直接接近；
- 侧向接近；
- 两架飞机采用不同航路；
- 保守攻击距离；
- 激进攻击距离。

### 资源与风险策略

例如：

- 高风险、高火力；
- 均衡策略；
- 弹药节约；
- 己方生存优先。

## 4. 第一代四候选建议结构

生成四个候选时，应覆盖至少两个不同策略维度。

### Candidate 00：高价值目标优先

核心思想：

- 航母作为主要目标；
- 对高价值目标集中火力；
- 可接受更高弹药消耗；
- 护航舰只分配必要压制力量。

### Candidate 01：护航压制优先

核心思想：

- 先攻击巡洋舰和驱逐舰；
- 降低敌方防空和拦截能力；
- 高价值目标放在后续攻击波次；
- 避免所有攻击方同时攻击航母。

### Candidate 02：目标去冲突与覆盖优先

核心思想：

- 舰艇和舰载机尽量攻击不同目标；
- 减少重复攻击已经被其他单位覆盖的目标；
- 提高多个目标被攻击的覆盖率；
- 保持舰艇与飞机之间的职责分工。

### Candidate 03：资源节约与生存优先

核心思想：

- 降低单次发射数量；
- 保留部分弹药；
- 使用较保守航路或攻击距离；
- 避免己方高价值单位承担不必要风险。

这四种方向只是策略原型，不允许直接复制固定数值。
具体参数必须根据当前 ScenarioDefinition 和库存生成。

## 5. 候选多样性要求

四个候选必须满足：

- StrategySpec checksum 不同；
- 不得只修改名称、描述或 strategy_id；
- 不得只通过数组重新排序制造差异；
- 每个候选与 Baseline 至少有一个战术字段变化；
- 整组候选至少覆盖两个策略维度；
- 不得生成四个仅有发射数量微小差异的候选；
- 不得生成非法单位、目标或武器引用。

## 6. 生成前检查

生成候选前确认：

- 当前有哪些攻击单位；
- 每个攻击单位有哪些武器；
- 每种武器的最大库存；
- 哪些目标属于高价值目标；
- 哪些单位是舰载机及其母舰；
- Baseline 当前如何分配目标；
- 哪些 StrategySpec 路径允许修改；
- 当前 RuntimeProfile 支持哪些策略能力。

RuntimeProfile 不支持的能力不得写入 StrategySpec。

## 7. 输出要求

每个候选必须输出：

- candidate_id；
- 完整 StrategySpec；
- proposal_summary；
- intended_difference。

intended_difference 只能使用已定义的策略维度，例如：

- target_priority
- target_assignment
- attack_timing
- fire_quantity
- air_route
- attack_range
- ammunition_reserve
- risk_policy

intended_difference 仅用于说明。

系统必须根据实际 StrategySpec 重新计算确定性差异，
不得直接信任 Agent 的声明。

## 8. 禁止行为

不得：

- 生成 Lua；
- 调用 CMO；
- 声称某候选一定得分最高；
- 根据评分规则反向构造作弊策略；
- 增加单位或弹药；
- 修改目标的初始状态；
- 修改评分事件；
- 使用 Runtime 不支持的能力；
- 输出四个基本相同的候选；
- 将本 Skill 内容视为经过实验验证的战术结论。