# 055 vs Burke 1v1 对决场景

## 场景概述

| 项目 | 内容 |
|------|------|
| 红方 | 055型驱逐舰（南昌舰）|
| 蓝方 | DDG 51 Arleigh Burke Flight I |
| 地点 | 南海中部 |
| 任务 | 055装16枚YJ-18，发射12枚攻击Burke |

## DBID 参考

| 装备 | DBID | 说明 |
|------|------|------|
| Type 055 Renhai | 3883 | 055型驱逐舰 |
| DDG 51 Arleigh Burke | 2868 | Burke Flight I |
| YJ-18 | 2867 | 侵彻弹头版 |

## 脚本执行顺序

```
1. main.lua    → 创建阵营和单位
2. reload.lua  → 装弹（16枚YJ-18）
3. attack.lua  → 发射12枚YJ-18攻击Burke
4. diagnose.lua → 诊断场景状态（可选）
```

## 执行方式

在 CMO Lua 控制台按顺序执行：

```lua
-- 1. 创建场景
dofile("C:\\Users\\user\\codex\\skills\\CMOLua-main\\outputs\\lua\\20260703_090800_055_vs_Burke_1v1\\main.lua")

-- 2. 装弹
dofile("C:\\Users\\user\\codex\\skills\\CMOLua-main\\outputs\\lua\\20260703_090800_055_vs_Burke_1v1\\reload.lua")

-- 3. 发射攻击
dofile("C:\\Users\\user\\codex\\skills\\CMOLua-main\\outputs\\lua\\20260703_090800_055_vs_Burke_1v1\\attack.lua")

-- 4. 诊断（可选）
dofile("C:\\Users\\user\\codex\\skills\\CMOLua-main\\outputs\\lua\\20260703_090800_055_vs_Burke_1v1\\diagnose.lua")
```

## 单位位置

| 单位 | 纬度 | 经度 | 航向 | 航速 |
|------|------|------|------|------|
| 055-Nanchang | 14.5 | 113.5 | 0° | 15节 |
| DDG-51-Burke | 15.2 | 113.8 | 180° | 12节 |

两舰相距约 40 海里。

## 关键配置

- **红方全知**: `ScenEdit_SetSideOptions({side="红方", awareness="OMNI"})`
- **目标 autodetectable**: `autodetectable = true`
- **Contact 攻击模式**: 优先使用 contact GUID 攻击

## 注意事项

1. YJ-18 是超音速反舰导弹，射程约 660km
2. Burke 配备标准防空系统，可能拦截部分导弹
3. 12枚YJ-18构成饱和攻击，提高突防概率
