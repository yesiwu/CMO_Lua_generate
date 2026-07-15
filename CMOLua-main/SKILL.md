# CMO Lua SKILL v2.0 — Command: Modern Operations AI 助手规范

> AI 助手使用 CMO Lua 编写脚本的完整行为规范。生成所有代码前必须遵循本文件。
>
> **本版本（v2.0）整合了 xiangding 项目（`agent_plan_dll2.py` / `agent_plan_lua3.py` / `scenario_parse1.py` / `parsed_situation.json`）实战中踩过的坑。**

---

## CHANGELOG

### v2.0 (2026-07-06) — xiangding 工程化经验沉淀

| 新增/修改 | 内容 |
|----------|------|
| 🔴 红线 #5 改写 | 阵营名必须从 JSON participants 提取，禁止 LLM 自行简化（中国→中、美国→美） |
| 🔴 新增红线 #10 | 输入数据质量红线：JSON 字段类型、闭合、空格的强制规范 |
| 🔴 新增红线 #11 | 幂等性红线：脚本必须可重跑，单位/Event 不重复创建 |
| 🔴 修复 Aircraft loadout_id 漏传 | `03_build_manifest.py` 生成 `UNITS` 时未从 `selected_dbids` 读取 `loadout_id`，导致 `ScenEdit_AddUnit` 报 `Missing 'LoadoutID'` |
| 🔴 修复 SKILL.md manifest 模板 | Aircraft 条目缺少 `loadout_id` 示例；`§6` 补 `checkAircraftLoadout()` 自检 |
| 🔴 修复 references/dbid/index.md | 补全中国装备（J-16/055/052D/YJ-18/YJ-83 等）；补全俄罗斯/其他国家装备；修正 LoadoutID 标注 |
| 🔴 修复 templates/basic/add-unit.lua | 补全 Ship/Submarine/Facility 分节；Aircraft 标注 `LoadoutID` 必须项 |
| 🔴 修复 templates/basic/add-aircraft.lua | 修正 `altitude` 参数类型；补全 EA-18G 示例 |
| 🔴 修复 mcp/server.py | `describe_table_impl` PRAGMA 直接拼接存在 SQL 注入风险，增加白名单校验 |
| 🔴 修复 references/lua-api/event-functions.md | Time 触发器 `Time` 参数说明模糊，补充分钟数和绝对时间两种格式 |
| 🔴 修复 staging/03_test_manifest.py | 测试脚本用 `require()` 无法在 CMO Console 工作，改为生成可粘贴的 `dofile()` 脚本 |
| 📘 新增 §2.5 | Word/Docx 文档结构预处理要求（编成表、多层级、聚合类型） |
| 📘 新增 §5.5 | `missions` 字段 → `STRIKE` 列表的推导规则 |
| 📘 重写 manifest 章节 | 增加 `dbid_verified` / `intent` / `balance` 字段 |
| 📘 扩展自审清单 | JSON 端校验 + 弹药预算自检 + 幂等性检查 |
| 📘 新增 §9 | 故障排查 SOP（执行后没动静的诊断流程） |
| 📘 新增 §10 | 输出格式选择指南（Lua vs DLL/XML） |

### v2.0.1 (2026-07-08) — 航母舰载机作战全流程沉淀（20260708_10_true_time_delay）

| 新增/修改 | 内容 |
|----------|------|
| 🔴 新增红线 #18 | `ScenEdit_AddSide` 必须传 table，不能传字符串（静默失败） |
| 🔴 新增红线 #19 | 舰载机返航必须同时设 `base` + `homebase`（只设一个 J-15 会在原地盘旋） |
| 📘 新增 §5.7 | 航母舰载机作战标准模板：建阵营 + 航母 + 舰载机 + 真延时齐射 + 自动 RTB 全流程 |
| 📘 §5.7 包含 5 段核心代码 + 1 段一体化模板 + 14 项自审清单 |
| 🛠️ 修复 all.lua v3 | `ScenEdit_AddSide(_SIDE_RED)` → `ScenEdit_AddSide({name=..., color=...})` |
| 🛠️ 修复 all.lua v3 | 缺 RTB 段：新增 `scheduleRtb` + 真延时触发器 + 三重保险（course/homebase/base） |

### v2.0.2 (2026-07-08) — 简化 contact 查找逻辑

| 新增/修改 | 内容 |
|----------|------|
| 🔴 重写 `fireAt` contact 逻辑 | 去掉 `collectContacts`/`collectContactsFromTable`/`findContactForTarget`，改为 `VP_GetSide({Side="红方"}).contacts` 单层遍历（逐字对齐 July 3 版代码） |
| 🛠️ 清理 SKILL.md | 删除所有 `collectContactsFromTable`/`findContactForTarget` 残留引用，更新错误速查表 |
| 🔴 新增红线 #20 | 所有 `ScenEdit_*` 必须用 `pcall(function() ... end)` 包一层（userdata vs function 区别） |

### v1.x 历史
- v1.0: 初版 9 条红线 + manifest 单一数据源流程
- v1.1: 完善 TOT 真延时模板、`fireAt` 全局化、`contact_settle_delay` 实践
- v1.2: 整合 manifest.lua → main/clear/reload/attack 四件套流程

---

## 概述

CMO Lua SKILL 是 Command: Modern Operations 海空兵棋的 AI 助手技能库。

**核心目标：** AI 生成的所有 Lua 代码，必须通过 MCP 连接真实 CMO 数据库，**禁止凭空编造 DBID、LoadoutID、GUID、阵营名等任何数据**。

**适用对象：** Cursor / Windsurf（`.cursorrules` 同名文件）、ChatGPT / Claude / Gemini（粘贴为 system prompt）、GitHub Copilot（`.github/copilot-instructions.md`）、API 集成（`system` 消息）。

**核心能力：**
- 🗣️ **自然语言 → Lua**：描述场景，自动生成可运行代码
- 🔍 **MCP 查 DBID**：连接 CMO 数据库，告别硬编码
- 📦 **模板库**：基础到高级，复制即用（TOT 真延时、舰载机作战等）
- 🐛 **报错速查**：常见错误 + 解决方案

**快速开始：**
```powershell
# 1. 安装依赖
pip install -r mcp/requirements.txt

# 2. 复制数据库（CMO 安装目录下 DB\DB3K_xxx.db3）
#    放到 mcp/db/DB3K_514.db3

# 3. 重启 IDE，MCP 自动加载

# 4. 开始对话，AI 自动查询 DBID
```

---

## 行为红线（违反直接报错）

1. **严禁硬编码 DBID**——任何 `dbid = 数字` 必须先通过 MCP 查询
2. **严禁编造 LoadoutID**——飞机必须先查 `DataAircraftLoadouts` 表
3. **严禁编造 GUID**——GUID 必须是真实单位创建后返回的 UUID
4. **严禁用中文查询 MCP**——CMO 数据库字段是英文，必须翻译成英文再查
5. **严禁用英文阵营名（Red/Blue）或自行简化中文阵营**——所有 `side=` 参数必须从 `parsed_situation.json` 的 `participants` 字段原样提取；不得 LLM 简化（如 `"中国"`→`"中"`、`"美国"`→`"美"`），不得使用 `"Red"` `"Blue"`
6. **红方全知全能必须用 `ScenEdit_SetSideOptions`**——不能用 EMCON/Doctrine 伪装，必须用 `ScenEdit_SetSideOptions({side="红方", awareness="OMNI"})`
7. **严禁多脚本单位名不一致**——所有脚本中引用同一单位时，单位名必须与 `main.lua` 中 `ScenEdit_AddUnit({name="..."})` 完全一致；常见错误：AI 自行在单位名前加"红方-"或"蓝方-"前缀，导致跨脚本找不到单位
8. **红方发射导弹前，蓝方目标必须设置 `autodetectable = true`**——即使红方设为 OMNI，如果蓝方单位没有 `autodetectable = true`，红方也无法稳定获得可攻击的 contact，导致 `ScenEdit_AttackContact` 失败或导弹脱靶
9. **真延时打击必须使用 CMO 事件触发器（Time Trigger + LuaScript Action）**——严禁只用 `for + fireAt(qty=N)` 同步循环"假延时"；必须把 `qty=N` 拆成 `N` 个 `qty=1` 的独立触发器，每个触发器 `delay = startDelay + (k-1)*interval + contact_settle_delay`，靠仿真时间推进发射
10. **输入 JSON 必须通过 schema 校验才能生成 Lua**——见 §2.5。常见违规：`unit` 字段从 `dict` 变成 `list`、数字写成字符串、单位名前后有空格、引号未闭合
11. **脚本必须可幂等重跑**——同一脚本执行两遍不会重复创建单位、不会创建同名 Event。单位创建前必须用 `VP_GetSide` 查重；Event/Trigger/Action 命名必须包含 `ScenEdit_CurrentTime()` 时间戳；清弹用 `AddReloadsToUnit + remove=true`（见红线 #21），`dumpAmmo` 仅用于清弹后读数自检、不是清弹手段
12. **红蓝双方 Doctrine 的 `weapon_control_status` 必须显式设置**——`Hold (2)` 时单位不会主动还击，蓝方 DDG 被击后会因 `wcs=2` 完全不攻击；STRIKE 成功发射后"导弹立即消失"就是这个原因。**默认必须用 `Free (0)` 或 `Tight (1)`**：`ScenEdit_SetDoctrine({side="红方"}, {weapon_control_status_surface=0})`
13. **`ScenEdit_AttackContact` 的 `mode` 必须是字符串 `"1"` 而非数字 `1`**——后者静默返回 `nil`（不抛错），导致"调用成功但导弹没发射"。STRIKE 模板必须用命名参数 `mode = "1"`
14. **`ScenEdit_AddUnit` 的 `latitude` / `longitude` 推荐用数字类型**——CMO 虽支持 `"35.0"` 字符串，但边界情况（如 DMS 解析失败）会触发 `Invalid latitude value`；建议统一用 `35.0`（十进制数字），纬度范围 ±90、经度 ±180
15. **`fireAt` / `scheduleOne` 必须是全局函数**（不带 `local`）——事件脚本运行在 CMO 沙箱中，无法访问外部作用域的 `local` 函数。**包括配置变量** `_SIDE_RED`、`_CONTACT_SETTLE_DELAY` 等也必须提升为全局
16. **🔴 MCP 关联表查询必须用正确的列名——多张关联表列名是"反"的**——DB3K_504.db3 里部分关联表的字段命名方向与表名暗示相反，写反了就拿不到任何数据：
    - **`DataAircraftLoadouts(ID, ComponentID)`**：ID = **Aircraft dbid**，ComponentID = **LoadoutID**（与表名暗示完全相反）
    - **`DataFacilityAircraftFacilities(ID, ComponentNumber, ComponentID)`**：ID = **Facility dbid**，ComponentNumber = 槽位编号，ComponentID = Aircraft dbid
    - **`DataShipAircraftFacilities(ID, ComponentID)`**：ID = Ship dbid，ComponentID = Aircraft dbid
    - **`DataLoadoutWeapons(ID, ComponentNumber, ComponentID, Optional, Internal)`**：ID = **LoadoutID**（这条正确），ComponentNumber = 挂点编号，ComponentID = Weapon dbid
    - 写查询时务必先 `describe_table` 确认列语义，**不要凭"表名暗示"推断**——这是 2026-07-08 排查 J-15 Loadout 时实测出来的坑
17. **🔴 MCP 调用必须设 fallback——Cursor MCP 客户端偶发吞参数**——`CallMcpTool(arguments=...)` 调用时偶发出现 `Input validation error: '<field>' is a required property`，但 schema 已合规。备用方案：用 `subprocess` spawn `mcp/server.py` 直接走 JSON-RPC stdio，**已验证 6/6 工具全部能跑通**。调用模板见 §11.5。
18. **🔴 `ScenEdit_AddSide` 必须传 table，不能传字符串**——`ScenEdit_AddSide("红方")` 静默失败、不抛错，但阵营实际未创建，后续 `ScenEdit_SetDoctrine({side="红方"})` 全部失效。正确：`ScenEdit_AddSide({name="红方", color="255,0,0"})`。**每次建阵营后必须用 `VP_GetSide` 诊断确认存在**。
20. **🔴 所有 `ScenEdit_*` 调用必须用 `pcall(function() ... end)` 包一层**——CMO 的 `ScenEdit_*` 函数底层是 userdata 而非 Lua function，直接 `pcall(ScenEdit_XXX, args)` 会报 `attempt to index a nil value` 崩溃；即使该函数单独调用正常，pcall 直接包也不安全。**正确写法**：
    ```lua
    -- ✅ 正确：包一层匿名函数
    pcall(function()
        ScenEdit_SetSideOptions({side="红方", awareness="OMNI"})
    end)

    -- ✅ 正确：需要返回值时加 return
    local ok, r = pcall(function()
        return ScenEdit_GetUnit({side="红方", name="055-Nanchang"})
    end)

    -- ❌ 错误：直接 pcall(function, args)
    pcall(function() ScenEdit_SetSideOptions({side="红方", awareness="OMNI"}) end)  -- 崩溃！
    local ok, r = pcall(function() return ScenEdit_GetUnit({side="红方", name="xxx"}) end)  -- 崩溃！
    ```
    - 涉及 `ScenEdit_SetTrigger / SetAction / SetEvent / SetEventTrigger / SetEventAction` 的 TOT 调度代码，每行都要包
    - `ScenEdit_GetUnit` 查重、`ScenEdit_AddUnit` 创建也要包（有 guid 返回）
21. **🔴 清弹只能用 `AddReloadsToUnit + remove=true`，严禁用 `DumpAmmo` / `remove_weapon` 清弹**——这是反复踩过的坑，务必遵守：
    - ❌ **错误做法**：用 `ScenEdit_DumpAmmo({unit_guid=..., quantity="all", weaponDbId=...})` 当清弹手段。`DumpAmmo` 只适合"自检读数量"，不是可靠的清空待发弹 API。
    - ❌ **错误做法**：用 `remove_weapon` 删武器记录——会把 mount 格子一起删掉，导致后续 `AddReloadsToUnit` 找不到兼容 mount，弹**装不回去**。
    - ❌ **错误做法**：装弹用 `ScenEdit_SetAircraftLoadout`——那是给飞机换挂载方案的，不能给水面舰艇 VLS 补反舰弹。舰艇/飞机补弹统一用 `ScenEdit_AddReloadsToUnit`。
    - ✅ **唯一正确做法**：遍历 `u.mounts → m.mount_weapons`，快照所有 `wpn_current > 0` 的武器，再逐条 `ScenEdit_AddReloadsToUnit({guid=u.guid, wpn_dbid=w.wpn_dbid, mount_guid=m.mount_guid, number=cur, remove=true})` 把数量减到 0、保留格子。标准模板见"Weapon Reloads（装弹）"章节的 `clearUnitWeapons()`。
    - ⚠️ 红线 #11 里"清弹前用 dumpAmmo 自检"仅指**读数验证**，不是清弹动作，切勿混淆。

---

## 单位命名一致性（多脚本协同必读）

### 核心原则

`main.lua` 创建单位时，`name=` 字段的值就是该单位的唯一标识。后续所有脚本（`clear.lua` / `reload.lua` / `attack.lua`）必须**原样引用**，不得擅自修改前缀、后缀或中英文。

```lua
-- main.lua
ScenEdit_AddUnit({ side = "红方", name = "<攻击方单位名>", dbid = <DBID>, ... })
--                                          ^^^^^^^^^^^^^^ 这个值必须在所有脚本中一模一样

-- clear.lua  ✓ 正确
local CLEAR_LIST = { "<攻击方单位名>" }

-- clear.lua  ✗ 错误（擅自加了"红方-"前缀，main.lua 中并没有这个前缀）
local CLEAR_LIST = { "红方-<攻击方单位名>" }

-- attack.lua  ✓ 正确（攻击方和目标名都与 main.lua 的 name= 一致）
local STRIKE = { { "<攻击方单位名>", "<目标单位名>", <武器DBID>, <数量> } }

-- attack.lua  ✗ 错误（红蓝双方单位名都擅自加了阵营前缀）
local STRIKE = { { "红方-<攻击方单位名>", "蓝方-<目标单位名>", <武器DBID>, <数量> } }
```

### side 与 name 的区别

| 参数 | 含义 | 示例 |
|------|------|------|
| `side` | 阵营名，固定用中文 | `"红方"` `"蓝方"` |
| `name` | 单位名，用 `main.lua` 创建时的实际值 | `"Red-052D-Alpha"` `"DDG-113"` |

```lua
-- 正确：side 是阵营名，name 是单位名（两者不能混淆）
ScenEdit_GetUnit({ side = "红方", name = "<攻击方单位名>" })
ScenEdit_AddReloadsToUnit({ side = "红方", unitname = "<攻击方单位名>", ... })
```

