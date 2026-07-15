-- ============================================================
-- 多轴饱和攻击方案 (Multi-Axis Saturation Attack Plan)
-- 生成时间: 2026-04-20
-- 方案编号: MASA001
-- 红方: 中国 (China)
-- 蓝方: 美国 (US)
-- ============================================================

print("========================================")
print("多轴饱和攻击方案 - 开始加载")
print("========================================")

-- ============================================================
-- 第一部分：阵营创建与关系设定
-- ============================================================

-- 创建红方阵营
ScenEdit_AddSide({
    name = "China",
    posture = "F"
})

-- 创建蓝方阵营
ScenEdit_AddSide({
    name = "US",
    posture = "H"
})

-- 设置红蓝双方为敌对关系 (正确API: ScenEdit_SetSidePosture)
-- 参数: sideA, sideB, posture (H=敌对, F=友好, N=中立, U=不友好)
ScenEdit_SetSidePosture("China", "US", "H")
ScenEdit_SetSidePosture("US", "China", "H")

print("阵营创建完成: China (红方) vs US (蓝方)")

-- ============================================================
-- 第二部分：红方单位创建
-- ============================================================
-- DBID 参考:
--   Type 055 Renhai: 2834 (Ship)
--   J-16 Flying Shark: 2853 (Aircraft)
--   J-16D Roaring Wolf: 4632 (Aircraft)
--   Type 039C Yuan: 695 (Submarine)
-- LoadoutID 参考:
--   J-16: 1821 (反舰配置), 3272 (对地配置)
--   J-16D: 753 (电子战配置)
-- ============================================================

-- 2.1 红方055型驱逐舰 #1
ScenEdit_AddUnit({
    side = "China",
    type = "Ship",
    dbid = 2834,
    name = "红方055驱逐舰1 [Nanchang]",
    latitude = 30.166666666666668,
    longitude = 123.5,
    altitude = 0,
    heading = 90,
    speed = 20
})

-- 2.2 红方055型驱逐舰 #2
ScenEdit_AddUnit({
    side = "China",
    type = "Ship",
    dbid = 2834,
    name = "红方055驱逐舰2 [Nanchang]",
    latitude = 29.833333333333332,
    longitude = 123.83333333333333,
    altitude = 0,
    heading = 90,
    speed = 20
})

-- 2.3 红方039C型潜艇
ScenEdit_AddUnit({
    side = "China",
    type = "Submarine",
    dbid = 695,
    name = "红方039C潜艇1",
    latitude = 30.5,
    longitude = 126.16666666666667,
    altitude = 60,
    heading = 135,
    speed = 8
})

-- 2.4 红方J-16战斗机 #1 (带反舰导弹配置)
ScenEdit_AddUnit({
    side = "China",
    type = "Aircraft",
    dbid = 2853,
    name = "红方J-16_1",
    latitude = 30.0,
    longitude = 122.0,
    altitude = 7620,
    heading = 90,
    speed = 250,
    LoadoutID = 1821
})

-- 2.5 红方J-16战斗机 #2
ScenEdit_AddUnit({
    side = "China",
    type = "Aircraft",
    dbid = 2853,
    name = "红方J-16_2",
    latitude = 30.083333333333332,
    longitude = 122.16666666666667,
    altitude = 7620,
    heading = 90,
    speed = 250,
    LoadoutID = 1821
})

-- 2.6 红方J-16战斗机 #3
ScenEdit_AddUnit({
    side = "China",
    type = "Aircraft",
    dbid = 2853,
    name = "红方J-16_3",
    latitude = 29.916666666666668,
    longitude = 122.08333333333333,
    altitude = 7315,
    heading = 0,
    speed = 250,
    LoadoutID = 1821
})

-- 2.7 红方J-16战斗机 #4
ScenEdit_AddUnit({
    side = "China",
    type = "Aircraft",
    dbid = 2853,
    name = "红方J-16_4",
    latitude = 30.033333333333335,
    longitude = 122.25,
    altitude = 7315,
    heading = 90,
    speed = 250,
    LoadoutID = 1821
})

