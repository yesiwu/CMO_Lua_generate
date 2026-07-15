# 红蓝 7V4 辽宁舰协同反舰 CMO Lua 脚本

## 方案概述

- **数据来源**: `json/red_blue_5v3_liaoning1.json`
- **场景**: 红方 7 单位（055×2 + 052D×2 + 辽宁舰 + J-15×2）协同打击蓝方 4 目标（DDG113×2 + CG-59 + CVN-70）
- **总导弹量**: YJ-18 装弹42枚/发射26枚，YJ-83K 装弹8枚/发射8枚，合计34枚齐射
- **时间戳**: 2026-07-08 19:56:32

## 文件清单

| 文件 | 说明 | 行数 |
|------|------|------|
| `main.lua` | 建阵营（红/蓝）+ 创建红蓝双方单位 | 85行 |
| `clear.lua` | 清弹（舰艇 YJ-18，J-15 跳过） | 45行 |
| `reload.lua` | 装弹（YJ-18：055-1=8 + 055-2=8 + 052D-1=16 + 052D-2=10） | 51行 |
| `attack.lua` | 真延时打击（TOT 事件驱动，contact_settle_delay=15s） | 136行 |
| `all.lua` | **四合一**（main → clear → reload → attack） | 317行 |

## 执行方式

### 方式一：分步执行（推荐调试时使用）

```lua
-- 在 CMO Lua Console 中依次粘贴执行
dofile("c:\\...\\outputs\\lua\\20260708_195632_rb_7v4_liaoning_json\\main.lua")
dofile("c:\\...\\outputs\\lua\\20260708_195632_rb_7v4_liaoning_json\\clear.lua")
dofile("c:\\...\\outputs\\lua\\20260708_195632_rb_7v4_liaoning_json\\reload.lua")
dofile("c:\\...\\outputs\\lua\\20260708_195632_rb_7v4_liaoning_json\\attack.lua")
```

### 方式二：一键执行（推荐）

```lua
-- 一次性粘贴 all.lua 全部内容到 CMO Lua Console 执行，或：
dofile("c:\\...\\outputs\\lua\\20260708_195632_rb_7v4_liaoning_json\\all.lua")
```

执行完成后，**推进仿真时间**（Time Acceleration / Step），15秒后导弹开始逐枚发射（每枚间隔1秒）。

## 打击方案明细

| 攻击方 | 目标 | 武器 | DBID | 发射量 | 备注 |
|--------|------|------|------|--------|------|
| Red-055-1 | DDG 113-1 | YJ-18 | 2868 | 7 | 055双舰编队 |
| Red-055-2 | DDG 113-2 | YJ-18 | 2868 | 6 | 055双舰编队 |
| Red-052D-1 | Blue-DBID-3551 (CVN-70) | YJ-18 | 2868 | 8 | |
| Red-052D-2 | Blue-DBID-2862 (CG-59) | YJ-18 | 2868 | 5 | |
| J-15-RED-01 | Blue-DBID-3551 (CVN-70) | YJ-83K | 2137 | 4 | loadoutId=9682 |
| J-15-RED-02 | Blue-DBID-2862 (CG-59) | YJ-83K | 2137 | 4 | loadoutId=9682 |
| **合计** | | | | **34** | |

## 关键技术点

### 红线遵守

- ✅ **红线 #6**: 红方 `awareness="OMNI"` 全知
- ✅ **红线 #8**: 蓝方目标 `autodetectable=true` + 传感器开启
- ✅ **红线 #9**: TOT 真延时（Time Trigger + LuaScript Action，qty=N 拆成 N × qty=1）
- ✅ **红线 #12**: 红蓝双方 `weapon_control_status=0` (Free)
- ✅ **红线 #13**: `ScenEdit_AttackContact` 的 `mode="1"` (字符串)
- ✅ **红线 #15**: `fireAt` / `scheduleOne` / `_SIDE_RED` / `_CONTACT_SETTLE` 全局函数/变量
- ✅ **红线 #18**: `ScenEdit_AddSide({name="红方", color="..."})` 传 table
- ✅ **红线 #20**: 所有 `ScenEdit_*` 用 `pcall(function() ... end)` 包裹
- ✅ **红线 #21**: 清弹用 `AddReloadsToUnit + remove=true` 遍历 mounts 逐条归零；严禁 `DumpAmmo` / `remove_weapon` / `SetAircraftLoadout`

