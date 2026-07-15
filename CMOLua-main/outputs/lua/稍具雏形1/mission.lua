-- =============================================================================
-- mission.lua — 隐蔽致命一击 作战任务规划
-- 东海多域联合反舰杀伤网 | 红方发起反舰攻击
-- 作战时间线:
--   T+0H    : 全部平台开始执行（侦察、巡逻、接敌）
--   T+50M   : 潜艇发射潜射导弹 + J-16D 转为电磁压制 + 空中打击激活
--   T+60M   : J-16 机群空中补充打击
--   T+75M   : 战果评估
-- JSON 映射: platformExecutions + killChains -> Lua 任务/事件
-- =============================================================================

Tool_EmulateNoConsole(true)

-- =============================================================================
-- 【第一部分】红方任务 — 侦察与巡逻
-- =============================================================================

-- -------------------------------------------------------------------------
-- M01: 红方 039C 潜艇隐蔽接敌（Strike/Naval — 航线机动，非自动寻敌）
-- 对应 JSON: red_sub_039c_1 / TASK_SUB_CRUISE
-- -------------------------------------------------------------------------

local m01 = ScenEdit_AddMission('红方', 'M01_潜艇接敌', 'strike', {type='naval'})
if m01 then
    ScenEdit_SetMission('红方', 'M01_潜艇接敌', {
        description        = '039C 潜艇隐蔽向蓝方编队机动，占领攻击阵位后待机',
        targetside       = '蓝方',
        consumablestrike = 1,
        one_shot        = false,
    })
    print('[任务] M01_潜艇接敌 已创建 (Strike/Naval, targetside=蓝方)')
else
    print('[INFO] M01_潜艇接敌 已存在，跳过')
end

-- 分配潜艇到 M01（沿 6 个航点向目标区机动）
pcall(ScenEdit_AssignUnitToMission, 'red_sub_039c_1', 'M01_潜艇接敌')

-- -------------------------------------------------------------------------
-- M02: 红方 J-16D + J-16-1 广域电磁侦察巡逻（Patrol/Air）
-- 对应 JSON: red_j16d_1 + red_j16_1 / 电磁侦察巡航
-- -------------------------------------------------------------------------

local m02 = ScenEdit_AddMission('红方', 'M02_侦察巡逻', 'patrol', {type='air'})
if m02 then
    ScenEdit_SetMission('红方', 'M02_侦察巡逻', {
        description        = 'J-16D + J-16-1 广域电磁侦察，精确定位蓝方编队',
        flightsize        = 2,
        minaircraftreq   = 2,
    })
    print('[任务] M02_侦察巡逻 已创建 (Patrol/Air, flightsize=2)')
else
    print('[INFO] M02_侦察巡逻 已存在，跳过')
end

-- 侦察巡逻区（4点矩形覆盖目标区域上方）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-侦察区-1', latitude=30.1,  longitude=123.0,  highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-侦察区-2', latitude=30.1,  longitude=128.0,  highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-侦察区-3', latitude=30.8,  longitude=128.0,  highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-侦察区-4', latitude=30.8,  longitude=123.0,  highlighted=false, type='generic'})

ScenEdit_SetMission('红方', 'M02_侦察巡逻', {
    patrolzone  = {'RP-侦察区-1', 'RP-侦察区-2', 'RP-侦察区-3', 'RP-侦察区-4'},
    patrolType  = 'FighterCAP',
    onethirdrule = false,
})

pcall(ScenEdit_AssignUnitToMission, 'red_j16d_1', 'M02_侦察巡逻')
pcall(ScenEdit_AssignUnitToMission, 'red_j16_1', 'M02_侦察巡逻')

-- -------------------------------------------------------------------------
-- M03: 红方 2x 055 驱逐舰区域警戒支援（Patrol/Naval）
-- 对应 JSON: red_ddg_055_1 + red_ddg_055_2 / 水面信息支援
-- -------------------------------------------------------------------------

local m03 = ScenEdit_AddMission('红方', 'M03_055巡逻', 'patrol', {type='naval'})
if m03 then
    ScenEdit_SetMission('红方', 'M03_055巡逻', {
        description      = '055驱逐舰A/B 在后方区域保持警戒，提供远程信息支援',
        flightsize      = 2,
        minaircraftreq  = 2,
    })
    print('[任务] M03_055巡逻 已创建 (Patrol/Naval)')
else
    print('[INFO] M03_055巡逻 已存在，跳过')