### 常见错误模式

| 错误写法 | 问题 |
|----------|------|
| `"红方-<单位名>"` / `"蓝方-<单位名>"` | `main.lua` 中 `name=` 不含阵营前缀，擅自添加导致查找不到 |
| `"<单位名>"` vs `"<单位名>-1"` 不一致 | 不同脚本中同一单位命名不统一 |
| `attack.lua` 目标名加了阵营前缀 | 目标单位在 `main.lua` 中 `name=` 值不含阵营前缀 |

### 自审清单（每次生成多脚本前必查）

**Lua 端自审：**

- [ ] `CLEAR_LIST` / `AMMO` / `STRIKE` 中的所有单位名，与 `main.lua` 中 `ScenEdit_AddUnit` 的 `name=` 完全一致
- [ ] 所有脚本的 `side` 参数统一为 `"红方"` / `"蓝方"`（不得写成 `"Red"` / `"Blue"`，不得简化如 `"中"`/`"美"`）
- [ ] `attack.lua` 中目标单位名不得加 `"蓝方-"` 前缀
- [ ] 多脚本生成时，建议先完成 `main.lua` 确定单位名，再生成其余脚本并引用相同值

**JSON 端自审（xiangding 实战新增）：**

- [ ] `json.loads(parsed_situation.json)` 能成功解析（无引号闭合错误、无未转义单引号）
- [ ] `intentions` 和 `missions` 数组非空（xiangding 红线 #68: 必须有内容）
- [ ] 每个 `force` 包含 `name`/`unit`/`title` 三个字段（缺一保留为 `""`）
- [ ] 所有 `unit` 字段是 `dict` 类型（`{"型号": 数量}`），不能是 `list` 或字符串
- [ ] 数字字段（`altitude` 等）是 `number`，不能是字符串 `"11000"`
- [ ] 飞机名称两侧无空格、无全角括号（`"DDG-113 "` ❌ → `"DDG-113"` ✅）
- [ ] `participants` 字段值与最终 Lua 中 `side=` 参数完全一致

**弹药预算自检：**

- [ ] 对每个 `attacker`: `sum(AMMO[].number where unitname=attacker) >= sum(STRIKE[].quantity where STRIKE[].attacker=attacker)`
- [ ] 装填后剩余弹药数应在脚本末尾打印（`"弹药余额: X"`）
- [ ] 若弹药不足，必须在生成阶段就报错，不得让脚本"默默少打几枚"

**幂等性自检（红线 #11）：**

- [ ] `main.lua` 创建单位前调用 `VP_GetSide` 检查 `name` 是否已存在
- [ ] `Event/Trigger/Action` 命名包含时间戳（如 `"TOT_1_1_<currentTime>"`），避免重跑时重名
- [ ] `clear.lua` 调用 `dumpAmmo` 自检，确认清弹成功后再装填

### 多脚本生成推荐流程

> **关键原则：先制定打击清单（manifest），再生成代码。清单是所有脚本的单一数据源。**

1. 生成 `manifest.lua` — **制定打击清单**（详细字段见 §6）
   - `SCENARIO`: 场景名称、地点、时间、participants
   - `UNITS`: 所有单位（side、name、dbid、坐标、`dbid_verified`）
   - `WEAPONS`: 武器配置（dbid、loadout_id、`loadout_verified`）
   - `CLEAR_LIST`: 需要清弹的单位名列表
   - `AMMO`: 装弹清单（unitname、wpn_dbid、number）
   - `STRIKE`: 打击任务清单（attacker、target、weapon_dbid、quantity、`intent`）
   - **清单确认后再生成其他脚本**

2. 生成 `main.lua` — 引用 `manifest.lua` 的 `UNITS` 创建单位
3. 生成 `clear.lua` — 引用 `manifest.lua` 的 `CLEAR_LIST` 执行清弹（使用标准 `clearUnitWeapons()` 模板）
4. 生成 `reload.lua` — 引用 `manifest.lua` 的 `AMMO` 执行装弹
5. 生成 `attack.lua` — 引用 `manifest.lua` 的 `STRIKE` 执行打击

> **禁止**在 `main.lua`/`clear.lua`/`reload.lua`/`attack.lua` 中硬编码单位名，必须从 `manifest.lua` 引用。

---

## §5.7 航母舰载机作战标准模板（v2.0 新增 — xiangding 实战沉淀）

> **场景原型**：红方辽宁舰（type=Ship，dbid=2007）+ 红方 055（type=Ship，dbid=3883）+ 红方 J-15（type=Aircraft，dbid=2496，loadout=9682，base=辽宁舰）→ 真延时齐射 YJ-83K 攻击蓝方 CG-59（type=Ship，dbid=2862）→ 攻击完 RTB 返航辽宁舰
>
> **本节约束**：5 个核心规则（建阵营、航母、舰载机、齐射、RTB）+ 1 个一体化模板 + 1 个自审清单。所有规则都与上文的"行为红线 #5 / #6 / #9 / #11 / #12 / #13 / #15"叠加生效。

### 5.7.1 建阵营（红线 #18）

```lua
-- ★ 必须传 table，否则静默失败，VP_GetSide 查不到
pcall(function() ScenEdit_AddSide({name="红方", color="255,0,0"}) end)
pcall(function() ScenEdit_AddSide({name="蓝方", color="0,0,255"}) end)

-- ★ 红方全知：找 contact 不依赖雷达（红线 #6）
pcall(function() ScenEdit_SetSideOptions({side="红方", awareness="OMNI"}) end)
pcall(function() ScenEdit_SetSideOptions({side="蓝方", awareness="OMNI"}) end)

-- 互为敌对
pcall(function() ScenEdit_SetSidePosture("红方", "蓝方", "H") end)
pcall(function() ScenEdit_SetSidePosture("蓝方", "红方", "H") end)

-- ★ 红蓝双方 wcs 全部 = 0（红线 #12）
pcall(function() ScenEdit_SetDoctrine({side="红方"}, {
  weapon_control_status_air="0",
  weapon_control_status_surface="0",
  weapon_control_status_subsurface="0",
  weapon_control_status_land="0"
}) end)
pcall(function() ScenEdit_SetDoctrine({side="蓝方"}, {
  weapon_control_status_air="0",
  weapon_control_status_surface="0",
  weapon_control_status_subsurface="0",
  weapon_control_status_land="0"
}) end)

-- ★ 阵营诊断（红线 #18 实施细则）
local sR = pcall(VP_GetSide, {Side="红方"})
local sB = pcall(VP_GetSide, {Side="蓝方"})
print(("[main] 阵营诊断: 红方存在=%s 蓝方存在=%s"):format(
  tostring(sR and true or false), tostring(sB and true or false)))
-- 预期：红方存在=true 蓝方存在=true
-- 退化：存在=false → AddSide 失败 → 检查是否传 table
```

### 5.7.2 航母 Ship（type 必须是 Ship，不能是 Air/Ground）

```lua
local CARRIER_NAME = "红方辽宁舰"
local CARRIER_LAT  = 30.60
local CARRIER_LON  = 122.50

-- ★ 幂等：先查再创建
local function getUnit(side, name)
  local ok, u = pcall(function() return ScenEdit_GetUnit({side=side, name=name}) end)
  if ok and u and u.guid then return u end
  return nil
end

local carrier = getUnit("红方", CARRIER_NAME)
if not carrier then
  local ok, r = pcall(function() return ScenEdit_AddUnit({
    type="Ship",        -- ★ 严格区分大小写（红线 #3）
    side="红方",
    name=CARRIER_NAME,
    dbid=2007,          -- 来自 MCP 实测，禁止硬猜
    latitude=CARRIER_LAT,
    longitude=CARRIER_LON,
    heading=90,
    speed=18,
    proficiency="Veteran"
  }) end)
  print(("[main] 辽宁舰 ok=%s err=%s"):format(tostring(ok), tostring(_errmsg_)))
  carrier = getUnit("红方", CARRIER_NAME)
end
```

### 5.7.3 舰载机 Aircraft（base=航母，loadout=YJ-83K）

```lua
local J15_NAME     = "J-15-RED-01"
local J15_DBID     = 2496
local LOADOUT_ID   = 9682   -- YJ-83K 反舰挂载

local j15 = getUnit("红方", J15_NAME)
if not j15 then
  -- ★ 第一次创建带 loadout（YJ-83K 反舰）
  local ok, r = pcall(function() return ScenEdit_AddUnit({
    type="Aircraft",      -- ★ 严格区分大小写
    side="红方",
    name=J15_NAME,
    dbid=J15_DBID,
    loadoutid=LOADOUT_ID, -- ★ LoadoutID（数值类型，9600 常见于反舰挂载）
    base=CARRIER_NAME,    -- ★ 关键：base 设到航母
    proficiency="Veteran"
  }) end)
  print(("[main] J-15 创建 ok=%s err=%s"):format(tostring(ok), tostring(_errmsg_)))
  j15 = getUnit("红方", J15_NAME)
  if not j15 then
    -- 后备：先建裸机再 LoadUnit
    pcall(function() ScenEdit_AddUnit({
      type="Aircraft", side="红方", name=J15_NAME,
      dbid=J15_DBID, base=CARRIER_NAME
    }) end)
    j15 = getUnit("红方", J15_NAME)
  end
end

if j15 then
  -- ★ 保险：再次强制装 Loadout
  pcall(function() ScenEdit_LoadUnit(j15.guid, LOADOUT_ID) end)

  -- ★ 准备时间归零
  pcall(function() ScenEdit_SetUnit({
    side="红方", unitname=J15_NAME, timetoready_minutes=0
  }) end)

  -- ★ 起飞
  pcall(function() ScenEdit_SetUnit({
    side="红方", unitname=J15_NAME, launch=true
  }) end)

  -- ★ 开雷达 + 预设航向（朝 CG-59 方向）
  pcall(function() ScenEdit_SetEMCON("Unit", J15_NAME, "Radar=Active") end)
  pcall(function() ScenEdit_SetUnit({
    side="红方", unitname=J15_NAME,
    course={
      {latitude=30.50, longitude=122.65},
      {latitude=30.42, longitude=122.82}
    },
    altitude=8000, throttle="Cruise"
  }) end)
end
```

### 5.7.4 真延时齐射（红线 #9 — Time Trigger + qty=1 逐枚）

```lua
local function totTicks(addSec)
  return string.format("%.0f", (ScenEdit_CurrentTime() + 62135596801 + addSec) * 1e7)
end

local function scheduleOne(atkName, tgtName, wpn, delay, tag)
  delay = delay + 15   -- ★ contact_settle_delay=15s（红线 #9）
  local ts = tostring(ScenEdit_CurrentTime())
  local evName = "Event " .. tag .. "_" .. ts
  local trName = "Trig "  .. tag .. "_" .. ts
  local acName = "Act "   .. tag .. "_" .. ts
  local fireTime = totTicks(delay)
  local script =
    ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..  -- ★ qty=1
    ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
    ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
    ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
  pcall(function() ScenEdit_SetTrigger({mode="add", type="Time", name=trName, Time=fireTime}) end)
  pcall(function() ScenEdit_SetAction({mode="add", type="LuaScript", name=acName, ScriptText=script}) end)
  pcall(function() ScenEdit_SetEvent(evName, {mode="add", IsActive=true, IsRepeatable=false}) end)
  pcall(function() ScenEdit_SetEventTrigger(evName, {mode="add", name=trName}) end)
  pcall(function() ScenEdit_SetEventAction(evName, {mode="add", name=acName}) end)
end

-- ★ fireAt 必须是全局（红线 #15）
function fireAt(attackerName, targetName, wpnDbid, qty)
  local atk = ScenEdit_GetUnit({side="红方", name=attackerName})
  local tgt = ScenEdit_GetUnit({side="蓝方", name=targetName})
  if not (atk and atk.guid) then return false end
  if not (tgt and tgt.guid) then return false end
  pcall(function() ScenEdit_SetUnit({guid=tgt.guid, autodetectable=true}) end)
  -- ... 收集 contact + ScenEdit_AttackContact（详见 §5.6 真延时打击）...
  _errnum_ = 0
  return ScenEdit_AttackContact(atk.guid, tgt.guid, {mode="1", weapon=wpnDbid, qty=qty})
end

-- 调度：2 枚 YJ-83K，间隔 1s
for k = 1, 2 do
  scheduleOne("J-15-RED-01", "CG59_Princeton", 2137, (k-1)*1, "TOT_attack_"..k)
end
```

### 5.7.5 自动 RTB 返航（红线 #19 — base + homebase 双重）

```lua
-- ★ 关键：base + homebase 都要设（红线 #19）
local function scheduleRtb(rtbDelay, tag)
  local ts = tostring(ScenEdit_CurrentTime())
  local evName = "Event " .. tag .. "_" .. ts
  local trName = "Trig "  .. tag .. "_" .. ts
  local acName = "Act "   .. tag .. "_" .. ts
  local fireTime = totTicks(rtbDelay)
  local script = table.concat({
    -- 强设航向回航母
    ("pcall(function() ScenEdit_SetUnit({side=%q, unitname=%q, course={{latitude=%f, longitude=%f}}, altitude=8000, throttle='Cruise', speed=300}) end)\n"):format(
      "红方", J15_NAME, CARRIER_LAT, CARRIER_LON),
    -- ★ homebase = 航母（舰载机回收关键）
    ("pcall(function() ScenEdit_SetUnit({side=%q, unitname=%q, homebase=%q}) end)\n"):format(
      "红方", J15_NAME, CARRIER_NAME),
    -- ★ base = 航母（调度系统识别用）
    ("pcall(function() ScenEdit_SetUnit({side=%q, unitname=%q, base=%q}) end)\n"):format(
      "红方", J15_NAME, CARRIER_NAME),
    ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName),
    ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName),
    ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName),
  })
  pcall(function() ScenEdit_SetTrigger({mode="add", type="Time", name=trName, Time=fireTime}) end)
  pcall(function() ScenEdit_SetAction({mode="add", type="LuaScript", name=acName, ScriptText=script}) end)
  pcall(function() ScenEdit_SetEvent(evName, {mode="add", IsActive=true, IsRepeatable=false}) end)
  pcall(function() ScenEdit_SetEventTrigger(evName, {mode="add", name=trName}) end)
  pcall(function() ScenEdit_SetEventAction(evName, {mode="add", name=acName}) end)
end

-- 攻击完时间 = 15s(contact settle) + 60s(导弹飞行) + 10s(缓冲) = 85s
scheduleRtb(85, "RTB_J15_ReturnToCarrier")
```

### 5.7.6 完整一体化模板（main + clear + reload + attack + rtb）

参考 `outputs/lua/20260708_10_true_time_delay/all.lua`，一次性 `dofile` 执行 5 段：建单位 → 清弹 → 装弹 → 齐射 → RTB。

```lua
-- 时间线（脚本跑完后观察）
-- T+15s     第 1 枚 YJ-83K 离架
-- T+16s     第 2 枚 YJ-83K 离架
-- T+~75s    2 枚导弹命中 CG-59
-- T+85s     J-15 自动 RTB 朝辽宁舰（homebase+base 双重生效）
-- T+~110s   J-15 降落到辽宁舰甲板
```

### 5.7.7 自审清单（舰载机作战专章）

每次生成航母舰载机作战脚本前必查：

- [ ] **建阵营用 table**：`ScenEdit_AddSide({name=..., color=...})`，不能用字符串（红线 #18）
- [ ] **阵营诊断**：`VP_GetSide` 查红蓝都返回 `true`，否则 AddSide 失败
- [ ] **航母 type=Ship**（不是 Air/Ground），latitude/longitude 数字类型
- [ ] **J-15 type=Aircraft** + `base=航母名`（起飞前就设）
- [ ] **LoadoutID 走 MCP**：`loadoutid=9682`（YJ-83K）必须 `read_query` 查得
- [ ] **真延时 Time Trigger**：`type="Time"` + `qty=1` 逐枚（红线 #9）
- [ ] **contact_settle_delay=15s**：每枚弹 delay 都叠加
- [ ] **fireAt 全局函数**（红线 #15）
- [ ] **mode="1" 字符串**（红线 #13）
- [ ] **CG-59 autodetectable=true**（创建时 + 创建后遍历 + 发射前三重）
- [ ] **红蓝双方 wcs=0**（红线 #12）
- [ ] **RTB 触发器时间正确**：contact_settle + 齐射时长 + 导弹飞行 + 缓冲
- [ ] **RTB 三重保险**：`course=航母坐标` + `homebase=航母名` + `base=航母名`（红线 #19）
- [ ] **Event/Action/Trigger 自清理** + tag 带时间戳（红线 #11）

---

## §6 manifest.lua 标准模板（v2.0 升级版）

> **xiangding 实战经验**：v1.x 的 manifest 字段太少，导致 LLM 经常漏装弹、找不到目标。v2.0 强制增加 `dbid_verified` / `intent` / 弹药余额追踪字段。