### MCP 验证

所有 DBID 已通过 MCP `read_query` 从 DB3K_504.db3 验证可用：

| 单位 | DBID | 数据库名称 |
|------|------|-----------|
| 055 | 3883 | Type 055 Renhai [101 Nanchang] |
| 052D-1 | 2296 | Type 052D Luyang III [172 Kunming] |
| 052D-2 | 3586 | Type 052DL Luyang III Mod [156 Zibo] |
| 辽宁舰 | 2007 | Type 001 Kuznetsov [16 Liaoning] |
| J-15 | 2496 | J-15 Flying Shark [Su-33 Copy] |
| YJ-18 | 2868 | YJ-18 [3M54E Klub Copy] |
| YJ-83K | 2137 | YJ-83K [C-802AK] |
| DDG 113 | 4299 | DDG 113 John Finn [Arleigh Burke Flight IIA Restart] |
| CG-59 | 2862 | CG 59 Princeton [Ticonderoga Baseline 3, VLS] |
| CVN-70 | 3551 | CVN 70 Carl Vinson [Nimitz Class] |

Loadout 验证：`DataAircraftLoadouts.ID=2496, ComponentID=9682` ✓

### 特殊处理

1. **052D DBID 覆盖**：JSON 里 052D 的 dbid 是 4936，但用户明确指定用 2296（052D-1）和 3586（052D-2），以用户为准。
2. **055 编队装弹分配**：JSON 里 055 是双舰共享一条记录（loaded=16, fired=13），两舰按平分 loaded=16 → 055-1=8、055-2=8。
3. **J-15 跳过清弹/装弹**：飞机用 `opts={mode="0"}` 创建，loadoutId=9682 已包含 YJ-83K，不需要手动 `AddReloadsToUnit` 补弹。
4. **contact_settle_delay=15秒**：红方虽然 OMNI、蓝方虽然 autodetectable，contact 列表仍需 15 秒稳定（< 15 秒会导致"无 contact"错误）。

## 预期效果

- 执行 `all.lua` 后立即看到日志输出：
  - `[main] 阵营/敌对/WCS 设置完毕`
  - `[main] 已存在: xxx` 或 `[main] 创建 xxx ok=true`
  - `[clear] Red-055-1: 减载归零 X 项 (失败 0)`
  - `[reload] Red-055-1 装弹 8x YJ-18 (errnum=0)`
  - `[attack] Red-055-1 -> DDG 113-1: 7x wpn=2868 调度完毕（T+15s 起）`
- **推进仿真时间** 15 秒后，开始逐枚发射（游戏 log 出现 `[fireAt] Red-055-1 -> DDG 113-1 x1 wpn=2868 ok=true`）
- 最终蓝方目标受到 34 枚导弹攻击（7+6+8+5+4+4）

## 常见问题

### Q1: 执行后没有导弹发射？

**A**: 真延时打击依赖 **Time Trigger**，必须推进仿真时间才会触发。暂停状态下不会发射。建议：
  - 点击 Time Acceleration 或 Step（步进）推进时间
  - 等待至少 15 秒（contact_settle_delay）

### Q2: 报错"无 contact"？

**A**: 
  - 确认蓝方目标 `autodetectable=true` 已生效（检查日志有无 `[main] 创建 Blue-DBID-xxx ok=true`）
  - 确认红方 `awareness=OMNI` 已生效
  - 增大 `_CONTACT_SETTLE` 至 20-30 秒（修改 attack.lua 第 20 行）

### Q3: J-15 无弹可发？

**A**: J-15 用 `loadoutId=9682` 创建，不需要手动装弹。如果仍报错，检查：
  - `opts={mode="0"}` 是否写入（防止 CMO 自动重置挂载）
  - MCP 查询 `DataAircraftLoadouts` 确认 ID=2496, ComponentID=9682 存在

### Q4: 如何修改齐射间隔？

**A**: 修改 `attack.lua` 第 21 行 `_INTERVAL = 1` 改为期望的秒数（如 0.5 秒急促齐射、5 秒宽松波次）。

## 版本历史

- **v1.0 (2026-07-08 19:56)**: 初始版本，符合 SKILL.md 2026-07-08 最新红线（#21 清弹逻辑修正）

---

生成工具: Cursor AI Agent + CMOLua Skill (SKILL.md 2026-07-08)  
MCP 数据库: DB3K_504.db3
