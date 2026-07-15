# A1场景 - 联合火力突击训练场景 Lua 脚本

## 场景概述

- **场景ID**: zzcjxxxxxxxxxx
- **场景名**: 联合火力突击训练场景
- **场景类型**: 演习
- **红方**: 中国（联合火力突击力量）
- **蓝方**: 美国（航母编队）
- **作战背景**: 东部方向进入战役阶段，蓝方在南部方向增强行动强度

## MCP 验证的 DBID

### 红方（China, OperatorCountry=2018）

| 装备 | DBID | 查询方式 | LoadoutID |
|------|------|---------|-----------|
| Type 052D Luyang III [172 Kunming] | 2296 | SQL DataShip | - |
| Type 054A Jiangkai II | 1965 | SQL DataShip | - |
| Type 055 Renhai [101 Nanchang] | 2834 | SQL DataShip | - |
| Type 039C Yuan | 695 | SQL DataSubmarine | - |
| J-16 Flying Shark [Su-30MKK] | 2853 | SQL DataAircraft | 1821 |
| J-16D Roaring Wolf (EW) | 4632 | SQL DataAircraft | 753 |
| H-6K Badger | 1731 | SQL DataAircraft | 863 |
| KJ-500 Cub AWACS | 3683 | SQL DataAircraft | 494 |
| J-20A Fagin | 5012 | SQL DataAircraft | 1191 |
| SSM Bn DF-21C (DF-26B替代) | 89 | SQL DataFacility | - |

### 蓝方（US, OperatorCountry=2101）

| 装备 | DBID | 查询方式 | LoadoutID |
|------|------|---------|-----------|
| CVN 70 Carl Vinson [Nimitz] | 246 | SQL DataShip | - |
| CG 56 San Jacinto [Ticonderoga] | 40 | SQL DataShip | - |
| DDG 72 Mahan [Burke Flight II] | 111 | SQL DataShip | - |
| DDG 51 Arleigh Burke [Flight I] | 112 | SQL DataShip | - |
| LHA 6 America [Flight 0] | 2362 | SQL DataShip | - |
| AOE 6 Supply | 490 | SQL DataShip | - |
| T-AGOS 19 Victorious | 365 | SQL DataShip | - |
| F-35C Lightning II | 824 | query_dbid | 689 |
| F-35B Lightning II | 534 | SQL DataAircraft | - |
| F/A-18E Super Hornet | 342 | SQL DataAircraft | 1561 |
| F/A-18F Super Hornet | 443 | SQL DataAircraft | 367 |

## 跳过的单位（MCP 查询不到）

| 装备类型 | 原因 |
|---------|------|
| SAT_JIANBING23（卫星） | CMO 数据库中无匹配记录 |
| USV_OVERLORD（无人水面艇） | CMO 数据库中无 Overlord USV 记录 |
| UAV_YILONG2D（翼龙-2D无人机） | DBID 未找到 |
| UUV_RED（红方无人潜航器） | CMO 数据库无对应 UUV 型号 |
| GND_TYPHON_LAUNCHER（海麻雀导弹发射车） | DBID 未找到 |

## 单位数量统计

### 红方（40+ 单位）

- DF-26B 导弹发射阵地：5个
- J-16D 电子战飞机：7架
- H-6K 轰炸机：8架
- KJ-500 预警机：2架
- J-20A 战斗机：8架
- J-16 战斗机：11架
- 052D 驱逐舰：3艘
- 054A 护卫舰：4艘
- 055 驱逐舰：1艘
- 039C 潜艇：2艘

### 蓝方（25+ 单位）

- CVN 林肯号航母：1艘
- 提康德罗加巡洋舰：1艘
- 阿利·伯克级驱逐舰：4艘
- LHA 美国号两栖攻击舰：1艘
- 补给舰：1艘
- AGOS 监视船：3艘
- F-35C：3架
- F-35B：5架
- F/A-18E：4架
- F/A-18F：2架

## 作战时序

| 事件 | 时间 | 内容 |
|------|------|------|
| 初始化 | T0 | 场景加载，所有单位创建 |
| EW飞机出动 | T0+30M | J-16D电子战飞机前出建立干扰阵位 |
| SSM导弹预热 | T0+60M | DF-21C反舰弹道导弹待发 |
| 空中突击 | T0+75M | H-6K+J-16联合反舰饱和打击 |
| 蓝方反击 | T0+90M | F-35C对红方轰炸机和导弹阵地反击 |

## 使用说明

在 CMO 控制台执行 `main.lua`，或通过事件系统加载。建议分配到场景加载事件中执行。
