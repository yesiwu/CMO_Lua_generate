-- =============================================================================
-- mission.lua — 隐蔽致命一击 作战任务规划
-- 方案：联合火力突击训练场景 | 红方发起反舰攻击
-- 作战时间线: T+0H 隐蔽接敌 | T+50M 潜艇打击 | T+60M 空中突击
-- =============================================================================

Tool_EmulateNoConsole(true)

-- =============================================================================
-- 【任务概览】
-- =============================================================================
--
-- 红方任务:
--   M01_红方_潜艇巡逻  — 039C 潜艇隐蔽巡逻待机 (Strike/Naval)
--   M02_红方_侦察巡逻  — J-16D + J-16-1 广域电磁侦察 (Patrol/Air)
--   M03_红方_055巡逻  — 2x 055 驱逐舰区域警戒支援 (Patrol/Naval)
--   M04_红方_打击1    — J-16-2/3/4 对补给舰发起反舰攻击 (Strike/Naval)
--   M05_红方_打击2    — J-16-2/3/4 对驱逐舰发起反舰攻击 (Strike/Naval)
--
-- 蓝方任务:
--   M11_蓝方_反潜巡逻  — 2x DDG-84 北部反潜巡逻 (Patrol/Sub)
--   M12_蓝方_补给警戒  — 补给舰保持航行，DDG-84 护卫 (Patrol/Naval)
--
-- =============================================================================
-- 【第一部分：红方任务】
-- =============================================================================

-- -------------------------------------------------------------------------
-- M01: 红方 039C 潜艇隐蔽巡逻待机（对海打击）
-- 任务类型: Strike/Naval | 航线: 6个航点隐蔽机动 | 触发: T+50min 打击
-- -------------------------------------------------------------------------

local m01 = ScenEdit_AddMission('红方', 'M01_红方_潜艇巡逻', 'strike', {type='naval'})
if m01 then
    ScenEdit_SetMission('红方', 'M01_红方_潜艇巡逻', {
        description       = '039C 潜艇隐蔽向蓝方编队机动，占领攻击阵位后待机',
        consumablestrike = 1,
        one shot         = false,
    })
    print('[任务] M01_红方_潜艇巡逻 已创建 (Strike/Naval)')
else
    print('[WARNING] M01_红方_潜艇巡逻 已存在，跳过创建')
end

-- 为潜艇分配航线点
local m01_guid = ScenEdit_GetMission('红方', 'M01_红方_潜艇巡逻')
if m01_guid then
    ScenEdit_SetMission('红方', 'M01_红方_潜艇巡逻', {
        courseofaction = '{
            'R-潜艇A-1:30.5,126.167,60,-10', "
            'R-潜艇A-2:30.6,126.5,60,-10', "
            'R-潜艇A-3:30.7,126.8,60,-10', "
            'R-潜艇A-4:30.5,127.0,60,-10', "
            'R-潜艇A-5:30.4,127.2,60,-10', "
            'R-潜艇A-6:30.35,127.3,60,-10'"}
    })
end

-- 将红方潜艇A 分配到 M01
pcall(ScenEdit_AssignUnitToMission, '红方潜艇A', 'M01_红方_潜艇巡逻')

-- 参考点：潜艇攻击阵位路线标注（供指挥员参考）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-潜艇A-1', latitude=30.5, longitude=126.167, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-潜艇A-2', latitude=30.6, longitude=126.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-潜艇A-3', latitude=30.7, longitude=126.8, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-潜艇A-4', latitude=30.5, longitude=127.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-潜艇A-5', latitude=30.4, longitude=127.2, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-潜艇A-6', latitude=30.35, longitude=127.3, highlighted=false, type='generic'})

-- -------------------------------------------------------------------------
-- M02: 红方 J-16D + J-16-1 广域电磁侦察巡逻
-- 任务类型: Patrol/Air | 航线: 6点方形巡逻区 | 持续: T+0~50min
-- -------------------------------------------------------------------------

