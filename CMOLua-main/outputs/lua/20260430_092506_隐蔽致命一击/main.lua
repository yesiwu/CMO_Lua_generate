-- =============================================================================
-- main.lua — 隐蔽致命一击 (covert_decisive_strike_c)
-- 方案：联合火力突击训练场景 | 红方发起反舰攻击
-- 创建日期：2025-10-22 | 版本：1.0
-- =============================================================================

Tool_EmulateNoConsole(true)

-- =============================================================================
-- 1. 创建阵营 & 设置敌对关系
-- =============================================================================

local ok, err = pcall(ScenEdit_AddSide, {name = '红方', color = '255,0,0'})
if not ok then print('[WARNING] 红方已存在: ' .. tostring(err)) end

local ok2, err2 = pcall(ScenEdit_AddSide, {name = '蓝方', color = '0,0,255'})
if not ok2 then print('[WARNING] 蓝方已存在: ' .. tostring(err2)) end

pcall(ScenEdit_SetSidePosture, '红方', '蓝方', 'H')
pcall(ScenEdit_SetSidePosture, '蓝方', '红方', 'H')

-- EMCON 设置：潜艇保持静默，舰艇雷达待机，电子战飞机有源干扰
pcall(ScenEdit_SetEMCON, 'Side', '红方', 'Radar=Passive;Sonar=Passive;OECM=Passive')
pcall(ScenEdit_SetEMCON, 'Side', '蓝方', 'Radar=Active;Sonar=Active;OECM=Passive')

-- 打击规则：红方水面/空中自由开火权，潜艇待机
pcall(ScenEdit_SetDoctrine, {side='红方'}, {
    weapon_control_status_surface = 0,
    weapon_control_status_air     = 0,
    weapon_control_status_subsurface = 2,
    ignore_plotted_course        = 'no',
    use_nuclear_weapons          = 'no',
})
pcall(ScenEdit_SetDoctrine, {side='蓝方'}, {
    weapon_control_status_surface = 0,
    weapon_control_status_air     = 0,
    weapon_control_status_subsurface = 0,
})

-- =============================================================================
-- 2. 蓝方单位（模拟目标编队：补给舰+2x DDG-84 护卫）
-- =============================================================================

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = '蓝方补给舰',
    dbid        = 753,
    latitude    = 30.167,
    longitude   = 127.25,
    heading     = 0,
    speed       = 10,
    proficiency = 'Veteran'
})
print('[蓝方] 补给舰 DBID=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = '蓝方驱逐舰1',
    dbid        = 2869,
    latitude    = 30.333,
    longitude   = 127.5,
    heading     = 180,
    speed       = 15,
    proficiency = 'Veteran'
})
print('[蓝方] 驱逐舰1 DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = '蓝方驱逐舰2',
    dbid        = 2869,
    latitude    = 30.0,
    longitude   = 127.75,
    heading     = 180,
    speed       = 15,
    proficiency = 'Veteran'
})
print('[蓝方] 驱逐舰2 DBID=2869 已添加')

-- =============================================================================
-- 3. 红方单位（水下突击群 + 空中打击群 + 水面支援群）
-- =============================================================================

-- 3.1 水下突击群：039C 潜艇（隐蔽待机）

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = '红方潜艇A',
    dbid        = 4260,
    latitude    = 30.5,
    longitude   = 126.167,
    heading     = 90,
    speed       = 5,
    proficiency = 'Veteran'
})
print('[红方] 039C潜艇A DBID=4260 已添加 (初始航向90, 航速5kn)')

-- 3.2 空中打击群：4x J-16 + 1x J-16D

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'J-16D-1',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 30.133,
    longitude   = 123.0,
    altitude    = 8534,
    heading     = 0,
    speed       = 250,
    proficiency = 'Veteran'
})
print('[红方] J-16D-1 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'J-16-1(侦察)',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 30.0,
    longitude   = 122.0,
    altitude    = 7620,
    heading     = 0,
    speed       = 250,
    proficiency = 'Veteran'
})
print('[红方] J-16-1(侦察) DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'J-16-2(打击)',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 30.083,
    longitude   = 122.167,
    altitude    = 7620,
    heading     = 90,
    speed       = 240,
    proficiency = 'Veteran'
})
print('[红方] J-16-2(打击) DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'J-16-3(打击)',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 29.917,
    longitude   = 122.083,
    altitude    = 7315,
    heading     = 90,
    speed       = 250,
    proficiency = 'Veteran'
})
print('[红方] J-16-3(打击) DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'J-16-4(打击)',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 30.033,
    longitude   = 122.25,
    altitude    = 7315,
    heading     = 0,
    speed       = 250,
    proficiency = 'Veteran'
})
print('[红方] J-16-4(打击) DBID=2853 Loadout=1821 已添加')

-- 3.3 水面支援群：2x 055 驱逐舰

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = '红方驱逐舰A',
    dbid        = 4352,
    latitude    = 30.167,
    longitude   = 123.5,
    heading     = 0,
    speed       = 10,
    proficiency = 'Veteran'
})
print('[红方] 055驱逐舰A DBID=4352 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = '红方驱逐舰B',
    dbid        = 4352,
    latitude    = 29.833,
    longitude   = 123.833,
    heading     = 0,
    speed       = 10,
    proficiency = 'Veteran'
})
print('[红方] 055驱逐舰B DBID=4352 已添加')

-- =============================================================================
-- 4. 场景参考点（巡逻区/目标区标注）
-- =============================================================================

-- 蓝方目标区域（补给舰位置附近）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='目标区-补给舰', latitude=30.167, longitude=127.25, highlighted=true, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='目标区-驱逐舰1', latitude=30.333, longitude=127.5, highlighted=true, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='目标区-驱逐舰2', latitude=30.0, longitude=127.75, highlighted=true, type='generic'})

-- 红方潜艇攻击阵位
pcall(ScenEdit_AddReferencePoint, {side='红方', name='潜艇攻击阵位', latitude=30.35, longitude=127.3, highlighted=true, type='generic'})

-- 蓝方巡逻区
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='北部巡逻区', latitude=30.2, longitude=127.3, highlighted=true, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='南部巡逻区', latitude=29.8, longitude=127.3, highlighted=true, type='generic'})

-- =============================================================================
-- 5. 事件记录
-- =============================================================================
ScenEdit_SpecialMessage('红方', '【作战开始】红方反舰打击群进入东海海域，潜艇隐蔽接敌中……')
ScenEdit_SpecialMessage('蓝方', '【警报】蓝方护航编队在东海海域活动，发现不明电磁信号')

print('========================================')
print('隐蔽致命一击 Lua 脚本执行完成')
print('红方: 1x 039C + 4x J-16 + 1x J-16D + 2x 055')
print('蓝方: 1x 补给舰(T-AKE) + 2x DDG-84')
print('后续请执行 mission.lua 加载任务规划')
print('========================================')