### 完整模板

```lua
-- ============================================================
-- manifest.lua — 打击清单（v2.0）
-- 单一数据源：main.lua / clear.lua / reload.lua / attack.lua
-- 全部从此文件引用，禁止在其他脚本硬编码。
-- ============================================================

-- ============================================================
-- §A 场景元数据（从 JSON title / participants / location / time 提取）
-- ============================================================
SCENARIO = {
    title        = "南海1V1对抗想定",     -- 来自 JSON: title
    location     = "南海",                -- 来自 JSON: location
    start_time   = "2026-07-06 10:00:00", -- 来自 JSON: start_time
    duration     = "1天5小时30分钟",      -- 来自 JSON: duration
    sides        = { "红方", "蓝方" },     -- 来自 JSON: participants（必须是中文）
}

-- ============================================================
-- §B 武器库（dbid_verified 必须是 true 才能进 AMMO）
-- ============================================================
WEAPONS = {
    {
        dbid              = 2868,
        name              = "YJ-18",
        category          = "Anti-ship missile",
        default_quantity  = 8,            -- §5.5 默认数量
        loadout_verified  = true,          -- ★ 必须是 true（已查 DataWeapon 表）
    },
    {
        dbid              = 3883,
        name              = "Type 055 Destroyer",
        category          = "Ship",
        loadout_verified  = true,
    },
    {
        dbid              = 4299,
        name              = "DDG-113 Arleigh Burke",
        category          = "Ship",
        loadout_verified  = true,
    },
}

-- ============================================================
-- §C 单位清单（dict-keyed：UNITS[id] = {...}，便于 UNITS["055-1"] 直接访问）
--    ★ 所有脚本必须 UNITS["<id>"] 引用，禁止 ipairs/下标遍历
--    ★ id 字段即是 main.lua 的 ScenEdit_AddUnit({name=id}) 的 name=
--    ★ dbid_verified 必须 true（已 MCP query_dbid 验证）
-- ============================================================
UNITS = {
    ["055-1"] = {
        side             = "红方",
        name             = "055-1",        -- id = name（统一）
        type             = "Ship",
        dbid             = 3883,           -- MCP query_dbid("Type 055")
        latitude         = 15.0,
        longitude        = 112.5,
        heading          = 45,
        speed            = 20,
        proficiency      = "Veteran",
        autodetectable   = false,          -- 红方不需要
        dbid_verified    = true,           -- ★ 必须 true
    },
    ["J-16-1"] = {
        side             = "红方",
        name             = "J-16-1",
        type             = "Aircraft",     -- ★ 必须带 loadout_id
        dbid             = 2853,           -- MCP query_dbid("J-16")
        loadout_id       = 1821,           -- ★ MCP read_query("SELECT ID FROM DataAircraftLoadouts WHERE ComponentID=2853")
        latitude         = 29.0,
        longitude        = 123.5,
        altitude         = 7620,
        heading          = 90,
        speed            = 450,
        proficiency      = "Regular",
        autodetectable   = false,
        dbid_verified    = true,
    },
    ["DDG-113-1"] = {
        side             = "蓝方",
        name             = "DDG-113-1",
        type             = "Ship",
        dbid             = 4299,
        latitude         = 19.0,
        longitude        = 117.5,
        heading          = 200,
        speed            = 0,
        proficiency      = "Veteran",
        autodetectable   = true,           -- ★ 红线 #8：必须 true
        dbid_verified    = true,
    },
}

-- ============================================================
-- §D 清弹/装弹/打击清单
-- ============================================================

-- 需要清弹的单位名（必须在 §C UNITS 中）
CLEAR_LIST = { "055-1" }

-- 装弹清单（list of dict）
AMMO = {
    { unitname = "055-1", wpn_dbid = 2868, number = 16 },  -- YJ-18 x16
}

-- ============================================================
-- ★★★ 打击清单（list of dict - 命名键，禁止下标访问 s[1]/s[2]） ★★★
-- ============================================================
STRIKE = {
    {
        attacker    = "055-1",      -- 必须在 UNITS 中存在
        target      = "DDG-113-1", -- 必须在 UNITS 中存在
        weapon_dbid = 2868,        -- 必须在 WEAPONS 中
        quantity    = 16,          -- ★ 弹总数（真延时会被拆成 qty 个独立触发器）
        startDelay  = 0,           -- 首发延迟（秒，相对 ScenEdit_CurrentTime）
        interval    = 1,           -- 枚间隔（秒）
        intent      = "055 编队对 DDG-113 实施 YJ-18 反舰突击，符合反介入任务",
    },
}

-- ============================================================
-- §E 弹药余额自检（红线：AMMO.sum >= STRIKE.sum）
-- ============================================================
local function checkAmmoBalance()
    local ammoByUnit = {}
    for _, a in ipairs(AMMO) do
        ammoByUnit[a.unitname] = (ammoByUnit[a.unitname] or 0) + a.number
    end
    local strikeByUnit = {}
    for _, s in ipairs(STRIKE) do
        -- 命名键访问（红线 #2：禁止 s[1]）
        strikeByUnit[s.attacker] = (strikeByUnit[s.attacker] or 0) + s.quantity
    end
    for unit, totalStrike in pairs(strikeByUnit) do
        local totalAmmo = ammoByUnit[unit] or 0
        if totalAmmo < totalStrike then
            error(("manifest.lua: 弹药不足! %s 装弹 %d 枚但 STRIKE 需要 %d 枚"):format(
                unit, totalAmmo, totalStrike))
        end
        print(("[manifest] %s 弹药余额 = %d"):format(unit, totalAmmo - totalStrike))
    end
end

-- ★ Aircraft loadout_id 必须存在（防止 ScenEdit_AddUnit 报 Missing LoadoutID）
local function checkAircraftLoadout()
    for uid, u in pairs(UNITS) do
        if u.type == "Aircraft" then
            if not u.loadout_id then
                error(("[manifest] Aircraft '%s' 缺少 loadout_id！必须先用 MCP 查询 DataAircraftLoadouts 表"):format(uid))
            end
        end
    end
    print("[manifest] Aircraft loadout_id 全部存在 ✓")
end

checkAmmoBalance()
local function tableCountKeys(t)
    local n = 0
    for _ in pairs(t) do n = n + 1 end
    return n
end
checkAircraftLoadout()

print("[manifest] 清单校验通过: " .. tableCountKeys(UNITS) .. " 单位, "
    .. #AMMO .. " 装弹项, " .. #STRIKE .. " 打击项")
```

### v2.0 vs v1.x 字段对比

| 字段 | v1.x | v2.0 | 作用 |
|------|------|------|------|
| `WEAPONS[].loadout_verified` | ❌ 无 | ✅ 必须 true | 强制 MCP 查询 |
| `UNITS[].dbid_verified` | ❌ 无 | ✅ 必须 true | 强制 MCP 查询 |
| `UNITS[].autodetectable` | ❌ 无 | ✅ 蓝方必须 true | 红线 #8 |
| `STRIKE[].intent` | ❌ 无 | ✅ 追溯到 JSON | 可追溯性 |
| `§E checkAmmoBalance()` | ❌ 无 | ✅ 强制自检 | 红线：弹药预算 |
| `SCENARIO.duration` | ❌ 无 | ✅ JSON 时间同步 | 排错时定位 |

### 校验失败时的处理

如果 manifest.lua 加载时报错（弹药不足 / dbid_verified=false）：

1. **不要**继续生成 main.lua / attack.lua
2. **必须**回到 parsed_situation.json 检查 missions[].quantity 是否合理
3. **必须**重新跑 MCP 查询确认 dbid_verified
4. 修正后再重跑校验

---

## 第一要求：MCP 连接（任何对话前必须完成）

> 每次打开新 IDE 会话，都要先确认 MCP 已运行。如果没有运行，AI 将无法查询 DBID，生成的所有代码都会是假数据。

### 安装步骤

```powershell
# 1. 进入项目目录
cd "C:\Users\user\.codex\skills\CMOLua-main"

# 2. 安装依赖（必须是 Cursor 使用的 Python 环境）
# 先确认 Python 路径是否正确：
#   cmd /c "where python"  查看可用的 python.exe
#   E:\Deep_learning\anconda\python.exe 是常见路径
python -m pip install -r mcp/requirements.txt

# 3. 复制数据库文件
# 将 CMO 游戏目录中的 DB3K_xxx.db3 复制到:
#   C:\Users\Administrator\.cursor\skills\cmo-hkbq-skill\mcp\db\DB3K_514.db3
# 数据库通常位于：Command - Modern Operations\DB\DB3K_xxx.db3

# 4. 重启 IDE 让 MCP 自动加载
```

### MCP 服务器信息

- **MCP 名称**: `HKBQ_SqlDB`
- **MCP 服务器路径**: `C:\Users\user\.codex\skills\CMOLua-main\mcp\server.py`
- **数据库路径**: `C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3`
- **配置文件**: `C:\Users\user\.cursor\mcp.json`

> ⚠️ **注意**：MCP 服务器的 Python 路径必须与系统实际安装的 Python 一致。请先运行 `cmd /c "where python"` 确认路径，然后检查 `mcp.json` 中的 `"command"` 是否匹配。常见错误是写成了不存在的路径（如 `C:\Program Files\Python313\python.exe`）。

### 验证 MCP 是否运行

在对话中问 AI：**"MCP 工具可以用吗？帮我查一下 F-16 的 DBID"**

- 返回真实数据 -> MCP 已就绪
- 报错或返回假数据 -> 先回到上面的步骤 1-4

### MCP 手动配置（mcp.json 示例）

**Cursor / Trae (C:\Users\你的用户名\\.cursor\\mcp.json):**
```json
{
  "mcpServers": {
    "HKBQ_SqlDB": {
      "command": "python",
      "args": [
        "C:\\Users\\user\\.codex\\skills\\CMOLua-main\\mcp\\server.py"
      ],
      "env": {
        "SQLITE_DB_PATH": "C:\\Users\\user\\.codex\\skills\\CMOLua-main\\mcp\\db\\DB3K_514.db3"
      }
    }
  }
}
```

**VS Code (settings.json):**
```json
{
  "mcpServers": {
    "HKBQ_SqlDB": {
      "command": "python",
      "args": ["${workspaceFolder}/mcp/server.py"],
      "env": {
        "SQLITE_DB_PATH": "${workspaceFolder}/mcp/db/DB3K_514.db3"
      }
    }
  }
}
```

### IDE 兼容表

| IDE | 支持情况 |
|-----|---------|
| Cursor | ✅ 完全支持（Skill 入口 + MCP） |
| Trae | ✅ MCP 兼容（注意使用自己的 Python 环境） |
| VS Code + Continue | ✅ MCP 兼容 |
| Claude Desktop | ✅ MCP 兼容 |
| 其他 Claude 系列 | ✅ MCP 兼容 |

### 常见问题（FAQ）

| 问题 | 解决方法 |
|------|---------|
| 报错 `"No module named fastmcp"` | 确保 `fastmcp` 安装到 IDE 使用的 Python 环境 |
| Trae 上 MCP 不工作 | Trae 使用自己的 Python 环境，在 Trae 设置中确认 Python 路径后安装 fastmcp |
| MCP 服务无法启动 | 检查数据库文件路径是否正确；检查 `mcp.json` 配置；数据库版本号需与 server.py 匹配 |

### 项目结构

```
CMOLua-main/
├── SKILL.md              # AI 助手行为规范（核心入口）
├── mcp/
│   ├── server.py         # MCP 服务端
│   ├── requirements.txt
│   └── db/               # CMO 数据库（首次需从游戏目录复制）
├── references/           # 知识库
│   ├── lua-api/          # CMO Lua API 参考
│   └── dbid/             # 常用 DBID 速查
├── templates/            # Lua 代码模板
├── examples/             # 案例库
└── errors/              # 报错记录库
```

### 案例来源

本项目大量案例来自公众号 **「海空兵棋与AI」** Lua 编程系列文章，详见 `examples/`。

---

## MCP 调用时机（强制）

**只要代码中涉及以下任何一项，必须立即调用 MCP 查询：**

| 代码中出现的内容 | 必须调用的 MCP 工具 |
|---------------|-------------------|
| 装备名称（如 F-16、宙斯盾舰） | `query_dbid("F-16C")` |
| 阵营名称（如 蓝方、红方） | `read_query` 查 `sides` 表 |
| 基地 DBID（type="Facility"） | `query_dbid("runway")` |
| 飞机 DBID（type="Aircraft"） | `query_dbid("F-16")` |
| 舰艇 DBID（type="Ship"） | `query_dbid("Aegis destroyer")` |
| 潜艇 DBID（type="Submarine"） | `query_dbid("attack submarine")` |
| LoadoutID（飞机挂载） | `read_query` 查 `DataAircraftLoadouts` |
| 数据库表结构不确定时 | `describe_table()` 或 `list_tables()` |

**查询内容必须翻译成英文！**

### MCP 工具详解

#### 1. query_dbid(query, limit=50)
自然语言查询 DBID，自动搜索飞机、舰艇、潜艇、设施四类表。

```python
query_dbid("J-16")  # 返回: [{"dbid": ..., "name": "J-16D", "type": "Aircraft", ...}, ...]
```

#### 2. read_query(sql, params=None, row_limit=1000)
执行 SELECT SQL 查询（仅允许 SELECT/WITH 语句）。

```python
read_query("SELECT ID FROM DataAircraftLoadouts WHERE ComponentID = 1234")
```

#### 3. list_tables()
列出数据库所有表名。

```python
list_tables()  # 返回: ["DataAircraft", "DataShip", "DataWeapon", ...]
```

#### 4. describe_table(table_name)
获取指定表的字段结构。

```python
describe_table("DataAircraft")  # 返回: [{"name": "ID", "type": "INTEGER", ...}, ...]
```

#### 5. get_dbid_by_name(name)
通过名称精确查找 DBID（返回第一条匹配）。

```python
get_dbid_by_name("F-22A")
```

#### 6. get_dbid_by_country(country, category=None, limit=20)
按国家查询 DBID。

```python
get_dbid_by_country("China", "aircraft")
```

---

## §2.5 Word/Docx 文档结构预处理要求（xiangding 实战沉淀）

> 这一节专门给**「输入是 Word 想定文档，要先解析成 JSON 再生成 Lua」**的完整链路（xiangding 项目流程：`docx → parsed_situation.json → lua`）。如果不走 docx 解析，可以跳过。

### 文档结构识别

CMO 想定文档通常包含以下结构，AI 在解析前必须先识别：

| 文档标记 | 含义 | 处理方式 |
|---------|------|---------|
| `=== TABLE X: 兵力部署表 ===` | 编成/部署表格 | 按行拆 force，每个单元格独立字段 |
| `=== TABLE X: 美空中组成司令部兵力编成表 ===` | 美方编成表 | 同上，作为某方 forces |
| `作战企图` / `任务` / `使命` 章节 | 任务定义 | 提取为 `missions[].objective` |
| `背景` / `情况` 章节 | 想定背景 | 提取为 `description` |
| `地点` / `海域` | 地理位置 | 提取为 `location` |

### 兵力部署表提取规则（xiangding 红线 #57）

> 这是 xiangding 项目 `scenario_parse1.py` 反复调试后沉淀下来的规则，必须严格遵守。

1. **多层级结构以最小单位为准**
   - 原文：`X旅下有ABCD营` → 输出 4 个 force（营级），不输出旅
   - 反例：把"X旅"作为一个 force（漏掉下属 4 个营）

2. **聚合类型合并到 `unit` 字段**
   - 原文：`卫星力量（含晨雾型卫星 1 颗）` → 1 个 force
     ```json
     { "name": "卫星力量", "unit": { "晨雾型卫星": 1 } }
     ```
   - 反例：拆成 `晨雾型卫星 #1`、`晨雾型卫星 #2`（错误）

3. **数量+量词必须提取**
   - 原文：`红-12 飞机 12 架` → `unit: { "红-12": 12 }`
   - 反例：只提取名称不提取数量 → `unit: { "红-12": 1 }`（编造）

4. **挂载信息提取到 `loadout`**
   - 原文：`红-12 挂 OFAB-100-120 破片弹` → `loadout: "OFAB-100-120 破片弹"`
   - 飞机必须保留 loadout 字段，舰艇不需要

5. **海拔/高度字段映射**
   - `超高空` → `20000`
   - `高空` → `11000`（默认）
   - `中空` → `6000`
   - `低空` → `1000`
   - `超低空` → `100`
   - 缺失时默认 `11000`

### 作战企图（intentions）提取