local m02 = ScenEdit_AddMission('红方', 'M02_红方_侦察巡逻', 'patrol', {type='air'})
if m02 then
    ScenEdit_SetMission('红方', 'M02_红方_侦察巡逻', {
        description    = 'J-16D + J-16-1 广域电磁侦察，精确定位蓝方编队',
        flightsize     = 2,
        minaircraftreq = 2,
    })
    print('[任务] M02_红方_侦察巡逻 已创建 (Patrol/Air)')
else
    print('[WARNING] M02_红方_侦察巡逻 已存在，跳过创建')
end

ScenEdit_SetMission('红方', 'M02_红方_侦察巡逻', {
    courseofaction = '{
        'R-J16D-1:30.133,123.0,8534,250', "
        'R-J16D-2:30.133,124.0,8534,250', "
        'R-J16D-3:30.2,126.0,8534,250', "
        'R-J16D-4:30.25,127.0,8534,250', "
        'R-J16D-5:30.3,127.5,8534,250', "
        'R-J16D-6:30.4,128.0,8534,250', "
        'R-J16D-7:30.133,125.0,8534,250'"}
    })
end

pcall(ScenEdit_AssignUnitToMission, 'J-16D-1', 'M02_红方_侦察巡逻')
pcall(ScenEdit_AssignUnitToMission, 'J-16-1(侦察)', 'M02_红方_侦察巡逻')

-- J-16-1 侦察航线标注（6点方形区）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16R-1', latitude=30.0, longitude=122.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16R-2', latitude=30.0, longitude=122.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16R-3', latitude=30.5, longitude=122.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16R-4', latitude=30.5, longitude=122.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16R-5', latitude=30.25, longitude=121.75, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16R-6', latitude=30.0, longitude=122.1, highlighted=false, type='generic'})

-- -------------------------------------------------------------------------
-- M03: 红方 2x 055 驱逐舰区域警戒支援
-- 任务类型: Patrol/Naval | 航线: 巡逻区 | 持续: T+0~50min
-- -------------------------------------------------------------------------

local m03 = ScenEdit_AddMission('红方', 'M03_红方_055巡逻', 'patrol', {type='naval'})
if m03 then
    ScenEdit_SetMission('红方', 'M03_红方_055巡逻', {
        description    = '055驱逐舰A/B 在后方区域保持警戒，提供远程信息支援',
        flightsize     = 2,
        minaircraftreq = 2,
    })
    print('[任务] M03_红方_055巡逻 已创建 (Patrol/Naval)')
else
    print('[WARNING] M03_红方_055巡逻 已存在，跳过创建')
end

-- 055-A 巡逻区标注 (4点矩形)
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-055A-1', latitude=30.167, longitude=123.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-055A-2', latitude=30.267, longitude=123.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-055A-3', latitude=30.267, longitude=123.6, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-055A-4', latitude=30.167, longitude=123.6, highlighted=false, type='generic'})
ScenEdit_SetMission('红方', 'M03_红方_055巡逻', {
    courseofaction = '{
        'R-055A-1', "
        'R-055A-2', "
        'R-055A-3', "
        'R-055A-4'"}
    })

pcall(ScenEdit_AssignUnitToMission, '红方驱逐舰A', 'M03_红方_055巡逻')
pcall(ScenEdit_AssignUnitToMission, '红方驱逐舰B', 'M03_红方_055巡逻')

-- -------------------------------------------------------------------------
-- M04: 红方 J-16-2/3/4 对蓝方补给舰打击任务
-- 任务类型: Strike/Naval | 触发: T+50min | 目标: 蓝方补给舰
-- -------------------------------------------------------------------------

local m04 = ScenEdit_AddMission('红方', 'M04_红方_打击_补给舰', 'strike', {type='naval'})
if m04 then
    ScenEdit_SetMission('红方', 'M04_红方_打击_补给舰', {
        description       = 'J-16-2/3/4 在潜艇攻击后对补给舰进行补充导弹打击',
        targetside       = '蓝方',
        consumablestrike = 1,
    })
    print('[任务] M04_红方_打击_补给舰 已创建 (Strike/Naval)')
else
    print('[WARNING] M04_红方_打击_补给舰 已存在，跳过创建')
end

