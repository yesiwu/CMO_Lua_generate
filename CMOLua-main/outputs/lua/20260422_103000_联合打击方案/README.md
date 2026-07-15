# 联合打击方案 (Plan 2026B) — CMO Lua 脚本说明

## 方案概述

| 字段 | 内容 |
|------|------|
| 方案代号 | 2026B |
| 方案名称 | 联合打击 |
| 方案代码 | ABC |
| 所属方 | 红方部队 |
| 方案时间 | 2025-10-27 13:30:00 (UTC+8) |
| 作战时间窗口 | 2025-10-27 13:30:00 ~ 16:10:00 (2h40m) |
| 任务类型 | 联合反击 — 反舰作战 |
| 安全等级 | 机密 |

## 打击目标（蓝方）

| 目标ID | 目标名称 | CMO 型号 | 坐标 (Lat, Lon) | DBID | 备注 |
|--------|----------|----------|-----------------|------|------|
| TICO002 | tico_simoer | CG 47 Ticonderoga Baseline 0 | 7.9704, 119.5038 | 42 | MCP 直接查询 |
| BDDG005 | ddg_chafei | DDG 51 Arleigh Burke Flight I | 8.2847, 119.7833 | 112 | MCP 直接查询 |
| LHA001 | lha_meiguo | LHA 1 Tarawa | 7.9229, 120.0936 | 502 | MCP 直接查询 |
| SUPPLY001 | supply_kz | DDG 51 Arleigh Burke Flight I (替代) | -0.1012, 106.1643 | 112 | 补给舰无匹配，用驱逐舰替代 |
| BDDG001 | ddg_momuseng | DDG 51 Arleigh Burke Flight I BMD | 7.1040, 116.2800 | 438 | MCP 直接查询 |

## 蓝方已部署舰艇

| 名称 | CMO 型号 | DBID | 坐标 (Lat, Lon) | heading | speed |
|------|----------|------|-----------------|---------|-------|
| tico_simoer | CG 47 Ticonderoga Baseline 0 | 42 | 7.9704, 119.5038 | 270 | 15kn |
| ddg_chafei | DDG 51 Arleigh Burke Flight I | 112 | 8.2847, 119.7833 | 270 | 15kn |
| lha_meiguo | LHA 1 Tarawa | 502 | 7.9229, 120.0936 | 270 | 12kn |
| ddg_momuseng | DDG 51 Arleigh Burke Flight I BMD | 438 | 7.1040, 116.2800 | 270 | 15kn |
| supply_kz | DDG 51 Arleigh Burke Flight I (替代) | 112 | -0.1012, 106.1643 | 270 | 12kn |

> supply_kz 原型为补给舰，数据库无匹配，用 DDG 51 Arleigh Burke Flight I（DBID=112）替代。

## 红方已部署作战单元

以下单元类型在 MCP 数据库中成功查到 DBID，已通过 `ScenEdit_AddUnit` 部署：

### 1. J-16D 电子战飞机（网电集群）

| 名称 | DBID | LoadoutID | 坐标 (Lat, Lon) | 高度 |
|------|------|-----------|-----------------|------|
| jd002 | 4632 | 965 | 9.91, 115.53 | 1500m |
| jd003 | 4632 | 965 | 9.91, 115.50 | 1500m |
| jd004 | 4632 | 965 | 9.90, 115.49 | 1500m |
| jd007 | 4632 | 965 | 9.94, 115.52 | 1500m |

- **用途**：电磁干扰，压制敌方雷达/通信系统
- **所属部队**：05干扰大队（团级，空军）

### 2. J-20A 隐身战斗机

| 名称 | DBID | LoadoutID | 坐标 (Lat, Lon) | 高度 |
|------|------|-----------|-----------------|------|
| zds001 | 5012 | 1191 | 18.50, 109.97 | 1000m |
| zds002 | 5012 | 1191 | 18.50, 109.98 | 1000m |
| zds003 | 5012 | 1191 | 18.49, 109.98 | 1000m |
| zds004 | 5012 | 1191 | 18.49, 109.99 | 1000m |

- **用途**：空中优势 / 对海打击
- **所属部队**：08战斗机大队（团级，空军）

### 3. H-6K 轰炸机

| 名称 | DBID | LoadoutID | 坐标 (Lat, Lon) | 高度 |
|------|------|-----------|-----------------|------|
| hk003 | 4900 | 1242 | 26.32, 112.79 | 900m |
| hk004 | 4900 | 1242 | 26.30, 112.91 | 1000m |
| hk005 | 4900 | 1242 | 26.45, 112.90 | 1000m |
| hk006 | 4900 | 1242 | 26.22, 112.68 | 1000m |
| hk007 | 4900 | 1242 | 26.20, 112.91 | 1000m |
| hk008 | 4900 | 1242 | 26.39, 112.98 | 1000m |

- **用途**：携带 BGM-109 巡航导弹实施远程对海打击
- **所属部队**：06轰炸机大队（团级，空军）

### 4. E-3C Sentry AWACS（预警机，功能替代 KJ-500）

| 名称 | DBID | LoadoutID | 坐标 (Lat, Lon) | 高度 | 说明 |
|------|------|-----------|-----------------|------|------|
| kja001 | 209 | 142 | 26.32, 112.63 | 1000m | 替代原 KJ-500，E-3C Sentry |

- **用途**：空中预警与指挥控制（等效 KJ-500 预警探测功能）
- **所属部队**：07预警大队（团级，空军）

### 5. SSN 688 Los Angeles（功能替代 DF-26B/D 发射车 + UUV）

