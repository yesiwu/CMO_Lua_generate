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

## 单位映射说明

### DBID 来源（MCP 查询结果 - 第二次查询更新版）

| 装备类型 | JSON EquipmentType | MCP 查询关键词 | 找到 DBID | 备注 |
|---------|-------------------|---------------|-----------|------|
| J-16D 电子战 | AC_J16D | J-16D electronic warfare aircraft | 4632 | J-16D Roaring Wolf |
| J-20A 战斗机 | AC_J20 | J-20 fighter | 5012 | J-20A Fagin (WS-10C) |
| J-16 战斗机 | AC_J16 | J-16 fighter | 2853 | J-16 Flying Shark |
| UUV 无人潜航器 | UUV_RED | unmanned underwater vehicle | 4309 | JHOD UUV Type 2 |
| 052D 驱逐舰 | DDG_052D | Type 052D destroyer | 4354 | Type 052D (CL-91) |
| 055 驱逐舰 | DDG_055 | Type 055 destroyer | 4352 | Type 055 (Renhai) |
| 054A 护卫舰 | FFG_054A | Type 054A frigate | 4361 | Type 054A (Jiangkai II) |
| 039C 潜艇 | SUB_039C | Type 039C submarine | 4260 | Type 039C (Yuan) |
| Burke 驱逐舰 | DDG_CHAFEE | Arleigh Burke destroyer | 2869 | DDG-84 USS Chafee |
| F-35B 闪电II | F35B | F-35B Lightning STOVL | 3870 | F-35B Lightning II STOVL |
| F-35C 闪电 | AC_F35C_LIGHTNING | F-35C Lightning carrier | 824 | F-35C Lightning II |
| HIMARS 火箭炮 | GND_HMS_LAUNCHER | M142 HIMARS | 3268 | Arty Plt, LRPF, PrSM |
| H-6N 轰炸机 | BOMBER_H6K | H-6N | 4837 | ALBM Launch Platform |
| KJ-500 预警机 | AWACS_KJ500 | KJ-500 | 3683 | Y-9 Rotodome AEW |
| DF-26D 发射车 | GND_DF26D_LAUNCHER | DF-26 | 2879 | SSM Bn, ASBM |
| 翼龙-2D 无人机 | UAV_YILONG2D | CH-4 Rainbow | 4334 | 侦察/攻击无人机 |
| DF-26B 发射车 | GND_DF26B_LAUNCHER | DF-26 | 2879 | 复用 DF-26D |
| Nimitz 航母 | CVN_LINCOLN | Nimitz | 429 | CVN 68 Nimitz |
| Ticonderoga 巡洋舰 | Ticonderoga | Ticonderoga | 599 | CG 59 Princeton, SM-3, Aegis BMD |
| 补给舰 | AUX_KZ_SUPPLY | Lewis Clark | 753 | T-AKE 1 Lewis and Clark |
| 监视船 | AGOS_VICTORIOUS | AGOS | 365 | T-AGOS 19 Victorious |

### 跳过的单位（无匹配）

| 装备类型 | 数量 | 原因 |
|---------|------|------|
| SAT_JIANBING23 (卫星) | 50+ | CMO 数据库无卫星数据 |
| LHA_AMERICA (两栖攻击舰) | 1 | 数据库无此舰型 |
| FFG_RICHMOND (护卫舰) | 1 | 无精确匹配 |
| USV_OVERLORD (无人水面艇) | 3 | 本次重新查询确认无匹配 |
| GND_TYPHON_LAUNCHER (标准导弹发射车) | 8 | 无匹配 |

### 可考虑替代方案

- **LHA_AMERICA** → Wasp class LHA 可能存在于其他数据库版本
- **FFG_RICHMOND** → Oliver Hazard Perry class (FFG-51) 可作为近似替代
- **USV_OVERLORD** → 无合适替代装备（已排除 USV Ranger 实验型号）
- **GND_TYPHON_LAUNCHER** → 可考虑使用 SAM Section (AEGIS Ashore) SM-3 Blk IB (DBID 1900) 作为替代

## LoadoutID 说明

所有飞机单位（`type = "Aircraft"`）均需要 `LoadoutID` 参数。

| 装备 | DBID | 可用 LoadoutID | 说明 |
|------|------|----------------|------|
| J-16D (4632) | 4632 | 753 | AGM-88B HARM, AN/ALQ-184 DECM Pod |
| J-20A (5012) | 5012 | 1191, 3589 | AS-14 Kedge / KAB-500Kr |
| J-16 (2853) | 2853 | 1821, 3272 | GBU-31 JDAM (Ferry) |
| F-35B (3870) | 3870 | 689, 827, 997, 1177, 2603, 2604 | AIM-9 Sidewinder / GBU-24 LGB |
| F-35C (824) | 824 | 2607 | GBU-24D/B LGB |
| KJ-500 (3683) | 3683 | 494 | GBU-12D/B LGB |
| H-6N (4837) | 4837 | 无 | 轰炸机无需 Loadout |
| 翼龙-2D (4334) | 4334 | 502, 1032, 3457, 3542, 3543 | CH-4 彩虹无人机 |

## 使用方法

1. 在 CMO 中打开或创建场景
2. 在编辑器 Lua 控制台中粘贴 `main.lua` 的内容，或通过事件脚本执行
3. 检查所有 `[TODO: LoadoutID]` 的标注是否已补全
4. 运行脚本，检查控制台输出

## 生成统计

| 类别 | 红方 | 蓝方 |
|------|------|------|
| 飞机 | 33 架 | 7 架 |
| 水面舰艇 | 5 艘 | 19 艘 |
| 潜艇 | 22 艘 | 0 艘 |
| 地面单位 | 12 个 | 10 个 |
| **已跳过单位** | 50+ | 17 |

### 详细统计

**红方:**
- J-16D 电子战: 8 架
- H-6N 轰炸机: 8 架 (新增)
- KJ-500 预警机: 2 架 (新增)
- J-16 战斗机: 12 架
- J-20A 战斗机: 8 架
- UUV 无人潜航器: 20 艘
- 039C 潜艇: 2 艘
- 052D 驱逐舰: 2 艘
- 055 驱逐舰: 1 艘
- 054A 护卫舰: 2 艘
- DF-26D 发射车: 12 个
- 翼龙-2D 无人机: 3 架 (新增)

**蓝方:**
- F-35C 战斗机: 3 架
- F-35B 战斗机: 4 架
- CVN 68 Nimitz: 1 艘 (新增)
- CG 59 Princeton: 1 艘 (新增)
- DDG-84 Burke: 14 艘
- T-AKE 补给舰: 1 艘 (新增)
- T-AGOS 监视船: 3 艘 (新增)
- HIMARS 火箭炮: 10 个

## 跳过的单位处理建议

对于跳过的单位，可以：
1. 在 CMO 编辑器中手动添加这些单位
2. 使用近似的 CMO 数据库装备替代（如上表所示）
3. 等待 CMO 数据库更新后重新生成
