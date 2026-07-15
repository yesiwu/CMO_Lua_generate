-- ============================================================
-- 隐蔽致命一击 (Covert Decisive Strike Plan C)
-- CMO Lua 自动生成脚本
-- 方案时间: 2026-04-10 12:00:00 (UTC+8)
-- ============================================================
-- 本脚本部署红方/蓝方作战单元到场景中，并设置基于时间轴的多域协同反舰打击链事件。
--
-- 【MCP 查询说明】
-- 所有 DBID/LoadoutID 均通过 MCP HKBQ_SqlDB 服务查询验证。
-- 数据库可查到的单元：
--   | 单元              | 类型     | DBID   |
--   | J-16 (Su-30MKK)   | Aircraft | 2853   |
--   | J-16D Roaring Wolf| Aircraft | 4632   |
--   | Type 039C Yuan     | Submarine| 695    |
--   | Type 055 Renhai    | Ship     | 2834   |
--   | DDG 51 Arleigh Burke| Ship   | 112    |
--   | Henry J. Kaiser T-AO| Ship    | 26     |
--   | LoadoutID (J-16 2853): 1821, 3272
--   | LoadoutID (J-16D 4632): 753, 965, 3482, 3483, 3828, 3829
--
-- 以下单元无等效替代，已跳过：
--   | 蓝方驱逐舰2 (blue_ddg_burke_2) — 数量充足，DBID 112 重复使用
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- === 常量定义
-- ============================================================
local SIDE_RED = '红方'
local SIDE_BLUE = '蓝方'

local SCENARIO_START = "2026-04-10 12:00:00!yyyy-MM-dd HH:mm:ss"

-- 时间节点（秒，相对于 T0）
local T_PHASE1_END   = 50 * 60   -- T+50min  隐蔽接敌结束
local T_PHASE2_END   = 60 * 60   -- T+60min  潜艇攻击结束
local T_PHASE3_END   = 75 * 60   -- T+75min  空中补充打击结束

-- ============================================================
-- === 工具函数
-- ============================================================
local function pscenAddUnit(params)
    local ok, result = pcall(ScenEdit_AddUnit, params)
    if not ok then
        print("[WARN] ScenEdit_AddUnit failed: " .. tostring(result))
        return nil
    end
    if result and result.guid then
        ScenEdit_SetKeyValue(tostring(params.name) .. '_GUID', result.guid)
    end
    return result
end

local function safeAddUnit(params)
    local ok, result = pcall(ScenEdit_AddUnit, params)
    if not ok then
        print("[ERROR] " .. tostring(params.name) .. ": " .. tostring(result))
        return nil
    end
    if result and result.guid then
        ScenEdit_SetKeyValue(tostring(params.name) .. '_GUID', result.guid)
    end
    return result
end

local function addRefPoint(side, name, lat, lon)
    local ok, rp = pcall(ScenEdit_AddReferencePoint, {
        side = side,
        name = name,
        latitude = lat,
        longitude = lon,
        highlighted = false
    })
    if not ok then
        print("[WARN] addRefPoint failed for " .. name .. ": " .. tostring(rp))
    end
    return rp
end

local function parsePT(s)
    local hours = tonumber(s:match("(%d+)H")) or 0
    local mins = tonumber(s:match("(%d+)M")) or 0
    local secs = tonumber(s:match("(%d+)S")) or 0
    return hours * 3600 + mins * 60 + secs
end

local function addTimeTrigger(name, offsetSeconds)
    local t = ScenEdit_CurrentTime() + offsetSeconds
    local ok = pcall(ScenEdit_SetTrigger, {
        mode = 'add',
        type = 'Time',
        name = name,
        time = t
    })
    if not ok then
        print("[WARN] addTimeTrigger failed: " .. name)
    end
    return ok
end

local function addRegularTrigger(name, intervalSeconds)
    local ok = pcall(ScenEdit_SetTrigger, {
        mode = 'add',
        type = 'RegularTime',
        name = name,
        interval = intervalSeconds
    })
    if not ok then
        print("[WARN] addRegularTrigger failed: " .. name)
    end
    return ok
end

-- ============================================================
-- === Sides
-- ============================================================
print("[INFO] Creating sides...")
ScenEdit_AddSide({name = SIDE_RED, color = '255,0,0'})
ScenEdit_AddSide({name = SIDE_BLUE, color = '0,0,255'})

-- 设置红蓝敌对关系
pcall(ScenEdit_SetSidePosture, SIDE_RED, SIDE_BLUE, 'H')
pcall(ScenEdit_SetSidePosture, SIDE_BLUE, SIDE_RED, 'H')