-- 2.8 红方J-16D电子战机
ScenEdit_AddUnit({
    side = "China",
    type = "Aircraft",
    dbid = 4632,
    name = "红方J-16D_1",
    latitude = 30.133333333333333,
    longitude = 123.0,
    altitude = 8534,
    heading = 90,
    speed = 250,
    LoadoutID = 753
})

print("红方单位创建完成: 2x055驱逐舰, 1x039C潜艇, 4xJ-16, 1xJ-16D")

-- ============================================================
-- 第三部分：蓝方目标单位创建
-- ============================================================
-- DBID 参考:
--   Arleigh Burke Flight IIA: 294 (DDG 79 Oscar Austin)
--   补给舰: 57 (629 Durance)
-- ============================================================

-- 3.1 蓝方伯克级驱逐舰 #1
ScenEdit_AddUnit({
    side = "US",
    type = "Ship",
    dbid = 294,
    name = "蓝方伯克舰1",
    latitude = 30.333333333333332,
    longitude = 127.5,
    altitude = 0,
    heading = 0,
    speed = 0
})

-- 3.2 蓝方伯克级驱逐舰 #2
ScenEdit_AddUnit({
    side = "US",
    type = "Ship",
    dbid = 294,
    name = "蓝方伯克舰2",
    latitude = 30.0,
    longitude = 127.75,
    altitude = 0,
    heading = 0,
    speed = 0
})

-- 3.3 蓝方补给舰
ScenEdit_AddUnit({
    side = "US",
    type = "Ship",
    dbid = 57,
    name = "蓝方补给舰",
    latitude = 30.166666666666668,
    longitude = 127.25,
    altitude = 0,
    heading = 0,
    speed = 0
})

print("蓝方目标创建完成: 2x伯克级驱逐舰, 1x补给舰")

-- ============================================================
-- 第四部分：任务创建
-- ============================================================

-- 4.1 J-16D电子战巡逻任务 (SEA=海上巡逻)
ScenEdit_AddMission({
    side = "China",
    name = "J-16D电磁压制巡逻",
    type = "Patrol",
    subtype = "SEA"
})

-- 4.2 J-16_1 反舰打击任务 (对海打击)
ScenEdit_AddMission({
    side = "China",
    name = "J-16_1反舰任务",
    type = "Strike",
    subtype = "SEA"
})

-- 4.3 J-16_2 反舰打击任务
ScenEdit_AddMission({
    side = "China",
    name = "J-16_2反舰任务",
    type = "Strike",
    subtype = "SEA"
})

-- 4.4 J-16_3 反舰打击任务
ScenEdit_AddMission({
    side = "China",
    name = "J-16_3反舰任务",
    type = "Strike",
    subtype = "SEA"
})

-- 4.5 J-16_4 反舰打击任务
ScenEdit_AddMission({
    side = "China",
    name = "J-16_4反舰任务",
    type = "Strike",
    subtype = "SEA"
})

-- 4.6 055驱逐舰1 打击任务
ScenEdit_AddMission({
    side = "China",
    name = "055驱逐舰1打击任务",
    type = "Strike",
    subtype = "SEA"
})

-- 4.7 055驱逐舰2 打击任务
ScenEdit_AddMission({
    side = "China",
    name = "055驱逐舰2打击任务",
    type = "Strike",
    subtype = "SEA"
})

-- 4.8 潜艇打击任务
ScenEdit_AddMission({
    side = "China",
    name = "039C潜艇打击任务",
    type = "Strike",
    subtype = "SEA"
})

print("打击任务创建完成")

-- ============================================================
-- 第五部分：设置任务攻击目标阵营
-- ============================================================

-- 设置所有打击任务的目标阵营为 US
ScenEdit_SetMission("China", "J-16_1反舰任务", {
    attackee = "US"
})

ScenEdit_SetMission("China", "J-16_2反舰任务", {
    attackee = "US"
})

ScenEdit_SetMission("China", "J-16_3反舰任务", {
    attackee = "US"
})

ScenEdit_SetMission("China", "J-16_4反舰任务", {
    attackee = "US"
})