end

-- 055-A 巡逻区
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-055A-1', latitude=30.1,  longitude=123.3, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-055A-2', latitude=30.3,  longitude=123.3, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-055A-3', latitude=30.3,  longitude=123.8, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-055A-4', latitude=30.1,  longitude=123.8, highlighted=false, type='generic'})

ScenEdit_SetMission('红方', 'M03_055巡逻', {
    patrolzone  = {'RP-055A-1', 'RP-055A-2', 'RP-055A-3', 'RP-055A-4'},
    patrolType  = 'AreaCAP',
    onethirdrule = false,
})

pcall(ScenEdit_AssignUnitToMission, 'red_ddg_055_1', 'M03_055巡逻')
pcall(ScenEdit_AssignUnitToMission, 'red_ddg_055_2', 'M03_055巡逻')

-- =============================================================================
-- 【第二部分】红方打击任务（Strike）
-- =============================================================================

-- -------------------------------------------------------------------------
-- M04: 潜艇打击任务 — 039C 发射潜射导弹（T+50min 激活）
-- 对应 JSON: red_sub_039c_1 / TASK_SUB_ATTACK
-- 武器: YJ-18 潜射反舰导弹 x4
-- 目标: blue_aux_supply_1, blue_ddg_burke_1, blue_ddg_burke_2
-- -------------------------------------------------------------------------

local m04 = ScenEdit_AddMission('红方', 'M04_潜艇打击', 'strike', {type='naval'})
if m04 then
    ScenEdit_SetMission('红方', 'M04_潜艇打击', {
        description        = '039C 潜艇占领攻击阵位后发射潜射导弹攻击蓝方舰艇',
        targetside       = '蓝方',
        consumablestrike = 1,
        one_shot        = true,
    })
    print('[任务] M04_潜艇打击 已创建 (Strike/Naval, targetside=蓝方, isactive=false — T+50M激活)')
else
    print('[INFO] M04_潜艇打击 已存在，跳过')
end

-- 初始不激活，由 T+50M 事件激活
ScenEdit_SetMission('红方', 'M04_潜艇打击', {isactive = false})

-- 分配潜艇到打击任务（但默认待机，由事件触发开火）
pcall(ScenEdit_AssignUnitToMission, 'red_sub_039c_1', 'M04_潜艇打击')

-- 为打击任务指定目标（补给舰为主，驱逐舰为次）
pcall(ScenEdit_AssignUnitAsTarget, {mission='M04_潜艇打击', unitname='blue_aux_supply_1'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M04_潜艇打击', unitname='blue_ddg_burke_1'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M04_潜艇打击', unitname='blue_ddg_burke_2'})

-- -------------------------------------------------------------------------
-- M05: 空中打击任务（第一波）— J-16-2/3/4 对补给舰协同突击
-- 对应 JSON: red_j16_2/3/4 / KC001-LK001-4
-- 武器: YJ-83K/YJ-12 空射反舰导弹
-- 目标: blue_aux_supply_1
-- -------------------------------------------------------------------------

local m05 = ScenEdit_AddMission('红方', 'M05_空中打击_补给舰', 'strike', {type='naval'})
if m05 then
    ScenEdit_SetMission('红方', 'M05_空中打击_补给舰', {
        description        = 'J-16 机群对蓝方补给舰发起反舰导弹攻击',
        targetside       = '蓝方',
        consumablestrike = 1,
        one_shot        = true,
    })
    print('[任务] M05_空中打击_补给舰 已创建 (Strike/Naval, isactive=false)')
else
    print('[INFO] M05_空中打击_补给舰 已存在，跳过')
end

ScenEdit_SetMission('红方', 'M05_空中打击_补给舰', {isactive = false})

-- J-16-2 预置打击航线（高空进入，低空突防）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S2-IP',  latitude=30.0833, longitude=122.1667, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S2-2',   latitude=30.4,    longitude=125.0,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S2-3',   latitude=30.5,    longitude=126.5,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S2-TGT', latitude=30.1667, longitude=127.25,  highlighted=true,  type='generic', appearance='bomb'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S2-E',   latitude=30.1,    longitude=125.0,   highlighted=false, type='generic'})

-- J-16-3 另一进入轴向
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S3-IP',  latitude=29.9167, longitude=122.0833, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S3-2',   latitude=30.0,    longitude=124.0,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S3-3',   latitude=30.167,  longitude=126.0,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S3-TGT', latitude=30.1667, longitude=127.25,  highlighted=true,  type='generic', appearance='bomb'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S3-E',   latitude=30.0,    longitude=125.0,   highlighted=false, type='generic'})

