# plan_a1_001_legacy - 联合反击作战方案

## 方案信息

| 字段 | 值 |
|------|-----|
| 方案编号 | 2026B |
| 方案名称 | 联合火力突击训练场景 |
| 作战方 | 红方部队 |
| 作战时间 | 2025-10-27 13:30:00 |
| 方案类别 | 联合反击 |
| 关键词 | 联合打击，预定目标，多平台协同 |

## 作战目的

- 空中编队遭袭后，组织反制（控权、歼敌）
- 慑敌制敌，稳局控局
- 弹群组网，协同突击

## 打击目标（Blue Side）

| 目标名称 | 装备类型 | 坐标 | 说明 |
|---------|---------|------|------|
| tico_simoer | CG 56 San Jacinto [Ticonderoga] | 7.97N, 119.50E | 提康德罗加级巡洋舰 |
| ddg_chafei | DDG 72 Mahan [Arleigh Burke FII] | 8.28N, 119.78E | 伯克级驱逐舰 |
| lha_meiguo | LHD 1 Wasp [Amphibious Assault] | 7.92N, 120.09E | 黄蜂级两栖攻击舰 |
| supply_kz | T-AKE 1 Lewis and Clark | 0.10S, 106.16E | 战斗后勤舰 |
| ddg_momuseng | DDG 72 Mahan [Arleigh Burke FII] | 7.10N, 116.28E | 伯克级驱逐舰 |

## 红方作战集群

### 侦察集群
- 卫星（SJIANBING23）：天基侦察监视

### 作战集群
- DF-26B导弹发射车 x12：反舰弹道导弹打击
- DF-26D导弹发射车 x12：反舰弹道导弹打击

### 网电集群
- J-16D电子战飞机 x4：电磁干扰压制

### 空中作战集群
- H-6K轰炸机 x6：对地/对海巡航导弹攻击
- KJ-500预警机 x1：空中预警指挥
- J-20A战斗机 x4：对海打击/制空

### 海上集群
- 无人潜航器（UUV_RED）x5：侦察监视

## Kill Chain 时序

| 时间 | 事件 |
|------|------|
| T0 | 所有打击平台激活，导弹发射 |
| T0+1H46M | 卫星发现 chafei / momuseng |
| T0+1H47M | 卫星发现 lha_meiguo |
| T0+1H48M | 卫星定位 lha_meiguo |
| T0+1H49M | 卫星跟踪/瞄准 chafei / momuseng / lha_meiguo |
| T0+1H50M | 瞄准 lha_meiguo |
| T0+1H52M | 卫星发现 tico_simoer |
| T0+1H53M | 卫星跟踪 tico_simoer；发现 supply_kz |
| T0+1H55M | 瞄准 tico_simoer；电子战飞机起飞 |
| T0+1H56M | 瞄准 supply_kz |
| T0+2H10M | 各目标毁伤评估开始 |
| T0+2H24M | tico_simoer/chafei/lha/momuseng 毁评完成 |
| T0+2H30M | supply_kz 毁评完成 |

## MCP 查询结果

### 红方装备 DBID（通过 MCP 查询）
- J-16D Roaring Wolf: DBID=4632, LoadoutID=753
- H-6K Badger: DBID=1731, LoadoutID=863
- KJ-500 Cub [GX9]: DBID=3683, LoadoutID=494
- J-20A Fagin: DBID=5012, LoadoutID=1191
- J-20B Fagin: DBID=2463, LoadoutID=198
- DF-26 SSM Battalion: DBID=89 (DF-21C CSS-5 代理)

### 蓝方装备 DBID（通过 MCP 查询）
- CG 56 San Jacinto [Ticonderoga]: DBID=40
- DDG 72 Mahan [Arleigh Burke FII]: DBID=111
- LHD 1 Wasp [Amphibious]: DBID=170
- T-AKE 1 Lewis and Clark: DBID=753

## 跳过的单位（MCP 未找到）

| 单位 | 原因 |
|------|------|
| SAT_JIANBING23（卫星） | CMO 数据库中无天基卫星模型 |
| UUV_RED（无人潜航器）x5 | CMO 数据库中无中国 UUV 对应型号 |

## 使用方法

1. 在 CMO 中打开对应场景
2. 将 `main.lua` 内容复制到 CMO Lua 控制台执行
3. 场景初始化后，各打击平台和事件将自动按时间线执行
4. 红方特别消息将显示在红方消息窗口

## 注意事项

- DF-26B/D 导弹在 CMO 中以 SSM Bn (DF-21C) 代理，因为 CMO 不包含 DF-26 的独立模型
- 天基卫星侦察在 CMO 中无法真实模拟，事件仅作为信息提示
- 所有武器发射由任务系统（Mission）自动处理
- 毁伤评估通过定时事件触发，实际结果取决于武器命中情况
