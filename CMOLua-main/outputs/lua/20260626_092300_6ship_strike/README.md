# 6舰对抗仿真 — 红方饱和打击

## 场景概述

| 项目 | 说明 |
|------|------|
| 场景类型 | 舰对舰饱和打击仿真 |
| 红方 | 3艘水面舰艇，全知模式 |
| 蓝方 | 3艘水面舰艇（静止目标） |
| 红蓝关系 | 敌对（H=Hostile） |

## 双方单位

### 蓝方（Blue）

| 单元名 | 类型 | 近似 DBID | 坐标 (Lon, Lat) | 朝向 |
|--------|------|-----------|------------------|------|
| DDG-113 | Arleigh Burke | 112 | (129.9125, 21.5419) | 294.05° |
| Blue-CG59 | CG 59 Princeton | 2869 | (130.1791, 21.6100) | 294.58° |
| Blue-CVN70 | CVN 70 Carl Vinson | 3551 | (130.1713, 21.4200) | 293.16° |

> 注：DDG-113 在 CMO 数据库中无精确匹配，用 DDG 51 Arleigh Burke (DBID=112) 替代。

### 红方（Red）

| 单元名 | 类型 | DBID | 坐标 (Lon, Lat) | 朝向 | 待发弹 |
|--------|------|------|------------------|------|--------|
| Red-052D-Alpha | Type 052D | 2296 | (123.451, 21.1437) | 115° | YJ-21 ×16 |
| Red-052D-Beta | Type 052D | 2296 | (123.988, 18.2035) | 50° | YJ-18 ×16, YJ-21 ×16 |
| Red-055-Alpha | Type 055 Renhai | 2834 | (128.583, 24.8324) | 135° | YJ-18 ×32 |

## 武器 DBID（MCP 查询）

| 武器 | DBID |
|------|------|
| YJ-21 [800kg HE] | 4058 |
| YJ-18 [3M54E Klub] | 2868 |

## 打击方案

| 攻击方 | 目标 | 武器 | 数量 |
|--------|------|------|------|
| Red-052D-Alpha | DDG-113 | YJ-21 | 4枚 |
| Red-052D-Beta | Blue-CVN70 | YJ-21 | 6枚 |
| Red-055-Alpha | Blue-CG59 | YJ-18 | 7枚 |

## 使用方法

在 CMO Lua 控制台**依次**执行：

```
1. main.lua   → 创建双方阵营和6艘舰艇单位
2. reload.lua → 为红方3舰装填弹药
3. attack.lua → 下达打击指令
```

## 注意事项

1. **GUID 存储**：各单元 GUID 通过 `ScenEdit_SetKeyValue` 存入 KeyStore，可在后续脚本中通过 `ScenEdit_GetKeyValue` 取用
2. **全知模式**：红方 `ScenEdit_SetEMCON` 设为雷达主动，并配合 `ignore_plotted_course=no`，打击系统自动选择 contact 精确打击
3. **BOL 降级**：若 contact 中未发现目标，脚本会自动降级为 BOL（Bearing Only Launch）朝坐标发射模式
4. **装弹上限**：实际装弹数量受该舰 VLS 格口数限制，脚本会静默截断超出部分
5. **DBID 替代说明**：
   - 用户指定 DDG-113 数据库无精确匹配 → 用 DDG 51 (DBID=112) 替代
   - 用户指定 DBID 2862 → 查到 CG 59 Princeton (DBID=2869)
   - 用户指定 DBID 3551 → CVN 70 Carl Vinson (DBID=3551)，精确匹配

## 验证清单

- [x] `dbid` 通过 MCP 查询（严禁硬编码）
- [x] 所有单位 type 为 `Ship`（非 Air/Ground）
- [x] `latitude` / `longitude` / `heading` 参数名正确
- [x] 阵营通过 `ScenEdit_AddSide` 创建
- [x] 敌对关系通过 `ScenEdit_SetSidePosture` 设置
- [x] 红方 EMCON 设为雷达主动（全知作战）
- [x] `errors/index.md` 无匹配问题
