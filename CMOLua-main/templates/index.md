# Lua 模板索引（补充版）

## 新增模板分类

### 舰载机操作 (carrier-ops/)

- `aircraft-launch.lua` - 舰载机起飞三步（创建→准备时间归零→launch）
- `aircraft-return.lua` - 舰载机返航两步（base→rtb）
- `carrier-strike-cycle.lua` - 完整打击周期（起飞→航路→延时攻击→延时返航）
- `formation-launch.lua` - 编队起飞（错开时间避免甲板拥堵）
- `carrier-group-ops.lua` - 航母打击群完整作业（CAP + 反舰 + 返航）

### 武器管理 (weapon-management/)

- `weapon-clear.lua` - 清弹（遍历挂载点，remove=true）
- `weapon-reload.lua` - 装弹（AddReloadsToUnit）
- `weapon-check.lua` - 弹药检查（Winchester/Bingo/OK）
- `fireAt.lua` - 攻击（自动选弹/指定弹种，含 contact 获取）

### 协同打击 (coordinated-strike/)

- `saturation-strike.lua` - 饱和攻击（多波次、多方向、时间协同）
- `tot-strike.lua` - TOT 时间协同（多平台同时到达）
- `scheduleLua.lua` - 通用延时调度器（触发器+事件+自清理）

### 战术条令 (tactical-doctrine/)

- `bait-and-ambush.lua` - 消耗与诱歼（诱饵前出→等待→伏击突击）
- `submarine-ambush.lua` - 隐蔽致命一击（潜艇伏击+电磁压制）

### 评估判断 (assessment/)

- `damage-assessment.lua` - 毁伤评估（检查目标损伤百分比）
- `mission-termination.lua` - 任务终止条件（损失/毁伤/超时）

## 使用示例

### 生成 5V3 场景

```
1. create-side.lua (红方/蓝方)
2. add-ship.lua (055, 052D, 辽宁舰)
3. add-aircraft.lua (J-15)
4. weapon-clear.lua (清弹)
5. weapon-reload.lua (装 YJ-18/YJ-83K)
6. aircraft-launch.lua (J-15 起飞)
7. fireAt.lua (舰艇攻击)
8. carrier-strike-cycle.lua (J-15 打击周期)
9. aircraft-return.lua (J-15 返航)
10. damage-assessment.lua (毁伤评估)
```

### 生成多轴饱和攻击

```
1. create-side.lua
2. add-ship.lua / add-aircraft.lua (多平台)
3. weapon-reload.lua
4. saturation-strike.lua (多波次调度)
5. damage-assessment.lua
6. mission-termination.lua
```

## 变量替换规则

所有模板使用 `{{变量名}}` 格式，AI 生成时替换为实际值：
- `{{SIDE}}` → "红方"
- `{{UNIT_NAME}}` → "055南昌舰"
- `{{DBID}}` → 3883
- `{{QTY}}` → 8

## 与 JSON 方案的映射

| JSON 字段 | 对应模板 |
|-----------|---------|
| basicInfo/sides | create-side.lua |
| units/ships | add-ship.lua |
| units/aircraft | add-aircraft.lua + aircraft-launch.lua |
| strikePlan/weaponEmployment | fireAt.lua + scheduleLua.lua |
| reloads | weapon-clear.lua + weapon-reload.lua |
| intentAnalysis/terminationStates | damage-assessment.lua + mission-termination.lua |
| 多波次/饱和攻击 | saturation-strike.lua |
| TOT 时间协同 | tot-strike.lua |
| 消耗与诱歼 | bait-and-ambush.lua |
| 隐蔽致命一击 | submarine-ambush.lua |
| 航母作业 | carrier-group-ops.lua |
