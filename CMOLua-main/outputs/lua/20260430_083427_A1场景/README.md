# A1场景 — 联合火力突击训练场景

## 概述

| 字段 | 值 |
|------|-----|
| 方案名称 | 联合火力突击训练场景 |
| 场景ID | zzcjxxxxxxxxxx |
| 版本 | 1.0 |
| 创建日期 | 2025-10-22 |
| 场景开始时间 | 2025/10/27 15:00:00 |
| 描述 | 东部方向进入战役阶段，蓝方在南部方向增强行动强度。蓝方驱护舰编队与我持续对峙，其火箭炮、中导部队进入战备状态；我无人干扰系统实施电磁压制，前沿防空系统进入高度戒备，潜艇部队实施机动部署。 |

## 阵营

| CMO 阵营名 | ForceSideID | 说明 |
|-----------|------------|------|
| 红方 | FORCE-SIDE-RED-001 | 红方部队 |
| 蓝方 | FORCE-SIDE-BLUE-001 | 蓝方部队 |

## DBID 来源（MCP 查询结果）

所有 DBID 均通过 MCP (HKBQ_SqlDB) 连接 DB3K_504.db3 数据库查询，100% 真实数据。

### 红方装备

| 装备类型 | JSON EquipmentType | MCP 查询关键词 | DBID | CMO 名称 |
|---------|-------------------|---------------|------|---------|
| J-16D 电子战 | AC_J16D | J-16D electronic warfare | 4632 | J-16D Roaring Wolf |
| H-6N 轰炸机 | BOMBER_H6K | H-6N | 4837 | H-6N (ALBM Launch Platform) |
| KJ-500 预警机 | AWACS_KJ500 | KJ-500 | 3683 | KJ-500 (Y-9 Rotodome AEW) |
| J-16 战斗机 | AC_J16 | J-16 fighter | 2853 | J-16 Flying Shark |
| J-20A 战斗机 | AC_J20 | J-20 fighter | 5012 | J-20A Fagin (WS-10C) |
| 翼龙-2D 无人机 | UAV_YILONG2D | CH-4 Rainbow | 4334 | CH-4 (Rainbow) |
| 052D 驱逐舰 | DDG_052D | Type 052D destroyer | 4354 | Type 052D (CL-91) |
| 055 驱逐舰 | DDG_055 | Type 055 destroyer | 4352 | Type 055 (Renhai) |
| 054A 护卫舰 | FFG_054A | Type 054A frigate | 4361 | Type 054A (Jiangkai II) |
| 039C 潜艇 | SUB_039C | Type 039C submarine | 4260 | Type 039C (Yuan) |
| UUV 无人潜航器 | UUV_RED | JHOD UUV Type 2 | 4309 | JHOD UUV Type 2 |
| DF-26B 发射车 | GND_DF26B_LAUNCHER | DF-26 ballistic missile | 2879 | SSM Bn (DF-26) |
| DF-26D 发射车 | GND_DF26D_LAUNCHER | DF-26 ballistic missile | 2879 | SSM Bn (DF-26) |

### 蓝方装备

| 装备类型 | JSON EquipmentType | MCP 查询关键词 | DBID | CMO 名称 |
|---------|-------------------|---------------|------|---------|
| F-35C 闪电 | AC_F35C_LIGHTNING | F-35C Lightning carrier | 824 | F-35C Lightning II |
| F-35B 闪电II | AC_F35B_LIGHTNING | F-35B Lightning STOVL | 3870 | F-35B Lightning II STOVL |
| CVN 林肯号 | CVN_LINCOLN | CVN 68 Nimitz | 429 | CVN 68 Nimitz |
| Ticonderoga 巡洋舰 | Ticonderoga | CG 47 Ticonderoga | 42 | CG 47 Ticonderoga Baseline 0 |
| Burke 驱逐舰 | DDG_CHAFEE | Arleigh Burke DDG-84 | 2869 | DDG-84 USS Chafee |
| 补给舰 | AUX_KZ_SUPPLY | T-AKE Lewis Clark | 753 | T-AKE 1 Lewis and Clark |
| FFG 里士满 | FFG_RICHMOND | Oliver Hazard Perry class | 4334 | FFG 7 Peary |
| T-AGOS 监视船 | AGOS_VICTORIOUS | T-AGOS Victorious | 365 | T-AGOS 19 Victorious |
| HIMARS 火箭炮 | GND_HMS_LAUNCHER | M142 HIMARS | 3268 | M142 HIMARS |

## 跳过的单位（数据库无匹配）

| 装备类型 | 数量 | 原因 |
|---------|------|------|
| SAT_JIANBING23 (卫星) | 51 | CMO 数据库无卫星数据 |
| LHA_AMERICA (两栖攻击舰) | 1 | 数据库无此舰型 |
| USV_OVERLORD (无人水面艇) | 3 | 数据库无此装备 |
| GND_TYPHON_LAUNCHER (标准导弹发射车) | 4 | 数据库无此装备 |

## LoadoutID 说明

所有飞机单位（`type = "Aircraft"`）均需要 `LoadoutID` 参数，以下为各机型使用的 Loadout：

| 装备 | DBID | LoadoutID | 说明 |
|------|------|-----------|------|
| J-16D (4632) | 4632 | 753 | AGM-88B HARM |
| J-20A (5012) | 5012 | 1191 | AS-14 Kedge |
| J-16 (2853) | 2853 | 1821 | GBU-31 JDAM |
| 翼龙-2D (4334) | 4334 | 502 | 侦察/攻击构型 |
| F-35C (824) | 824 | 2607 | GBU-24D/B LGB |
| F-35B (3870) | 3870 | 689 | AIM-9 / GBU-24 |
| KJ-500 (3683) | 3683 | 494 | GBU-12 LGB |
| H-6N (4837) | 4837 | 无 | 轰炸机无需 Loadout |

## 生成统计

| 类别 | 红方 | 蓝方 |
|------|------|------|
| 飞机 | 34 架 | 7 架 |
| 水面舰艇 | 8 艘 | 12 艘 |
| 潜艇 | 23 艘 | 0 艘 |
| 地面单位 | 40 个 | 9 个 |
| **生成合计** | **105** | **28** |
| **跳过** | **51** | **8** |

### 详细统计

**红方 (105 单位):**
- J-16D 电子战: 7 架
- H-6N 轰炸机: 14 架
- KJ-500 预警机: 2 架
- J-16 战斗机: 12 架
- J-20A 战斗机: 8 架
- 翼龙-2D 无人机: 3 架
- UUV 无人潜航器: 21 艘
- 039C 潜艇: 2 艘
- 052D 驱逐舰: 3 艘
- 055 驱逐舰: 1 艘
- 054A 护卫舰: 4 艘
- DF-26B 发射车: 20 个
- DF-26D 发射车: 20 个

**蓝方 (28 单位):**
- F-35C 战斗机: 3 架
- F-35B 战斗机: 4 架
- CVN 68 Nimitz: 1 艘
- CG 47 Ticonderoga: 2 艘
- DDG-84 Burke: 5 艘
- T-AKE 补给舰: 1 艘
- FFG 7 Peary: 1 艘
- T-AGOS Victorious: 3 艘
- HIMARS 火箭炮: 9 个

## 使用方法

1. 在 CMO 中打开或创建场景
2. 在编辑器 Lua 控制台中粘贴 `main.lua` 的内容，或通过事件脚本执行
3. 运行脚本，检查控制台输出

## 文件说明

- `main.lua` — 主执行脚本，包含所有单位的 `ScenEdit_AddUnit` 调用
- `README.md` — 本文档，包含 DBID 来源、统计信息和使用说明