-- J-16-2 预置打击航线（高空进入，低空突防）
ScenEdit_SetMission('红方', 'M04_红方_打击_补给舰', {
    courseofaction = '{
        'R-J16S2-1:30.083,122.167,7620,240', "
        'R-J16S2-2:30.2,123.5,8000,250', "
        'R-J16S2-3:30.4,125.0,8000,250', "
        'R-J16S2-4:30.5,126.5,7000,220', "
        'R-J16S2-5:30.45,127.2,6000,200', "
        'R-J16S2-6:30.333,127.5,5000,180', "
        'R-J16S2-7:30.1,126.8,8000,220', "
        'R-J16S2-8:30.0,125.0,8000,240'"}
    })
end

pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S2-1', latitude=30.083, longitude=122.167, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S2-2', latitude=30.2, longitude=123.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S2-3', latitude=30.4, longitude=125.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S2-4', latitude=30.5, longitude=126.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S2-5', latitude=30.45, longitude=127.2, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S2-6', latitude=30.333, longitude=127.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S2-7', latitude=30.1, longitude=126.8, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S2-8', latitude=30.0, longitude=125.0, highlighted=false, type='generic'})

-- J-16-3 预置打击航线（另一轴向进入）
pcall(ScenEdit_SetMission, '红方', 'M04_红方_打击_补给舰', {
    courseofaction = 'append:{'R-J16S3-1:29.917,122.083,7315,250' 'R-J16S3-2:30.0,123.0,10000,300' 'R-J16S3-3:30.083,124.0,10000,300' 'R-J16S3-4:30.167,126.0,8000,400' 'R-J16S3-5:30.167,127.25,5000,500' 'R-J16S3-6:30.0,126.5,6000,500'}'}
end

pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S3-1', latitude=29.917, longitude=122.083, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S3-2', latitude=30.0, longitude=123.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S3-3', latitude=30.083, longitude=124.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S3-4', latitude=30.167, longitude=126.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S3-5', latitude=30.167, longitude=127.25, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S3-6', latitude=30.0, longitude=126.5, highlighted=false, type='generic'})

-- J-16-4 预置打击航线（第三进入轴向）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S4-1', latitude=30.033, longitude=122.25, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S4-2', latitude=30.05, longitude=122.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S4-3', latitude=30.1, longitude=123.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S4-4', latitude=30.0, longitude=125.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S4-5', latitude=30.1, longitude=126.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S4-6', latitude=30.167, longitude=127.25, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S4-7', latitude=30.0, longitude=127.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='R-J16S4-8', latitude=30.05, longitude=124.0, highlighted=false, type='generic'})

-- 分配打击飞机到 M04（T+60min 后激活）
pcall(ScenEdit_AssignUnitToMission, 'J-16-2(打击)', 'M04_红方_打击_补给舰')
pcall(ScenEdit_AssignUnitToMission, 'J-16-3(打击)', 'M04_红方_打击_补给舰')
pcall(ScenEdit_AssignUnitToMission, 'J-16-4(打击)', 'M04_红方_打击_补给舰')

-- -------------------------------------------------------------------------
-- M05: 红方 J-16-2/3/4 对蓝方驱逐舰打击任务（补充打击）
-- 任务类型: Strike/Naval | 触发: T+60min | 目标: 蓝方驱逐舰
-- -------------------------------------------------------------------------

local m05 = ScenEdit_AddMission('红方', 'M05_红方_打击_驱逐舰', 'strike', {type='naval'})
if m05 then
    ScenEdit_SetMission('红方', 'M05_红方_打击_驱逐舰', {
        description       = 'J-16-2/3/4 对未被摧毁的蓝方驱逐舰进行补充打击',
        targetside       = '蓝方',
        consumablestrike = 1,
    })
    print('[任务] M05_红方_打击_驱逐舰 已创建 (Strike/Naval)')
else
    print('[WARNING] M05_红方_打击_驱逐舰 已存在，跳过创建')
end

pcall(ScenEdit_AssignUnitToMission, 'J-16-2(打击)', 'M05_红方_打击_驱逐舰')
pcall(ScenEdit_AssignUnitToMission, 'J-16-3(打击)', 'M05_红方_打击_驱逐舰')
pcall(ScenEdit_AssignUnitToMission, 'J-16-4(打击)', 'M05_红方_打击_驱逐舰')

