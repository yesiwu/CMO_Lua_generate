



可以把 Phase 2 理解为：**把“作战方案”翻译成一套可执行步骤，再由一套稳定的 CMO Lua 零件库组装成最终 Lua。**

它不是让模型重新写一大份 Lua，也不是把 JSON 直接硬拼成字符串。

先看整体链路：

```text
ScenarioDefinition
+ StrategySpec
→ ExecutionPlan
→ LuaRuntimeProfile
→ LuaRenderer
→ candidate.lua
```

用一句话概括：

```text
场景里有什么
+ 这次准备怎么打
→ 具体要按什么顺序做
→ 调用哪些可靠的 CMO 能力
→ 组装成完整 Lua
```

---

## 一、先用“拍电影”类比

可以把整个过程想成拍电影。

### ScenarioDefinition：演员、场地和道具

它描述客观条件：

```text
有哪些舰艇
有哪些飞机
双方是谁
各自在什么位置
每艘舰有什么武器
飞机挂载是什么
```

它相当于：

```text
演员名单
拍摄场地
道具清单
```

这些东西不能因为导演换了一个拍法就发生变化。

例如当前场景中：

```text
红方有 055、052D、辽宁舰、J-15
蓝方有 CVN-70、CG-59、DDG-113
055 有多少枚 YJ-18
J-15 使用哪个 Loadout
```

这些都属于场景事实。你现在的 JSON 已经包含阵营、单位、武器库存和初始任务。fileciteturn0file4

### StrategySpec：导演的作战方案

它描述：

```text
谁攻击谁
发射几枚
什么时候攻击
飞机飞哪条航线
距离多近时攻击
什么时候返航
```

例如：

```text
055 攻击 DDG-113-1，发射 8 枚
052D-1 攻击 CG-59，发射 8 枚
J-15-1 攻击 CVN-70
J-15-2 攻击 DDG-113-2
```

这相当于导演写的“剧情和意图”。

它只说“要发生什么”，还没有说在 CMO 里具体怎么实现。

### ExecutionPlan：分镜脚本和拍摄顺序

导演说：

```text
J-15 攻击 CVN-70
```

这句话不能直接执行。

实际需要拆成：

```text
1. 检查 J-15 是否存在
2. 检查辽宁舰是否存在
3. 校验 J-15 挂载
4. 设置准备时间
5. 请求飞机起飞
6. 等待飞机真正进入飞行状态
7. 设置航路
8. 等待进入攻击距离
9. 获取 CVN-70 的 Contact
10. 发起攻击
11. 延时返航
```

这就是 ExecutionPlan。

它相当于拍电影时的：

```text
第 1 镜做什么
第 2 镜依赖什么
第 3 镜什么时候执行
```

### LuaRuntimeProfile：经过验证的摄影设备和操作方法

它是一组已经验证能用的 Lua 能力，例如：

```text
怎么获取单位
怎么检查 CMO API 是否真的成功
怎么获取 Contact
怎么建立延时事件
怎么等待飞机起飞
怎么计算飞机与目标距离
怎么命令飞机返航
```

你当前成功 Lua 已经验证了大量这样的机制，包括 `getUnit`、`cmoCall`、`scheduleLua`、`fireAt`、`airLaunchPoll` 和 `airAttackPoll`。fileciteturn0file5

这些不是每个策略都要重新发明的“战术”，而是稳定的 CMO 操作能力。

### LuaRenderer：按分镜调用设备，生成最终成片

LuaRenderer 读取：

```text
ExecutionPlan
+ LuaRuntimeProfile
```

然后生成：

```text
candidate.lua
```

它相当于按照分镜表，把可靠的拍摄方法组合成完整电影。

---

# 二、为什么不能 StrategySpec 直接拼 Lua

最直接的写法可能是：

```python
if mission.type == "ship_attack":
    lua += f'fireAt("{attacker}", "{target}", {weapon}, {quantity})'
```

看起来简单，但很快会出问题。

因为一个“攻击任务”背后不只是调用一次 `fireAt`。

可能还需要：

```text
确保攻击单位存在
确保目标存在
设置目标可探测
设置红方态势感知
等待 Contact 出现
创建延时事件
检查 API 返回值
执行后删除事件
记录日志
```

如果 StrategySpec 直接拼 Lua，这些隐藏步骤会散落在大量字符串拼接代码里，最后形成一个很难维护的大模板。

因此要增加 ExecutionPlan：

