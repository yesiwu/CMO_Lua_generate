# 有限反击训练场景 (A24场景) — CMO Lua 脚本说明

## 方案概述

| 字段 | 内容 |
|------|------|
| 方案名称 | 有限反击训练场景 |
| 方案ID | zzcjxxxxxx0 |
| 所属方 | 红方部队 / 蓝方部队 |
| 方案时间 | 2025/10/26 17:20:00 |
| 场景描述 | 东部方向进入战役阶段，蓝方在南部方向增强行动强度。红蓝双方大量水面/空中/太空力量对峙。 |
| 安全等级 | 秘密 |

## MCP DBID 查询结果

### Blue 方

| JSON EquipmentType | DBID (MCP) | CMO 型号 | 部署 | 备注 |
|-------------------|-------------|---------|------|------|
| CVN_LINCOLN | 246 | CVN 70 Carl Vinson Nimitz | ✅ | MCP: `query_dbid("CVN 70 Carl Vinson")` |
| Ticonderoga | 42 | CG 47 Ticonderoga Baseline 0 | ✅ | MCP: `query_dbid("Ticonderoga")` |
| LHA_AMERICA | 2362 | LHA 6 America Flight 0 | ✅ | MCP: `query_dbid("LHA")` |
| AGOS_VICTORIOUS | 365 | T-AGOS 19 Victorious SWATH | ✅ | MCP: `query_dbid("AGOS")` |
| AC_F35C_LIGHTNING | 824 | F-35C Lightning II | ✅ | MCP: `query_dbid("F-35C Lightning")`, LoadoutID=689 |
| F35B | 534 | F-35B Lightning II | ✅ | MCP: `query_dbid("F-35B")`, LoadoutID=184 |
| DDG_CHAFEE | — | — | ❌ 跳过 | MCP: `query_dbid("DDG CHAFEE")` 无结果 |
| AUX_KZ_SUPPLY | — | — | ❌ 跳过 | MCP: `query_dbid("US Navy supply ship")` 无结果 |
| FFG_RICHMOND | — | — | ❌ 跳过 | MCP: `query_dbid("FFG Richmond")` 无结果 |
| USV_OVERLORD | — | — | ❌ 跳过 | MCP: `query_dbid("overlord")` 无结果 |
| GND_HMS_LAUNCHER | — | — | ❌ 跳过 | MCP: `query_dbid("HIMARS")` 无结果 |
| GND_TYPHON_LAUNCHER | — | — | ❌ 跳过 | MCP: `query_dbid("Aegis ground")` 无结果 |

### Red 方

| JSON EquipmentType | DBID (MCP) | CMO 型号 | 部署 | 备注 |
|-------------------|-------------|---------|------|------|
| AC_J16D | 4632 | J-16D Roaring Wolf | ✅ | MCP: `query_dbid("J-16D")`, LoadoutIDs={753,965,3482,3483,3828} |
| BOMBER_H6K | 4900 | H-6K Badger | ✅ | MCP: `query_dbid("H-6K")`, LoadoutID={1242} |
| AC_J20 | 5012 | J-20A Fagin | ✅ | MCP: `query_dbid("J-20A")`, LoadoutIDs={1191,3589} |
| AC_J16 | 2853 | J-16 Flying Shark (Su-30MKK) | ✅ | MCP: `query_dbid("J-16 fighter")`, LoadoutIDs={1821,3272} |
| UAV_YILONG2D | 4725 | GJ-2 Wing Loong II UCAV | ✅ | MCP: `query_dbid("Wing Loong")`, LoadoutID=2179 |
| AWACS_KJ500 → 替代 | 209 | E-3C Sentry AWACS | ✅ | 功能替代，预警探测能力等效 |
| UAV_LONG_ENDURANCE → 替代 | 3310 | GJ-1 Wing Loong I | ✅ | 功能替代，x3 代表 |
| SAT_JIANBING23 | — | — | ❌ 跳过 | 数据库无卫星条目 |
| GND_DF17_LAUNCHER | — | — | ❌ 跳过 | MCP: `query_dbid("DF conventional")` 无结果 |
| GND_DF26B_LAUNCHER | — | — | ❌ 跳过 | MCP: `query_dbid("DF missile")` 无结果 |
| DDG_055 | — | — | ❌ 跳过 | MCP: `query_dbid("Type 055 destroyer")` 无结果 |
| UUV_RED | — | — | ❌ 跳过 | MCP: `query_dbid("UUV")` 无结果 |
| EW_YUNLEIGAN9 | — | — | ✅ 已合并 | 等同于 J-16D，合并到 AC_J16D 组 |

