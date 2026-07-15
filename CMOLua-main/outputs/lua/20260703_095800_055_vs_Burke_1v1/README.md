# 055 vs Burke 1v1 场景说明

## 场景概述

| 项目 | 值 |
|------|-----|
| 红方 | 055型驱逐舰 (101南昌舰) |
| 蓝方 | DDG-113 John Finn (Arleigh Burke Flight IIA) |
| 武器 | YJ-18 反舰导弹 |
| 装弹量 | 16枚 |
| 打击数量 | 13枚 |

## 单位 DBID (MCP 查询结果)

| 单位 | DBID | 备注 |
|------|------|------|
| 055 Renhai | 3883 | 用户指定 |
| DDG-113 John Finn | 4299 | MCP 查询确认 |
| YJ-18 | 2868 | 用户指定 |

## 场景配置

- **红方全知全能**: `ScenEdit_SetSideOptions({awareness="OMNI"})`
- **红蓝敌对**: `ScenEdit_SetSidePosture`
- **蓝方 autodetectable**: 已设置为 `true`

## 执行顺序

### 1. main.lua (场景初始化)
创建红方、蓝方，设置敌对关系和红方全知全能，创建 055 和 DDG-113 单位。

### 2. clear.lua (清空弹药)
清空 055 现有弹药，为后续装弹做准备。

### 3. reload.lua (装填弹药)
向 055 装填 16 枚 YJ-18。

### 4. attack.lua (发起打击)
055 发射 13 枚 YJ-18 攻击 DDG-113。

## 使用方法

1. 在 CMO 中打开新场景
2. 依次打开 Lua 控制台
3. 按顺序执行:
   - `main.lua`
   - `clear.lua`
   - `reload.lua`
   - `attack.lua`

## 注意事项

- 所有脚本必须在同一个 CMO 会话中运行
- 单位名称在所有脚本中保持一致
- 红方全知全能确保稳定获取蓝方 contact
- 蓝方 autodetectable=true 是 contact 攻击的前置条件