```text
StrategySpec
描述“想做什么”

ExecutionPlan
描述“按什么步骤做”

LuaRuntime
描述“每一步在 CMO 中怎么可靠实现”
```

这是三个不同层次。

---

# 三、用当前舰艇攻击举一个完整例子

假设 StrategySpec 中有：

```json
{
  "attackerId": "red_055_nanchang",
  "targetId": "blue_ddg113_1",
  "weaponDbid": 2868,
  "fireQuantity": 8,
  "delaySeconds": 30
}
```

它表达的是：

```text
055 南昌舰
在 30 秒后
向 DDG-113-1
发射 8 枚指定武器
```

ExecutionPlan 不会直接保存一段 Lua，而会转换成类似：

```json
{
  "operations": [
    {
      "operation_id": "resolve_attacker_001",
      "primitive_type": "resolve_unit",
      "parameters": {
        "side_id": "red",
        "unit_id": "red_055_nanchang"
      },
      "depends_on": [],
      "source_strategy_path": "/targetAssignments/0"
    },
    {
      "operation_id": "resolve_target_001",
      "primitive_type": "resolve_contact",
      "parameters": {
        "side_id": "red",
        "target_id": "blue_ddg113_1"
      },
      "depends_on": [
        "resolve_attacker_001"
      ],
      "source_strategy_path": "/targetAssignments/0"
    },
    {
      "operation_id": "attack_001",
      "primitive_type": "schedule_surface_attack",
      "parameters": {
        "attacker_id": "red_055_nanchang",
        "target_id": "blue_ddg113_1",
        "weapon_dbid": 2868,
        "quantity": 8,
        "delay_seconds": 30
      },
      "depends_on": [
        "resolve_attacker_001",
        "resolve_target_001"
      ],
      "source_strategy_path": "/targetAssignments/0"
    }
  ]
}
```

然后 LuaRenderer看到：

```text
resolve_unit
resolve_contact
schedule_surface_attack
```

就去 RuntimeProfile 中找到对应实现，最终生成类似：

```lua
local attacker = runtime.resolve_unit("red", "red_055_nanchang")
local contact = runtime.resolve_contact("red", "blue_ddg113_1")

runtime.schedule_surface_attack({
    attacker = attacker,
    contact = contact,
    weapon_dbid = 2868,
    quantity = 8,
    delay_seconds = 30,
})
```

实际实现可能不是这种模块调用形式，但逻辑边界是一样的。

---

# 四、ExecutionPlan 每个字段是什么意思

你列出的五个字段可以这样理解。

## 1. `operation_id`

这一操作的唯一编号。

例如：

```text
resolve_target_001
launch_aircraft_001
wait_airborne_001
attack_target_001
```

作用是：

- 后续步骤可以引用它；
- 出错时知道具体哪一步失败；
- 日志可以定位；
- Lua 代码可以反查到 ExecutionPlan；
- 后续保存轨迹时能精确记录。

## 2. `primitive_type`

这一操作属于哪种标准能力。

例如：

```text
ensure_unit
resolve_contact
schedule_surface_attack
request_aircraft_launch
wait_until_airborne
set_aircraft_route
attack_from_aircraft
return_to_base
```

它不是任意字符串，而必须是 Runtime 已注册的能力。

## 3. `parameters`

这一步所需的参数。

例如：

```json
{
  "aircraft_id": "red_j15_1",
  "target_id": "blue_cvn70",
  "attack_range_nm": 80
}
```

## 4. `depends_on`

说明当前操作依赖哪些前置操作。

例如：

```text
设置航路
依赖
飞机已经起飞
```

所以：

```json
{
  "operation_id": "set_route_001",
  "depends_on": [
    "wait_airborne_001"
  ]
}
```

这很重要，因为当前成功 Lua明确验证了：

> 飞机必须先通过 `isOperating` 确认已经起飞，才能设置航路。fileciteturn0file5

如果没有依赖关系，生成器可能写成：

```text
先设置航路
再请求起飞
```

代码语法可能没问题，但实际运行会失败。

## 5. `source_strategy_path`

说明这一操作来自 StrategySpec 的哪个字段。

例如：

```text
/airOperations/0/route
/targetAssignments/2/fireQuantity
```

它的用途是出错时能追根溯源。

例如 CMO 报错：

```text
攻击距离参数非法
```

系统可以定位：

```text
operation: wait_attack_range_001
source: /airOperations/0/attackRangeNm
```

这样未来 RepairAgent 不需要阅读几百行 Lua，只需要检查 StrategySpec 对应字段。

---

# 五、LuaRuntimeProfile 到底是什么