-- J-16-4 第三进入轴向
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S4-IP',  latitude=30.0333, longitude=122.25,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S4-2',   latitude=30.0,    longitude=125.0,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S4-3',   latitude=30.1,    longitude=126.5,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S4-TGT', latitude=30.1667, longitude=127.25,  highlighted=true,  type='generic', appearance='bomb'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J16S4-E',   latitude=30.05,   longitude=124.0,   highlighted=false, type='generic'})

-- 分配飞机到打击任务（初始待机，T+50M 激活后出发）
pcall(ScenEdit_AssignUnitToMission, 'red_j16_2', 'M05_空中打击_补给舰')
pcall(ScenEdit_AssignUnitToMission, 'red_j16_3', 'M05_空中打击_补给舰')
pcall(ScenEdit_AssignUnitToMission, 'red_j16_4', 'M05_空中打击_补给舰')

-- 指定打击目标
pcall(ScenEdit_AssignUnitAsTarget, {mission='M05_空中打击_补给舰', unitname='blue_aux_supply_1'})

-- -------------------------------------------------------------------------
-- M06: 空中打击任务（第二波）— J-16-2/3 对驱逐舰补充打击
-- 对应 JSON: red_j16_2/3/4 / KC002-LK002-3, KC003-LK003-3
-- 目标: blue_ddg_burke_1, blue_ddg_burke_2
-- -------------------------------------------------------------------------

local m06 = ScenEdit_AddMission('红方', 'M06_空中打击_驱逐舰', 'strike', {type='naval'})
if m06 then
    ScenEdit_SetMission('红方', 'M06_空中打击_驱逐舰', {
        description        = 'J-16 机群对未被摧毁的蓝方驱逐舰进行补充打击',
        targetside       = '蓝方',
        consumablestrike = 1,
        one_shot        = true,
    })
    print('[任务] M06_空中打击_驱逐舰 已创建 (Strike/Naval, isactive=false)')
else
    print('[INFO] M06_空中打击_驱逐舰 已存在，跳过')
end

ScenEdit_SetMission('红方', 'M06_空中打击_驱逐舰', {isactive = false})

pcall(ScenEdit_AssignUnitToMission, 'red_j16_2', 'M06_空中打击_驱逐舰')
pcall(ScenEdit_AssignUnitToMission, 'red_j16_3', 'M06_空中打击_驱逐舰')
pcall(ScenEdit_AssignUnitToMission, 'red_j16_4', 'M06_空中打击_驱逐舰')

pcall(ScenEdit_AssignUnitAsTarget, {mission='M06_空中打击_驱逐舰', unitname='blue_ddg_burke_1'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M06_空中打击_驱逐舰', unitname='blue_ddg_burke_2'})

-- -------------------------------------------------------------------------
-- M07: J-16D 电磁干扰压制（SEAD Patrol，替代电子战激光攻击类型）
-- 对应 JSON: red_j16d_1 / 电磁干扰与压制 / KC003-LK003-2
-- T+50M 激活，持续到 T+75M
-- -------------------------------------------------------------------------

local m07 = ScenEdit_AddMission('红方', 'M07_J16D干扰压制', 'patrol', {type='SEAD'})
if m07 then
    ScenEdit_SetMission('红方', 'M07_J16D干扰压制', {
        description      = 'J-16D 对蓝方防空/反潜区域实施有源电子干扰压制',
        flightsize      = 1,
        minaircraftreq  = 1,
        targetside     = '蓝方',
    })
    print('[任务] M07_J16D干扰压制 已创建 (Patrol/SEAD, isactive=false)')
else
    print('[INFO] M07_J16D干扰压制 已存在，跳过')
end

ScenEdit_SetMission('红方', 'M07_J16D干扰压制', {isactive = false})

-- 干扰压制巡逻区（覆盖蓝方编队上空）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-干扰区-1', latitude=30.0,  longitude=126.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-干扰区-2', latitude=30.0,  longitude=128.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-干扰区-3', latitude=30.6,  longitude=128.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-干扰区-4', latitude=30.6,  longitude=126.0, highlighted=false, type='generic'})

ScenEdit_SetMission('红方', 'M07_J16D干扰压制', {
    patrolzone  = {'RP-干扰区-1', 'RP-干扰区-2', 'RP-干扰区-3', 'RP-干扰区-4'},
    onethirdrule = false,
})