-- ============================================================
-- === 作战条令设置
-- ============================================================
print("[INFO] Setting doctrine...")

-- 红方条令：自由开火，允许使用反舰导弹
ScenEdit_SetDoctrine({side = SIDE_RED}, {
    weapon_control_status_air        = 0,  -- Free
    weapon_control_status_surface    = 0,  -- Free
    weapon_control_status_subsurface = 0,  -- Free
    use_nuclear_weapons              = 'no',
})

-- 蓝方条令
ScenEdit_SetDoctrine({side = SIDE_BLUE}, {
    weapon_control_status_air        = 0,
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 0,
    use_nuclear_weapons              = 'no',
})

-- ============================================================
-- === 蓝方目标单元
-- ============================================================
print("[INFO] Adding Blue side target units...")

-- 蓝方补给舰 (Henry J. Kaiser T-AO, DBID=26)
safeAddUnit({
    side   = SIDE_BLUE,
    type   = 'Ship',
    name   = 'blue_aux_supply_1',
    dbid   = 26,
    latitude = 30.166666666666668,
    longitude = 127.25,
    heading  = 0,
    speed    = 0,
    proficiency = 'Veteran',
})

-- 蓝方驱逐舰1 (Arleigh Burke Flight I, DBID=112)
safeAddUnit({
    side   = SIDE_BLUE,
    type   = 'Ship',
    name   = 'blue_ddg_burke_1',
    dbid   = 112,
    latitude = 30.333333333333332,
    longitude = 127.5,
    heading  = 0,
    speed    = 0,
    proficiency = 'Veteran',
})

-- 蓝方驱逐舰2 (Arleigh Burke Flight I, DBID=112)
safeAddUnit({
    side   = SIDE_BLUE,
    type   = 'Ship',
    name   = 'blue_ddg_burke_2',
    dbid   = 112,
    latitude = 30.0,
    longitude = 127.75,
    heading  = 0,
    speed    = 0,
    proficiency = 'Veteran',
})

-- ============================================================
-- === 红方作战单元
-- ============================================================
print("[INFO] Adding Red side units...")

-- ===== 潜艇 (Type 039C Yuan, DBID=695) =====
-- 潜深60m = manualAltitude = 60
local sub_unit = safeAddUnit({
    side   = SIDE_RED,
    type   = 'Submarine',
    name   = 'red_sub_039c_1',
    dbid   = 695,
    latitude = 30.5,
    longitude = 126.16666666666667,
    manualAltitude = 60,
    heading  = 0,
    speed    = 5,
    proficiency = 'Veteran',
})

-- 潜艇 EMCON：被动声呐，隐蔽航行
ScenEdit_SetEMCON('Unit', ScenEdit_GetKeyValue('red_sub_039c_1_GUID') or '', 'Sonar=Passive;Radar=Passive')

-- ===== 水面舰艇 (Type 055 Renhai, DBID=2834) =====
safeAddUnit({
    side   = SIDE_RED,
    type   = 'Ship',
    name   = 'red_ddg_055_1',
    dbid   = 2834,
    latitude = 30.166666666666668,
    longitude = 123.5,
    heading  = 0,
    speed    = 10,
    proficiency = 'Veteran',
})

safeAddUnit({
    side   = SIDE_RED,
    type   = 'Ship',
    name   = 'red_ddg_055_2',
    dbid   = 2834,
    latitude = 29.833333333333332,
    longitude = 123.83333333333333,
    heading  = 0,
    speed    = 10,
    proficiency = 'Veteran',
})

-- 055驱逐舰 EMCON：雷达被动，信息支援
local ddg055_1_guid = ScenEdit_GetKeyValue('red_ddg_055_1_GUID') or ''
if ddg055_1_guid ~= '' then
    pcall(ScenEdit_SetEMCON, 'Unit', ddg055_1_guid, 'Radar=Passive;Sonar=Active;OECM=Active')
end
local ddg055_2_guid = ScenEdit_GetKeyValue('red_ddg_055_2_GUID') or ''
if ddg055_2_guid ~= '' then
    pcall(ScenEdit_SetEMCON, 'Unit', ddg055_2_guid, 'Radar=Passive;Sonar=Active;OECM=Active')
end

-- ===== 空中作战单元 (J-16D 电子战型, DBID=4632) =====
-- LoadoutID 使用 965 (典型电子战挂载)
local j16d_unit = safeAddUnit({
    side      = SIDE_RED,
    type      = 'Aircraft',
    name      = 'red_j16d_1',
    dbid      = 4632,
    LoadoutID = 965,
    latitude  = 30.133333333333333,
    longitude = 123.0,
    altitude  = 8534,
    heading   = 0,
    speed     = 250,
    proficiency = 'Veteran',
})

