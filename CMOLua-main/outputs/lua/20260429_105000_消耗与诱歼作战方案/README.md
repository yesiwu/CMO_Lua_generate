# 消耗与诱歼作战方案 - Lua 脚本

## 方案概述

- **方案ID**: plan_strategy_C
- **作战方**: 红方 (Red)
- **作战类型**: 反舰作战 — 消耗与诱歼
- **核心思想**: 以水面舰艇为诱饵吸引蓝方注意力并消耗其远程防空导弹，随后空中与水下力量发动决定性突击

## MCP 验证的 DBID

| 单位 | DBID | 备注 |
|------|------|------|
| Type 055 Renhai [101 Nanchang] | 2834 | MCP: query_dbid "Type 055 Renhai" |
| Type 052D Luyang III [172 Kunming] | 2296 | MCP: query_dbid "Type 052D Luyang III" |
| Type 039C Yuan | 695 | MCP: SQL DataSubmarine WHERE Name LIKE '%039C%' |
| J-16 Flying Shark [Su-30MKK Copy] | 2853 | MCP: query_dbid "J-16 Flying Shark" |
| J-15D Growler Shark (EW) | 4957 | MCP: SQL DataAircraft EW search; **替代EA-18G**（EA-18G为美方单位） |

## LoadoutID（MCP: DataAircraftLoadouts）

| 飞机 | LoadoutID |
|------|-----------|
| J-16 Flying Shark (DBID 2853) | 1821 |
| J-15D Growler Shark (DBID 4957) | 1210 |

## 作战时间线

| 阶段 | 时间 | 内容 |
|------|------|------|
| Phase 1 | T0 (10:00) | 水面诱饵编队前出，开启雷达吸引蓝方 |
| Phase 2 | T0+30M (10:30) | J-15D电子战飞机前出，建立干扰阵位 |
| Phase 3 | T0+60M (11:00) | J-16低空突防，039C潜艇上浮攻击阵位 |
| Phase 3b | T0+65M (11:05) | J-16发射YJ-83，039C发射YJ-18 |
| Phase 4 | T0+75M (11:15) | 各平台撤离 |
| 评估 | T0+90M (11:30) | 战果评估 |

## 创建的红方单位

1. **RED-055 #1** (Type 055 Renhai) — 诱饵/主攻驱逐舰
2. **RED-052D #1** (Type 052D Luyang III) — 协同诱饵驱逐舰
3. **RED-SUB #1** (Type 039C Yuan) — 隐蔽攻击潜艇
4. **RED-J16 #1** (J-16 Flying Shark) — 空中突击飞机
5. **RED-J15D-EW #1** (J-15D Growler Shark) — 电子战飞机

## 目标（蓝方）

| 目标 | 大致位置 |
|------|---------|
| 蓝方驱逐舰1 | lat 28.833, lon 126.333 |
| 蓝方驱逐舰2 | lat 28.5, lon 126.667 |
| 蓝方补给舰 | lat 28.167, lon 126.833 |

## 跳过的单位

- **EA-18G Growler**: 数据库中 EA-18G 为美方阵营（OperatorCountry=2101），红方无法使用，替换为 **J-15D Growler Shark** (DBID 4957, PLANAF 电子战型)

## 使用方式

在 CMO 控制台执行 `main.lua`，或通过事件系统加载：
1. 将脚本附加到场景加载事件
2. 所有红方单位将被创建并分配GUID到KeyStore
3. 四个阶段事件自动按时序触发
