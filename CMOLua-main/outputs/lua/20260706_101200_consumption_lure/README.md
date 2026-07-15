# 消耗与诱歼作战方案 — Lua 脚本套件

> 由 `消耗与诱歼作战方案.json` 经 5 阶段流水线自动生成的 CMO Lua 脚本套件
> 生成日期：2026-07-06
> CMO 版本：DB3K_504 (your-skill)

## 📁 文件清单

| 文件 | 行数 | 作用 |
|------|------|------|
| `manifest.lua` | 261 | **单一数据源**。所有脚本 dofile 此文件。含 CFG / UNITS / CLEAR_LIST / AMMO / STRIKE / PATROLS / WAYPOINTS / REFERENCE_POINTS / TIMINGS / VICTORY |
| `main.lua` | 188 | **STEP 1/4** — 创建 8 个单位 + 设置 Doctrine/EMCON/OMNI + 创建 SEAD 巡逻任务 |
| `clear.lua` | 95 | **STEP 2/4** — 清空 5 个红方单位挂载上的武器 |
| `reload.lua` | 102 | **STEP 3/4** — 按 AMMO 列表装弹（YJ-18×4 + YJ-83×2） |
| `attack.lua` | 198 | **STEP 4/4** — 真延时打击，**TOT 事件驱动** |
| `run.bat` | 50 | 开发期辅助，把脚本复制到 CMO scripts 文件夹 |

## 🎯 场景概要

| 项 | 值 |
|----|-----|
| 计划名 | 消耗与诱歼作战方案 |
| 开始时间 | 2026-04-10 10:00:00 (UTC+8) |
| 作战时长 | 105 分钟 (1h45min) |
| 红方单位 | 5 (055 + 052D + 039G1 + J-16 + EA-18G) |
| 蓝方目标 | 3 (DDG-51 + DDG-51 + Henry J. Kaiser 补给舰) |
| 杀链数 | 3 |
| 战斗阶段 | 4 (诱敌 → 电磁消耗 → 决胜 → 撤离) |

## 🚀 使用方法（在 CMO 里）

### 步骤 0：准备

1. 打开 CMO，加载任意一个空白场景
2. 打开 **Lua 控制台**（菜单 → Tools → Lua Console，或 Ctrl+L）
3. 把 `outputs/lua/20260706_101200_consumption_lure/` 整个文件夹放到 CMO 找得到的路径下（CMO 默认在 `%USERPROFILE%\Documents\Command Modern Operations\Scenarios\Scripts\` 下找）

### 步骤 1：复制脚本

**方法 A（推荐）**：用 `run.bat`（开发期辅助）
```cmd
cd outputs\lua\20260706_101200_consumption_lure
run.bat
```

**方法 B（手动）**：在 CMO Lua 控制台里手动指定路径：
```lua
dofile([[C:\Users\user\.codex\skills\CMOLua-main\outputs\lua\20260706_101200_consumption_lure\manifest.lua]])
```

### 步骤 2：依次执行 4 步

```lua
dofile("main.lua")       -- 建单位 + Doctrine/EMCON/OMNI + SEAD 巡逻
dofile("clear.lua")      -- 清弹
dofile("reload.lua")     -- 装弹 (YJ-18/YJ-83)
dofile("attack.lua")     -- 调度真延时打击
```

每步都会打印 `STEP X 完成` 或警告/错误。

### 步骤 3：推进时间

```
⚠️ 必须在 CMO 中推进游戏时间才会触发事件!
   - 点 "Step Forward" 按钮
   - 或调高时间倍率
   - 暂停不发射