-- J-16D EMCON：电子干扰模式
local j16d_guid = ScenEdit_GetKeyValue('red_j16d_1_GUID') or ''
if j16d_guid ~= '' then
    pcall(ScenEdit_SetEMCON, 'Unit', j16d_guid, 'Radar=Active;OECM=Active')
end

-- ===== J-16 战斗机群 (J-16 Su-30MKK, DBID=2853) =====
-- LoadoutID 使用 1821
safeAddUnit({
    side      = SIDE_RED,
    type      = 'Aircraft',
    name      = 'red_j16_1',
    dbid      = 2853,
    LoadoutID = 1821,
    latitude  = 30.0,
    longitude = 122.0,
    altitude  = 7620,
    heading   = 0,
    speed     = 250,
    proficiency = 'Veteran',
})

-- J-16 攻击编队 (DBID=2853, LoadoutID=3272 挂载反舰导弹)
safeAddUnit({
    side      = SIDE_RED,
    type      = 'Aircraft',
    name      = 'red_j16_2',
    dbid      = 2853,
    LoadoutID = 3272,
    latitude  = 30.083333333333332,
    longitude = 122.16666666666667,
    altitude  = 7620,
    heading   = 90,
    speed     = 240,
    proficiency = 'Veteran',
})

safeAddUnit({
    side      = SIDE_RED,
    type      = 'Aircraft',
    name      = 'red_j16_3',
    dbid      = 2853,
    LoadoutID = 3272,
    latitude  = 29.916666666666668,
    longitude = 122.08333333333333,
    altitude  = 7315,
    heading   = 90,
    speed     = 250,
    proficiency = 'Veteran',
})

safeAddUnit({
    side      = SIDE_RED,
    type      = 'Aircraft',
    name      = 'red_j16_4',
    dbid      = 2853,
    LoadoutID = 3272,
    latitude  = 30.033333333333335,
    longitude = 122.25,
    altitude  = 7315,
    heading   = 0,
    speed     = 250,
    proficiency = 'Veteran',
})

-- ============================================================
-- === 参考点定义（巡逻区域与攻击阵位）
-- ============================================================
print("[INFO] Creating reference points...")

-- 潜艇攻击阵位
addRefPoint(SIDE_RED, 'RP_SUB_ATTACK', 30.35, 127.3)

-- 蓝方编队巡逻区域参考点
addRefPoint(SIDE_RED, 'RP_BLUE_PATROL_1', 30.166666666666668, 127.25)
addRefPoint(SIDE_RED, 'RP_BLUE_PATROL_2', 30.333333333333332, 127.5)
addRefPoint(SIDE_RED, 'RP_BLUE_PATROL_3', 30.0, 127.75)

-- 红方水面舰支援区域
addRefPoint(SIDE_RED, 'RP_DDG055_1', 30.166666666666668, 123.5)
addRefPoint(SIDE_RED, 'RP_DDG055_2', 29.833333333333332, 123.83333333333333)

-- J-16D 电子干扰压制区
addRefPoint(SIDE_RED, 'RP_J16D_STATION_1', 30.2, 126.0)
addRefPoint(SIDE_RED, 'RP_J16D_STATION_2', 30.4, 128.0)

-- J-16 突击进入点
addRefPoint(SIDE_RED, 'RP_J16_IP_1', 30.5, 126.5)
addRefPoint(SIDE_RED, 'RP_J16_IP_2', 30.166666666666668, 127.25)

-- ============================================================
-- === 任务创建
-- ============================================================
print("[INFO] Creating missions...")

-- ===== Phase 1: 隐蔽接敌阶段 (T0 - T+50min) =====

-- 潜艇接敌机动任务（巡航型）
local mSubCruise = ScenEdit_AddMission(SIDE_RED, 'MSUB_CRUISE', 'Patrol', {
    type = 'NAVAL',
    zone = {'RP_SUB_ATTACK'},
})
if mSubCruise then
    ScenEdit_SetMission(SIDE_RED, 'MSUB_CRUISE', {
        patrolType   = 'TargetPatrol',
        onethirdrule = false,
    })
    -- 分配潜艇到任务
    local sub_guid = ScenEdit_GetKeyValue('red_sub_039c_1_GUID') or ''
    if sub_guid ~= '' then
        pcall(ScenEdit_AssignUnitToMission, sub_guid, 'MSUB_CRUISE')
    end
end

