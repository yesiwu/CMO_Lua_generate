# 055 vs DDG-113 1v1 打击场景

## 场景概述

| 项目 | 内容 |
|------|------|
| 红方 | 055型驱逐舰（南昌舰），装载16枚YJ-18 |
| 蓝方 | DDG-113 John Finn（阿利·伯克级Flight IIA） |
| 打击目标 | 13枚YJ-18攻击DDG-113 |
| 区域 | 南海 |

## DBID 信息

| 装备 | DBID | 数据来源 |
|------|------|---------|
| Type 055 Renhai | 3883 | MCP查询 |
| DDG-113 John Finn | 4299 | MCP查询 |
| YJ-18 | 2868 | 用户指定 |

## 脚本执行顺序

### 1. main.lua - 场景初始化
```bash
# 在CMO Lua控制台运行
dofile("outputs/lua/20260703_095000_055_vs_Burke_1v1/main.lua")
```
- 创建红方、蓝方阵营
- 设置红蓝敌对关系
- 红方设置全知全能 (OMNI)
- 部署055和DDG-113单位

### 2. clear.lua - 清空待发弹
```bash
dofile("outputs/lua/20260703_095000_055_vs_Burke_1v1/clear.lua")
```
- 清空055现有待发弹

### 3. reload.lua - 装填弹药
```bash
dofile("outputs/lua/20260703_095000_055_vs_Burke_1v1/reload.lua")
```
- 为055装填16枚YJ-18

### 4. attack.lua - 执行打击
```bash
dofile("outputs/lua/20260703_095000_055_vs_Burke_1v1/attack.lua")
```
- 发射13枚YJ-18攻击DDG-113

## 关键设计

1. **蓝方autodetectable**: DDG-113创建时设置`autodetectable=true`，确保红方全知后能稳定获得contact
2. **contact攻击模式**: 使用`ScenEdit_AttackContact`进行精确打击，不使用BOL
3. **全知全能**: 红方通过`ScenEdit_SetSideOptions`设置为OMNI，自动发现所有蓝方单位

## 单位位置

| 单位 | 纬度 | 经度 | 航向 | 航速 |
|------|------|------|------|------|
| 055-南昌舰 | 15.0°N | 115.0°E | 东(90°) | 15节 |
| DDG-113 | 13.5°N | 117.0°E | 西(270°) | 12节 |

两舰相距约100海里，符合YJ-18有效射程。