| 原 JSON 单位 | 替代后名称 | DBID | 坐标 (Lat, Lon) | 数量 | 说明 |
|-------------|-----------|------|-----------------|------|------|
| GND_DF26B_LAUNCHER | dfb001 ~ dfb003 | 22 | 18.54~18.55, 110.00~110.01 | 3 | 替代弹道导弹发射车，作为海上打击平台 |
| GND_DF26D_LAUNCHER | dfd001 ~ dfd003 | 22 | 23.65~23.67, 112.98~113.00 | 3 | 替代弹道导弹发射车 |
| UUV_RED | wruuv001 ~ wruuv003 | 22 | 0.06~0.20, 105.65~105.93 | 3 | 替代无人潜航器，作为水下作战平台 |

- **用途**：SSN 潜艇作为 DF-26 弹道导弹 / UUV 无人潜航器的等效海上打击平台
- 原 JSON 中 dfb/dfd 各 12 台、wruuv 5 台，功能合并为各 3 艘 SSN

## 未部署单元

| 平台类型 | 代表名称 | MCP 查询关键词 | 结果 | 替代方案 |
|----------|----------|---------------|------|----------|
| SAT_JIANBING23 | wxjb | "satellite" | 无结果（数据库无卫星条目） | 无等效替代，标注参考点 `RP_wxjb` |

> 数据库 `DB3K_504.db3` 以美制装备为主，中国 DF-26 地射车、UUV 查无结果；中国地面武器系统数据库条目严重缺失。
> 已通过功能近似的 SSN 688 Los Angeles（潜艇）替代 DF-26 发射车和 UUV，通过 E-3C Sentry AWACS 替代 KJ-500，通过 DDG 51 Arleigh Burke 替代补给舰。

## 打击链事件（Kill Chain Events）

| 事件名称 | 触发时间 | 内容 |
|----------|----------|------|
| KC_ST01_001_打击lha_meiguo | T0+0s | 打击两栖攻击舰 lha_meiguo |
| KC_ST01_002_打击tico_simoer | T0+0s | 打击巡洋舰 tico_simoer（含电子战+H-6K巡航导弹） |
| KC_ST01_002_评估tico | T0+2h10m | tico_simoer 打击效果评估 |
| KC_ST01_003_打击ddg_chafei | T0+0s | 打击驱逐舰 ddg_chafei |
| KC_ST01_003_评估ddg_chafei | T0+2h | ddg_chafei 打击效果评估 |
| KC_ST01_004_打击supply_kz | T0+0s | 打击补给舰 supply_kz |
| KC_ST01_005_打击ddg_momuseng | T0+0s | 打击驱逐舰 ddg_momuseng（含J-20A出击） |
| KC_ST01_005_评估ddg_momuseng | T0+2h | ddg_momuseng 打击效果评估 |
| RED_STATUS_REPORT | 每5分钟 | Red 方作战单元状态定期报告 |
| PHASE_END_REPORT | T0+2h40m | 反舰作战阶段结束，最终战果评估 |

## MCP DBID 查询记录

所有 DBID 均通过 `HKBQ_SqlDB` MCP 服务查询验证：

```
query_dbid("J-16D")           → dbid=4632 (J-16D Roaring Wolf)
query_dbid("J-20A")           → dbid=5012 (J-20A Fagin)
query_dbid("H-6K")            → dbid=4900 (H-6K Badger)
query_dbid("Ticonderoga")     → dbid=42 (CG 47 Ticonderoga Baseline 0)
query_dbid("Arleigh Burke")   → dbid=112 (DDG 51 Arleigh Burke Flight I)
query_dbid("LHA")             → dbid=502 (LHA 1 Tarawa)
query_dbid("SSN 688 LA")     → dbid=22 (SSN 688 Los Angeles Flight I) — 功能替代 DF-26/UUV
query_dbid("E-3 AWACS")       → dbid=209 (E-3C Sentry) — 功能替代 KJ-500
query_dbid("US Navy supply ship") → 无结果 → 用 DDG 51 Arleigh Burke 替代
query_dbid("DF missile")       → 无结果 → 用 SSN 688 替代
query_dbid("UUV")             → 无结果 → 用 SSN 688 替代
query_dbid("satellite")        → 无结果 → 无法替代，标注参考点

read_query: DataAircraftLoadouts WHERE ComponentID=4632 → LoadoutIDs={753,965,3482,3483,3828}
read_query: DataAircraftLoadouts WHERE ComponentID=5012 → LoadoutIDs={1191,3589}
read_query: DataAircraftLoadouts WHERE ComponentID=4900 → LoadoutIDs={1242}
read_query: DataAircraftLoadouts WHERE ComponentID=209  → LoadoutID=142
```

## 脚本使用说明

1. **在 CMO 场景编辑器中**：打开 Lua 控制台，加载本脚本
2. **或者作为 Event 脚本**：将脚本内容粘贴到场景加载事件（On Load）中
3. **注意事项**：
   - wxjb 卫星因数据库无卫星条目，无法替代，仅标注参考点 `RP_wxjb`
   - GUID 自动存入 KeyStore，格式为 `{unitName}_GUID`
   - 所有 `ScenEdit_AddUnit` 调用均使用 `pcall` 包裹，错误时打印警告而非崩溃

## 生成信息

| 字段 | 内容 |
|------|------|
| 原始文件 | plan_a1_001_legacy(1).json |
| 生成时间 | 2026-04-22 |
| AI 助手 | CMO Lua SKILL (Cursor) |
| DB 版本 | DB3K_504.db3 |