它不是一份固定 Lua 文件，也不是整个 Lua 模板。

更准确地说，它是：

> 当前系统已经支持并验证过的 CMO Lua 能力集合，以及这些能力对应的实现版本。

可以想象成：

```json
{
  "profile_id": "naval_air_strike_v1",
  "runtime_version": "1.0.0",
  "supported_primitives": [
    "ensure_side",
    "ensure_surface_unit",
    "ensure_aircraft",
    "resolve_contact",
    "schedule_surface_attack",
    "request_aircraft_launch",
    "wait_until_airborne",
    "set_aircraft_route",
    "wait_until_in_attack_range",
    "attack_from_aircraft",
    "return_to_base"
  ]
}
```

同时，它关联真正的 Lua 实现。

例如：

```text
resolve_contact
→ 使用 VP_GetSide().contacts

wait_until_airborne
→ 使用 isOperating 轮询

wait_until_in_attack_range
→ 使用 Tool_Range

schedule_action
→ 使用 Time Trigger + LuaScript Action + Event
```

这些实现来自当前已经成功运行的 Lua，不是理论猜测。你的成功 Lua明确说明：

- `VP_GetSide().contacts` 在当前版本可用；
- 延时事件需要游戏时间推进；
- 飞机不能用舰艇装弹 API 设置挂载；
- 起飞要轮询 `isOperating`；
- 攻击要根据实际距离判断。fileciteturn0file5

所以 RuntimeProfile 本质上是：

```text
当前 CMO 版本下
我们已经确认可靠的 Lua 能力清单
```

---

# 六、RuntimeProfile 为什么要有版本

假设现在使用：

```text
runtime_version = 1.0
```

其中 Contact 获取方式是：

```lua
VP_GetSide({Side="红方"}).contacts
```

以后你发现新的、更稳定的实现，改成：

```text
runtime_version = 1.1
```

那么历史候选仍然可以知道：

```text
它当时使用的是哪个 Runtime
```

否则两次运行即使 StrategySpec 相同，也可能因为底层 Runtime 改了而出现不同结果，却无法解释原因。

所以后续候选结果必须至少记录：

```text
strategy_version
runtime_version
renderer_version
```

---

# 七、CapabilityGap 是什么意思

CapabilityGap 可以翻译成：

```text
能力缺口
```

即：

> 这个策略是合法的，但当前 Runtime 还不会实现它。

例如规划 Agent 生成：

```text
让潜艇在指定区域巡逻并伏击航母
```

但当前 Runtime 只支持：

```text
水面舰艇反舰
舰载机起飞、攻击和返航
```

系统应该返回：

```json
{
  "capability": "submarine_patrol",
  "status": "unsupported",
  "required_by": "/submarineOperations/0",
  "runtime_profile": "naval_air_strike_v1",
  "message": "当前 Runtime 不支持潜艇巡逻任务"
}
```

而不是：

### 错误做法一：直接忽略

```text
潜艇任务不会出现在 Lua 中
但系统仍然声称生成成功
```

这样生成的 Lua 与策略不一致。

### 错误做法二：随便降级

```text
不会潜艇巡逻
就改成潜艇立即攻击
```

策略已经被系统偷偷改变。

### 错误做法三：让 LLM 临时自由写 Lua

```text
Runtime 不会
→ 让模型自己写一段潜艇 Lua
```

这样会重新回到不可控的完整 Lua 生成。

正确做法是明确返回：

```text
这个策略当前无法编译
缺少 submarine_patrol 能力
```

以后你可以专门新增这个 Primitive、测试并升级 Runtime。

---

# 八、LuaRenderer 具体做什么

LuaRenderer主要完成四件事。

## 1. 加入稳定 Runtime

例如加入：

```text
错误检查函数
单位解析函数
Contact 解析函数
事件调度函数
飞机轮询函数
标准日志函数
```

## 2. 写入场景数据

例如：

```lua
local SCENARIO = {
    red_side = "红方",
    blue_side = "蓝方",
    units = {...},
}
```

## 3. 写入候选策略对应的执行步骤

例如：

```lua
schedule_surface_attack(...)
schedule_air_operation(...)
```

## 4. 生成入口和版本信息

例如：

```lua
local RUNTIME_VERSION = "naval_air_strike_v1"
local STRATEGY_ID = "baseline_6v4_v1"
local PLAN_ID = "plan_baseline_6v4_v1"
```

最终输出一个 CMO 能直接执行的完整 Lua 文件。

---

# 九、什么叫“确定性”

确定性意味着：