- **不预设阵营名**：必须从原文提取（`"中国"`、`"台湾"`、`"美国"`、`"日本"`、`"越方"`、`"北约"`、`"朝鲜"`）
- **禁止简化**：原文写 `"中国"` 就用 `"中国"`，禁止 LLM 改成 `"中"`
- **每个 intention 必须含**：
  - `objective`: 该方作战企图（≤50 字，引号需转义）
  - `forces`: 下属指挥单位/作战集群列表
  - 若某方无明确"作战企图"或"编成"，字段留空字符串或空数组

### 任务（missions）提取

每个 mission 必须包含以下字段（xiangding 红线 #67）：

```json
{
  "id": "M001",          // 自动编号，原文有则用原文
  "side": "中国",         // 必须从 intentions 中已有阵营名取值
  "name": "...",          // 任务名
  "type": "strike",      // strike/patrol/support/escort/...
  "area": "台海北部",     // 任务区域描述
  "unit": "055-1",       // 任务执行单位（必须能在 UNITS 中查到）
  "time": "T+30min"      // 任务开始时间
}
```

### 输出 JSON 的红线（红线 #10 实施细则）

| 错误模式 | 正确模式 |
|---------|---------|
| `"description": ' 2026年3月15日...'`（单引号未转义） | `"description": "2026年3月15日..."` |
| `"altitude": "11000"`（字符串） | `"altitude": 11000`（数字） |
| `"unit": ["红-12", 1]`（list） | `"unit": {"红-12": 1}`（dict） |
| `"unit": {"红-12": "1"}`（数量是字符串） | `"unit": {"红-12": 1}` |
| `"DDG-113 "`（末尾有空格） | `"DDG-113"` |
| `"DDG（113）"`（全角括号） | `"DDG-113"` |
| `intentions: {}` 为空对象 | `intentions: {"中国": {...}}` 必须有内容 |

> **建议**：xiangding 项目已经封装了 `scenario_parse1.py` 的 `schema_template` 提示词，配合 `lua_validator.py` 的 JSON 预校验使用。AI 在生成 main.lua 之前**必须先调用 `json.loads(parsed_situation.json)` 校验通过**。

---

## 关键规则（Critical Rules）

1. **Always use GUIDs over unit names** when possible. Names can be duplicated across sides and can be changed at runtime.
2. **Event scripts fail silently** — always check return values and wrap critical operations in `pcall`.
3. **Multi-line scripts in event actions** require `'\r\n'` for newlines, not `'\n'`.
4. `Tool_EmulateNoConsole(true)` at the top of console scripts that test event behavior.
5. **Contact GUIDs are not the same as unit GUIDs.** Use `contact.actualunitid` to get the real unit GUID from a contact.
6. **The KeyStore only accepts strings.** Use `tostring()`/`tonumber()` for numeric values.
7. **Altitude defaults to meters.** Use the `'FT'` suffix for feet: `{altitude='5000 FT'}`.
8. **Lat/Lon:** decimal `(-38.5)` or DMS string `('N38.50.00'/'W72.00.00')`.
9. **DateTime format with specifier:** `"2027-06-09 1:30:00!yyyy-MM-dd HH:mm:ss"`
10. **EMCON string format:** `'Radar=Active;Sonar=Passive;OECM=Active'`
11. `ScenEdit_AddUnit` returns a Unit wrapper — always store `.guid` immediately in the KeyStore.
12. `VP_GetSide` returns a Side wrapper — `.units` is an array of unit wrappers.
13. Wrapper properties are **live snapshots**; re-fetch the unit if you need updated values after modification.
14. `ScenEdit_SetUnit({guid=..., ...})` modifies a unit in place; `ScenEdit_UpdateUnit` is for sensors/loadouts.
15. Lua script actions in events run in a **sandboxed context** — they cannot access upvalues from outer scope; use KeyStore for cross-script state.

---

## 函数命名规范

| Prefix | Purpose |
|--------|---------|
| `ScenEdit_*` | Modify the scenario (add/set/delete/get operations) |
| `VP_*` | View-Point — read-only scenario state (`VP_GetSide`, `VP_GetUnit`, etc.) |
| `Tool_*` | Utility calculations (`Tool_Range`, `Tool_Bearing`, `Tool_LOS`, etc.) |
| `World_*` | Geographic/world data (`World_GetElevation`, etc.) |
| `UI_*` | User interface (`UI_SetCameraView`, etc.) |

---

## Units

```lua
-- Add a unit (Ship, Aircraft, Submarine, Facility, Satellite)
local unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',         -- 'Ship','Aircraft','Submarine','Facility','Satellite'
    name        = 'USS Burke',
    dbid        = 2869,           -- 必须通过 MCP 查询得到
    latitude    = 'N38.50.00',    -- 或十进制: -38.5
    longitude   = 'W72.00.00',     -- 或十进制: -72.0
    proficiency = 'Veteran'        -- 'Novice','Cadet','Regular','Veteran','Ace'
})
-- ALWAYS persist the GUID immediately
ScenEdit_SetKeyValue('BURKE_GUID', unit.guid)

-- For aircraft: LoadoutID is REQUIRED (CMO will reject without it)
-- 1. Query: read_query("SELECT ID FROM DataAircraftLoadouts WHERE ComponentID = <dbid>")
-- 2. Pick one ID from results (each ID = a different weapon loadout)
-- 3. Pass as LoadoutID below
local unit = ScenEdit_AddUnit({
    side      = '蓝方',
    type      = 'Aircraft',
    name      = 'F-16C #1',
    dbid      = 2276,           -- MCP query_dbid("F-16C")
    LoadoutID = 12345,         -- MCP read_query DataAircraftLoadouts ★ 必须
    latitude  = 35.6762,
    longitude = 139.6503,
    Base      = 'Aircraft Base Name',
    heading   = 90,
    speed     = 450,
    altitude  = 3000,
})

-- Get a unit
local u = ScenEdit_GetUnit({guid='abc-123'})              -- preferred
local u = ScenEdit_GetUnit({side='蓝方', name='Burke'})   -- fallback

-- Modify a unit
ScenEdit_SetUnit({guid='abc-123', heading=270, speed=20, altitude='5000 FT'})

-- Delete a unit
ScenEdit_DeleteUnit({guid='abc-123'})

-- Change sides
ScenEdit_SetUnitSide({guid='abc-123', side='红方'})

-- Add sensor to unit
ScenEdit_UpdateUnit({
    guid       = 'unit-guid',
    mode       = 'add_sensor',
    dbid       = 6099,
    arc_detect = {'360'},
    arc_track  = {'360'}
})
```

### type 合法值（严格区分大小写）

| type 值 | 适用单位 | 需要 LoadoutID |
|---------|---------|--------------|
| `Aircraft` | 固定翼飞机 | 必须 |
| `Ship` | 水面舰艇 | 不需要 |
| `Submarine` | 潜艇 | 不需要 |
| `Facility` | 地面设施（机场、雷达等） | 不需要 |

---

## Sides & Posture

### 阵营名规范（必须遵守）

所有 `side=` 参数**必须使用中文阵营名**，禁止使用英文阵营名：

```lua
-- ✅ 正确
side = '红方'
side = '蓝方'

-- ❌ 错误（严禁）
side = 'Red'
side = 'Blue'
side = 'red'
side = 'blue'
```

> 包括 `ScenEdit_AddSide`、`ScenEdit_GetUnit`、`ScenEdit_AddReloadsToUnit` 等所有接受 `side` 参数的 API。

### 全知全能（Omniscience）

若场景中某方需要**无限视野、所有目标自动发现**，必须使用以下 API，**不得用 EMCON 或 Doctrine 伪装**：

```lua
ScenEdit_SetSideOptions({side = '红方', awareness = 'OMNI'})
```

此调用使红方全方自动发现所有蓝方单位，无需雷达探测。

### 基本阵营操作

```lua
-- 获取阵营信息
local side = VP_GetSide({Side='红方'})
-- side.units     — 己方单位数组
-- side.contacts — 已探测接触数组
-- side.missions — 任务数组
-- side.rps      — 参考点数组

-- 创建阵营
ScenEdit_AddSide({name = '红方', color = '255,0,0'})
ScenEdit_AddSide({name = '蓝方', color = '0,0,255'})

-- 敌对关系设定
ScenEdit_SetSidePosture('红方', '蓝方', 'H')   -- 红方视蓝方为敌对
ScenEdit_SetSidePosture('蓝方', '红方', 'H')   -- 蓝方视红方为敌对

-- EMCON 控制（常规电磁管控，非全知）
ScenEdit_SetEMCON('Side', '红方', 'Radar=Passive;Sonar=Active;OECM=Passive')
ScenEdit_SetEMCON('Unit', 'unit-guid', 'Radar=Active')
```

> ⚠️ 注意：`ScenEdit_SetSideOptions(awareness='OMNI')` 和 `ScenEdit_SetEMCON` 是两个独立概念。前者控制"能发现什么"，后者控制"用什么传感器模式发现"。全知方仍可叠加 EMCON 设置。

---

## Missions

```lua
-- Create mission
local m = ScenEdit_AddMission('Blue', 'CAP Alpha', 'patrol', {type='air'})
-- Mission types: 'strike','patrol','support','ferry','mining','mineclearing','escort','cargo'
-- Strike subtypes: 'land','air','sub','naval'
-- Patrol subtypes: 'air','sub','naval','land'

-- Configure mission
ScenEdit_SetMission('Blue', 'CAP Alpha', {
    patrolzone     = {'RP-1','RP-2','RP-3','RP-4'},
    onethirdrule  = true,
    flightsize    = 2,
    minaircraftreq = 2,
})

-- Assign unit
ScenEdit_AssignUnitToMission('unit-guid', 'mission-name-or-guid')

-- Delete mission
ScenEdit_DeleteMission('Blue', 'CAP Alpha')
```

---

## §5.5 missions 字段 → STRIKE 推导规则（xiangding 实战新增）

> **核心问题**：`parsed_situation.json` 里的 `missions[]` 字段如何映射到 `attack.lua` 的 `STRIKE[]` 列表？这一节给出强制规则。

### 推导矩阵

| mission.type | 处理方式 | 是否进 STRIKE |
|-------------|---------|--------------|
| `strike` | 从 JSON 中选同名阵营火力单位 → STRIKE 一行 | ✅ |
| `strike-multi`（多目标） | 每个目标单独一行 STRIKE | ✅ |
| `patrol` | 创建 `ScenEdit_AddMission` + `ScenEdit_AssignUnitToMission` | ❌ |
| `defend` | 设置 `weapon_control_status=0`，让单位自行还击 | ❌ |
| `escort` | 同 patrol，挂载到护航任务下 | ❌ |
| `support` | 同 patrol，挂载到支援任务下 | ❌ |
| `ferry` / `cargo` / `mining` / `mineclearing` | 创建任务 + 分配单位 | ❌ |

### STRIKE 推导步骤

```python
def derive_strike(missions, units, ammo):
    strike = []
    for m in missions:
        if m.type not in ("strike", "strike-multi"):
            continue
        
        # 1. 找攻击方（必须与 JSON 同阵营、且在 AMMO 装弹清单中）
        attacker = pick_attacker(m.unit, m.side, units, ammo)
        if not attacker:
            raise ValueError(f"mission {m.id} 找不到能发射武器的攻击方")
        
        # 2. 找武器（必须已在 AMMO 清单装弹）
        weapon_dbid = ammo.get(attacker.name)
        if not weapon_dbid:
            raise ValueError(f"attack.lua 中 {attacker.name} 没装弹")
        
        # 3. 找目标
        if m.type == "strike-multi":
            targets = parse_area_centers(m.area)  # 区域中心点
            for tgt in targets:
                strike.append({
                    "attacker":    attacker.name,
                    "target":      tgt.name,
                    "weapon_dbid": weapon_dbid,
                    "quantity":    m.quantity or default_qty(weapon_dbid),
                    "startDelay":  m.delay or 0,        # ★ 字段名必须用 startDelay
                    "interval":    m.interval or 1,
                    "intent":      m.objective,        # ★ 追溯到 JSON 原始 objective
                })
        else:  # strike
            strike.append({
                "attacker":    attacker.name,
                "target":      m.target,
                "weapon_dbid": weapon_dbid,
                "quantity":    m.quantity or default_qty(weapon_dbid),
                "startDelay":  m.delay or 0,
                "interval":    m.interval or 1,
                "intent":      m.objective,
            })

    return strike
```

### STRIKE 行格式（v2.0 强制命名键，禁止位置数组）

> ⚠ 红线 #2：**禁止** `{ "055-1", "DDG-113-1", 2868, 13 }`（位置数组）。LLM 写代码时极易把字段顺序弄错，导致误用 `s[2]` 当 weapon_dbid。**统一用命名键**：

```lua
local STRIKE = {
    -- { attacker, target, weapon_dbid, quantity, startDelay, interval, intent }
    {
        attacker    = "055-1",
        target      = "DDG-113-1",
        weapon_dbid = 2868,
        quantity    = 13,                  -- 总弹数（会被真延时拆成 qty 个 scheduleOne）
        startDelay  = 0,                    -- 首发延迟（秒，相对 ScenEdit_CurrentTime）
        interval    = 1,                    -- 枚间隔（秒）
        intent      = "055 编队对 DDG-113 实施 YJ-18 反舰突击",
    },
    {
        attacker    = "052D-1",
        target      = "CVN-70",
        weapon_dbid = 2868,
        quantity    = 8,
        startDelay  = 30,
        interval    = 1,
        intent      = "052D 对 CVN-70 实施远程反舰打击，符合反介入任务",
    },
}
```

### intent 字段的作用

`intent` 字段是 **JSON 任务到 Lua 代码的可追溯性锚点**，作用：

1. **代码审查时**，一眼看出每行 STRIKE 对应 JSON 哪个 mission
2. **弹药预算溢出时**，知道该删哪个 mission 的 STRIKE
3. **执行日志中**，每枚弹发射时可以打印 intent，便于复盘

### field 访问规范（红线 #2 实施细则）

| 推荐（命名键） | ❌ 禁止（位置） | 风险 |
|------|------|------|
| `s.attacker` | `s[1]` | LLM 加列后位置全错 |
| `s.quantity` | `s[4]` | 同上 |
| `s.weapon_dbid` | `s[3]` | 同上 |
| `s.intent` | `s[7]` | 没有第 7 位会被 nil |

> LLM 生成 STRIKE 时应**始终**用命名键；生成代码审阅时**发现 s[N] 必须打回重写**。

### 默认数量规则

| 武器 DBID | 武器名 | 默认 quantity |
|----------|--------|-------------|
| 2868 | YJ-18 | 8 |
| 2865 | YJ-12 | 4 |
| 2787 | CJ-10 | 4 |
| 2862 | YJ-83 | 8 |

> 若 JSON 中 `mission.quantity` 未指定，使用上表默认值；若指定但超过 AMMO 装弹量，必须在生成阶段就报错（不进入 STRIKE）。

---

## Doctrine

```lua
-- Set doctrine for a side
ScenEdit_SetDoctrine({side='红方'}, {
    weapon_control_status_air        = 0,  -- WCS: Free=0, Tight=1, Hold=2
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 1,
    ignore_plotted_course            = 'no',
    use_nuclear_weapons             = 'no',
})

-- Set for a specific unit (overrides side doctrine)
ScenEdit_SetDoctrine({guid='unit-guid'}, {
    weapon_control_status_air = 2,  -- Hold for this unit
})
```

---

## Weapon Reloads (装弹)

### Add a weapon to a unit

```lua
-- 为舰艇/潜艇添加待发弹（DBID 必须通过 MCP 查询）
ScenEdit_AddReloadsToUnit({
    side     = '红方',           -- 阵营名
    unitname = 'DDG-123',       -- 单元名（与 side 二选一，不可同时省略）
    wpn_dbid = 2868,            -- 武器 DBID（MCP 查询）
    number   = 8,               -- 添加数量（最多不超过该武器在 VLS 中的格子数）
    mount_guid = 'xxx',         -- 可选：指定挂载位 GUID（不填则自动分配）
})
-- 返回: true 成功 / false 失败（超出格子数也不会报错，实际弹数可能少于请求数）
```

### Remove (clear) weapons from a unit

CMO 没有"删除弹种"的直接 API。正确做法是用 `AddReloadsToUnit + remove=true` **减少数量到 0**（保留挂载格子）。

> **严禁用 remove_weapon 删记录**——那会把格子也删掉，导致后续 `AddReloadsToUnit` 找不到兼容 mount，弹装不回去。

```lua
-- 原理：传入当前数量 + remove=true，等价于清空该弹种
ScenEdit_AddReloadsToUnit({
    guid       = unit_guid,
    wpn_dbid   = 2868,
    mount_guid = mount_guid,
    number     = 8,
    remove     = true,
})
```

### Full reload pattern: clear → reload → verify

适用场景：主脚本已创建单元，需更新装弹方案时执行本段。

