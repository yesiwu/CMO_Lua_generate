-- =============================================================================
-- main.lua — 隐蔽致命一击 (covert_decisive_strike_c)
-- 东海多域联合反舰杀伤网 | 红方发起反舰攻击
-- DBID/LuaoutID 来源: MCP HKBQ_SqlDB 查询
-- 创建日期: 2026-04-30
-- =============================================================================

Tool_EmulateNoConsole(true)

-- =============================================================================
-- 【常量定义】所有 DBID/LoadoutID 必须通过 MCP 查询，禁止硬编码
-- =============================================================================

local DBID = {
    -- 蓝方（目标）
    supply_ship   = 753,   -- T-AKE 1 Lewis and Clark (MCP: T-AKE supply ship)
    burke_ddg    = 112,   -- DDG 51 Arleigh Burke Flight I (MCP: Arleigh Burke destroyer)
    -- 红方
    sub_039c     = 695,   -- Type 039C Yuan (MCP: 039C submarine)
    j16          = 2853,  -- J-16 Flying Shark Su-30MKK Copy (MCP: J-16)
    j16d         = 4632,  -- J-16D Roaring Wolf EW (MCP: J-16D)
    ddg_055      = 2834,  -- Type 055 Renhai 101 Nanchang (MCP: Type 055 destroyer)
}

local LOADOUT = {
    j16_strike  = 1821,   -- J-16 对海打击挂载 (MCP: ComponentID=2853)
    j16_escort  = 3272,   -- J-16 护航/侦察挂载 (MCP: ComponentID=2853)
    j16d_ew     = 753,    -- J-16D 电子战挂载 (MCP: ComponentID=4632)
}

-- =============================================================================
-- 【第一部分】创建阵营 & 设置敌对关系
-- =============================================================================

local ok, err = pcall(ScenEdit_AddSide, {name = '红方', color = '255,0,0'})
if not ok then print('[INFO] 红方已存在: ' .. tostring(err)) end

local ok2, err2 = pcall(ScenEdit_AddSide, {name = '蓝方', color = '0,0,255'})
if not ok2 then print('[INFO] 蓝方已存在: ' .. tostring(err2)) end

pcall(ScenEdit_SetSidePosture, '红方', '蓝方', 'H')
pcall(ScenEdit_SetSidePosture, '蓝方', '红方', 'H')

-- =============================================================================
-- 【第二部分】EMCON 设置
-- =============================================================================

-- 潜艇全程静默航行，被动探测
pcall(ScenEdit_SetEMCON, 'Side', '红方', 'Radar=Passive;Sonar=Passive;OECM=Passive')
-- 电子战飞机有源干扰（侦察阶段后切换）
-- 水面舰艇雷达待机，被动警戒
-- 蓝方积极探测
pcall(ScenEdit_SetEMCON, 'Side', '蓝方', 'Radar=Active;Sonar=Active;OECM=Passive')

-- =============================================================================
-- 【第三部分】打击规则（Doctrine）
-- =============================================================================

-- 红方：水面/空中自由开火，潜艇默认待机（后续事件中授权）
pcall(ScenEdit_SetDoctrine, {side='红方'}, {
    weapon_control_status_surface     = 0,  -- Free
    weapon_control_status_air         = 0,  -- Free
    weapon_control_status_subsurface = 2,  -- Hold（潜艇待机）
    ignore_plotted_course           = 'no',
    use_nuclear_weapons             = 'no',
})
-- 蓝方：全向自由开火
pcall(ScenEdit_SetDoctrine, {side='蓝方'}, {
    weapon_control_status_surface     = 0,
    weapon_control_status_air         = 0,
    weapon_control_status_subsurface  = 0,
})

-- =============================================================================
-- 【第四部分】蓝方单位（目标编队：补给舰 + 2x DDG）
-- =============================================================================

-- 蓝方补给舰 (T-AKE)
local supply = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'blue_aux_supply_1',
    dbid        = DBID.supply_ship,
    latitude    = 30.1667,
    longitude   = 127.25,
    heading     = 0,
    speed       = 10,
    proficiency = 'Veteran'
})
if supply then ScenEdit_SetKeyValue('BLUE_SUPPLY_GUID', supply.guid) end
print('[蓝方] 补给舰 DBID=' .. DBID.supply_ship .. ' 已添加 (name=blue_aux_supply_1)')