ScenEdit_SetMission("China", "055驱逐舰1打击任务", {
    attackee = "US"
})

ScenEdit_SetMission("China", "055驱逐舰2打击任务", {
    attackee = "US"
})

ScenEdit_SetMission("China", "039C潜艇打击任务", {
    attackee = "US"
})

print("任务目标阵营设置完成")

-- ============================================================
-- 第六部分：分配单位到任务
-- ============================================================

-- J-16D分配到巡逻任务
ScenEdit_AssignUnitToMission("红方J-16D_1", "J-16D电磁压制巡逻")

-- J-16_1 分配到打击任务
ScenEdit_AssignUnitToMission("红方J-16_1", "J-16_1反舰任务")

-- J-16_2 分配到打击任务
ScenEdit_AssignUnitToMission("红方J-16_2", "J-16_2反舰任务")

-- J-16_3 分配到打击任务
ScenEdit_AssignUnitToMission("红方J-16_3", "J-16_3反舰任务")

-- J-16_4 分配到打击任务
ScenEdit_AssignUnitToMission("红方J-16_4", "J-16_4反舰任务")

-- 055驱逐舰1 分配到打击任务
ScenEdit_AssignUnitToMission("红方055驱逐舰1 [Nanchang]", "055驱逐舰1打击任务")

-- 055驱逐舰2 分配到打击任务
ScenEdit_AssignUnitToMission("红方055驱逐舰2 [Nanchang]", "055驱逐舰2打击任务")

-- 039C潜艇 分配到打击任务
ScenEdit_AssignUnitToMission("红方039C潜艇1", "039C潜艇打击任务")

print("单位与任务分配完成")

-- ============================================================
-- 第七部分：巡逻区域参考点
-- ============================================================

-- 设置巡逻区域参考点 (J-16D巡逻区)
ScenEdit_AddReferencePoint({
    side = "China",
    name = "J-16D巡逻区1",
    latitude = 30.2,
    longitude = 124.0
})

ScenEdit_AddReferencePoint({
    side = "China",
    name = "J-16D巡逻区2",
    latitude = 30.25,
    longitude = 125.0
})

ScenEdit_AddReferencePoint({
    side = "China",
    name = "J-16D巡逻区3",
    latitude = 30.15,
    longitude = 125.5
})

ScenEdit_AddReferencePoint({
    side = "China",
    name = "J-16D巡逻区4",
    latitude = 30.1,
    longitude = 124.5
})

-- 设置J-16D巡逻任务区域
ScenEdit_SetMission("China", "J-16D电磁压制巡逻", {
    patrolzone = {"J-16D巡逻区1", "J-16D巡逻区2", "J-16D巡逻区3", "J-16D巡逻区4"}
})

print("巡逻区域设置完成")

-- ============================================================
-- 第八部分：时序控制事件
-- ============================================================
-- T0 = 场景开始时间
-- Phase 1 (T0+0 ~ T0+30M): 兵力集结与机动
-- Phase 2 (T0+30M ~ T0+40M): 电磁压制与目标确认
-- Phase 3 (T0+40M ~ T0+50M): 多轴饱和攻击
-- Phase 4 (T0+50M ~ T0+70M): 效果评估与兵力撤收
-- ============================================================

-- 8.1 阶段1开始：启动所有打击任务 (T0+0M)
ScenEdit_SetEvent("阶段1_启动打击任务", {mode="add", IsActive=true, IsRepeatable=0, Probability=100})

ScenEdit_SetTrigger({
    mode = "add",
    event = "阶段1_启动打击任务",
    type = "Time",
    Time = "0"
})

ScenEdit_SetAction({
    mode = "add",
    event = "阶段1_启动打击任务",
    type = "LuaScript",
    ScriptText = "print('阶段1: 启动所有打击任务'); ScenEdit_SpecialMessage('China', '阶段1: 兵力开始向阵位机动')"
})

-- 8.2 阶段2开始：J-16D电子战压制 (T0+30M)
ScenEdit_SetEvent("阶段2_J-16D电磁压制", {mode="add", IsActive=true, IsRepeatable=0, Probability=100})