## 已部署单元清单

### Blue 方（10 单元）

| 名称 | CMO 型号 | DBID | 坐标 (Lat, Lon) |
|------|---------|------|-----------------|
| CVN_LINCOLN_001 | CVN 70 Carl Vinson | 246 | -1.83, 107.78 |
| CG_BLUE_001 | CG 47 Ticonderoga Baseline 0 | 42 | -1.72, 107.45 |
| CG_BLUE_002 | CG 47 Ticonderoga Baseline 0 | 42 | 6.94, 118.36 |
| LHA_BLUE_001 | LHA 6 America Flight 0 | 2362 | 6.57, 118.95 |
| AGOS_VICTORIOUS_001 | T-AGOS 19 Victorious SWATH | 365 | 19.72, 124.75 |
| AGOS_VICTORIOUS_002 | T-AGOS 19 Victorious SWATH | 365 | 20.29, 119.57 |
| AGOS_VICTORIOUS_003 | T-AGOS 19 Victorious SWATH | 365 | 14.06, 119.20 |
| AC_F35C_LIGHTNING_001~004 | F-35C Lightning II | 824 | 见坐标表 |
| F-35B_001, F-35B_002 | F-35B Lightning II | 534 | 见坐标表 |

### Red 方（43 单元 + 替代 5 单元）

| 类型 | CMO 型号 | DBID | 数量 |
|------|---------|------|------|
| J-16D Roaring Wolf (含 EW_YUNLEIGAN9) | J-16D EW Variant | 4632 | 6 |
| H-6K Badger | H-6K Badger | 4900 | 8 |
| J-20A Fagin | J-20A Fagin | 5012 | 8 |
| J-16 Flying Shark (Su-30MKK) | J-16 Flying Shark | 2853 | 15 |
| GJ-2 Wing Loong II UCAV | GJ-2 Wing Loong II | 4725 | 3 |
| GJ-1 Wing Loong I (UAV_LONG proxy) | GJ-1 Wing Loong I | 3310 | 3 |
| E-3C Sentry (KJ-500 proxy) | E-3C Sentry AWACS | 209 | 2 |

## 跳过的单元

| 方 | EquipmentType | 数量 | 原因 |
|----|-------------|------|------|
| BLUE | DDG_CHAFEE | 8 | MCP 无结果 |
| BLUE | AUX_KZ_SUPPLY | 1 | MCP 无结果 |
| BLUE | FFG_RICHMOND | 1 | MCP 无结果 |
| BLUE | USV_OVERLORD | 6 | MCP 无结果 |
| BLUE | GND_HMS_LAUNCHER | 9 | MCP 无结果 |
| BLUE | GND_TYPHON_LAUNCHER | 4 | MCP 无结果 |
| RED | SAT_JIANBING23 | 50 | 数据库无卫星 |
| RED | GND_DF17_LAUNCHER | 2 | MCP 无结果 |
| RED | GND_DF26B_LAUNCHER | 4 | MCP 无结果 |
| RED | DDG_055 | 7 | MCP 无结果 |
| RED | UUV_RED | 29 | MCP 无结果 |

## 脚本使用说明

1. **在 CMO 场景编辑器中**：打开 Lua 控制台，加载本脚本
2. **或者作为 Event 脚本**：将脚本内容粘贴到场景加载事件（On Load）中
3. 所有 `ScenEdit_AddUnit` 调用均使用 `pcall` 包裹，错误时打印警告而非崩溃
4. GUID 自动存入 KeyStore，格式为 `{unitName}_GUID`

## 生成信息

| 字段 | 内容 |
|------|------|
| 原始文件 | A24场景.json |
| 生成时间 | 2026-04-22 |
| AI 助手 | CMO Lua SKILL (Cursor) |
| DB 版本 | DB3K_504.db3 |