```text
相同 ScenarioDefinition
+ 相同 StrategySpec
+ 相同 Runtime 版本
+ 相同 Renderer 版本
```

每次都应该得到相同的：

```text
ExecutionPlan
candidate.lua
```

不能第一次生成：

```text
事件名 event_abc123
```

第二次生成：

```text
事件名 event_xyz789
```

也不能因为字典遍历顺序不同导致 Lua 顺序变化。

因此应避免：

```text
随机 UUID
当前时间戳
未排序的 dict
不固定的临时名称
```

可以使用稳定命名：

```text
event_candidate_001_operation_005
```

确定性的价值是：

- 能做 Golden Test；
- 能比较代码差异；
- 能复现错误；
- 能证明评分变化来自策略，而不是生成器随机变化；
- 后续经验和训练数据更可信。

---

# 十、各项输入在 Phase 2 中怎么用

## Phase 1 输出

提供：

```text
ScenarioDefinition
Baseline StrategySpec
```

这是 Phase 2 的正式输入。

## 当前成功 Lua

它不是直接作为模板复制，而是用于提取：

```text
哪些逻辑已验证可用
正确调用顺序是什么
有哪些 CMO 特殊坑
```

当前 Lua 已经是一套完整运行程序，而不是 JSON 的简单翻译。fileciteturn0file3

## CMOLua-main 已验证逻辑

用于复用：

```text
单位生成
DBID 映射
Loadout 处理
Lua 字符串生成经验
```

但长期不再把它当作不可解释的唯一黑盒生成器。当前状态文档也明确指出，它仍包含自己的 JSON 解释、DBID 兜底和模板逻辑，后续应作为 Runtime Primitive 的迁移来源。fileciteturn0file0

## LuaGenerationDiagnostics

用于发现生成结果中的明显问题，例如：

```text
Runtime 片段缺失
生成清单不完整
未注册 Primitive
不允许的自由 Lua 内容
```

它不是 Lua 语义解释器，也不应该继续添加大量正则猜测。当前实现状态也明确把它定位为过渡期静态诊断。fileciteturn0file0

---

# 十一、各项输出是什么意思

## `execution_plan.json`

描述这次策略最终被拆成哪些执行步骤。

用途：

```text
审计
调试
可视化
修复定位
轨迹保存
Lua Source Map
```

## `runtime_profile_version`

记录这次使用哪一套 Runtime 能力。

例如：

```text
naval_air_strike_runtime_v1.0.0
```

## `rendered_baseline.lua`

由 BaselineStrategy 重新生成的完整 Lua。

这是 Phase 2 最重要的产物。

它需要经过真实 CMO 验证：

```text
能创建单位
能配置挂载
舰艇能攻击
飞机能起飞
飞机能进入射程
飞机能攻击和返航
```

## `lua_generation_manifest.json`

记录这份 Lua 是怎么生成的，例如：

```json
{
  "scenario_id": "red_blue_6v4_liaoning",
  "strategy_id": "baseline_6v4_v1",
  "plan_id": "plan_baseline_6v4_v1",
  "runtime_version": "1.0.0",
  "renderer_version": "1.0.0",
  "primitive_types": [
    "ensure_unit",
    "resolve_contact",
    "schedule_surface_attack",
    "request_aircraft_launch"
  ],
  "lua_sha256": "..."
}
```

它不是战斗结果，而是生成过程的身份证。

## `CapabilityGap`

只有策略使用未支持能力时才产生。

例如：

```text
策略需要电子战压制
当前 Runtime 不支持
→ 输出 CapabilityGap
→ 不生成伪成功 Lua
```

---

# 十二、Phase 2 最终要证明什么

Phase 2 不是要证明“系统能生成任意 Lua”。

它只需要证明这一条链路：

```text
手工确认的 Baseline StrategySpec
→ ExecutionPlan
→ 当前最小海空反舰 Runtime
→ rendered_baseline.lua
→ 真实 CMO 成功执行
```

如果这条链路成立，后续 PlanningAgent 生成的候选策略才有可靠落地方式。

否则即使 Agent 能生成四个漂亮的 StrategySpec，也只是四份 JSON，无法稳定转成可执行仿真。

最核心的职责边界是：

```text
StrategySpec
决定“怎么打”

ExecutionPlan
决定“要按哪些步骤执行”

LuaRuntimeProfile
提供“每一步可靠怎么实现”

LuaRenderer
负责“把步骤和实现组装成完整 Lua”

CMO
负责“实际跑起来并给出结果”
```