ScenEdit_SetTrigger({
    mode = "add",
    event = "阶段2_J-16D电磁压制",
    type = "Time",
    Time = "30"
})

ScenEdit_SetAction({
    mode = "add",
    event = "阶段2_J-16D电磁压制",
    type = "LuaScript",
    ScriptText = "print('阶段2: J-16D开始电磁压制'); ScenEdit_SpecialMessage('China', '阶段2: J-16D开始电磁侦察压制')"
})

-- 8.3 阶段3开始：饱和攻击导弹齐射 (T0+40M)
ScenEdit_SetEvent("阶段3_饱和攻击开始", {mode="add", IsActive=true, IsRepeatable=0, Probability=100})

ScenEdit_SetTrigger({
    mode = "add",
    event = "阶段3_饱和攻击开始",
    type = "Time",
    Time = "40"
})

ScenEdit_SetAction({
    mode = "add",
    event = "阶段3_饱和攻击开始",
    type = "LuaScript",
    ScriptText = [[
print('阶段3: 多轴饱和攻击 - 导弹齐射开始')
local t1 = ScenEdit_GetUnit({side='US', name='蓝方伯克舰1'})
local t2 = ScenEdit_GetUnit({side='US', name='蓝方伯克舰2'})
local t3 = ScenEdit_GetUnit({side='US', name='蓝方补给舰'})
if t1 then ScenEdit_AttackContact('红方J-16_1', t1.guid, {weapon_dbpid=0}) end
if t2 then ScenEdit_AttackContact('红方J-16_2', t2.guid, {weapon_dbpid=0}) end
if t3 then ScenEdit_AttackContact('红方J-16_3', t3.guid, {weapon_dbpid=0}) end
if t3 then ScenEdit_AttackContact('红方J-16_4', t3.guid, {weapon_dbpid=0}) end
if t1 then ScenEdit_AttackContact('红方055驱逐舰1 [Nanchang]', t1.guid, {weapon_dbpid=0}) end
if t2 then ScenEdit_AttackContact('红方055驱逐舰2 [Nanchang]', t2.guid, {weapon_dbpid=0}) end
if t3 then ScenEdit_AttackContact('红方039C潜艇1', t3.guid, {weapon_dbpid=0}) end
ScenEdit_SpecialMessage('China', '阶段3: 多轴饱和攻击 - 导弹齐射!')
]]
})

-- 8.4 阶段4：效果评估 (T0+50M)
ScenEdit_SetEvent("阶段4_效果评估", {mode="add", IsActive=true, IsRepeatable=0, Probability=100})

ScenEdit_SetTrigger({
    mode = "add",
    event = "阶段4_效果评估",
    type = "Time",
    Time = "50"
})

ScenEdit_SetAction({
    mode = "add",
    event = "阶段4_效果评估",
    type = "LuaScript",
    ScriptText = [[
print('阶段4: 开始效果评估')
local targets = {'蓝方伯克舰1', '蓝方伯克舰2', '蓝方补给舰'}
local destroyed_count = 0
for _, name in ipairs(targets) do
    local unit = ScenEdit_GetUnit({side='US', name=name})
    if not unit then
        print('目标 ' .. name .. ' 已摧毁')
        destroyed_count = destroyed_count + 1
    else
        print('目标 ' .. name .. ' 仍存活, 损伤: ' .. tostring(unit.damage))
    end
end
if destroyed_count >= 2 then
    ScenEdit_SpecialMessage('China', '作战成功: 已摧毁' .. destroyed_count .. '个目标')
else
    ScenEdit_SpecialMessage('China', '效果评估: 摧毁' .. destroyed_count .. '个目标, 继续监控战况')
end
]]
})

print("时序控制事件创建完成")