pcall(ScenEdit_AssignUnitToMission, 'red_j16d_1', 'M07_J16D干扰压制')

-- =============================================================================
-- 【第三部分】蓝方任务
-- =============================================================================

-- -------------------------------------------------------------------------
-- M11: 蓝方 2x DDG 反潜巡逻（Patrol/Sub）
-- 对应 JSON: 蓝方反潜巡逻
-- -------------------------------------------------------------------------

local m11 = ScenEdit_AddMission('蓝方', 'M11_蓝方反潜', 'patrol', {type='sub'})
if m11 then
    ScenEdit_SetMission('蓝方', 'M11_蓝方反潜', {
        description      = 'DDG-51 驱逐舰在北部巡逻区执行反潜警戒',
        flightsize      = 2,
        minaircraftreq  = 2,
    })
    print('[任务] M11_蓝方反潜 已创建 (Patrol/Sub)')
else
    print('[INFO] M11_蓝方反潜 已存在，跳过')
end

-- 反潜巡逻区（4点矩形）
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-反潜-1', latitude=30.8, longitude=126.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-反潜-2', latitude=30.8, longitude=128.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-反潜-3', latitude=29.8, longitude=128.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-反潜-4', latitude=29.8, longitude=126.5, highlighted=false, type='generic'})

ScenEdit_SetMission('蓝方', 'M11_蓝方反潜', {
    patrolzone  = {'B-RP-反潜-1', 'B-RP-反潜-2', 'B-RP-反潜-3', 'B-RP-反潜-4'},
    onethirdrule = false,
})

pcall(ScenEdit_AssignUnitToMission, 'blue_ddg_burke_1', 'M11_蓝方反潜')
pcall(ScenEdit_AssignUnitToMission, 'blue_ddg_burke_2', 'M11_蓝方反潜')

-- -------------------------------------------------------------------------
-- M12: 蓝方补给舰航行警戒（Patrol/Naval）
-- -------------------------------------------------------------------------

local m12 = ScenEdit_AddMission('蓝方', 'M12_蓝方补给航行', 'patrol', {type='naval'})
if m12 then
    ScenEdit_SetMission('蓝方', 'M12_蓝方补给航行', {
        description      = '补给舰低速航行，保持编队航线',
        flightsize      = 1,
        minaircraftreq  = 1,
    })
    print('[任务] M12_蓝方补给航行 已创建 (Patrol/Naval)')
else
    print('[INFO] M12_蓝方补给航行 已存在，跳过')
end

-- 补给舰航行路线参考点
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-SUPPLY-1', latitude=30.167, longitude=127.25, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-SUPPLY-2', latitude=30.1,  longitude=127.5,  highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-SUPPLY-3', latitude=30.0,  longitude=127.75, highlighted=false, type='generic'})

ScenEdit_SetMission('蓝方', 'M12_蓝方补给航行', {
    patrolzone  = {'B-SUPPLY-1', 'B-SUPPLY-2', 'B-SUPPLY-3'},
    onethirdrule = false,
})

pcall(ScenEdit_AssignUnitToMission, 'blue_aux_supply_1', 'M12_蓝方补给航行')

-- =============================================================================
-- 【第四部分】时间事件触发链（TCA）
-- 忠实翻译 JSON combatPhases 时间节点：
--   Phase 1 (T+0~50M):  隐蔽接敌与目标确认
--   Phase 2 (T+50~60M): 潜艇致命一击 + 电磁压制 + 空中打击激活
--   Phase 3 (T+60~75M): 空中火力补充与评估
-- =============================================================================

local NOW = ScenEdit_CurrentTime()

-- -------------------------------------------------------------------------
-- EV_A: 作战开始（T+0，场景加载触发）
-- 通知双方，进入 Phase 1
-- -------------------------------------------------------------------------

local evA = ScenEdit_SetEvent('EV_A_作战开始', {
    mode         = 'add',
    IsRepeatable = false,
    IsActive     = true,
})
ScenEdit_SetTrigger({mode='add', type='ScenLoaded', name='场景加载'})
ScenEdit_SetEventTrigger(evA.guid, {mode='add', name='场景加载'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='A_开始通知',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【Phase 1 — 隐蔽接敌】各平台开始向目标区机动，侦察平台就位")\r\n'..
                 'ScenEdit_SpecialMessage("蓝方", "【警戒】发现红方电磁活动，编队提高戒备")'})
