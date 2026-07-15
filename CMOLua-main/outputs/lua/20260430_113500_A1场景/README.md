# 联合火力突击训练场景 (A1场景)

## 方案概述

- **方案名称**: 联合火力突击训练场景 (A1场景)
- **原始文件**: `json/A1场景.json`
- **场景时间**: 2025/10/27 15:00:00
- **作战地域**: 南海海域（蓝方航母编队约 -0.66°N, 105.81°E）
- **参演方**: 红方（攻） vs 蓝方（守）

## 作战企图

蓝方以 CVN 林肯号航母为核心的两栖/水面编队在南海活动。红方整合天基、电子、航空侦察资源，对蓝方编队实施多域联合火力打击，核心目标是摧毁蓝方航母。

---

## 参战平台

### 红方

| 类别 | 装备 | 数量 | DBID | LoadoutID | 位置 |
|------|------|------|------|-----------|------|
| 地基反舰导弹 | DF-26B 发射车 | 10 | 2879 | — | Lat 18.5°, Lon 110° |
| 地基反舰导弹 | DF-26D 发射车 | 5 | 2879 | — | Lat 18.5°, Lon 110° |
| 电子战飞机 | J-16D | 7 | 4632 | 753 | Lat 9.9°, Lon 115.5° |
| 轰炸机 | H-6K | 6 | 140 | 87 | Lat 9.7°, Lon 115.3° |
| 预警机 | KJ-500 | 2 | 3683 | 494 | Lat 9.6°, Lon 115.4° |
| 隐身战斗机 | J-20A | 8 | 5012 | 1191 | Lat 10.2°, Lon 114.2° |
| 多用途战机 | J-16 | 10 | 2853 | 1821 | Lat 9.5-10.9°, Lon 113-114° |
| 无人潜航器 | UUV (Remus 600) | 10 | 490 | — | Lat 0-3°, Lon 105-106° |
| 常规潜艇 | 039C (接近 039B Yuan) | 2 | 577 | — | Lat 1-5.7°, Lon 105-107° |
| 驱逐舰 | 052D Luyang III | 3 | 2296 | — | Lat 5.7-6.1°, Lon 108.2-108.9° |
| 万吨驱逐舰 | 055 Renhai | 1 | 2834 | — | Lat 6.14°, Lon 108.60° |
| 护卫舰 | 054A Jiangkai II | 4 | 1965 | — | Lat 5.6-5.9°, Lon 108.2-108.4° |

### 蓝方（目标编队）

| 类别 | 装备 | 数量 | DBID | LoadoutID | 位置 |
|------|------|------|------|-----------|------|
| 航母 | CVN 林肯号 (Nimitz) | 1 | 34 | — | Lat -0.66°, Lon 105.81° |
| 巡洋舰 | CG-47 Ticonderoga | 1 | 42 | — | Lat -0.66°, Lon 105.81° |
| 驱逐舰 | DDG-51 Arleigh Burke | 5 | 112 | — | Lat -1.5°~7.1°, Lon 106°~116° |
| 护卫舰 | FFG-62 Constellation | 1 | 3229 | — | Lat 8°, Lon 116° |
| 两栖攻击舰 | LHD-1 Wasp (近似 LHA) | 1 | 170 | — | Lat 1°, Lon 106° |
| 补给舰 | T-AKE 1 Lewis and Clark | 1 | 753 | — | Lat -0.1°, Lon 106.16° |
| 无人水面艇 | USV (Spruance 级近似) | 3 | 114 | — | Lat 7°, Lon 115° |
| 海洋监视船 | AGOS | 3 | 170 | — | Lat 0-0.4°, Lon 106.8-107.2° |
| 隐身战斗机 | F-35C Lightning II | 3 | 824 | 689 | Lat -0.72°, Lon 106.12° |
| 隐身战斗机 | F-35B Lightning II | 4 | 534 | 184 | Lat -0.8°, Lon 106.2° |
| 轰炸机 | H-6K | 6 | 140 | 87 | Lat 6-7°, Lon 115.8-116.2° |
| 火箭炮 | HIMARS / M270 MLRS | 9 | 18 | — | Lat 7.5-7.7°, Lon 116° |
| 防空系统 | Patriot | 4 | 33 | — | Lat 7.8-7.9°, Lon 116° |

> DBID/LoadoutID 来源: MCP HKBQ_SqlDB 查询（2026-04-30），禁止硬编码。
> 部分装备（如 UUV_RED、AGOS_VICTORIOUS、USV_OVERLORD）在 CMO 数据库中无精确匹配型号，使用最接近替代型号并标注。

---

## 作战时间线

```
T+0H   [Phase 1] 侦察与部署
        ├─ 全部平台进入侦察/巡逻状态
        ├─ KJ-500 预警机大范围侦察
        ├─ J-16D 电子战飞机待机
        └─ 潜艇/UUV 向蓝方编队方向机动
T+30M  [Phase 2] 联合火力突击开始
        ├─ DF-26B/D 反舰弹道导弹对蓝方航母编队发起第一波次攻击
        ├─ J-16D 全面开启电子压制模式
        └─ 蓝方 F-35 CAP 起飞拦截
T+40M  [Phase 2续] 空中打击编队前出
        ├─ H-6K 轰炸机 + J-16 机群发起导弹攻击
        └─ 蓝方防空系统全力运转
T+60M  [Phase 3] 第二波次打击
        ├─ 052D/055/054A 水面舰艇发起协同反舰攻击
        └─ 蓝方 H-6K 起飞反击
T+120M [Phase 3] 战果评估
        └─ 双方评估战损
```