-- ============================================================
-- 第九部分：打击链注释 (Kill Chain Documentation)
-- ============================================================
-- 打击链KC001: 攻击蓝方伯克舰1
--   L001: 兵力机动集结 (T0+0 ~ T0+30M)
--   L002: 电磁侦察压制 (T0+30M ~ T0+40M) - J-16D
--   L003: 瞄准目标 (T0+30M ~ T0+40M)
--   L004: 导弹齐射攻击 (T0+40M ~ T0+50M)
--   攻击平台: 红方J-16_1, 红方055驱逐舰1
--   武器: YJ-12 (J-16), YJ-18 (055)
--
-- 打击链KC002: 攻击蓝方伯克舰2
--   L005: 兵力机动集结
--   L006: 电磁侦察压制
--   L007: 瞄准目标
--   L008: 导弹齐射攻击
--   攻击平台: 红方J-16_2, 红方055驱逐舰2
--
-- 打击链KC003: 攻击蓝方补给舰
--   L009: 兵力机动集结
--   L010: 电磁侦察压制
--   L011: 瞄准目标
--   L012: 导弹齐射攻击
--   攻击平台: 红方J-16_3, 红方J-16_4, 红方039C潜艇
-- ============================================================

print("打击链配置完成")

-- ============================================================
-- 第十部分：特殊动作 - 手动发射导弹
-- ============================================================

local missile_script_1 = [[
local target = ScenEdit_GetUnit({side='US', name='蓝方伯克舰1'})
if target then
    print('红方055驱逐舰1发射YJ-18攻击' .. target.name)
    ScenEdit_AttackContact('红方055驱逐舰1 [Nanchang]', target.guid, {weapon_dbpid=0})
end
]]

ScenEdit_AddSpecialAction({
    Side = "China",
    ActionNameOrID = "manual_strike_burke1",
    description = "手动发射: 055舰攻击伯克舰1",
    IsActive = true,
    IsRepeatable = true,
    ScriptText = missile_script_1
})

local missile_script_2 = [[
local target = ScenEdit_GetUnit({side='US', name='蓝方伯克舰2'})
if target then
    print('红方055驱逐舰2发射YJ-18攻击' .. target.name)
    ScenEdit_AttackContact('红方055驱逐舰2 [Nanchang]', target.guid, {weapon_dbpid=0})
end
]]

ScenEdit_AddSpecialAction({
    Side = "China",
    ActionNameOrID = "manual_strike_burke2",
    description = "手动发射: 055舰攻击伯克舰2",
    IsActive = true,
    IsRepeatable = true,
    ScriptText = missile_script_2
})

local missile_script_3 = [[
local target = ScenEdit_GetUnit({side='US', name='蓝方补给舰'})
if target then
    print('J-16机群发射YJ-12攻击' .. target.name)
    ScenEdit_AttackContact('红方J-16_3', target.guid, {weapon_dbpid=0})
    ScenEdit_AttackContact('红方J-16_4', target.guid, {weapon_dbpid=0})
end
]]

ScenEdit_AddSpecialAction({
    Side = "China",
    ActionNameOrID = "manual_strike_supply",
    description = "手动发射: J-16攻击补给舰",
    IsActive = true,
    IsRepeatable = true,
    ScriptText = missile_script_3
})

print("特殊动作创建完成")

-- ============================================================
-- 完成
-- ============================================================

print("========================================")
print("多轴饱和攻击方案 - 加载完成")
print("========================================")
print("")
print("作战时间轴:")
print("  T0+0M:   兵力机动集结开始")
print("  T0+30M:  J-16D电磁压制巡逻开始")
print("  T0+40M:  多轴饱和攻击 - 导弹齐射")
print("  T0+50M:  攻击效果评估")
print("")
print("打击力量:")
print("  空中: 4xJ-16 (各带YJ-12)")
print("  水面: 2x055 (各带YJ-18)")
print("  水下: 1x039C (带潜射导弹)")
print("  电子: 1xJ-16D")
print("")
print("目标:")
print("  蓝方伯克舰1 (DDG-51)")
print("  蓝方伯克舰2 (DDG-51)")
print("  蓝方补给舰 (Durance)")
print("")
print("特殊动作:")
print("  [手动发射: 055舰攻击伯克舰1]")
print("  [手动发射: 055舰攻击伯克舰2]")
print("  [手动发射: J-16攻击补给舰]")
print("========================================")