```lua
-- ============================================================
-- 完整装弹流程：先清空所有待发弹 → 再装填新弹 → 自检
-- 注意：不能用 remove_weapon 删记录——那会把格子也删掉，导致后续
--       AddReloadsToUnit 找不到兼容 mount，弹装不回去。
--       这里用 AddReloadsToUnit + remove=true 仅扣减数量，格子保留。
-- ============================================================

-- ---------- 日志工具函数 ----------
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 清空：遍历 mounts，批量 remove ----------
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("clearUnitWeapons: 找不到 " .. side .. "/" .. name)
        return false
    end
    -- 快照所有 mount 中 cur>0 的武器（边减边遍历原表不安全）
    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs + 1] = {
                    dbid = w.wpn_dbid, num = cur, mountid = m.mount_guid,
                }
            end
        end
    end
    -- 逐条把数量减到 0（保留记录）
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({
            guid = u.guid, wpn_dbid = j.dbid,
            mount_guid = j.mountid, number = j.num, remove = true,
        })
        if (_errnum_ or 0) == 0 then done = done + 1
        else fail = fail + 1 end
    end
    ok(("%s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
end

-- ---------- 装弹后自检 ----------
local function dumpAmmo(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u then return end
    local total = 0
    for i, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then
                info(("  MOUNT %d dbid=%s cur=%d"):format(i, tostring(w.wpn_dbid), c))
                total = total + c
            end
        end
    end
    ok(name .. " 待发弹合计 = " .. total)
end

-- ---------- 配置区 ----------
local SIDE_RED = "红方"

-- 1) 要清空的舰（必须与 main.lua 创建时完全一致）
local CLEAR_LIST = { "<攻击方单位名-A>", "<攻击方单位名-B>", ... }

-- 2) 装弹清单（unitname 必须与 main.lua 创建时完全一致）
local AMMO = {
    { unitname = "<攻击方单位名-A>", wpn_dbid = <武器DBID>, number = <数量> },  -- <武器名>
    { unitname = "<攻击方单位名-B>", wpn_dbid = <武器DBID>, number = <数量> },  -- <武器名>
    ...
}

-- ---------- 执行：先清空 ----------
info("=== 清空待发弹 ===")
for _, name in ipairs(CLEAR_LIST) do clearUnitWeapons(SIDE_RED, name) end

-- ---------- 执行：再装弹 ----------
info("=== 装弹 ===")
for _, a in ipairs(AMMO) do
    local ok2 = pcall(function() ScenEdit_AddReloadsToUnit({
        side = SIDE_RED, unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, number = a.number,
    }) end)
    if ok2 then
        ok("+ " .. a.number .. "x [" .. a.wpn_dbid .. "] → " .. a.unitname)
    else
        warn("弹药补给失败: " .. a.unitname .. " (dbid=" .. a.wpn_dbid .. ")")
    end
end

-- ---------- 执行：装弹后自检 ----------
info("=== 装弹自检 ===")
for _, name in ipairs(CLEAR_LIST) do dumpAmmo(SIDE_RED, name) end
```

**注意事项：**

- `ScenEdit_AddReloadsToUnit` 在事件脚本的沙箱环境中可能**静默失败**（不抛异常），必须用 `pcall` 包装并检查返回值
- 装弹上限由该武器在舰艇 Loadout 中的 VLS 格口数决定，超出不会报错但实际装填数量会截断
- `mount_guid` 不填时 API 自动分配；指定 `mount_guid` 可精确控制弹药填入哪个 VLS 格口
- **严禁硬编码武器 DBID**——必须通过 MCP `query_dbid()` 查询
- **严禁用 `remove_weapon` 删格子**——必须用 `remove=true` 扣数量

---

## 真延时打击（TOT 事件驱动）

> **核心原则**：CMO 没有"延迟发射 N 枚"的单一 API。要实现 TOT（Time On Target）齐射，必须把 `qty=N` 拆成 N 个独立的 `Time Trigger + LuaScript Action`，每个触发器在仿真时间推进到指定时刻时，调用 `fireAt(..., qty=1)` 发射 1 枚。

### 同步 for 循环 ≠ 真延时（常见错误）

```lua
-- ❌ 假延时：脚本跑完即发射，没有 TOT 间隔；暂停游戏时也会立即打出
for _, s in ipairs(STRIKE) do
    fireAt(s[1], s[2], s[3], s[4])   -- qty=N 一次性塞给 CMO
end
```

**为什么是假延时：**
- 脚本执行瞬间全部弹射出去，无"首发延迟"
- 没有"逐枚 1 秒间隔"，无法做 TOT 同时到达
- `contact_settle_delay` 只是 print，没有真正等待
- 暂停游戏时仍能发射（违背实战）

**真延时的 3 个关键点：**

| 要素 | 实现方式 |
|------|---------|
| 时间基准 | `ScenEdit_CurrentTime() + 偏移秒数` → 转 .NET ticks |
| 逐枚调度 | `qty=N` 拆成 N 个 `qty=1`，每个独立 Time 触发器 |
| contact 稳定 | `delay += contact_settle_delay`（≥15 秒） |

### 1. 时间基准换算（仿真秒 → CMO Ticks）

CMO 事件触发器的 `Time` 字段需要 .NET `DateTime.Ticks`（100ns 单位，自 0001-01-01 起）。

```lua
local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()      -- Unix 秒（自 1970-01-01）
    local offSet = 62135596801            -- 0001-01-01 到 1970-01-01 的秒数
    return string.format("%.0f", (t + offSet + addSeconds) * 1e7)
end
```

### 2. 逐枚调度：每枚导弹一个独立触发器

```lua
local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    -- contact_settle_delay 必须叠加到每枚弹的延迟上
    delay = delay + CONTACT_SETTLE_DELAY

    local evName = "Event " .. tag
    local trName = "Trig "  .. tag
    local acName = "Act "   .. tag
    local fireTime = totTicks(delay)

    -- 关键：Lua 脚本内容必须是完整自含的（沙箱执行，不能引用外部 upvalue）
    local script =
        ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)

    _errnum_ = 0
    pcall(function() ScenEdit_SetTrigger({mode="add", type="Time", name=trName, Time=fireTime}) end)
    pcall(function() ScenEdit_SetAction({mode="add", type="LuaScript", name=acName, ScriptText=script}) end)
    pcall(function() ScenEdit_SetEvent(evName, {mode="add", IsActive=true, IsRepeatable=false}) end)
    pcall(function() ScenEdit_SetEventTrigger(evName, {mode="add", name=trName}) end)
    pcall(function() ScenEdit_SetEventAction(evName, {mode="add", name=acName}) end)
end
```

### 3. 齐射循环：TOT 同时到达公式

```lua
for i, s in ipairs(STRIKE) do
    local atkName, tgtName, wpn, qty, startDelay, interval =
        s[1], s[2], s[3], s[4], s[5] or 0, s[6] or 1
    for k = 1, qty do
        local delay = startDelay + (k - 1) * interval
        local tag = "TOT_" .. i .. "_" .. k
        scheduleOne(atkName, tgtName, wpn, delay, tag)
    end
end
```

**典型 TOT 配置示例：**

| 场景 | startDelay | interval | qty | 含义 |
|------|------------|----------|-----|------|
| 同时到达 | 60 | 1 | 16 | 60 秒后首发，每枚间隔 1 秒（弹飞行时间 ≈ 1 分钟差） |
| 急促齐射 | 0 | 0.5 | 8 | 立即开始，每枚间隔 0.5 秒 |
| 波次打击 | 0, 120, 240 | 1 | 16 | 3 波齐射，每波 16 枚，每波间隔 120 秒 |

### 4. contact 等待（contact_settle_delay）

CMO 的 contact 列表刷新有滞后。即使红方设为 OMNI、目标设了 autodetectable，contact 也要等若干仿真秒才稳定出现。

```lua
local CONTACT_SETTLE_DELAY = 15  -- 必须 >= 15 秒，5 秒通常不够

-- 在 scheduleOne 内部必须叠加
delay = delay + CONTACT_SETTLE_DELAY
```

**contact 等待的两种实现：**

#### 方案 A：在每枚弹的 delay 里直接加（推荐）

```lua
-- 每枚弹的真实触发时间 = 任务延迟 + 15 秒 contact 稳定期
local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    delay = delay + CONTACT_SETTLE_DELAY   -- 直接叠加
    -- ...
end
```

#### 方案 B：递归事件等待 contact 出现后再调度

适用于首枚弹就需要 contact 才能打的场景：

```lua
local function waitForContactThenSchedule(retryLeft)
    if retryLeft == nil then retryLeft = 12 end

    local first = STRIKE[1]
    local tgt = ScenEdit_GetUnit({side = "蓝方", name = first[2]})
    if not (tgt and tgt.guid) then return false end

    local contactGuid
    local ok2, s2 = pcall(VP_GetSide, {Side="红方"})
    if ok2 and s2 and type(s2.contacts)=="table" then
        local tg = tostring(tgt.guid):lower()
        for _, c in ipairs(s2.contacts) do
            local aid = c.actualunitid or c.actualUnitID or c.actualunitguid
            if aid and tostring(aid):lower()==tg then contactGuid=c.guid; break end
        end
        if not contactGuid then
            for _, c in ipairs(s2.contacts) do
                local nm = tostring(c.name or "")
                if nm~="" and (nm==first[2] or nm:find(first[2],1,true)) then contactGuid=c.guid; break end
            end
        end
    end
    if contactGuid then
        scheduleSalvo()  -- 已有 contact，立即调度齐射
        return true
    end

    if retryLeft > 0 then
        -- 5 秒后再尝试（递归调用）
        scheduleContactWait(retryLeft - 1)
        return true
    end
    return false
end
```

### 5. fireAt 函数必须是全局函数

事件脚本运行在**沙箱环境**，无法访问外部作用域的局部变量。

```lua
-- ❌ 错误：local，事件脚本无法调用
local function fireAt(...)
    ...
end

-- ✅ 正确：全局函数
function fireAt(attackerName, targetName, wpnDbid, qty)
    ...
end

-- ✅ 配置变量也必须提升为全局
_SIDE_RED = "红方"
_SIDE_BLUE = "蓝方"
_CONTACT_SETTLE_DELAY = 15
```

### 6. 完整真延时模板

```lua
-- ============================================================
-- 真延时打击脚本（事件驱动 TOT 齐射）
-- ============================================================

-- 全局变量（供事件沙箱访问）
_SIDE_RED = "红方"
_SIDE_BLUE = "蓝方"
_CONTACT_SETTLE_DELAY = 15
_CONTACT_RETRY_DELAY = 5
_CONTACT_RETRY_COUNT = 12
_ALLOW_BOL_FALLBACK = false
_CONTACT_CACHE = {}

-- ★★★ STRIKE 命名键访问（红线 #2：禁止位置数组）★★★
local STRIKE = {
    { attacker="055-Nanchang", target="DDG-113",  weapon_dbid=2868, quantity=13, startDelay=0,  interval=1, intent="055对DDG-113反舰突击" },  -- YJ-18 立即开打，每枚 1 秒
    { attacker="052D-1",       target="CVN-70",   weapon_dbid=2868, quantity=8,  startDelay=0,  interval=1, intent="052D对CVN-70反舰突击" },
    { attacker="052D-2",       target="CG-59",    weapon_dbid=2868, quantity=5,  startDelay=30, interval=1, intent="052D-2对CG-59反舰突击" },  -- 30 秒后开打
}

-- ... fireAt（含 VP_GetSide contact 查找，必须为全局） ...

-- ============================================================
-- TOT 调度
-- ============================================================

local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    local offSet = 62135596801
    return string.format("%.0f", (t + offSet + addSeconds) * 1e7)
end

local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    delay = delay + _CONTACT_SETTLE_DELAY
    -- ★★★ tag 必须带时间戳（红线 #11 幂等性），避免重跑时 Event 已存在报错
    tag = tag .. "_" .. tostring(ScenEdit_CurrentTime())
    local evName = "Event " .. tag
    local trName = "Trig "  .. tag
    local acName = "Act "   .. tag
    local fireTime = totTicks(delay)
    local script =
        ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    pcall(function() ScenEdit_SetTrigger({mode="add", type="Time", name=trName, Time=fireTime}) end)
    pcall(function() ScenEdit_SetAction({mode="add", type="LuaScript", name=acName, ScriptText=script}) end)
    pcall(function() ScenEdit_SetEvent(evName, {mode="add", IsActive=true, IsRepeatable=false}) end)
    pcall(function() ScenEdit_SetEventTrigger(evName, {mode="add", name=trName}) end)
    pcall(function() ScenEdit_SetEventAction(evName, {mode="add", name=acName}) end)
end

-- ★★★ STRIKE 命名键访问（红线 #2：禁止 s[N] 位置访问）★★★
function scheduleSalvo()
    for i, s in ipairs(STRIKE) do
        -- ★★★ 命名键解包（红线 #2），不允许 s[1]/s[4] ★★★
        local atkName   = s.attacker
        local tgtName   = s.target
        local wpn       = s.weapon_dbid
        local qty       = s.quantity or 1
        local startDelay= s.startDelay or 0
        local interval  = s.interval or 1
        local intent    = s.intent or ""

        if not atkName or not tgtName or not wpn then
            warn(("STRIKE[%d] 字段缺失（attacker/target/weapon_dbid 必填）"):format(i))
            goto continue
        end

        -- ★★★ qty=N 拆成 N 个 qty=1 的独立触发器（红线 #9）★★★
        for k = 1, qty do
            local delay = startDelay + (k - 1) * interval
            local tag = ("TOT_%d_%d_%s"):format(i, k, intent:gsub("%s+", "_"):sub(1, 30))
            scheduleOne(atkName, tgtName, wpn, delay, tag)
        end
        ::continue::
    end
end

-- 入口
scheduleSalvo()
print("[CMO] 真延时齐射已调度（" .. _CONTACT_SETTLE_DELAY .. " 秒 contact 稳定后开始发射）")
```

### 7. 真延时 vs 假延时对比表

| 维度 | 假延时（同步 for） | 真延时（事件触发器） |
|------|-------------------|---------------------|
| 发射时机 | 脚本跑完即弹 | 仿真时间推进到指定时刻 |
| 首发延迟 | 0 | `startDelay + contact_settle_delay` |
| 枚间隔 | 0（`qty=N` 一次发完） | `interval` 秒（每枚独立触发器） |
| TOT 同时到达 | ❌ | ✅ |
| 暂停游戏时 | 仍发射 | 不发射（依赖时间推进） |
| contact 等待 | 无 | `+15s` 稳定期 |
| 失败重试 | 同步一次查找 | 递归事件，每 5 秒重试，最多 12 次 |
| 副作用 | 无 | 创建大量 Event/Trigger/Action（需清理） |

### 8. 自审清单（真延时专章）

- [ ] **是否使用 `ScenEdit_SetTrigger` 注册了 Time 触发器**（非仅同步 for 循环）
- [ ] **`qty=N` 是否拆成 N 个 `qty=1` 的独立触发器**
- [ ] **每枚弹的 `delay` 是否叠加了 `contact_settle_delay`（≥15 秒）**
- [ ] **`fireAt` 函数是否为全局函数**（不带 `local`）
- [ ] **配置变量是否提升为全局**（`_SIDE_RED`、`_CONTACT_SETTLE_DELAY` 等）
- [ ] **TOT 时间转换是否使用 `totTicks` 公式**（Unix 秒 → .NET ticks）
- [ ] **每个触发器是否包含自我清理代码**（`ScenEdit_SetEvent/Action/Trigger {mode='remove'}`）
- [ ] **多波齐射场景下，每波的 startDelay 是否错开**

---

## Strike / Attack (打击)

### Complete workflow: Manifest → MCP → Clear → Reload → Strike

生成 CMO Lua 打击脚本的标准流程：

```
① 制定打击清单  →  ② MCP 查询武器 DBID  →  ③ 获取目标位置/方位角  →  ④ 清空待发弹  →  ⑤ 重新装弹  →  ⑥ 下达打击指令
   manifest.lua        query_dbid()               VP_GetSide /              clearUnitWeapons()    ScenEdit_AddReloadsToUnit()   ScenEdit_AttackContact()
                                                    ScenEdit_GetUnit
                                                    .latitude / .longitude
                                                    .heading / .speed
```

| 步骤 | 做什么 | 核心 API |
|------|--------|---------|
| ① | 制定打击清单 | `manifest.lua` — SCENARIO/UNITS/WEAPONS/CLEAR_LIST/AMMO/STRIKE |
| ② | 武器 DBID（MCP） | `query_dbid("YJ-21")` |
| ③ | 目标位置/方位角/航向 | `ScenEdit_GetUnit({name})` → `.latitude` `.longitude` `.heading` `.speed` |
| ③ | 清空现有待发弹 | `clearUnitWeapons(side, name)` — 见 Weapon Reloads 章节 |
| ④ | 重新装填弹药 | `ScenEdit_AddReloadsToUnit(...)` — 见 Weapon Reloads 章节 |
| ⑤ | 下达打击指令 | `ScenEdit_AttackContact(...)` — 见下方模板 |