-- =============================================================================
-- 【第二部分：蓝方任务】
-- =============================================================================

-- -------------------------------------------------------------------------
-- M11: 蓝方 2x DDG-84 反潜巡逻
-- 任务类型: Patrol/Sub | 航线: 北部巡逻区 | 持续: 全程
-- -------------------------------------------------------------------------

local m11 = ScenEdit_AddMission('蓝方', 'M11_蓝方_反潜巡逻', 'patrol', {type='sub'})
if m11 then
    ScenEdit_SetMission('蓝方', 'M11_蓝方_反潜巡逻', {
        description    = 'DDG-84 在北部巡逻区执行反潜警戒',
        flightsize     = 2,
        minaircraftreq = 2,
    })
    print('[任务] M11_蓝方_反潜巡逻 已创建 (Patrol/Sub)')
else
    print('[WARNING] M11_蓝方_反潜巡逻 已存在，跳过创建')
end

-- 蓝方反潜巡逻区参考点（北部 4点矩形）
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-N-1', latitude=30.8, longitude=126.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-N-2', latitude=30.8, longitude=128.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-N-3', latitude=29.8, longitude=128.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-N-4', latitude=29.8, longitude=126.5, highlighted=false, type='generic'})

ScenEdit_SetMission('蓝方', 'M11_蓝方_反潜巡逻', {
    courseofaction = '{
        'B-RP-N-1', "
        'B-RP-N-2', "
        'B-RP-N-3', "
        'B-RP-N-4'"}
    })
end

pcall(ScenEdit_AssignUnitToMission, '蓝方驱逐舰1', 'M11_蓝方_反潜巡逻')
pcall(ScenEdit_AssignUnitToMission, '蓝方驱逐舰2', 'M11_蓝方_反潜巡逻')

-- -------------------------------------------------------------------------
-- M12: 蓝方补给舰 + 驱逐舰护卫（航行补给+防空）
-- 任务类型: Patrol/Naval | 补给舰低速航行 | DDG-84 伴随护卫
-- -------------------------------------------------------------------------

local m12 = ScenEdit_AddMission('蓝方', 'M12_蓝方_补给航行', 'patrol', {type='naval'})
if m12 then
    ScenEdit_SetMission('蓝方', 'M12_蓝方_补给航行', {
        description    = '补给舰低速航行，DDG-84 保持护航',
        flightsize     = 3,
        minaircraftreq = 3,
    })
    print('[任务] M12_蓝方_补给航行 已创建 (Patrol/Naval)')
else
    print('[WARNING] M12_蓝方_补给航行 已存在，跳过创建')
end

-- 补给舰航行路线参考点
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-SUPPLY-1', latitude=30.167, longitude=127.25, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-SUPPLY-2', latitude=30.1, longitude=127.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-SUPPLY-3', latitude=30.0, longitude=127.75, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-SUPPLY-4', latitude=29.9, longitude=128.0, highlighted=false, type='generic'})

ScenEdit_SetMission('蓝方', 'M12_蓝方_补给航行', {
    courseofaction = '{
        'B-SUPPLY-1', "
        'B-SUPPLY-2', "
        'B-SUPPLY-3', "
        'B-SUPPLY-4'"}
    })
end

pcall(ScenEdit_AssignUnitToMission, '蓝方补给舰', 'M12_蓝方_补给航行')

-- =============================================================================
-- 【第三部分：时间事件（TCA 触发链）】
-- =============================================================================

-- T+50min 事件：潜艇打击阶段 + 空中打击激活 + 侦察任务结束

local ev_t50 = ScenEdit_SetEvent('EV_T50_潜艇打击', {
    mode         = 'add',
    IsRepeatable = false,
    IsActive     = true,
})
ScenEdit_SetTrigger({mode='add', type='Time', name='T50_trigger',
    time = ScenEdit_CurrentTime() + 3000})
ScenEdit_SetEventTrigger(ev_t50.guid, {mode='add', name='T50_trigger'})