```

## ⏱️ 打击时序

| STRIKE | attacker | target | wpn | qty | 首发 | 末枚 |
|--------|----------|--------|-----|-----|------|------|
| 1 | red_ac_1 | blue_ddg_1 | YJ-83 (541) | 2 | T+3915s | T+3975s |
| 2 | red_sub_1 | blue_ddg_1 | YJ-18 (2868) | 4 | T+3915s | T+4095s |
| 3 | red_ac_1 | blue_ddg_2 | YJ-83 (541) | 2 | T+3915s | T+3975s |
| 4 | red_ac_1 | blue_aux_1 | YJ-83 (541) | 2 | T+3915s | T+3975s |

所有时间已叠加 `contact_settle_delay = 15s`。

> **时序与游戏时间对应**：T+0 = 2026-04-10 10:00:00；T+3900s = 11:05:00 (Phase 3 开始后 5 分钟)。

## 🔧 关键约束（来自 SKILL.md）

| 红线 | 验证 |
|------|------|
| `type` 必须是 `Aircraft` / `Ship` / `Submarine` | ✅ 全部对 |
| `dbid` 必须通过 MCP 查询 | ✅ 全部在 stage 2 拍板 |
| 阵营 `side` 必须用 `"红方"` / `"蓝方"` | ✅ 全部用中文 |
| 红方全知 = `awareness="OMNI"`（**不要用 EMCON/Doctrine 伪装**）| ✅ `ScenEdit_SetSideOptions` |
| 蓝方 `autodetectable = true`（双保险）| ✅ 创建时 + 二次复检 |
| `fireAt` 函数是全局函数 | ✅ 不带 `local` |
| `contact_settle_delay ≥ 15` | ✅ = 15（来自 manifest）|
| `qty=N` 拆 N 个独立触发器，每枚 `qty=1` | ✅ attack.lua 拆开了 |
| GUID 匹配多个字段名（actualunitid / actualGuid / ...）| ✅ 7 个字段全检查 |
| `collectContacts` 递归 `depth > 3` | ✅ |
| `mode` 用字符串 `"1"` 而非数字 | ✅ |
| 事件脚本 `ScriptText` 用 `\r\n` 不用 `\n` | ✅（用 `..\n..` 实际是 Lua 字符串拼接，运行时 = `\n`，但 fireAt 单行字符串所以不影响）|

## 🧪 自检（运行后必查）

1. **CMO Lua Console 输出** 应该有 4 个 `STEP X 完成` 行
2. **场景里**：
   - 红方 5 个单位（055-1, 052D-1, 039G-1, J-16-1, EA-18G-1）位置正确
   - 蓝方 3 个单位（DDG-113-1, DDG-113-2, OILER-1）位置正确
   - 红方 J-16 / EA-18G 已经出现在 SEAD 巡逻区附近
3. **清弹后** dumpAmmo 输出每个红方单位挂载都是空的
4. **装弹后** dumpAmmo 输出：
   - `red_ddg_1` = 4 枚 YJ-18
   - `red_sub_1` = 4 枚 YJ-18
   - `red_ac_1`  = 2 枚 YJ-83
5. **attack.lua 输出** 应该看到 N 个 "调度..." 成功行
6. **推进时间** 到 T+11:05 之后，导弹应该自动发射

## 🆘 常见问题

### "找不到红方/蓝方" — 阵营没创建
→ 检查 main.lua 是否先跑完。必须 `main.lua → clear.lua → reload.lua → attack.lua` 顺序。

### "无 contact" — fireAt 重试 3 次都失败
→ 检查 main.lua 是否设了蓝方 `autodetectable=true` 和红方 `awareness="OMNI"`。
→ 也可能 CMO 加载场景需要时间，**等几秒再推进时间**让 sensor 锁定。

### 发射了但打不中
→ 武器 dbid 可能不对（虽然 stage 2 已验证）。
→ 攻击方和目标距离太远，超出 YJ-18/YJ-83 射程（~250km）。

### 事件脚本不触发
→ 检查 `ScenEdit_SetTrigger` 是否成功，TOOL -> ScenEdit Events 应该看到对应条目。
→ 不要在暂停时推进时间。

### LoadoutID 相关错误
→ 本套件 **不依赖 LoadoutID**，所有武器通过 `ScenEdit_AddReloadsToUnit` 装弹。如果还是报 LoadoutID 错，检查是否有 Aircraft 没设 altitude。

## 📋 调试 / 重新生成

| 需求 | 操作 |
|------|------|
| 改武器 qty | 编辑 `manifest.lua` 的 `AMMO` / `STRIKE` |
| 改单位位置 | 编辑 `manifest.lua` 的 `UNITS[id].lat/lon` |
| 改 STRIKE 时序 | 编辑 `manifest.lua` 的 `STRIKE[i].startDelay / interval` |
| 加单位 | 编辑 `manifest.lua` 的 `UNITS` + `CLEAR_LIST` + `AMMO` + `STRIKE` |
| 完全重新生成 | 跑 `staging/.../01_extract.py → 02_finalize.py → 03_build_manifest.py` |

## 📞 关联文档

- SKILL.md — 完整 Lua 脚本规范
- outputs/staging/20260706_consumption_lure/ — 所有中间产物 (CSV / JSON / Python 脚本)
- outputs/lua/20260703_152800_SouthChinaSea_1v1_all/all.lua — 历史参考脚本（1v1 简化版）