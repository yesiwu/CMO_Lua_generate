# 055 vs Burke 1v1 场景

## 场景概述

- **红方**: Type 055 Renhai (DBID 3883, YJ-21版)
- **蓝方**: DDG-51 Arleigh Burke (DBID 112)
- **武器**: YJ-18 反舰导弹 (DBID 2868)
- **位置**: 南海

## DBID 查询记录

| 单位/武器 | DBID | 来源 |
|-----------|------|------|
| Type 055 Renhai | 3883 | MCP查询 + 用户指定 |
| DDG-51 Arleigh Burke | 112 | MCP查询 |
| YJ-18 | 2868 | 用户指定 |

## 执行顺序

```bash
1. main.lua   # 创建红蓝方单位，设置全知全能
2. clear.lua  # 清空055现有待发弹
3. reload.lua # 为055装填16枚YJ-18
4. attack.lua # 发射13枚YJ-18攻击Burke
```

## 关键配置

- **红方全知全能**: `ScenEdit_SetSideOptions({side="红方", awareness="OMNI"})`
- **敌对关系**: `ScenEdit_SetSidePosture`
- **autodetectable**: 蓝方Burke设置为可探测
- **contact攻击**: 优先使用contact GUID打击

## 文件结构

```
20260703_094200_055_vs_Burke_1v1/
├── main.lua    # 创建单位
├── clear.lua   # 清弹
├── reload.lua  # 装弹
├── attack.lua  # 打击
└── README.md   # 本文档
```