ScenEdit_SetEventAction(evA.guid, {mode='add', name='A_开始通知'})

-- -------------------------------------------------------------------------
-- EV_T50: T+50min — 潜艇致命一击 + 电磁压制 + 空中打击激活
-- 对应 JSON Phase 2: CT2-1 潜射导弹攻击 + CT2-2 电磁干扰压制
-- -------------------------------------------------------------------------

local evT50 = ScenEdit_SetEvent('EV_T50_潜艇打击', {
    mode         = 'add',
    IsRepeatable = false,
    IsActive     = true,
})
ScenEdit_SetTrigger({mode='add', type='Time', name='T50触发器',
    time = NOW + 3000})  -- 3000 秒 = 50 分钟
ScenEdit_SetEventTrigger(evT50.guid, {mode='add', name='T50触发器'})

-- 动作 1: 激活潜艇打击任务（M04），潜艇获得开火权
ScenEdit_SetAction({mode='add', type='LuaScript', name='T50_激活潜艇打击',
    ScriptText = 'local ok1 = pcall(ScenEdit_SetMission, "红方", "M04_潜艇打击", {isactive=true})\r\n'..
                 'pcall(ScenEdit_SetDoctrine, {name="red_sub_039c_1"}, {\r\n'..
                 '    weapon_control_status_surface = 0,\r\n'..
                 '    weapon_control_status_subsurface = 0\r\n'..
                 '})\r\n'..
                 'ScenEdit_SpecialMessage("红方", "【Phase 2 — 潜艇打击】039C 占领攻击阵位，向蓝方舰艇齐射导弹！")'})
ScenEdit_SetEventAction(evT50.guid, {mode='add', name='T50_激活潜艇打击'})

-- 动作 2: 激活 J-16D 电磁压制任务（M07），J-16D 从侦察切换为有源干扰
ScenEdit_SetAction({mode='add', type='LuaScript', name='T50_激活电磁压制',
    ScriptText = 'pcall(ScenEdit_SetEMCON, "Unit", "red_j16d_1", "Radar=Active;Sonar=N/A;OECM=Active")\r\n'..
                 'local ok2 = pcall(ScenEdit_SetMission, "红方", "M07_J16D干扰压制", {isactive=true})\r\n'..
                 'ScenEdit_SpecialMessage("红方", "【Phase 2 — 电磁压制】J-16D 有源干扰开启，蓝方雷达效能降低")'})
ScenEdit_SetEventAction(evT50.guid, {mode='add', name='T50_激活电磁压制'})

-- 动作 3: 激活空中打击任务（第一波：补给舰）
ScenEdit_SetAction({mode='add', type='LuaScript', name='T50_激活空中打击',
    ScriptText = 'pcall(ScenEdit_SetMission, "红方", "M05_空中打击_补给舰", {isactive=true})\r\n'..
                 'ScenEdit_SpecialMessage("红方", "【Phase 2 — 空中突击】J-16 机群前出，对蓝方补给舰发起导弹攻击！")'})
ScenEdit_SetEventAction(evT50.guid, {mode='add', name='T50_激活空中打击'})

-- 动作 4: 通知蓝方受到攻击
ScenEdit_SetAction({mode='add', type='LuaScript', name='T50_蓝方警报',
    ScriptText = 'ScenEdit_SpecialMessage("蓝方", "【警报】反舰导弹来袭！编队进入战斗状态，启动防空拦截！")'})
ScenEdit_SetEventAction(evT50.guid, {mode='add', name='T50_蓝方警报'})

-- -------------------------------------------------------------------------
-- EV_T60: T+60min — 空中补充打击（第二波：驱逐舰）
-- 对应 JSON Phase 3: CT3-1 空中补充打击
-- -------------------------------------------------------------------------

local evT60 = ScenEdit_SetEvent('EV_T60_空中补充', {
    mode         = 'add',
    IsRepeatable = false,
    IsActive     = true,
})
ScenEdit_SetTrigger({mode='add', type='Time', name='T60触发器',
    time = NOW + 3600})  -- 3600 秒 = 60 分钟
ScenEdit_SetEventTrigger(evT60.guid, {mode='add', name='T60触发器'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='T60_激活补充打击',
    ScriptText = 'pcall(ScenEdit_SetMission, "红方", "M06_空中打击_驱逐舰", {isactive=true})\r\n'..
                 'ScenEdit_SpecialMessage("红方", "【Phase 3 — 补充打击】J-16 机群对残存蓝方驱逐舰发起第二波导弹攻击！")'})