-- J-16D 电磁侦察巡航任务
local mJ16DRecon = ScenEdit_AddMission(SIDE_RED, 'MJ16D_RECON', 'Patrol', {
    type = 'SEA',
    zone = {'RP_J16D_STATION_1', 'RP_J16D_STATION_2'},
})
if mJ16DRecon then
    ScenEdit_SetMission(SIDE_RED, 'MJ16D_RECON', {
        patrolType   = 'AreaCAP',
        onethirdrule = false,
    })
    local j16d_guid = ScenEdit_GetKeyValue('red_j16d_1_GUID') or ''
    if j16d_guid ~= '' then
        pcall(ScenEdit_AssignUnitToMission, j16d_guid, 'MJ16D_RECON')
    end
end

-- J-16(侦察型) 广域侦察任务
local mJ16Recon = ScenEdit_AddMission(SIDE_RED, 'MJ16_RECON', 'Patrol', {
    type = 'SEA',
    zone = {'RP_BLUE_PATROL_1', 'RP_BLUE_PATROL_2', 'RP_BLUE_PATROL_3'},
})
if mJ16Recon then
    ScenEdit_SetMission(SIDE_RED, 'MJ16_RECON', {
        patrolType   = 'AreaCAP',
        onethirdrule = false,
    })
    local j16_1_guid = ScenEdit_GetKeyValue('red_j16_1_GUID') or ''
    if j16_1_guid ~= '' then
        pcall(ScenEdit_AssignUnitToMission, j16_1_guid, 'MJ16_RECON')
    end
end

-- 055驱逐舰区域巡逻任务
local mDDGPatrol1 = ScenEdit_AddMission(SIDE_RED, 'MDDG055_1_PATROL', 'Patrol', {
    type = 'NAVAL',
    zone = {'RP_DDG055_1'},
})
if mDDGPatrol1 then
    ScenEdit_SetMission(SIDE_RED, 'MDDG055_1_PATROL', {
        patrolType   = 'AreaCAP',
        onethirdrule = false,
    })
    local ddg055_1_guid = ScenEdit_GetKeyValue('red_ddg_055_1_GUID') or ''
    if ddg055_1_guid ~= '' then
        pcall(ScenEdit_AssignUnitToMission, ddg055_1_guid, 'MDDG055_1_PATROL')
    end
end

local mDDGPatrol2 = ScenEdit_AddMission(SIDE_RED, 'MDDG055_2_PATROL', 'Patrol', {
    type = 'NAVAL',
    zone = {'RP_DDG055_2'},
})
if mDDGPatrol2 then
    ScenEdit_SetMission(SIDE_RED, 'MDDG055_2_PATROL', {
        patrolType   = 'AreaCAP',
        onethirdrule = false,
    })
    local ddg055_2_guid = ScenEdit_GetKeyValue('red_ddg_055_2_GUID') or ''
    if ddg055_2_guid ~= '' then
        pcall(ScenEdit_AssignUnitToMission, ddg055_2_guid, 'MDDG055_2_PATROL')
    end
end

-- ===== Phase 2: 潜艇致命一击 (T+50min) =====

-- 潜艇打击任务：攻击补给舰
local mSubStrike1 = ScenEdit_AddMission(SIDE_RED, 'MSUB_STRIKE_SUPPLY', 'Strike', {
    type = 'SEA',
    attackee = SIDE_BLUE,
})
if mSubStrike1 then
    ScenEdit_SetMission(SIDE_RED, 'MSUB_STRIKE_SUPPLY', {
        flightSize = 1,
        minaircraftreq = 1,
    })
    -- 分配目标
    pcall(ScenEdit_AssignUnitAsTarget, {
        mission = 'MSUB_STRIKE_SUPPLY',
        unitname = 'blue_aux_supply_1',
    })
end

-- 潜艇打击任务：攻击驱逐舰1
local mSubStrike2 = ScenEdit_AddMission(SIDE_RED, 'MSUB_STRIKE_BURKE1', 'Strike', {
    type = 'SEA',
    attackee = SIDE_BLUE,
})
if mSubStrike2 then
    ScenEdit_SetMission(SIDE_RED, 'MSUB_STRIKE_BURKE1', {
        flightSize = 1,
        minaircraftreq = 1,
    })
    pcall(ScenEdit_AssignUnitAsTarget, {
        mission = 'MSUB_STRIKE_BURKE1',
        unitname = 'blue_ddg_burke_1',
    })
end