---

## 任务列表

| 任务 ID | 名称 | 方 | 类型 | 激活时机 |
|---------|------|-----|------|---------|
| M01 | DF-26 打击 | 红 | Strike/Naval | T+30M |
| M02 | H-6K 轰炸打击 | 红 | Strike/Naval | T+40M |
| M03 | J-16 空中打击 | 红 | Strike/Naval | T+40M |
| M04 | J-16D 电子战 | 红 | Patrol/SEAD | T+30M |
| M05 | J-20 空中优势 | 红 | Patrol/Air | T+0 |
| M06 | KJ-500 预警 | 红 | Patrol/Air | T+0 |
| M07 | 水面舰打击 | 红 | Strike/Naval | T+60M |
| M08 | 潜艇/UUV 巡逻 | 红 | Patrol/Sub | T+0 |
| M11 | F-35 CAP | 蓝 | Patrol/Air | T+30M |
| M12 | 蓝方轰炸 | 蓝 | Strike/Naval | T+60M |
| M13 | 蓝方防空 | 蓝 | Patrol/Naval | T+0 |

---

## 事件系统

| 事件 | 触发 | 动作 |
|------|------|------|
| EV_A_作战开始 | ScenLoaded | 双方进入 Phase 1 |
| EV_T30_联合打击 | T+30min | 激活 M01 DF-26打击 + M04 电子战 + M11 F-35 CAP |
| EV_T40_空中前出 | T+40min | 激活 M02 H-6K + M03 J-16 打击 |
| EV_T60_第二波次 | T+60min | 激活 M07 水面舰打击 + M12 蓝方反击 |
| EV_T120_战果评估 | T+120min | 双方评估通知 |
| EV_红方胜利_CVN | CVN≥70%受损 | 红方+100 / 蓝方-100 |
| EV_红方胜利_舰艇 | DDG≥50%受损 | 红方+50 |
| EV_蓝方胜利_055 | 055≥60%受损 | 蓝方+100 / 红方-50 |

---

## 使用方法

1. **加载 main.lua**：在 CMO Lua Console 中执行，完成所有单位部署
2. **加载 mission.lua**：继续执行，完成任务和事件链设置
3. **运行场景**：按时间线自动执行各阶段作战

---

## MCP 数据来源

| 查询内容 | MCP 工具 | 关键词 |
|---------|---------|--------|
| J-16 / J-16D DBID | `query_dbid` | "J-16", "J-16D" |
| J-20 DBID | `read_query` | `WHERE Name LIKE '%J-20%'` |
| KJ-500 DBID | `read_query` | `WHERE Name LIKE '%KJ-500%'` |
| H-6K DBID | `query_dbid` | "H-6 bomber" |
| 052D/055/054A DBID | `read_query` | `WHERE Name LIKE '%052D%'` / '%055%' / '%054A%'` |
| F-35C/B DBID | `query_dbid` | "F-35C Lightning", "F-35B Lightning" |
| CVN/Ticonderoga DBID | `read_query` | `WHERE Name LIKE '%Nimitz%'` / '%Ticonderoga%'` |
| DF-26/Patriot/HIMARS DBID | `read_query` | `WHERE Name LIKE '%DF-26%'` / '%Patriot%'` / '%M270%'` |
| LoadoutID | `read_query` | `SELECT ID FROM DataAircraftLoadouts WHERE ComponentID = ...` |

---

## DBID 替代说明

以下 JSON 中的装备类型在 CMO DB3K_504.db3 中无精确匹配，使用最接近替代型号：

| JSON EquipmentType | JSON 装备名 | CMO 替代 DBID | 说明 |
|---|---|---|---|
| UUV_RED | UUV 无人潜航器 | 490 (Remus 600) | UUV 类 |
| SUB_039C | 039C 常规潜艇 | 577 (Type 039B Yuan) | 039 系列 |
| CVN_LINCOLN | CVN 林肯号 | 34 (CVN-69 Eisenhower) | Nimitz 级 |
| DDG_CHAFEE | DDG Chafee | 112 (DDG-51 Burke) | Arleigh Burke 级 |
| LHA_AMERICA | LHA 美国号 | 170 (LHD-1 Wasp) | America 级近似 |
| USV_OVERLORD | USV 无人艇 | 114 (DD-963 Spruance) | 水面战斗舰 |
| AGOS_VICTORIOUS | 海洋监视船 | 170 (LHD-1 Wasp) | 辅助舰艇近似 |
| GND_HMS_LAUNCHER | HIMARS | 18 (M270 MLRS) | 火箭炮系统 |
| UAV_YILONG2D | 翼龙-2D 无人机 | 276 (CH-47D Chinook) | 无人机近似 |

> 如需精确匹配，请使用更高版本的 CMO 数据库（如 DB3K_514.db3）重新查询。

---

## 文件清单

```
outputs/lua/20260430_113500_A1场景/
├── main.lua    # 单位创建脚本（先执行）
├── mission.lua # 任务规划脚本（后执行）
└── README.md   # 本文件
```