-- T+50: 通知红方潜艇发起攻击
ScenEdit_SetAction({mode='add', type='LuaScript', name='T50_潜艇开火',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【T+50min】潜艇占领攻击阵位，向蓝方补给舰齐射反舰导弹！")'})
ScenEdit_SetEventAction(ev_t50.guid, {mode='add', name='T50_潜艇开火'})

-- T+50: 通知蓝方受到攻击
ScenEdit_SetAction({mode='add', type='LuaScript', name='T50_蓝方警报',
    ScriptText = 'ScenEdit_SpecialMessage("蓝方", "【警报】反舰导弹来袭！编队进入战斗状态！")'})
ScenEdit_SetEventAction(ev_t50.guid, {mode='add', name='T50_蓝方警报'})

-- T+50: J-16D 转为电磁压制（从侦察切换为干扰）
ScenEdit_SetAction({mode='add', type='LuaScript', name='T50_J16D干扰',
    ScriptText = 'pcall(ScenEdit_SetEMCON, "Unit", "J-16D-1", "Radar=Passive;Sonar=N/A;OECM=Active")'})
ScenEdit_SetEventAction(ev_t50.guid, {mode='add', name='T50_J16D干扰'})

-- T+50: 激活空中打击任务 M04
ScenEdit_SetAction({mode='add', type='LuaScript', name='T50_激活打击',
    ScriptText = 'pcall(ScenEdit_SetMission, "红方", "M04_红方_打击_补给舰", {isactive=true}) ' ..
        'pcall(ScenEdit_SpecialMessage, "红方", "【T+50min】空中打击群前出，对蓝方补给舰发起导弹攻击！")'})
ScenEdit_SetEventAction(ev_t50.guid, {mode='add', name='T50_激活打击'})

-- T+50: 记录战果评估（1分钟后）
local ev_t51 = ScenEdit_SetEvent('EV_T51_战果评估', {
    mode         = 'add',
    IsRepeatable = false,
    IsActive     = true,
})
ScenEdit_SetTrigger({mode='add', type='Time', name='T51_trigger',
    time = ScenEdit_CurrentTime() + 3600})
ScenEdit_SetEventTrigger(ev_t51.guid, {mode='add', name='T51_trigger'})
ScenEdit_SetAction({mode='add', type='LuaScript', name='T51_评估',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【T+60min 战果评估】攻击效果评估中……")'})
ScenEdit_SetEventAction(ev_t51.guid, {mode='add', name='T51_评估'})

-- =============================================================================
-- 【第四部分：任务完成判定事件】
-- =============================================================================

-- 条件：蓝方补给舰被摧毁（80%毁伤）
local ev_win = ScenEdit_SetEvent('EV_红方胜利', {
    mode         = 'add',
    IsRepeatable = false,
    IsActive     = true,
})
ScenEdit_SetTrigger({mode='add', type='UnitDamaged', name='补给舰受损',
    side = '蓝方', unitname = '蓝方补给舰', damaged_threshold = 80})
ScenEdit_SetEventTrigger(ev_win.guid, {mode='add', name='补给舰受损'})
ScenEdit_SetAction({mode='add', type='LuaScript', name='WinAction',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【胜利】蓝方补给舰达成80%毁伤，联合反舰打击任务完成！") ' ..
        'ScenEdit_SetScore("红方", 100, "补给舰击毁") ' ..
        'ScenEdit_SpecialMessage("蓝方", "【失败】补给舰被击毁，护航任务失败") ' ..
        'ScenEdit_SetScore("蓝方", -50, "补给舰损失")'})
ScenEdit_SetEventAction(ev_win.guid, {mode='add', name='WinAction'})

-- =============================================================================
-- 【第五部分：开火规则（Doctrine）最终确认】
-- =============================================================================

-- 确保潜艇在打击阶段获得开火权（覆盖待机设置）
pcall(ScenEdit_SetDoctrine, {name='红方潜艇A'}, {
    weapon_control_status_surface = 0,
    weapon_control_status_subsurface = 0,
})

print('========================================')
print('任务规划加载完成')
print('任务列表: M01~M05 (红方) + M11~M12 (蓝方)')
print('时间事件: EV_T50 (打击激活) + EV_T51 (战评) + EV_红方胜利')
print('========================================')