ScenEdit_SetEventAction(evT60.guid, {mode='add', name='T60_激活补充打击'})

-- -------------------------------------------------------------------------
-- EV_T75: T+75min — 战果评估
-- 对应 JSON Phase 3: CT3-2 持续电磁压制与评估
-- -------------------------------------------------------------------------

local evT75 = ScenEdit_SetEvent('EV_T75_战果评估', {
    mode         = 'add',
    IsRepeatable = false,
    IsActive     = true,
})
ScenEdit_SetTrigger({mode='add', type='Time', name='T75触发器',
    time = NOW + 4500})  -- 4500 秒 = 75 分钟
ScenEdit_SetEventTrigger(evT75.guid, {mode='add', name='T75触发器'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='T75_评估通知',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【战果评估】攻击效果评估中，请检查各目标毁伤状态")\r\n'..
                 'ScenEdit_SpecialMessage("蓝方", "【战损报告】编队遭受攻击，损失情况统计中")'})
ScenEdit_SetEventAction(evT75.guid, {mode='add', name='T75_评估通知'})

-- =============================================================================
-- 【第五部分】任务完成判定事件（胜利条件）
-- 对应 JSON terminationStates: TS001
-- 条件: 蓝方补给舰达成 80% 毁伤 或 驱逐舰达成 60% 毁伤
-- =============================================================================

-- 补给舰 80% 毁伤 -> 红方胜利
local evWinSupply = ScenEdit_SetEvent('EV_补给舰击毁', {
    mode         = 'add',
    IsRepeatable = false,
    IsActive     = true,
})
ScenEdit_SetTrigger({mode='add', type='UnitDamaged', name='补给舰受损',
    side='蓝方', unitname='blue_aux_supply_1', damaged_threshold=80})
ScenEdit_SetEventTrigger(evWinSupply.guid, {mode='add', name='补给舰受损'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='WinSupply',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【任务完成】蓝方补给舰达成 80% 毁伤，联合反舰打击任务成功！")\r\n'..
                 'ScenEdit_SpecialMessage("蓝方", "【任务失败】补给舰被击毁，护航任务失败")\r\n'..
                 'ScenEdit_SetScore("红方", 100, "补给舰击毁")\r\n'..
                 'ScenEdit_SetScore("蓝方", -50, "补给舰损失")'})
ScenEdit_SetEventAction(evWinSupply.guid, {mode='add', name='WinSupply'})

-- 驱逐舰 60% 毁伤 -> 红方胜利
local evWinDDG = ScenEdit_SetEvent('EV_驱逐舰击毁', {
    mode         = 'add',
    IsRepeatable = false,
    IsActive     = true,
})
ScenEdit_SetTrigger({mode='add', type='UnitDamaged', name='驱逐舰受损',
    side='蓝方', unitname='blue_ddg_burke_1', damaged_threshold=60})
ScenEdit_SetEventTrigger(evWinDDG.guid, {mode='add', name='驱逐舰受损'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='WinDDG',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【任务完成】蓝方驱逐舰达成 60% 毁伤，区域拒止目标达成！")\r\n'..
                 'ScenEdit_SpecialMessage("蓝方", "【任务失败】护航驱逐舰丧失战斗力")\r\n'..
                 'ScenEdit_SetScore("红方", 50, "驱逐舰击伤")\r\n'..
                 'ScenEdit_SetScore("蓝方", -30, "驱逐舰损失")'})
ScenEdit_SetEventAction(evWinDDG.guid, {mode='add', name='WinDDG'})

-- =============================================================================
-- 【第六部分】潜艇开火权最终确认（确保打击时能发射）
-- 在场景加载后统一设置，但由 T50 事件激活实际开火
-- =============================================================================

-- 潜艇 Doctrine：水面/水下均 Hold（待机），由 T50 事件临时开放
pcall(ScenEdit_SetDoctrine, {name='red_sub_039c_1'}, {
    weapon_control_status_surface  = 2,
    weapon_control_status_subsurface = 2,
})

print('========================================')
print('任务规划加载完成 — mission.lua')
print('红方任务: M01~M07')
print('蓝方任务: M11~M12')
print('事件链: EV_A(开始) -> EV_T50(打击) -> EV_T60(补充) -> EV_T75(评估)')
print('胜利条件: 补给舰80% / 驱逐舰60%')
print('========================================')