-- J-16D 电磁压制任务（接替侦察，进入压制模式）
local mJ16DJamming = ScenEdit_AddMission(SIDE_RED, 'MJ16D_JAMMING', 'Patrol', {
    type = 'SEAD',
    zone = {'RP_BLUE_PATROL_1', 'RP_BLUE_PATROL_2', 'RP_BLUE_PATROL_3'},
})
if mJ16DJamming then
    ScenEdit_SetMission(SIDE_RED, 'MJ16D_JAMMING', {
        patrolType   = 'AreaCAP',
        onethirdrule = false,
    })
    local j16d_guid = ScenEdit_GetKeyValue('red_j16d_1_GUID') or ''
    if j16d_guid ~= '' then
        pcall(ScenEdit_AssignUnitToMission, j16d_guid, 'MJ16D_JAMMING')
    end
end

-- ===== Phase 3: 空中火力补充 (T+60min) =====

-- KC001 空中打击：攻击补给舰
local mStrikeSupply = ScenEdit_AddMission(SIDE_RED, 'MSTRIKE_KC001_SUPPLY', 'Strike', {
    type = 'SEA',
    attackee = SIDE_BLUE,
})
if mStrikeSupply then
    ScenEdit_SetMission(SIDE_RED, 'MSTRIKE_KC001_SUPPLY', {
        flightSize = 4,
        minaircraftreq = 1,
    })
    pcall(ScenEdit_AssignUnitAsTarget, {
        mission = 'MSTRIKE_KC001_SUPPLY',
        unitname = 'blue_aux_supply_1',
    })
    pcall(ScenEdit_AssignUnitAsTarget, {
        mission = 'MSTRIKE_KC001_SUPPLY',
        unitname = 'blue_ddg_burke_1',
    })
    pcall(ScenEdit_AssignUnitAsTarget, {
        mission = 'MSTRIKE_KC001_SUPPLY',
        unitname = 'blue_ddg_burke_2',
    })
    -- 分配 J-16 攻击机
    local j16_2_guid = ScenEdit_GetKeyValue('red_j16_2_GUID') or ''
    local j16_3_guid = ScenEdit_GetKeyValue('red_j16_3_GUID') or ''
    local j16_4_guid = ScenEdit_GetKeyValue('red_j16_4_GUID') or ''
    if j16_2_guid ~= '' then pcall(ScenEdit_AssignUnitToMission, j16_2_guid, 'MSTRIKE_KC001_SUPPLY') end
    if j16_3_guid ~= '' then pcall(ScenEdit_AssignUnitToMission, j16_3_guid, 'MSTRIKE_KC001_SUPPLY') end
    if j16_4_guid ~= '' then pcall(ScenEdit_AssignUnitToMission, j16_4_guid, 'MSTRIKE_KC001_SUPPLY') end
end

-- KC002 打击：攻击驱逐舰1
local mStrikeBurke1 = ScenEdit_AddMission(SIDE_RED, 'MSTRIKE_KC002_BURKE1', 'Strike', {
    type = 'SEA',
    attackee = SIDE_BLUE,
})
if mStrikeBurke1 then
    ScenEdit_SetMission(SIDE_RED, 'MSTRIKE_KC002_BURKE1', {
        flightSize = 2,
        minaircraftreq = 1,
    })
    pcall(ScenEdit_AssignUnitAsTarget, {
        mission = 'MSTRIKE_KC002_BURKE1',
        unitname = 'blue_ddg_burke_1',
    })
    pcall(ScenEdit_AssignUnitAsTarget, {
        mission = 'MSTRIKE_KC002_BURKE1',
        unitname = 'blue_ddg_burke_2',
    })
    local j16_2_guid = ScenEdit_GetKeyValue('red_j16_2_GUID') or ''
    if j16_2_guid ~= '' then
        pcall(ScenEdit_AssignUnitToMission, j16_2_guid, 'MSTRIKE_KC002_BURKE1')
    end
end

-- KC003 打击：攻击驱逐舰2
local mStrikeBurke2 = ScenEdit_AddMission(SIDE_RED, 'MSTRIKE_KC003_BURKE2', 'Strike', {
    type = 'SEA',
    attackee = SIDE_BLUE,
})
if mStrikeBurke2 then
    ScenEdit_SetMission(SIDE_RED, 'MSTRIKE_KC003_BURKE2', {
        flightSize = 2,
        minaircraftreq = 1,
    })
    pcall(ScenEdit_AssignUnitAsTarget, {
        mission = 'MSTRIKE_KC003_BURKE2',
        unitname = 'blue_ddg_burke_2',
    })
    local j16_3_guid = ScenEdit_GetKeyValue('red_j16_3_GUID') or ''
    local j16_4_guid = ScenEdit_GetKeyValue('red_j16_4_GUID') or ''
    if j16_3_guid ~= '' then pcall(ScenEdit_AssignUnitToMission, j16_3_guid, 'MSTRIKE_KC003_BURKE2') end
    if j16_4_guid ~= '' then pcall(ScenEdit_AssignUnitToMission, j16_4_guid, 'MSTRIKE_KC003_BURKE2') end
