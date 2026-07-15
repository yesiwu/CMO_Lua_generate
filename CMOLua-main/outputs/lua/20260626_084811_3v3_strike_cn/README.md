# CMO 3v3 红蓝对抗 — 中文阵营版

## 重要修正：用户原始 API 拼写错误

```lua
-- 用户的写法（错误）
local a = ScenEdit_SetSideOptions({ side = "红方", awareness = "OMNI" })

-- 正确写法（reference docs 验证）
ScenEdit_SetSideOptions({ side = "红方", awareness = "Omniscient" })
```

`"OMNI"` 不是 CMO 认识的值，API 静默失败——红方不会全知。正确值是 `"Omniscient"`。

## DBID 查询结果（实时 MCP 查询）

> ⚠️ **关键发现**：用户原来给的 2862/3551 是旧数据库 ID，当前连接的数据库中：
> - CG 59 Princeton = **550**
> - CVN 70 Carl Vinson = **246**
> - DDG 113 John Finn = **数据库中不存在**

| 项 | 用户原值 | MCP 实时查询结果 | 状态 |
|----|---------|----------------|------|
| 蓝方-DDG113 | 4299 | **DDG 79 Oscar Austin (Flight IIA) = 294** | ⚠️ 替代品 |
| 蓝方-2862 | 2862 | **CG 59 Princeton = 550** | ✅ 已更正 |
| 蓝方-3551 | 3551 | **CVN 70 Carl Vinson = 246** | ✅ 已更正 |
| 052D Luyang III | 3587 | **3587 / 3586** | ✅ |
| 055 Renhai | 3883 | **2834** | ✅ 已更正 |
| YJ-21 | 4058 | **4058** | ✅ |
| YJ-18 | 2868 | **2868** | ✅ |

## 脚本架构

```
创建阵营（红方/蓝方）
    ↓
红方 SetSideOptions(awareness="Omniscient") ← 【全知核心】
    ↓
红蓝敌对 (SetSidePosture)
    ↓
创建蓝方舰艇 x3（DDG 79 Oscar Austin + CG 59 Princeton + CVN 70）
    ↓
创建红方舰艇 x3（2x 052D Luyang III + 1x 055 Renhai）
    ↓
AddReloadsToUnit 加弹药
    ↓
Strike/SEA 任务（红方全知感知蓝方）
    ↓
AttackContact 手动攻击
    ↓
汇总报告
```

## 执行方法

1. **暂停场景**
2. Lua 控制台（Ctrl+F9）粘贴 `main.lua` → Enter
3. 观察日志，确认无 `[ERROR]`
4. **Play** → 观察海图导弹轨迹

## 故障排查

| 症状 | 原因 |
|------|------|
| `attempt to call a nil value` | DBID 不存在，检查 CFG |
| 全知不生效 | `awareness` 拼写错误，应用 `"Omniscient"` |
| DDG 113 显示为 DDG 79 | 数据库中确实没有 DDG 113 John Finn |
| AttackContact 失败 | 全知模式下目标应已在 contact 中，可能是 build 限制 |