### Overview

CMO 的打击分为两种模式：

- **contact 攻击**：红方全知或已探测到目标 → 精确跟踪发射，可中途修正
- **BOL 攻击**（Bearing Only Launch）：未探测到目标 → 朝目标坐标发射，不跟踪

完整流程：先在 contact 列表中查找目标 GUID → 命中则用 `ScenEdit_AttackContact(atkGuid, contactGuid, ...)` → 找不到则降级为 BOL

### ⚠️ autodetectable 是 contact 攻击的前置条件

**即使红方设为 `awareness = "OMNI"`，如果蓝方单位没有 `autodetectable = true`，红方也无法获得可攻击的 contact。**

这是导致"完全不发射"或"导弹脱靶"最常见的原因。

**必须在三个时间点都设置 autodetectable：**

| 时机 | 代码 | 说明 |
|------|------|------|
| 创建蓝方单位时 | `ScenEdit_AddUnit({..., autodetectable = true})` | 初次创建 |
| 创建后遍历设 | `ScenEdit_SetUnit({guid = ..., autodetectable = true})` | 双保险 |
| 每次发射前 | `ScenEdit_SetUnit({guid = tgt.guid, autodetectable = true})` | 延迟发射前再次确认 |

```lua
-- ① 创建时设 autodetectable
ScenEdit_AddUnit({
    side = "蓝方", name = "DDG-113", dbid = 4299,
    autodetectable = true,  -- 关键
    ...
})

-- ② 创建后强制确认（双保险，尤其 overwrite_existing=false 时）
local u = ScenEdit_GetUnit({side="蓝方", name="DDG-113"})
if u and u.guid then
    pcall(function() ScenEdit_SetUnit({guid = u.guid, autodetectable = true}) end)
end

-- ③ 每次 fireAt 发射前再次设（延迟发射的触发器需要）
pcall(function() ScenEdit_SetUnit({guid = tgt.guid, autodetectable = true}) end)
```

**为什么 BOL 不适合打击移动目标？** BOL 发射后导弹朝发射时的坐标飞行，不跟踪目标坐标。如果蓝方舰艇在移动，导弹会打在空水域。因此对移动舰艇，应使用 contact 攻击，并设置 `allow_bol_fallback = false`。

```lua
ScenEdit_AttackContact(attackerGuid, targetGuidOrBOL, {
    latitude  = lat,     -- BOL 模式必须填写
    longitude = lon,     -- BOL 模式必须填写
    mode      = 1,        -- 1=精确打击；0=区域压制
    weapon    = wpnDbid,  -- 武器 DBID（必须 MCP 查询）
    qty       = n,        -- 发射数量
})
```

### Full strike pattern (通用打击模板)

适用场景：红方全知 / BOL 兜底均可

```lua
-- ============================================================
-- 通用打击脚本：autodetectable → contact → 打击
-- 使用方式：修改 CFG 区后直接在 CMO Lua 控制台运行
-- ============================================================

local CFG_SIDE_RED  = "红方"
local CFG_SIDE_BLUE = "蓝方"
local CFG_BLUE_AUTODETECTABLE = true   -- 必须为 true，红方才能稳定获得 contact
local CFG_ALLOW_UNIT_GUID     = true   -- OMNI 模式下允许直接用单位 GUID 攻击
local CFG_CONTACT_SETTLE_DELAY = 15    -- 必须 >= 15 秒，等待 contact 稳定刷新
local CFG_ALLOW_BOL_FALLBACK   = true   -- 兜底，防止无 contact 时完全不发射

local STRIKE = {
    -- { 攻击方单位名（与 main.lua 创建时一致）, 目标单位名, 武器DBID, 数量 },
}

local LOG = "[CMO]"

-- ---------- 工具函数 ----------
local function sameGuid(a, b)
    return a and b and tostring(a):lower() == tostring(b):lower()
end

local function forceBlueAutodetectable(name)
    local u = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = name})
    if not (u and u.guid) then return false end
    return pcall(function() ScenEdit_SetUnit({guid = u.guid, autodetectable = true}) end)
end

-- 收集红方 contact（★ 简洁写法：VP_GetSide().contacts）
local function getContacts()
    local out = {}
    local ok, s = pcall(VP_GetSide, {Side = "红方"})
    if ok and s and type(s.contacts) == "table" then
        for _, c in ipairs(s.contacts) do
            out[#out + 1] = c
        end
    end
    return out
end

-- ---------- 全局打击函数（供事件脚本调用） ----------
-- ★ fireAt 必须是全局（红线 #15）
-- 1) 蓝方 autodetectable=true  2) 红方 OMNI  3) 用 VP_GetSide().contacts
-- 4) 用【真延时触发器】把发射安排到未来，让游戏推进后再执行
--    （脚本只"预约"，玩家按播放让时间流逝，到点 contact 已生成）
function fireAt(atkName, tgtName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side="红方", name=atkName})
    local tgt = ScenEdit_GetUnit({side="蓝方", name=tgtName})
    pcall(function() ScenEdit_SetUnit({guid=tgt.guid, autodetectable=true}) end)
    pcall(function() ScenEdit_SetSideOptions({side="红方", awareness="OMNI"}) end)

    local contactGuid
    local ok, s = pcall(VP_GetSide, {Side="红方"})       -- ★ 不用 GetContacts
    if ok and s and type(s.contacts)=="table" then
        local tg = tostring(tgt.guid):lower()
        for _, c in ipairs(s.contacts) do                -- 先按 actualunitid 匹配
            local aid = c.actualunitid or c.actualUnitID or c.actualunitguid
            if aid and tostring(aid):lower()==tg then contactGuid=c.guid; break end
        end
        if not contactGuid then                          -- 再按名称匹配
            for _, c in ipairs(s.contacts) do
                local nm = tostring(c.name or "")
                if nm~="" and (nm==tgtName or nm:find(tgtName,1,true)) then contactGuid=c.guid; break end
            end
        end
    end
    if not contactGuid then print("无 contact，加大延迟或多推进游戏"); return false end

    _errnum_=0
    return ScenEdit_AttackContact(atk.guid, contactGuid, {mode="1", weapon=wpnDbid, qty=qty}) and true or false
end

print(LOG .. " === 下达打击指令 ===")
for _, s in ipairs(STRIKE) do fireAt(s[1], s[2], s[3], s[4]) end
print(LOG .. " === 打击指令下达完毕 ===")
```

**关键修复点（务必照抄）：**

1. **contact 获取用 `VP_GetSide().contacts`**：`pcall(VP_GetSide, {Side="红方"})` 直接拿 contact 列表，不需要 `ScenEdit_GetContacts` 也不需要递归遍历

2. **mode 参数用字符串**：`mode = "1"` 而非 `mode = 1`（数字类型可能失败）

3. **GUID 字段全匹配**：检查 `actual_guid`, `actualGuid` 等所有可能的字段名

4. **UNIT_GUID 后备**：`CFG_ALLOW_UNIT_GUID = true`，contact 找不到时直接用单位 GUID 攻击

5. **contact 稳定等待**：TOT 场景必须设置 `CFG_CONTACT_SETTLE_DELAY = 15`，5 秒通常不够

6. **fireAt 重试机制**：每次发射前重试 3 次，每次间隔 2 秒

7. **三个 autodetectable 时间点**：
   - 创建蓝方单位时 `autodetectable = true`
   - 创建后遍历所有蓝方单位 `ScenEdit_SetUnit(..., autodetectable = true)`
   - 每次 `fireAt` 发射前 `pcall(function() ScenEdit_SetUnit({guid = tgt.guid, autodetectable = true}) end)`

**注意事项：**

- `ScenEdit_GetContacts` 返回 contact 列表，contact 的 `.guid` 与 unit 的 `.guid` **不同**，必须用 `c.actualunitid == tgt.guid` 匹配
- BOL 模式发射后武器不会跟踪目标坐标，需确认目标基本静止或等待其进入武器导引头搜索范围
- `weapon = wpnDbid` 传入数值 DBID；若留空或不传，API 可能自动选择射程最近的武器（结果不确定）
- `mode = 1` 为精确打击；`mode = 0` 为区域压制（对目标群有效）
- **严禁硬编码武器 DBID**——必须通过 MCP `query_dbid()` 查询

---

## Reference Points (zones)

```lua
ScenEdit_AddReferencePoint({
    side        = '蓝方',
    name        = 'RP-1',
    latitude    = 38.5,
    longitude   = -72.0,
    highlighted = false
})

ScenEdit_DeleteReferencePoint({side='蓝方', name='RP-1'})
```

---

## Event System (TCA Pattern)

The event system uses **Triggers -> Conditions -> Actions** chains.

```lua
-- Add event
local ev = ScenEdit_SetEvent('MyEvent', {
    mode         = 'add',
    IsRepeatable = true,
    IsActive     = true,
})

-- Add trigger (fire on scenario load)
ScenEdit_SetTrigger({mode='add', type='ScenLoaded', name='OnLoad'})
ScenEdit_SetEventTrigger(ev.guid, {mode='add', name='OnLoad'})

-- Add timed trigger (offset from now)
ScenEdit_SetTrigger({mode='add', type='Time', name='T+60min',
    time = ScenEdit_CurrentTime() + 3600})
ScenEdit_SetEventTrigger(ev.guid, {mode='add', name='T+60min'})

-- Add repeating trigger (every N seconds)
ScenEdit_SetTrigger({mode='add', type='RegularTime', name='Every5min', interval=300})
ScenEdit_SetEventTrigger(ev.guid, {mode='add', name='Every5min'})

-- Add Lua script action
ScenEdit_SetAction({mode='add', type='LuaScript', name='DoStuff',
    ScriptText = 'ScenEdit_SpecialMessage("Blue","Hello")'})
ScenEdit_SetEventAction(ev.guid, {mode='add', name='DoStuff'})

-- Context variables inside event scripts (always nil-check)
local unit    = ScenEdit_UnitX()   -- the triggering unit (e.g., destroyed unit)
local unitY   = ScenEdit_UnitY()   -- the "other" unit (e.g., the detector)
local contact = ScenEdit_UnitC()   -- contact wrapper in detection events
```

---

## Persistent State (KeyStore)

```lua
-- Store (KeyStore only accepts strings!)
ScenEdit_SetKeyValue('phase', '2')
ScenEdit_SetKeyValue('carrier_guid', unit.guid)
ScenEdit_SetKeyValue('counter', tostring(count + 1))

-- Retrieve
local phase = ScenEdit_GetKeyValue('phase')     -- returns '' if not set
local count = tonumber(ScenEdit_GetKeyValue('counter')) or 0
```

---

## Scoring & Messages

```lua
ScenEdit_SetScore('Blue', 100, 'Target destroyed')
local score = ScenEdit_GetScore('Blue')
ScenEdit_SpecialMessage('Blue', 'Intel update: enemy carrier located')
ScenEdit_EndScenario()   -- end scenario when win condition met
```

---

## Utility Functions

```lua
-- Distance in nautical miles
local nm = Tool_Range({latitude=lat1, longitude=lon1}, {latitude=lat2, longitude=lon2})

-- Bearing in degrees
local deg = Tool_Bearing({latitude=lat1, longitude=lon1}, {latitude=lat2, longitude=lon2})

-- Line of sight check
local los = Tool_LOS({latitude=lat1, longitude=lon1}, {latitude=lat2, longitude=lon2})

-- Current scenario time (Unix timestamp)
local t = ScenEdit_CurrentTime()

-- Elevation at a point (meters)
local elev = World_GetElevation({latitude=lat, longitude=lon})
```

---

## Key Wrapper Properties

**Unit:**
`.guid` `.name` `.side` `.type` `.latitude` `.longitude` `.altitude` `.heading` `.speed` `.fuel` `.damage` `.magazines` `.mounts` `.sensors` `.doctrine` `.mission` `.base` `.group` `.course` `.proficiency`

**Side:**
`.guid` `.name` `.units` `.contacts` `.missions` `.doctrine` `.rps` `.losses` `.expenditures`

**Mission:**
`.guid` `.name` `.side` `.type` `.isactive` `.unitlist` `.targetlist` `.doctrine`

**Contact:**
`.guid` `.name` `.latitude` `.longitude` `.altitude` `.heading` `.speed` `.type` `.classificationlevel` `.actualunitid` `.detectionBy` `.BDA`

---

## 错误处理模式

```lua
-- Basic pcall wrapping
local ok, result = pcall(function() return ScenEdit_AddUnit({...}) end)
if not ok then
    print("Error: " .. tostring(result))
    ScenEdit_SpecialMessage('Blue', 'Script error — check console')
    return
end

-- Safe unit lookup
local function getUnit(guid)
    local ok, u = pcall(function() return ScenEdit_GetUnit({guid=guid}) end)
    return (ok and u) or nil
end

-- Iterate side units safely
local ok, side = pcall(VP_GetSide, {Side='Blue'})
if ok and side then
    for _, u in ipairs(side.units or {}) do
        -- process u
    end
end
```

---

## 常见陷阱

| Pitfall | Correct Approach |
|---------|-----------------|
| `ScenEdit_GetUnit` raises an error if unit not found | Wrap in `pcall` or check return value |
| Using unit names across sides | Use GUIDs — names are not unique |
| `VP_GetSide().units` may be empty | Check `#side.units > 0` before iterating |
| `ScenEdit_SetMission` with `patrolzone` overwrites the entire zone | Always supply all RPs in the array |
| Timed triggers fire at scenario time, not real time | Use `ScenEdit_CurrentTime() + offset` |
| `loadoutid` missing for aircraft | Spawns with no weapons; always specify |
| KeyStore value is a string | Always `tonumber()` when expecting a number |
| Contact GUID used where unit GUID expected | Use `contact.actualunitid` |
| Event script tries to use module-level variable | Use KeyStore; event scripts are sandboxed |

---

## 代码风格

- Use `local` for all variables inside functions
- Name constants in UPPER_SNAKE_CASE: `local MAX_UNITS = 10`
- Use EmmyLua/LuaLS annotations: `--- @param name type description`
- Nil-check all unit/side/mission lookups before use
- Store GUIDs in KeyStore immediately after `ScenEdit_AddUnit`
- Group related code with `-- ===` section comments
- Use `ScenEdit_SpecialMessage` for player-visible feedback, `print` for debug only
- Prefix event handler functions with `on_`: `local function on_carrier_destroyed()`

---

## 常见错误速查

生成代码前必须检查：`errors/index.md`

| 错误信息 | 最常见原因 |
|---------|----------|
| `Missing 'LoadoutID'` | Aircraft 未填 LoadoutID，或参数名拼错（`loadoutid`） |
| `The requested object has been deprecated` | DBID 不存在——必须用 MCP 重新查询 |
| `Invalid unit type 'xxx'` | type 拼写错误（如 `Air`、`Ground`、`ship`） |
| `Invalid latitude/longitude value` | 参数名拼错，或值超出范围（纬度 +-90 / 经度 +-180） |
| `side 'xxx' does not exist` | 阵营未创建，或名称大小写不一致 |
| `No points have been set` (Tool_Range) | `Tool_Range` 必须传 `{latitude, longitude}` 表格，不能直接传 unit 对象 |
| 导弹完全不发射 / 无 contact | 蓝方单位没有 `autodetectable = true`——即使红方设为 OMNI 也看不到；必须创建时设 + 创建后遍历设 + 发射前再设 |
| contact 找到了但导弹脱靶 | 用了 BOL 而非 contact 攻击；移动目标不能 BOL |
| contact 获取数量为 0 | 没用 `VP_GetSide({Side="红方"}).contacts`；直接用 `pcall(VP_GetSide, {Side="红方"})` |
| `_errmsg_: Invalid GUID` | 用了 `tgt.guid` 而不是 contact.guid | 在 `fireAt` 里通过 `actualunitid` 匹配拿到 `contactGuid` 后再攻击 |
| `attempt to index a nil value` | `pcall(ScenEdit_XXX, args)` 直接包函数引用——CMO 的 `ScenEdit_*` 是 userdata，不是 Lua function，**必须**用 `pcall(function() ScenEdit_XXX(args) end)` |

### attack.lua 常见错误（多脚本协同必读）

#### 1. 单位名称不一致（最常见错误）

`attack.lua` 中的单位名称必须与 `main.lua` 创建时的 `name=` **完全一致**，包括大小写、前缀、后缀。

