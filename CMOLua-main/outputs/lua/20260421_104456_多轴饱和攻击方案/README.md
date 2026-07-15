# 多轴饱和攻击方案 — README

## 方案信息

| 项目 | 内容 |
|------|------|
| 方案编号 | MASA001 |
| 方案名称 | 多轴饱和攻击方案 |
| 生成时间 | 2026-04-21 10:44:56 |
| 适用平台 | Command: Modern Operations |
| 红方 | RedForce (中国) |
| 蓝方 | BlueForce (美国) |

## 作战目的

摧毁蓝方护航驱逐舰与补给舰编队（至少2艘伯克级驱逐舰），压垮蓝方点防御能力。

## 作战时间轴

| 阶段 | 时间 | 内容 |
|------|------|------|
| 阶段1 | T+0M | 兵力机动集结 |
| 阶段2 | T+30M | J-16D电磁压制与目标确认 |
| 阶段3 | T+40M | 多轴饱和攻击（导弹齐射） |
| 阶段4 | T+60M | 打击效果评估与兵力撤收 |

## 红方参战平台

| 平台 | 数量 | 主要武器 |
|------|------|---------|
| 055型驱逐舰 | 2 | YJ-18反舰导弹（各8枚） |
| J-16战斗机 | 4 | YJ-12空射反舰导弹（各2枚） |
| J-16D电子战机 | 1 | 电子压制 |
| 039C型潜艇 | 1 | YJ-83潜射反舰导弹（4枚） |

## 蓝方目标

| 目标 | 类型 | DBID |
|------|------|------|
| 蓝方伯克舰1 | Arleigh Burke Flight IIA | 294 |
| 蓝方伯克舰2 | Arleigh Burke Flight IIA | 294 |
| 蓝方补给舰 | T-AO 187 Henry J. Kaiser | 26 |

## 数据库ID说明（均通过MCP查询）

所有 DBID、LoadoutID、WeaponID 均通过 MCP 查询 CMO 数据库获得，非编造数据：

- **DDG 055 Renhai** (dbid=2834): Type 055 Renhai [101 Nanchang]
- **Arleigh Burke Flight IIA** (dbid=294): DDG 79 Oscar Austin
- **T-AO Kaiser** (dbid=26): T-AO 187 Henry J. Kaiser [Mod Cimarron]
- **Type 039C Yuan** (dbid=695): Type 039C Yuan
- **J-16 Flying Shark** (dbid=2853): J-16 Flying Shark
- **J-16D Roaring Wolf** (dbid=4632): J-16D Roaring Wolf
- **YJ-12** (dbid=2862): 空射反舰导弹
- **YJ-18** (dbid=2867): 舰射冲压穿甲弹 [3M54E Klub Copy]
- **YJ-83** (dbid=541): 潜射导弹 [C-802A]
- **J-16 ASM Loadout** (loadoutid=1821): 含YJ-12 x2 + RAE设备
- **J-16D EW Loadout** (loadoutid=753): 电子战配置

## 脚本结构

```
main.lua
├── Section 1: 常量定义（DBID, LoadoutID, WeaponID）
├── Section 2: 辅助函数（阵营创建、态度设置）
├── Section 3: 创建红蓝阵营，设置敌对关系
├── Section 4: 创建红方单位（055x2, 039Cx1, J-16x4, J-16Dx1）
├── Section 5: 创建蓝方目标单位
├── Section 6: 创建参考点（电子战巡逻区、目标指示区）
├── Section 7: 设置作战条令（EMCON、火力控制状态）
├── Section 8: 创建任务（1个巡逻任务 + 7个打击任务）
├── Section 9: 分配单位到任务
├── Section 10: 特殊动作（手动发射控制）
├── Section 11: 时序事件（T+0M, T+30M, T+40M, T+60M）
└── Section 12: 指定打击目标
```

## 使用说明

1. 在 CMO 场景编辑器中加载此脚本（Console → Load Lua Script）
2. 脚本将自动创建双方阵营、单位、任务和时序事件
3. 阶段3（T+40M）将自动触发多轴饱和攻击
4. 可通过特殊动作手动控制各平台武器发射

## 注意事项

- 所有 DBID 均通过 MCP 实时查询确认
- 阵营名称：`RedForce`（红方）、`BlueForce`（蓝方）
- 事件脚本使用 `\r\n` 换行符
- 武器 DBID 使用 0 表示由系统自动选择武器
- 效果评估根据目标摧毁数量自动计分
