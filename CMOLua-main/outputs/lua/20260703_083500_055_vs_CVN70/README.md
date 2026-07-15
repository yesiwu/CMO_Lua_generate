# 红蓝1v1对抗: 055 vs CVN-70

## 想定概述

红方 055 型驱逐舰（南昌舰）vs 蓝方 CVN-70 卡尔·文森号航母，地点位于南海。

## 兵力对比

| 阵营 | 单位 | 装备 | 武器 |
|------|------|------|------|
| 红方 | 055-Nanchang | Type 055 Renhai [101 Nanchang] | YJ-18 x16 |
| 蓝方 | CVN-70 | CVN 70 Carl Vinson [Nimitz Class] | 舰载机群 |

## 作战方案

- 红方 055 装载 **16枚 YJ-18 反舰导弹**
- 发射 **13枚** 打击蓝方 CVN-70 航母
- 红方设定为**全知全能模式**（无限视野）

## DBID 信息

| 装备 | DBID | 说明 |
|------|------|------|
| Type 055 Renhai | 2834 | 红方主力驱逐舰 |
| CVN 70 Carl Vinson | 246 | 蓝方核动力航母 |
| YJ-18 | 2868 | 反舰导弹 |

## 部署位置

```
南 海

    [055-Nanchang]
    北纬20.0° 东经115.0°
          ↘
           ← 13枚 YJ-18 →
          ↙
    [CVN-70]
    北纬18.0° 东经117.0°
```

**直线距离**: 约 140 海里

## 执行步骤

在 CMO Lua 控制台依次执行以下脚本：

### 1. main.lua — 创建单位

```lua
-- 创建红蓝双方单位
-- 蓝方: CVN-70 (CVN 70 Carl Vinson)
-- 红方: 055-Nanchang (Type 055 Renhai)
```

### 2. reload.lua — 装填导弹

```lua
-- 055 装载 16 枚 YJ-18
```

### 3. attack.lua — 发射打击

```lua
-- 发射 13 枚 YJ-18 打击 CVN-70
```

## 技术要点

### 红方全知全能

```lua
ScenEdit_SetSideOptions({side = "红方", awareness = "OMNI"})
```

### 蓝方 autodetectable 设置

CVN-70 创建时和创建后均设置 `autodetectable = true`，确保红方能稳定探测。

### Contact 攻击模式

优先使用 contact 攻击（非 BOL），确保导弹能跟踪移动目标。

## 预期结果

YJ-18 反舰导弹从 055 发射，飞行约 140 海里攻击 CVN-70 航母。

## 文件清单

```
20260703_083500_055_vs_CVN70/
├── main.lua      # 创建红蓝双方单位
├── reload.lua    # 装填 YJ-18 导弹
├── attack.lua    # 发射 13 枚打击 CVN-70
└── README.md    # 本说明文档
```

## 参考资料

- SKILL.md — CMO Lua 脚本规范
- errors/index.md — 常见错误速查
- templates/advanced/strike-mission.lua — 打击任务模板