```lua
-- main.lua 中创建的单位
ScenEdit_AddUnit({ side = "蓝方", name = "DDG 113", dbid = 4299, ... })

-- attack.lua  ✓ 正确
local STRIKE = { { "055-Nanchang", "DDG 113", 2868, 13 } }

-- attack.lua  ✗ 错误（擅自加了连字符和后缀，与 main.lua 不一致）
local STRIKE = { { "055-Nanchang", "DDG-113-JohnFinn", 2868, 13 } }
```

**自审检查：** 对比 `attack.lua` 的 `STRIKE`/`CLEAR_LIST`/`AMMO` 中的每个单位名，与 `main.lua` 的 `ScenEdit_AddUnit({name="..."})` 是否完全一致。

#### 2. `fireAt` 函数必须是全局函数

事件脚本（TOT 定时触发器中的 Lua 脚本）运行在**沙箱环境**中，无法访问外部作用域的局部变量。

```lua
-- ✗ 错误：局部函数，事件脚本无法调用
local function fireAt(attackerName, targetName, wpnDbid, qty)
    ...
end

-- ✓ 正确：全局函数，事件脚本可以调用
function fireAt(attackerName, targetName, wpnDbid, qty)
    ...
end
```

**解决方案：** 如果事件脚本需要调用 `fireAt`，必须：
1. 将 `fireAt` 定义为全局函数（不加 `local`）
2. 将配置变量也提升为全局变量（`_SIDE_RED = "红方"`）

#### 3. contact 获取（★ 简洁写法：VP_GetSide().contacts）

**原理：** 用 `VP_GetSide({Side="红方"}).contacts` 直接拿 contact 列表，不需要 `ScenEdit_GetContacts`，也不需要递归遍历。

```lua
-- ✗ 错误：用 ScenEdit_GetContacts + 递归深度遍历
local function collectContacts(sideName)
    local out = {}
    local r = ScenEdit_GetContacts({ side = sideName })
    for _, c in ipairs(r or {}) do
        table.insert(out, c)
    end
    return out
end

-- ✓ 正确：VP_GetSide().contacts
local function getContacts()
    local out = {}
    local ok, s = pcall(VP_GetSide, {Side = "红方"})
    if ok and s and type(s.contacts) == "table" then
        for _, c in ipairs(s.contacts) do
            out[#out + 1] = c
        end
    end
    return out
end
```

#### 4. mode 参数类型错误

**问题症状：** `ScenEdit_AttackContact` 调用后返回 nil，但没有错误信息。

**根本原因：** `mode` 参数必须用字符串 `"1"`，不能用数字 `1`。

```lua
-- ✗ 错误：mode 是数字类型
r = ScenEdit_AttackContact(atk.guid, contactGuid, {
    mode = 1,  -- 数字，可能失败
    weapon = wpnDbid,
    qty = qty,
})

-- ✓ 正确：mode 是字符串类型
r = ScenEdit_AttackContact(atk.guid, contactGuid, {
    mode = "1",  -- 字符串
    weapon = wpnDbid,
    qty = qty,
})
```

#### 5. contact 匹配（★ 简洁写法）

**原理：** 用 `VP_GetSide({Side="红方"}).contacts` 直接拿 contact 列表，不依赖 `ScenEdit_GetContacts`。

```lua
-- ★ fireAt 必须是全局（红线 #15）
-- 1) 蓝方 autodetectable=true  2) 红方 OMNI  3) 用 VP_GetSide().contacts
-- 4) 用【真延时触发器】把发射安排到未来，让游戏推进后再执行
--    （脚本只"预约"，玩家按播放让时间流逝，到点 contact 已生成）
function fireAt(atkName, tgtName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side="红方", name=atkName})
    local tgt = ScenEdit_GetUnit({side="蓝方", name=tgtName})
    pcall(function() ScenEdit_SetUnit({guid=tgt.guid, autodetectable=true}) end)
    pcall(function() ScenEdit_SetSideOptions({side="红方", awareness="OMNI"}) end)

    local contactGuid
    local ok, s = pcall(VP_GetSide, {Side="红方"})       -- ★ 不用 GetContacts
    if ok and s and type(s.contacts)=="table" then
        local tg = tostring(tgt.guid):lower()
        for _, c in ipairs(s.contacts) do                -- 先按 actualunitid 匹配
            local aid = c.actualunitid or c.actualUnitID or c.actualunitguid
            if aid and tostring(aid):lower()==tg then contactGuid=c.guid; break end
        end
        if not contactGuid then                          -- 再按名称匹配
            for _, c in ipairs(s.contacts) do
                local nm = tostring(c.name or "")
                if nm~="" and (nm==tgtName or nm:find(tgtName,1,true)) then contactGuid=c.guid; break end
            end
        end
    end
    if not contactGuid then print("无 contact，加大延迟或多推进游戏"); return false end

    _errnum_=0
    return ScenEdit_AttackContact(atk.guid, contactGuid, {mode="1", weapon=wpnDbid, qty=qty}) and true or false
end
```

#### 6. contact 稳定等待时间（关键！）

定时发射（TOT）场景中，**contact 刷新有延迟**。即使设置了 `autodetectable = true` 和 `awareness = "OMNI"`，红方也需要时间来发现并稳定识别蓝方目标。

**必须设置 `contact_settle_delay = 15` 秒**，5 秒通常不够。

```lua
-- CFG 配置区
contact_settle_delay = 15,  -- 必须 >= 15 秒，等待 contact 稳定
allow_bol_fallback   = true, -- 兜底，防止无 contact 时完全不发射
```

**TOT 调度逻辑示例：**

```lua
local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    -- 实际延迟 = 任务延迟 + contact 稳定等待时间
    local actualDelay = delay + (tonumber(CFG.contact_settle_delay) or 15)

    if actualDelay <= 0 then
        fireAt(atkName, tgtName, wpn, 1)
        return true
    end

    local evName = "Event " .. tag
    local trName = "Trig " .. tag
    local acName = "Act " .. tag
    local fireTime = totTicks(actualDelay)

    local script =
        ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)

    -- 创建事件：触发器 + 动作 + 事件
    pcall(function() ScenEdit_SetTrigger({ mode="add", type="Time", name=trName, Time=fireTime }) end)
    pcall(function() ScenEdit_SetAction({ mode="add", type="LuaScript", name=acName, ScriptText=script }) end)
    pcall(function() ScenEdit_SetEvent(evName, { mode="add", IsActive=true, IsRepeatable=false }) end)
    pcall(function() ScenEdit_SetEventTrigger(evName, { mode="add", name=trName }) end)
    pcall(function() ScenEdit_SetEventAction(evName, { mode="add", name=acName }) end)

    return true
end
```

> ⚠️ **常见错误：** 只设置 5 秒 delay，contact 还没刷新完就发射，导致"完全不发射"或"导弹脱靶"。

#### 7. 创建后缺少第二次 `forceBlueAutodetectable` 遍历

仅在创建时设置一次 `autodetectable` 可能不够，应在创建完成后再次遍历所有蓝方单位确认。

#### 8. BOL 模式用于移动目标

**问题症状：** 导弹发射了但脱靶，打在空水域。

**根本原因：** BOL（Bearing Only Launch）发射后导弹朝发射时的坐标飞行，不跟踪目标。如果蓝方舰艇在移动，导弹会打空。

**解决方案：** 对移动舰艇，使用 contact 攻击，并设置 `allow_bol_fallback = false`。

#### 9. 假延时：同步 for 循环 + qty=N（致命错误）

**问题症状：**
- 13 枚 YJ-18 在脚本执行瞬间全部离架，无 TOT 间隔
- 暂停游戏也能发射
- `contact_settle_delay = 15` 配置了但不生效（常量从未被使用）
- 多波齐射只能手动间隔运行脚本

**根本原因：** 把"齐射"理解为 for 循环调用 `fireAt(qty=N)`，没有用 CMO 事件触发器做真正的延时调度。

**正确做法：**

```lua
-- ❌ 假延时（同步循环）
for _, s in ipairs(STRIKE) do
    fireAt(s[1], s[2], s[3], s[4])   -- qty=13 一次性塞给 CMO
end

-- ✅ 真延时（事件触发器 + qty=1 逐枚调度）
for i, s in ipairs(STRIKE) do
    local atk, tgt, wpn, qty, startDelay, interval = s[1], s[2], s[3], s[4], s[5], s[6]
    for k = 1, qty do
        local delay = startDelay + (k - 1) * interval + 15  -- +15s contact 稳定期
        scheduleOne(atk, tgt, wpn, delay, "TOT_"..i.."_"..k)  -- 创建 Time 触发器
    end
end
```

详见上方 **真延时打击（TOT 事件驱动）** 章节。

#### 10. fireAt 函数定义成 local（事件脚本沙箱无法调用）

**问题症状：** Time 触发器触发时 Lua 脚本静默失败，导弹不发射。

**根本原因：** 事件脚本运行在沙箱环境，无法访问外部 upvalue。

```lua
-- ❌ 错误：事件沙箱找不到 fireAt
local function fireAt(...)
end

-- ✅ 正确：全局函数
function fireAt(...)
end
```

#### 11. Time 触发器时间换算错误

**问题症状：** 触发器在错误的时间触发（如脚本执行前就触发，或几小时后）。

**根本原因：** CMO `Time` 字段是 .NET Ticks（自 0001-01-01 起，100ns 单位），不是 Unix 秒。

```lua
-- ❌ 错误：直接传 Unix 秒
ScenEdit_SetTrigger({mode="add", type="Time", name="T1",
    Time = ScenEdit_CurrentTime() + 60})  -- 触发器在 1970 年触发！

-- ✅ 正确：换算成 .NET Ticks
local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    local offSet = 62135596801
    return string.format("%.0f", (t + offSet + addSeconds) * 1e7)
end
ScenEdit_SetTrigger({mode="add", type="Time", name="T1",
    Time = totTicks(60)})
```

### 自审清单（生成 attack.lua 前必查）

- [ ] `STRIKE` 中的所有攻击方/目标单位名，与 `main.lua` 的 `name=` 完全一致
- [ ] `fireAt` 函数是全局函数（不带 `local`）
- [ ] 配置变量已提升为全局变量（供事件脚本访问）
- [ ] `collectContacts` 使用递归遍历到 `depth > 3`，而非只遍历顶层
- [ ] `ScenEdit_AttackContact` 的 `mode` 参数使用字符串 `"1"` 而非数字 `1`
- [ ] contact GUID 匹配检查所有可能的字段名：`actualunitid`, `actual_guid`, `actualGuid` 等
- [ ] 包含 `CFG_ALLOW_UNIT_GUID = true` 后备方案
- [ ] **TOT 场景必须设置 `contact_settle_delay = 15`**（5 秒不够）
- [ ] **推荐在 `fireAt` 中增加重试机制（3次，每次间隔2秒）**
- [ ] 创建蓝方单位后有第二次 `forceBlueAutodetectable` 遍历
- [ ] **真延时：每条 `STRIKE` 都有 `startDelay`、`interval`，并通过 `scheduleOne` 创建 Time 触发器**
- [ ] **真延时：`qty=N` 拆成 N 个独立触发器，每个调用 `fireAt(..., qty=1)`**
- [ ] **真延时：每枚弹的 delay 已叠加 `contact_settle_delay`**

---

## JSON 作战方案 → Lua 代码映射规范

当用户提供 JSON 作战方案文件时，**必须**将 JSON 的每个字段忠实翻译为对应的 CMO Lua API 调用。以下为强制映射规则：

### 映射总表

| JSON 字段路径 | 必须生成的 Lua 代码 | 说明 |
|---|---|---|
| `basicInfo.side` | `ScenEdit_AddSide` | 创建阵营 |
| `basicInfo` → EMCON | `ScenEdit_SetEMCON` | 根据平台类型和角色设置电磁管控 |
| `situationAssessment` | `ScenEdit_SetDoctrine` | 设置打击规则 |
| `targets[].location` | `ScenEdit_AddUnit` + `latitude/longitude/altitude` | **用 JSON 的坐标**，单位类型由 `objectType` 决定 |
| `forceOrganization[].platformSelection[].platformLocation` | `ScenEdit_AddUnit` | 同上 |
| `forceOrganization[].platformSelection[].loadList` | 挂载方案 | 通过 MCP 查 LoadoutID |
| `platformExecutions[].platformId` | **直接用作 `name` 参数** | 禁止改名，必须与 JSON 一致 |
| `platformExecutions[].route.waypoints[]` | `ScenEdit_AddReferencePoint` + `courseofaction` | 航线航点转为参考点 |
| `platformExecutions[].platformTasks[].platformTaskType` | `ScenEdit_AddMission` 的 `type` | 见下方类型映射 |
| `platformExecutions[].platformTasks[].relatedKillChain` | `ScenEdit_AssignUnitToMission` + `ScenEdit_AssignUnitAsTarget` | 任务关联 kill chain |
| `platformExecutions[].platformTasks[].timing` | 时间事件：`ScenEdit_SetTrigger(type=Time)` | T+0H=0s, T+50M=3000s, T+1H=3600s… |
| `platformExecutions[].platformTasks[].weapons[]` | 记录在任务描述和 README 中 | 武器由 LoadoutID 决定，LoadoutID 需 MCP 查询 |
| `combatPhases[].timeWindow` | `ScenEdit_SetTrigger(time=ScenEdit_CurrentTime()+偏移秒数)` | 每个 phase 的 startTime/endTime 均需映射 |
| `killChains[].LinkList[].startCondition` | `ScenEdit_SetTrigger` 的 type 选择 | type=时间 → Time触发器, type=事件 → 事件触发器 |
| `terminationStates[].thresholds` | `ScenEdit_SetTrigger(type=UnitDamaged, damaged_threshold=阈值)` | 胜利条件 |
| `killChains[].LinkList[].platforms[].weapon` | 标注在任务说明和 README 中 | LoadoutID 包含武器 |

### platformTaskType → Mission type 映射

| JSON platformTaskType | ScenEdit_AddMission type | ScenEdit_AddMission subtype |
|---|---|---|
| `巡逻` / `巡航` | `patrol` | `air`/`naval`/`sub`（由平台决定） |
| `地对地导弹发射`（潜艇） | `strike` | `naval` |
| `空对地/舰火力突击` | `strike` | `naval` |
| `巡逻` + 电子战角色 | `patrol` | `SEAD` |
| `发现` | `patrol` | `air` |

### timing 格式转换规则

| JSON 格式 | 转换为秒数 | 示例 |
|---|---|---|
| `T0+PT0H` | `0` | 立即开始 |
| `T0+PT50M` | `3000` | 50分钟 = 50×60秒 |
| `T0+PT1H` | `3600` | 1小时 = 60×60秒 |
| ISO datetime `2026-04-10 12:50:00` | 相对场景开始的秒数差 | 与 relativeTimeBase 求差 |

### 禁止行为

- ❌ **禁止**因为 Lua 变量名习惯而修改 JSON 的 `platformId`/`targetID`
- ❌ **禁止**省略 `ScenEdit_AssignUnitAsTarget`（打击任务必须有目标）
- ❌ **禁止**把巡逻航线写成打击任务的航线（type 不匹配）
- ❌ **禁止**用固定字符串代替 MCP 查询得到的 LoadoutID
- ❌ **禁止**时间触发器不乘以 60（CMO 时间单位是秒，不是分钟）

---

## 生成代码前必须查阅下面资料库：
| 资料 | 位置 | 用途 |
|------|------|------|
| Lua 函数参考 | `references/lua-api/index.md` | API 参数详解 |
| 数据类型参考 | `references/data-types/index.md` | latitude/longitude/altitude 等 |
| 常见 DBID 速查 | `references/dbid/index.md` | 仅最常用装备速查，大多数场景仍需 MCP 查询 |
| 报错记录库 | `errors/index.md` | 常见错误及解决方案 |
| 基础模板 | `templates/basic/` | add-aircraft.lua / add-ship.lua 等 |
| 高级模板 | `templates/advanced/` | patrol-mission.lua 等 |
| 官方案例 | `examples/official/` | 完整场景参考 |

---


## 输出前自审（必须执行）

每次生成 Lua 代码后，输出前必须逐项检查：

- [ ] `latitude` / `longitude` / `altitude` 参数名正确（lat/lon/alt 是官方别名，同样有效）
- [ ] `LoadoutID` 参数存在且大写 L/I，类型为数值
- [ ] `type` 为 `Aircraft` / `Ship` / `Submarine` / `Facility`（非 Air/Ground）
- [ ] `dbid` 为数值，且通过 MCP 查询得到（非编造）
- [ ] 阵营 `side` 已在代码中通过 `ScenEdit_AddSide` 创建
- [ ] **所有 `side=` 参数使用 `"红方"` / `"蓝方"`，不得出现 `"Red"` `"Blue"`**
- [ ] **红方全知全能使用 `ScenEdit_SetSideOptions({side="红方", awareness="OMNI"})`，不得用 EMCON/Doctrine 伪装**
- [ ] `errors/index.md` 中没有匹配到本次代码的问题
- [ ] 查询 MCP 时使用英文关键词
- [ ] **蓝方目标单位已设置 `autodetectable = true`**（创建时 + 创建后遍历 + 发射前）
- [ ] **真延时打击场景必须使用 Time 触发器 + 逐枚 `qty=1` 调度**，禁止同步 for + `qty=N` 假延时
- [ ] **`fireAt` 函数是全局函数**（不带 `local`），配置变量提升为全局
- [ ] **`contact_settle_delay ≥ 15 秒`**，且已叠加到每枚弹的 delay