-- 蓝方驱逐舰1 (DDG 51 Arleigh Burke)
local ddg1 = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'blue_ddg_burke_1',
    dbid        = DBID.burke_ddg,
    latitude    = 30.3333,
    longitude   = 127.5,
    heading     = 180,
    speed       = 15,
    proficiency = 'Veteran'
})
if ddg1 then ScenEdit_SetKeyValue('BLUE_DDG1_GUID', ddg1.guid) end
print('[蓝方] 驱逐舰1 DBID=' .. DBID.burke_ddg .. ' 已添加 (name=blue_ddg_burke_1)')

-- 蓝方驱逐舰2 (DDG 51 Arleigh Burke)
local ddg2 = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'blue_ddg_burke_2',
    dbid        = DBID.burke_ddg,
    latitude    = 30.0,
    longitude   = 127.75,
    heading     = 180,
    speed       = 15,
    proficiency = 'Veteran'
})
if ddg2 then ScenEdit_SetKeyValue('BLUE_DDG2_GUID', ddg2.guid) end
print('[蓝方] 驱逐舰2 DBID=' .. DBID.burke_ddg .. ' 已添加 (name=blue_ddg_burke_2)')

-- =============================================================================
-- 【第五部分】红方单位
-- =============================================================================

-- 5.1 039C 潜艇（水下突击群核心）
local sub = ScenEdit_AddUnit({
    side            = '红方',
    type            = 'Submarine',
    name            = 'red_sub_039c_1',
    dbid            = DBID.sub_039c,
    latitude        = 30.5,
    longitude       = 126.1667,
    heading         = 90,
    speed           = 5,
    proficiency     = 'Veteran',
    manualAltitude  = 60
})
if sub then ScenEdit_SetKeyValue('RED_SUB_GUID', sub.guid) end
print('[红方] 039C潜艇 DBID=' .. DBID.sub_039c .. ' 已添加 (name=red_sub_039c_1, LoadoutIDs: 658/6189/6190)')

-- 5.2 空中打击与支援群

-- J-16D 电子战飞机（侦察+干扰）
local j16d = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'red_j16d_1',
    dbid        = DBID.j16d,
    LoadoutID   = LOADOUT.j16d_ew,
    latitude    = 30.1333,
    longitude   = 123.0,
    altitude    = 8534,
    heading     = 0,
    speed       = 250,
    proficiency = 'Veteran'
})
if j16d then ScenEdit_SetKeyValue('RED_J16D_GUID', j16d.guid) end
print('[红方] J-16D DBID=' .. DBID.j16d .. ' LoadoutID=' .. LOADOUT.j16d_ew .. ' 已添加 (name=red_j16d_1)')

-- J-16 侦察机
local j16r = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'red_j16_1',
    dbid        = DBID.j16,
    LoadoutID   = LOADOUT.j16_escort,
    latitude    = 30.0,
    longitude   = 122.0,
    altitude    = 7620,
    heading     = 0,
    speed       = 250,
    proficiency = 'Veteran'
})
if j16r then ScenEdit_SetKeyValue('RED_J16R_GUID', j16r.guid) end
print('[红方] J-16(侦察) DBID=' .. DBID.j16 .. ' LoadoutID=' .. LOADOUT.j16_escort .. ' 已添加 (name=red_j16_1)')

-- J-16 打击机 1
local j16s1 = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'red_j16_2',
    dbid        = DBID.j16,
    LoadoutID   = LOADOUT.j16_strike,
    latitude    = 30.0833,
    longitude   = 122.1667,
    altitude    = 7620,
    heading     = 90,
    speed       = 240,
    proficiency = 'Veteran'
})
if j16s1 then ScenEdit_SetKeyValue('RED_J16S1_GUID', j16s1.guid) end
print('[红方] J-16(#2 打击) DBID=' .. DBID.j16 .. ' LoadoutID=' .. LOADOUT.j16_strike .. ' 已添加 (name=red_j16_2)')