end

-- ============================================================
-- === 事件系统：TCA 触发链
-- ============================================================
print("[INFO] Creating event triggers...")

-- ===== 事件1: Phase 1 开始 - 隐蔽接敌 =====
local ev1 = ScenEdit_SetEvent('EVT_PHASE1_START', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if ev1 then
    ScenEdit_SetTrigger({mode = 'add', type = 'ScenLoaded', name = 'OnLoad'})
    ScenEdit_SetEventTrigger(ev1.guid, {mode = 'add', name = 'OnLoad'})
    ScenEdit_SetAction({
        mode = 'add',
        type = 'LuaScript',
        name = 'ACT_PHASE1_START',
        ScriptText = (
            'ScenEdit_SpecialMessage("' .. SIDE_RED .. '","[阶段1] 隐蔽接敌 - 潜艇和侦察机开始向目标区域机动")' ..
            '\r\nScenEdit_SetKeyValue("phase","1")'
        ),
    })
    ScenEdit_SetEventAction(ev1.guid, {mode = 'add', name = 'ACT_PHASE1_START'})
end

-- ===== 事件2: T+50min - 潜艇发起攻击 =====
local ev2 = ScenEdit_SetEvent('EVT_PHASE2_SUB_ATTACK', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if ev2 then
    addTimeTrigger('T_SUB_ATTACK', T_PHASE1_END)
    ScenEdit_SetEventTrigger(ev2.guid, {mode = 'add', name = 'T_SUB_ATTACK'})
    ScenEdit_SetAction({
        mode = 'add',
        type = 'LuaScript',
        name = 'ACT_SUB_ATTACK',
        ScriptText = (
            'ScenEdit_SpecialMessage("' .. SIDE_RED .. '","[阶段2] 潜艇发起攻击!")' ..
            '\r\nScenEdit_SetKeyValue("phase","2")' ..
            '\r\n-- 潜艇已分配到打击任务，CMO 自动发射武器' ..
            '\r\nlocal sub_guid = ScenEdit_GetKeyValue("red_sub_039c_1_GUID")' ..
            '\r\nif sub_guid and sub_guid ~= "" then' ..
            '\r\n  pcall(ScenEdit_AssignUnitToMission, sub_guid, "MSUB_STRIKE_SUPPLY")' ..
            '\r\n  pcall(ScenEdit_AssignUnitToMission, sub_guid, "MSUB_STRIKE_BURKE1")' ..
            '\r\nend'
        ),
    })
    ScenEdit_SetEventAction(ev2.guid, {mode = 'add', name = 'ACT_SUB_ATTACK'})
end

-- ===== 事件3: T+50min - J-16D 电磁压制开始 =====
local ev3 = ScenEdit_SetEvent('EVT_J16D_JAMMING_START', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if ev3 then
    addTimeTrigger('T_J16D_JAMMING', T_PHASE1_END)
    ScenEdit_SetEventTrigger(ev3.guid, {mode = 'add', name = 'T_J16D_JAMMING'})
    ScenEdit_SetAction({
        mode = 'add',
        type = 'LuaScript',
        name = 'ACT_J16D_START_JAM',
        ScriptText = (
            'ScenEdit_SpecialMessage("' .. SIDE_RED .. '","[阶段2] J-16D 开始电磁压制!")' ..
            '\r\nlocal j16d_guid = ScenEdit_GetKeyValue("red_j16d_1_GUID")' ..
            '\r\nif j16d_guid and j16d_guid ~= "" then' ..
            '\r\n  pcall(ScenEdit_SetEMCON, "Unit", j16d_guid, "Radar=Active;OECM=Active")' ..
            '\r\n  pcall(ScenEdit_AssignUnitToMission, j16d_guid, "MJ16D_JAMMING")' ..
            '\r\nend'
        ),
    })
    ScenEdit_SetEventAction(ev3.guid, {mode = 'add', name = 'ACT_J16D_START_JAM'})
end

-- ===== 事件4: T+60min - 空中打击群发起攻击 =====
local ev4 = ScenEdit_SetEvent('EVT_PHASE3_AIR_STRIKE', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if ev4 then
    addTimeTrigger('T_AIR_STRIKE', T_PHASE2_END)
    ScenEdit_SetEventTrigger(ev4.guid, {mode = 'add', name = 'T_AIR_STRIKE'})
    ScenEdit_SetAction({
        mode = 'add',
        type = 'LuaScript',
        name = 'ACT_AIR_STRIKE',
        ScriptText = (
            'ScenEdit_SpecialMessage("' .. SIDE_RED .. '","[阶段3] 空中打击群发起导弹攻击!")' ..
            '\r\nScenEdit_SetKeyValue("phase","3")' ..
            '\r\n-- 分配 J-16 到打击任务' ..
            '\r\nlocal j16_2 = ScenEdit_GetKeyValue("red_j16_2_GUID")' ..
            '\r\nlocal j16_3 = ScenEdit_GetKeyValue("red_j16_3_GUID")' ..
            '\r\nlocal j16_4 = ScenEdit_GetKeyValue("red_j16_4_GUID")' ..
            '\r\nif j16_2 and j16_2 ~= "" then' ..
            '\r\n  pcall(ScenEdit_AssignUnitToMission, j16_2, "MSTRIKE_KC001_SUPPLY")' ..
            '\r\n  pcall(ScenEdit_AssignUnitToMission, j16_2, "MSTRIKE_KC002_BURKE1")' ..
            '\r\nend' ..
            '\r\nif j16_3 and j16_3 ~= "" then' ..
            '\r\n  pcall(ScenEdit_AssignUnitToMission, j16_3, "MSTRIKE_KC001_SUPPLY")' ..
            '\r\n  pcall(ScenEdit_AssignUnitToMission, j16_3, "MSTRIKE_KC003_BURKE2")' ..
            '\r\nend' ..
            '\r\nif j16_4 and j16_4 ~= "" then' ..
            '\r\n  pcall(ScenEdit_AssignUnitToMission, j16_4, "MSTRIKE_KC001_SUPPLY")' ..
            '\r\n  pcall(ScenEdit_AssignUnitToMission, j16_4, "MSTRIKE_KC003_BURKE2")' ..
            '\r\nend'
        ),
    })
    ScenEdit_SetEventAction(ev4.guid, {mode = 'add', name = 'ACT_AIR_STRIKE'})
end

-- ===== 事件5: 蓝方补给舰被摧毁 =====
local ev5 = ScenEdit_SetEvent('EVT_SUPPLY_DESTROYED', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if ev5 then
    ScenEdit_SetTrigger({
        mode = 'add',
        type = 'UnitDestroyed',
        name = 'TRIG_SUPPLY_DESTROYED',
        side = SIDE_BLUE,
        unitname = 'blue_aux_supply_1',
    })
    ScenEdit_SetEventTrigger(ev5.guid, {mode = 'add', name = 'TRIG_SUPPLY_DESTROYED'})
    ScenEdit_SetAction({
        mode = 'add',
        type = 'LuaScript',
        name = 'ACT_SUPPLY_DESTROYED',
        ScriptText = (
            'ScenEdit_SpecialMessage("' .. SIDE_RED .. '","** 蓝方补给舰已被摧毁! KC001 主要目标完成 **")' ..
            '\r\nScenEdit_SetScore("' .. SIDE_RED .. '", 200, "蓝方补给舰摧毁")' ..
            '\r\nScenEdit_SetKeyValue("supply_destroyed","true")'
        ),
    })
    ScenEdit_SetEventAction(ev5.guid, {mode = 'add', name = 'ACT_SUPPLY_DESTROYED'})
end

-- ===== 事件6: 蓝方驱逐舰1被摧毁 =====
local ev6 = ScenEdit_SetEvent('EVT_BURKE1_DESTROYED', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if ev6 then
    ScenEdit_SetTrigger({
        mode = 'add',
        type = 'UnitDestroyed',
        name = 'TRIG_BURKE1_DESTROYED',
        side = SIDE_BLUE,
        unitname = 'blue_ddg_burke_1',
    })
    ScenEdit_SetEventTrigger(ev6.guid, {mode = 'add', name = 'TRIG_BURKE1_DESTROYED'})
    ScenEdit_SetAction({
        mode = 'add',
        type = 'LuaScript',
        name = 'ACT_BURKE1_DESTROYED',
        ScriptText = (
            'ScenEdit_SpecialMessage("' .. SIDE_RED .. '","** 蓝方驱逐舰1已被摧毁! KC002 主要目标完成 **")' ..
            '\r\nScenEdit_SetScore("' .. SIDE_RED .. '", 150, "蓝方驱逐舰1摧毁")' ..
            '\r\nScenEdit_SetKeyValue("burke1_destroyed","true")'
        ),
    })
    ScenEdit_SetEventAction(ev6.guid, {mode = 'add', name = 'ACT_BURKE1_DESTROYED'})
end

-- ===== 事件7: 蓝方驱逐舰2被摧毁 =====
local ev7 = ScenEdit_SetEvent('EVT_BURKE2_DESTROYED', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if ev7 then
    ScenEdit_SetTrigger({
        mode = 'add',
        type = 'UnitDestroyed',
        name = 'TRIG_BURKE2_DESTROYED',
        side = SIDE_BLUE,
        unitname = 'blue_ddg_burke_2',
    })
    ScenEdit_SetEventTrigger(ev7.guid, {mode = 'add', name = 'TRIG_BURKE2_DESTROYED'})
    ScenEdit_SetAction({
        mode = 'add',
        type = 'LuaScript',
        name = 'ACT_BURKE2_DESTROYED',
        ScriptText = (
            'ScenEdit_SpecialMessage("' .. SIDE_RED .. '","** 蓝方驱逐舰2已被摧毁! KC003 主要目标完成 **")' ..
            '\r\nScenEdit_SetScore("' .. SIDE_RED .. '", 150, "蓝方驱逐舰2摧毁")' ..
            '\r\nScenEdit_SetKeyValue("burke2_destroyed","true")'
        ),
    })
    ScenEdit_SetEventAction(ev7.guid, {mode = 'add', name = 'ACT_BURKE2_DESTROYED'})
end

-- ===== 事件8: T+75min - 作战结束评估 =====
local ev8 = ScenEdit_SetEvent('EVT_OPERATION_END', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if ev8 then
    addTimeTrigger('T_OPERATION_END', T_PHASE3_END)
    ScenEdit_SetEventTrigger(ev8.guid, {mode = 'add', name = 'T_OPERATION_END'})
    ScenEdit_SetAction({
        mode = 'add',
        type = 'LuaScript',
        name = 'ACT_OPERATION_END',
        ScriptText = (
            'local supply_ok = ScenEdit_GetKeyValue("supply_destroyed") == "true"' ..
            '\r\nlocal burke1_ok = ScenEdit_GetKeyValue("burke1_destroyed") == "true"' ..
            '\r\nlocal burke2_ok = ScenEdit_GetKeyValue("burke2_destroyed") == "true"' ..
            '\r\nlocal total = 0' ..
            '\r\nif supply_ok then total = total + 1 end' ..
            '\r\nif burke1_ok then total = total + 1 end' ..
            '\r\nif burke2_ok then total = total + 1 end' ..
            '\r\nlocal msg = "[阶段结束] 作战评估: 已摧毁 " .. tostring(total) .. "/3 个主要目标"' ..
            '\r\nScenEdit_SpecialMessage("' .. SIDE_RED .. '", msg)' ..
            '\r\nif total >= 2 then' ..
            '\r\n  ScenEdit_SpecialMessage("' .. SIDE_RED .. '","作战成功! 红方攻击群开始脱离接触")' ..
            '\r\n  ScenEdit_SetScore("' .. SIDE_RED .. '", 300, "作战成功完成")' ..
            '\r\nend'
        ),
    })
    ScenEdit_SetEventAction(ev8.guid, {mode = 'add', name = 'ACT_OPERATION_END'})
end

-- ============================================================
-- === 初始化完成
-- ============================================================
print("[INFO] === 隐蔽致命一击方案部署完成 ===")
print("[INFO] 方案概述:")
print("  阶段1 (T+0 ~ T+50min): 隐蔽接敌")
print("    - 潜艇 red_sub_039c_1 秘密向攻击阵位机动")
print("    - J-16D red_j16d_1 电磁侦察定位蓝方编队")
print("    - J-16 red_j16_1 广域光学/雷达侦察")
print("    - 055驱逐舰 red_ddg_055_1/2 区域警戒支援")
print("  阶段2 (T+50min ~ T+60min): 潜艇致命一击")
print("    - 潜艇发射潜射反舰导弹攻击补给舰和驱逐舰1")
print("    - J-16D 转为电磁压制模式")
print("  阶段3 (T+60min ~ T+75min): 空中火力补充")
print("    - J-16 攻击编队对残存目标实施补充打击")
print("    - 完成战果评估和脱离接触")
print("[INFO] 所有事件已注册，等待触发...")

ScenEdit_SpecialMessage(SIDE_RED, "=== 隐蔽致命一击方案已部署 ===")
ScenEdit_SpecialMessage(SIDE_RED, "阶段1: 隐蔽接敌阶段开始 - 各单位按计划向目标区域机动")