发现问题：**立即修正后再输出**。

---


## 输出成果保存位置

用户通过 Skill 生成的 Lua 代码，**按日期时间+方案名创建子文件夹**保存到 `outputs/lua/` 目录：

```
outputs/lua/
└── <YYYYMMDD>_<HHMMSS>_<方案名>/
    ├── main.lua       # 主执行脚本
    └── README.md      # 说明文档
```

示例：`outputs/lua/20260420_104500_多轴饱和攻击方案/main.lua`

- **不要**将生成代码保存到 `templates/` 或 `examples/contributed/`
- `examples/contributed/` 仅接受通过审核的正式贡献案例

---

## §9 故障排查 SOP（xiangding execution_log 实战沉淀）

> 这一节专门给**"脚本跑完了，但仿真里没动静"**的诊断流程。xiangding 项目 57KB 的 execution_log 暴露了大量此类问题，按以下顺序排查可以 90% 定位根因。

### 9.1 故障决策树

```
脚本执行完成 → 仿真里没发射导弹？
  │
  ├─ 1. 检查 [CMO] 打印行数 < 5
  │   └─ 脚本提前 return nil → 大概率 dbid=0 或 MCP 未查表
  │
  ├─ 2. 检查 contact count 是否 > 0
  │   ├─ count = 0 → 红方 EMCON 没开 或 蓝方 autodetectable=false
  │   └─ count > 0 → 继续步骤 3
  │
  ├─ 3. 检查 ScenEdit_AttackContact 是否返回非 nil
  │   ├─ 返回 nil + _errmsg_ → 看红线 #6（awareness=OMNI）或 #8（autodetectable）
  │   └─ 返回正常 → 继续步骤 4
  │
  ├─ 4. 检查是否注册了 Time 触发器
  │   ├─ 仅同步 for 循环 → 红线 #9 违规，假延时，暂停游戏也发射
  │   └─ 有 Time 触发器 → 继续步骤 5
  │
  ├─ 5. 检查触发器 Time 字段是否 > ScenEdit_CurrentTime()
  │   ├─ Time 已过期 → 时间换算错误（Unix 秒 vs .NET ticks）
  │   └─ Time 未到 → 用户必须推进仿真时间（暂停不触发）
  │
  └─ 6. 检查 Event/Trigger/Action 是否同名冲突
      └─ 重跑脚本时未用时间戳命名 → 触发器被静默覆盖
```

### 9.2 常见错误速查表

| 症状 | 最常见根因 | 修复方法 |
|------|----------|---------|
| `[CMO] [INFO] contact count = 0` | 红方 EMCON 全 Passive | 加 `ScenEdit_SetEMCON('Side', '红方', 'Radar=Active;Sonar=Active;OECM=Active')` |
| `Attempt 1/3: 无 contact, 2s 重试...` 后放弃 | 蓝方 `autodetectable=false` | `pcall(function() ScenEdit_SetUnit({guid=tgt.guid, autodetectable=true}) end)` |
| `[ERROR] ScenEdit_AttackContact: ...` | 红方 awareness 不是 OMNI | `pcall(function() ScenEdit_SetSideOptions({side='红方', awareness='OMNI'}) end)` |
| `[SUCCESS] 发射 ...` 但仿真里没弹 | 假延时（同步 for 循环） | 改用 §6 真延时模板（Time Trigger + LuaScript Action） |
| 时间到了但没发射 | 触发器 Time 已过期（用 `t + delay` 而非 `(t + 62135596801) * 1e7`） | 修正 totTicks 公式 |
| 暂停时仍发射 | 没用 Event Trigger 而是 for 循环 | 见红线 #9 |
| 重跑时报 "Event already exists" | Event/Trigger/Action 未带时间戳 | 命名改为 `"TOT_<i>_<k>_<currentTime>"` |
| `_errmsg_: Invalid GUID` | 用了 `tgt.guid` 而不是 contact.guid | 用 `VP_GetSide().contacts` 匹配拿到 `contactGuid` 后再攻击 |
| 装弹成功但 dumpAmmo = 0 | mount_guid 错位 | 不指定 mount_guid，让 API 自动分配 |
| 导弹发射后立即消失 | 蓝方 weapon_control_status=Hold 且不攻击 | 把红方 doctrine WCS 设为 Free（0） |
| `attempt to index a nil value` | `pcall(ScenEdit_XXX, args)` ——CMO 的 `ScenEdit_*` 是 userdata，**必须**用 `pcall(function() ScenEdit_XXX(args) end)` |

### 9.3 诊断时必带的日志输出

每个 attack.lua 必须包含：

```lua
-- 执行前
print("[CMO] 红方 contact count = " .. tostring(#collectContacts(_SIDE_RED)))
print("[CMO] 蓝方 autodetectable = " .. 
    tostring(VP_GetUnit({Side=_SIDE_BLUE, Name=targetName}).autodetectable))

-- AttackContact 后
print("[CMO] AttackContact 返回 = " .. tostring(r))
print("[CMO] _errmsg_ = " .. tostring(_errmsg_))
print("[CMO] _errnum_ = " .. tostring(_errnum_))

-- 调度后
print("[CMO] TOT 触发器已注册: 时间 = " .. fireTime 
    .. " (仿真时间 + " .. (delay) .. " 秒)")
```

### 9.4 弹药账本追踪

攻击完成后，应打印实际消耗：

```lua
-- 攻击后自检：剩余弹药
local u = ScenEdit_GetUnit({side = "红方", name = attackerName})
local remain = 0
for _, m in ipairs(u.mounts or {}) do
    for _, w in ipairs(m.mount_weapons or {}) do
        if tonumber(w.wpn_dbid) == wpnDbid then
            remain = remain + (tonumber(w.wpn_current) or 0)
        end
    end
end
print("[CMO] " .. attackerName .. " 剩余 YJ-18 = " .. remain 
    .. " (原始装填 " .. ammoTotal .. " - 计划发射 " .. qty .. ")")
```

> 如果 `remain != ammoTotal - qty`，说明有部分弹没发射（contact 不稳定 / 拦截 / 故障），需要回查 execution_log。

---

## §10 输出格式选择指南（xiangding 双路生成实战沉淀）

> xiangding 项目同时维护了 **LLM 直接生成 DLL/XML** 和 **LLM 生成 Lua** 两套流程。这一节给出明确选择标准。

### 10.1 三种输出格式对比

| 格式 | 适用场景 | 优势 | 劣势 |
|------|---------|------|------|
| **Lua 四件套**（main/clear/reload/attack） | 简单 1V1 / 2V2 / 3V3，装备固定 | 易调试、日志清晰、事件驱动支持真延时 | 大规模编队时脚本过长（>2000 行） |
| **DLL / XML**（ScenEdit 导出改） | 4V4+ 大规模编队，需要复用现有模板 | 单位/挂载/任务直接来自模板，零 LLM 编造 | 改 XML 易破坏 schema，复杂任务难加 |
| **混合**（XML 初始 + Lua 攻击） | 实战最常用 | XML 批量建单位，Lua 负责打击逻辑 | 需要双路校验 |

### 10.2 选择决策树

```
场景规模？
  │
  ├─ 单挑 / 双挑 / 三挑（≤6 单位）
  │   └─ ✅ Lua 四件套
  │
  ├─ 中等规模（7-30 单位）
  │   ├─ 必须真延时齐射？
  │   │   ├─ 是 → ✅ Lua（XML 不支持事件触发）
  │   │   └─ 否 → 任选
  │   └─ 装备型号来自标准模板？
  │       ├─ 是 → ✅ XML + Lua 混合
  │       └─ 否 → ✅ Lua
  │
  └─ 大规模（>30 单位 / 多波次）
      └─ ✅ XML 初始 + Lua 打击
```

### 10.3 xiangding 双路生成经验

xiangding 项目实践发现：

| 任务 | LLM 直接生成 | LLM + 模板填空 |
|------|-------------|---------------|
| 飞机 LoadoutID | ❌ 高错率（编造数字） | ✅ 100% 准（走 MCP） |
| 单位坐标 | ⚠️ 中等（需要校验 JSON） | ✅ 100% 准（JSON 已含） |
| 武器数量 | ❌ 高错率（凭印象） | ✅ 100% 准（JSON missions 字段） |
| TOT 时间换算 | ❌ 高错率（Unix vs Ticks） | ✅ 100% 准（模板自带 totTicks） |
| 事件触发器命名 | ❌ 易重名冲突 | ✅ 100% 准（模板自带时间戳） |

**结论**：**装备数据 + 时间换算 + 命名规范** 这 3 类必须走模板/MCP，不能让 LLM 自由发挥。

### 10.4 不推荐：纯 LLM 一次性输出整个 main.lua

xiangding 早期（v1.x）的 `agent_plan_lua.py` 就是让 LLM 一次性生成整个脚本（建单位+清弹+装弹+攻击），结果：

- 弹药数量编造（"凭印象" 写 16 发，实际舰艇 VLS 只有 8 格）
- TOT 时间错算（用 Unix 秒直接传给 Time 字段）
- Event 命名冲突（重跑脚本时旧 Event 没清理）
- 蓝方 autodetectable 漏设（红线 #8 违规）

**v2.0 强制使用 manifest.lua 四件套流程**，禁止一次性输出。

---

## §11 MCP 工具使用与故障排查

### 11.1 MCP 工具一览

| 工具名 | 必填参数 | 用途 |
|---|---|---|
| `query_dbid` | `query` | 自然语言模糊搜索（"J-15"/"F-16"/"战斗机"） |
| `get_dbid_by_name` | `name` | 精确名称匹配 |
| `get_dbid_by_country` | `country` | 按国家筛选装备 |
| `list_tables` | （无） | 列出所有表名 |
| `describe_table` | `table_name` | 查看表结构 |
| `read_query` | `sql` | 任意 SELECT SQL |

### 11.2 高频查询真值表（**已实测**）

| 想查的 | 正确 SQL / 工具 |
|---|---|
| J-15 等飞机 dbid | `query_dbid("J-15")` 或 `get_dbid_by_name("J-15 Flying Shark")` |
| J-15 的 LoadoutID 列表 | `SELECT al.ComponentID FROM DataAircraftLoadouts al WHERE al.ID=2496`（**ID=飞机dbid, ComponentID=LoadoutID, 列名是反的**——见红线 #16） |
| Loadout 名称/武器清单 | JOIN `DataLoadout dl ON dl.ID=al.ComponentID` + `DataLoadoutWeapons w ON w.ID=dl.ID` |
| 反舰挂载 (YJ-83K 等) | `WHERE dw.Name LIKE '%YJ%'` |
| 中国机场 | DB 里所有机场 `OperatorCountry=1003 (Generic)`，中国机场由 `side="红方"` + dbid 决定；用 `query_dbid("airfield")` 查全部机场 dbid |

### 11.3 🔴 关联表列名反向真值表（红线 #16 配套）

| 表名 | ID 列含义 | ComponentID 列含义 |
|---|---|---|
| `DataAircraftLoadouts` | **Aircraft dbid** | **LoadoutID** ⚠️ 反向 |
| `DataFacilityAircraftFacilities` | Facility dbid | Aircraft dbid |
| `DataShipAircraftFacilities` | Ship dbid | Aircraft dbid |
| `DataSubmarineAircraftFacilities` | Sub dbid | Aircraft dbid |
| `DataGroundUnitAircraftFacilities` | Ground dbid | Aircraft dbid |
| `DataLoadoutWeapons` | **LoadoutID** ✅ 正向 | Weapon dbid |
| `DataFacilityWeapons` | Facility dbid | Weapon dbid |
| `DataShipWeapons` | Ship dbid | Weapon dbid |
| `DataWeapon` / `DataAircraft` / `DataShip` / `DataFacility` | 自身 dbid | — |

### 11.4 关联表使用 SQL 模板

**飞机 LoadoutID 查询（J-15=2496 为例）：**

```sql
SELECT al.ComponentID AS LoadoutID, dl.Name, dl.ROF, dl.Capacity,
       dl.LoadoutRole, dl.DefaultCombatRadius, dl.DefaultTimeOnStation,
       w.ComponentNumber AS mount, dw.Name AS weapon
FROM DataAircraftLoadouts al                    -- 注意是 al.ID=飞机, al.ComponentID=Loadout
JOIN DataLoadout dl ON dl.ID = al.ComponentID
LEFT JOIN DataLoadoutWeapons w ON w.ID = dl.ID
LEFT JOIN DataWeapon dw ON dw.ID = w.ComponentID
WHERE al.ID = 2496
  AND (dl.Deprecated = 0 OR dl.Deprecated IS NULL)
ORDER BY dl.LoadoutRole, al.ComponentID, w.ComponentNumber;
```

**设施能容纳哪些飞机：**

```sql
SELECT f.ID AS facility_dbid, f.Name, faf.ComponentID AS aircraft_dbid, da.Name
FROM DataFacility f
JOIN DataFacilityAircraftFacilities faf ON faf.ID = f.ID
JOIN DataAircraft da ON da.ID = faf.ComponentID
WHERE f.Name LIKE '%Airfield%';
```

### 11.5 🔴 MCP 调用失败的 Fallback 方案

**症状**：用 Cursor `CallMcpTool(server="user-HKBQ_SqlDB", arguments={...})` 时偶发返回：
```
Input validation error: 'query' is a required property
```
但 schema 已合规、`list_tables`（无 required）能跑通。

**根因**：Cursor MCP client 序列化参数时偶发吞掉 arguments（已实测，缓存 30s 期间可能 schema 与参数不匹配）。

**Fallback**：用 `subprocess` 直接 spawn `mcp/server.py` 走 JSON-RPC stdio，绕过 Cursor client：

```python
import subprocess, json, os

PY = r"E:\Deep_learning\anconda\python.exe"
SCRIPT = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\server.py"
env = os.environ.copy()
env["SQLITE_DB_PATH"] = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"

def mcp_call(tool, args):
    p = subprocess.Popen([PY, SCRIPT], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env)
    rid = 0
    def send(msg):
        nonlocal rid; rid += 1
        msg["id"] = rid
        p.stdin.write((json.dumps(msg) + "\n").encode())
        p.stdin.flush()
    send({"jsonrpc": "2.0", "method": "initialize",
          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                     "clientInfo": {"name": "fallback", "version": "1.0"}}})
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "method": "tools/call",
          "params": {"name": tool, "arguments": args}})
    # ... read line, parse, close
    out = p.stdout.readline().decode()
    p.stdin.close(); p.wait(timeout=5)
    return json.loads(out)  # parse jsonrpc response
```

**或者最简单：直接用 sqlite3 Python 模块**（DB 已知路径）：

```python
import sqlite3
con = sqlite3.connect(r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3")
con.row_factory = sqlite3.Row
for r in con.execute("SELECT ID, Name FROM DataAircraft WHERE Name LIKE '%J-15%'"):
    print(dict(r))
```

> 已实测：上述 sqlite3 直连 + MCP 直连均能完整复现所有数据，**不依赖 Cursor MCP client**。

### 11.6 Enum 表查询（Type/Category 翻译）

CMO 数据库中大量字段是**枚举 ID**（如 `OperatorCountry=2018`、`LoadoutRole=3202`），查具体含义：

| 想翻译 | SQL |
|---|---|
| 国家 2018 | `SELECT Description FROM EnumOperatorCountry WHERE ID=2018` → `China` |
| LoadoutRole 3202 | `SELECT Description FROM EnumLoadoutRole WHERE ID=3202` → `Strike` |
| Aircraft Type 2001 | `SELECT Description FROM EnumAircraftType WHERE ID=2001` → 战斗机 |
| Weapon Type 1001 | `SELECT Description FROM EnumWeaponType WHERE ID=1001` |

枚举表均以 `Enum` 前缀，可在 `list_tables` 结果里筛选。

---

## 参考链接

- **API Docs:** https://commandlua.github.io
- **Wrappers reference:** https://commandlua.github.io/assets/Wrappers.html
- **Functions reference:** https://commandlua.github.io/assets/Functions.html
- **Enumerations:** https://commandlua.github.io/assets/Enumerations.html
- **Community forum (Lua Legion):** https://www.matrixgames.com/forums/tt.asp?forumid=1681
- **CMO Intellisense (blu3ser):** https://github.com/blu3ser/CMO_Intellisense