-- J-16 打击机 2
local j16s2 = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'red_j16_3',
    dbid        = DBID.j16,
    LoadoutID   = LOADOUT.j16_strike,
    latitude    = 29.9167,
    longitude   = 122.0833,
    altitude    = 7315,
    heading     = 90,
    speed       = 250,
    proficiency = 'Veteran'
})
if j16s2 then ScenEdit_SetKeyValue('RED_J16S2_GUID', j16s2.guid) end
print('[红方] J-16(#3 打击) DBID=' .. DBID.j16 .. ' LoadoutID=' .. LOADOUT.j16_strike .. ' 已添加 (name=red_j16_3)')

-- J-16 打击机 3
local j16s3 = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'red_j16_4',
    dbid        = DBID.j16,
    LoadoutID   = LOADOUT.j16_strike,
    latitude    = 30.0333,
    longitude   = 122.25,
    altitude    = 7315,
    heading     = 0,
    speed       = 250,
    proficiency = 'Veteran'
})
if j16s3 then ScenEdit_SetKeyValue('RED_J16S3_GUID', j16s3.guid) end
print('[红方] J-16(#4 打击) DBID=' .. DBID.j16 .. ' LoadoutID=' .. LOADOUT.j16_strike .. ' 已添加 (name=red_j16_4)')

-- 5.3 水面支援群（2x 055 驱逐舰）
local ddg1 = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'red_ddg_055_1',
    dbid        = DBID.ddg_055,
    latitude    = 30.1667,
    longitude   = 123.5,
    heading     = 0,
    speed       = 10,
    proficiency = 'Veteran'
})
if ddg1 then ScenEdit_SetKeyValue('RED_DDG1_GUID', ddg1.guid) end
print('[红方] 055驱逐舰#1 DBID=' .. DBID.ddg_055 .. ' 已添加 (name=red_ddg_055_1)')

local ddg2 = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'red_ddg_055_2',
    dbid        = DBID.ddg_055,
    latitude    = 29.8333,
    longitude   = 123.8333,
    heading     = 0,
    speed       = 10,
    proficiency = 'Veteran'
})
if ddg2 then ScenEdit_SetKeyValue('RED_DDG2_GUID', ddg2.guid) end
print('[红方] 055驱逐舰#2 DBID=' .. DBID.ddg_055 .. ' 已添加 (name=red_ddg_055_2)')

-- =============================================================================
-- 【第六部分】参考点标注（目标区、巡逻区、攻击阵位）
-- =============================================================================

-- 蓝方目标区域标注（红方视角）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-补给舰', latitude=30.1667, longitude=127.25, highlighted=true, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-驱逐舰1', latitude=30.3333, longitude=127.5, highlighted=true, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-驱逐舰2', latitude=30.0,    longitude=127.75, highlighted=true, type='generic'})

-- 潜艇攻击阵位（6个航点）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-潜艇A-1', latitude=30.5,  longitude=126.1667, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-潜艇A-2', latitude=30.6,  longitude=126.5,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-潜艇A-3', latitude=30.7,  longitude=126.8,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-潜艇A-4', latitude=30.5,  longitude=127.0,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-潜艇A-5', latitude=30.4,  longitude=127.2,   highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-潜艇A-6', latitude=30.35, longitude=127.3,   highlighted=false, type='generic'})

-- 蓝方巡逻区（蓝方视角）
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-N-1', latitude=30.8, longitude=126.5, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-N-2', latitude=30.8, longitude=128.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-N-3', latitude=29.8, longitude=128.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-N-4', latitude=29.8, longitude=126.5, highlighted=false, type='generic'})

-- =============================================================================
-- 【第七部分】初始消息
-- =============================================================================

ScenEdit_SpecialMessage('红方', '【作战开始】红方反舰打击群进入东海，潜艇隐蔽接敌中……')
ScenEdit_SpecialMessage('蓝方', '【警报】不明水下目标接近，编队进入反潜戒备状态')

print('========================================')
print('隐蔽致命一击 — main.lua 执行完成')
print('红方: 1x 039C + 4x J-16 + 1x J-16D + 2x 055')
print('蓝方: 1x T-AKE补给舰 + 2x DDG-51')
print('DBID 来源: MCP HKBQ_SqlDB (真实数据)')
print('后续执行 mission.lua 加载任务规划')
print('========================================')
