# 055 vs Burke 1v1 场景

## 场景概述

- **红方**: 055型驱逐舰（南昌舰），携带16枚YJ-18反舰导弹
- **蓝方**: 伯克级驱逐舰（DDG-51 Arleigh Burke）
- **地点**: 南海
- **战术**: 红方055对蓝方Burke发动饱和打击，发射13枚YJ-18

## DBID 来源（MCP 查询）

| 单位/武器 | DBID | 查询方式 |
|-----------|------|----------|
| Type 055 Renhai | 2834 | `query_dbid("Type 055")` |
| DDG-51 Arleigh Burke | 112 | `query_dbid("Burke")` |
| YJ-18 (3M54E Klub Copy) | 2867 | `read_query("SELECT ...")` |

## 文件说明

| 文件 | 功能 |
|------|------|
| `main.lua` | 创建红蓝双方单位，设置红方全知全能(OMNI) |
| `clear.lua` | 清空055舰上所有待发弹 |
| `reload.lua` | 为055装填16枚YJ-18 |
| `attack.lua` | 发射13枚YJ-18攻击Burke |

## 执行顺序

```bash
# 1. 先运行 main.lua - 创建单位
# 2. 再运行 clear.lua - 清空待发弹
# 3. 然后运行 reload.lua - 装填弹药
# 4. 最后运行 attack.lua - 执行打击
```

## 关键设计点

### 1. autodetectable = true
蓝方单位必须设为 `autodetectable = true`，否则红方即使设为 OMNI 也无法稳定获得可攻击的 contact。

### 2. 三处设置 autodetectable
- 创建蓝方单位时: `autodetectable = true`
- 创建后遍历确认: `ScenEdit_SetUnit(..., autodetectable = true)`
- 每次发射前: `pcall(ScenEdit_SetUnit, {guid, autodetectable = true})`

### 3. Contact 攻击 vs BOL
- 优先使用 contact 攻击（精确跟踪）
- 对移动舰艇禁用 BOL（Bearing Only Launch），因为 BOL 不跟踪目标

## 单位位置

| 单位 | 纬度 | 经度 | 航向 | 航速 |
|------|------|------|------|------|
| 南昌舰 (红方) | 15.5°N | 113.5°E | 90° | 18节 |
| Burke (蓝方) | 14.0°N | 115.0°E | 270° | 15节 |

## 注意事项

1. 055装填YJ-18的实际数量受VLS格口限制
2. 打击前确保055已完成装弹
3. 导弹发射后可在CMO界面观察飞行轨迹和命中结果
