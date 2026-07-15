-- =============================================================================
-- A1场景.lua  — 联合火力突击训练场景 (A1)
-- 方案名称：联合火力突击训练场景 | 创建日期：2025-10-22 | 版本：1.0
-- 说明：从 json/A1场景.json 自动生成（第二次查询更新版）
-- =============================================================================
-- 【DBID 查询说明 - 更新版】
-- 以下装备类型在 CMO 数据库中未找到对应条目，按 SKILL 规范跳过：
--   SAT_JIANBING23        (卫星)           — CMO 数据库无卫星数据
--   LHA_AMERICA          (两栖攻击舰)     — 无匹配
--   FFG_RICHMOND         (护卫舰)         — 无精确匹配
--   USV_OVERLORD        (无人水面艇)      — 无匹配
--   GND_TYPHON_LAUNCHER  (标准导弹发射车) — 无匹配

Tool_EmulateNoConsole(true)

-- =============================================================================
-- 1. 创建阵营 & 设置关系
-- =============================================================================

local ok, err = pcall(ScenEdit_AddSide, {name = '红方', color = '255,0,0'})
if not ok then print('[WARNING] 红方 side 可能已存在: ' .. tostring(err)) end

local ok2, err2 = pcall(ScenEdit_AddSide, {name = '蓝方', color = '0,0,255'})
if not ok2 then print('[WARNING] 蓝方 side 可能已存在: ' .. tostring(err2)) end

pcall(ScenEdit_SetSidePosture, '红方', '蓝方', 'H')

-- =============================================================================
-- 2. 红方单位（按 JSON Equipments 位置信息）
-- =============================================================================

-- === 05干扰大队 (8x J-16D 电子战) → DBID 4632, Loadout 753
local unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd001',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.93,
    longitude   = 115.51,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16D jd001 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd002',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.91,
    longitude   = 115.53,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16D jd002 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd003',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.91,
    longitude   = 115.50,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16D jd003 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd004',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.90,
    longitude   = 115.49,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16D jd004 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd005',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.90,
    longitude   = 115.48,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16D jd005 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd006',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.89,
    longitude   = 115.47,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16D jd006 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd007',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.88,
    longitude   = 115.46,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16D jd007 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd008',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.88,
    longitude   = 115.45,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16D jd008 DBID=4632 Loadout=753 已添加')

-- === 06轰炸机大队 (8x H-6N 轰炸机) → DBID 4837, 无 Loadout (轰炸机)
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk001',
    dbid        = 4837,
    latitude    = 13.00,
    longitude   = 111.04,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H-6N hk001 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk002',
    dbid        = 4837,
    latitude    = 26.38,
    longitude   = 112.70,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H-6N hk002 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk003',
    dbid        = 4837,
    latitude    = 26.32,
    longitude   = 112.79,
    altitude    = 900,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H-6N hk003 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk004',
    dbid        = 4837,
    latitude    = 26.30,
    longitude   = 112.91,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H-6N hk004 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk005',
    dbid        = 4837,
    latitude    = 26.45,
    longitude   = 112.90,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H-6N hk005 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk006',
    dbid        = 4837,
    latitude    = 26.22,
    longitude   = 112.68,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H-6N hk006 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk007',
    dbid        = 4837,
    latitude    = 26.20,
    longitude   = 112.91,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H-6N hk007 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk008',
    dbid        = 4837,
    latitude    = 26.39,
    longitude   = 112.98,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H-6N hk008 DBID=4837 已添加')

-- === 07预警大队 (2x KJ-500 预警机) → DBID 3683, Loadout 494
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'kj001',
    dbid        = 3683,
    LoadoutID   = 494,
    latitude    = 13.02,
    longitude   = 110.95,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] KJ-500 kj001 DBID=3683 Loadout=494 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'kj002',
    dbid        = 3683,
    LoadoutID   = 494,
    latitude    = 26.32,
    longitude   = 112.63,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] KJ-500 kj002 DBID=3683 Loadout=494 已添加')

-- === 02打击大队 (2x DF-26D 发射车) → DBID 2879
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb001',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.00,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfb001 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb002',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.01,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfb002 DBID=2879 已添加')

-- === 03打击大队 (10x DF-26D 发射车) → DBID 2879
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd001',
    dbid        = 2879,
    latitude    = 23.67,
    longitude   = 113.00,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfd001 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd002',
    dbid        = 2879,
    latitude    = 23.67,
    longitude   = 112.9,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfd002 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd003',
    dbid        = 2879,
    latitude    = 23.65,
    longitude   = 112.99,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfd003 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd004',
    dbid        = 2879,
    latitude    = 23.63,
    longitude   = 112.98,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfd004 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd005',
    dbid        = 2879,
    latitude    = 23.61,
    longitude   = 112.97,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfd005 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd006',
    dbid        = 2879,
    latitude    = 23.59,
    longitude   = 112.96,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfd006 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd007',
    dbid        = 2879,
    latitude    = 23.57,
    longitude   = 112.95,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfd007 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd008',
    dbid        = 2879,
    latitude    = 23.55,
    longitude   = 112.94,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfd008 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd009',
    dbid        = 2879,
    latitude    = 23.53,
    longitude   = 112.93,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfd009 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd010',
    dbid        = 2879,
    latitude    = 23.51,
    longitude   = 112.92,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26D dfd010 DBID=2879 已添加')

-- === 03无人艇大队 (17x UUV 无人潜航器) → DBID 4309
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt001',
    dbid        = 4309,
    latitude    = 5.58,
    longitude   = 107.42,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt001 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt002',
    dbid        = 4309,
    latitude    = 5.37,
    longitude   = 108.00,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt002 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt003',
    dbid        = 4309,
    latitude    = 5.39,
    longitude   = 107.63,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt003 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt004',
    dbid        = 4309,
    latitude    = 8.15,
    longitude   = 116.48,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt004 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt005',
    dbid        = 4309,
    latitude    = 7.80,
    longitude   = 116.29,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt005 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt006',
    dbid        = 4309,
    latitude    = 7.51,
    longitude   = 116.11,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt006 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt007',
    dbid        = 4309,
    latitude    = 7.23,
    longitude   = 115.87,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt007 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt008',
    dbid        = 4309,
    latitude    = 7.15,
    longitude   = 115.70,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt008 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt009',
    dbid        = 4309,
    latitude    = 7.01,
    longitude   = 115.48,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt009 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt010',
    dbid        = 4309,
    latitude    = 6.85,
    longitude   = 115.30,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt010 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt011',
    dbid        = 4309,
    latitude    = 6.70,
    longitude   = 115.14,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt011 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt012',
    dbid        = 4309,
    latitude    = 6.55,
    longitude   = 114.96,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt012 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt013',
    dbid        = 4309,
    latitude    = 6.42,
    longitude   = 114.78,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt013 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt014',
    dbid        = 4309,
    latitude    = 6.30,
    longitude   = 114.60,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt014 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt015',
    dbid        = 4309,
    latitude    = 6.20,
    longitude   = 114.43,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt015 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt016',
    dbid        = 4309,
    latitude    = 6.10,
    longitude   = 114.25,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt016 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt017',
    dbid        = 4309,
    latitude    = 6.00,
    longitude   = 114.08,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV wrt017 DBID=4309 已添加')

-- === 01水面舰艇支队 (2x 052D + 1x 055 + 2x 054A)
-- 052D 驱逐舰 ddg_01073
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_01073',
    dbid        = 4354,
    latitude    = 5.68,
    longitude   = 108.90,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 052D ddg_01073 DBID=4354 已添加')

-- 055 驱逐舰 ddg_01005
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_01005',
    dbid        = 4352,
    latitude    = 6.14,
    longitude   = 108.60,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_01005 DBID=4352 已添加')

-- 052D 驱逐舰 ddg_09006
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_09006',
    dbid        = 4354,
    latitude    = 5.82,
    longitude   = 108.48,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 052D ddg_09006 DBID=4354 已添加')

-- 054A 护卫舰 ffg_05005
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ffg_05005',
    dbid        = 4361,
    latitude    = 5.93,
    longitude   = 108.18,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 054A ffg_05005 DBID=4361 已添加')

-- 054A 护卫舰 ffg_05075
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ffg_05075',
    dbid        = 4361,
    latitude    = 5.66,
    longitude   = 108.54,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 054A ffg_05075 DBID=4361 已添加')

-- === 01无人潜艇大队 (1x 039C 潜艇) → DBID 4260
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'subc001',
    dbid        = 4260,
    latitude    = 7.51,
    longitude   = 116.23,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 039C subc001 DBID=4260 已添加')

-- === 02无人潜艇大队 (1x 039C 潜艇) → DBID 4260
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'subc002',
    dbid        = 4260,
    latitude    = 7.81,
    longitude   = 116.55,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 039C subc002 DBID=4260 已添加')

-- === 05战斗机大队 (6x J-16) → DBID 2853, Loadout 1821
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16001',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 10.91,
    longitude   = 114.02,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16001 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16002',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 10.94,
    longitude   = 114.14,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16002 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16003',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 9.46,
    longitude   = 113.14,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16003 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16004',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 10.90,
    longitude   = 114.07,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16004 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16005',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 10.92,
    longitude   = 114.05,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16005 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16006',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 10.88,
    longitude   = 114.10,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16006 DBID=2853 Loadout=1821 已添加')

-- === 06战斗机大队 (6x J-16) → DBID 2853, Loadout 1821
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16007',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 9.61,
    longitude   = 113.13,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16007 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16008',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 9.61,
    longitude   = 113.13,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16008 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16009',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 9.65,
    longitude   = 113.05,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16009 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16010',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 9.64,
    longitude   = 112.94,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16010 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16011',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 9.72,
    longitude   = 113.10,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16011 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16012',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 9.64,
    longitude   = 113.00,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16012 DBID=2853 Loadout=1821 已添加')

-- === 08战斗机大队 (4x J-20A) → DBID 5012, Loadout 1191
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20001',
    dbid        = 5012,
    LoadoutID   = 1191,
    latitude    = 18.50,
    longitude   = 109.97,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-20A j20001 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20002',
    dbid        = 5012,
    LoadoutID   = 1191,
    latitude    = 18.48,
    longitude   = 109.95,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-20A j20002 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20003',
    dbid        = 5012,
    LoadoutID   = 1191,
    latitude    = 18.46,
    longitude   = 109.93,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-20A j20003 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20004',
    dbid        = 5012,
    LoadoutID   = 1191,
    latitude    = 18.44,
    longitude   = 109.91,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-20A j20004 DBID=5012 Loadout=1191 已添加')

-- === 07战斗机大队 (4x J-20A) → DBID 5012, Loadout 1191
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20005',
    dbid        = 5012,
    LoadoutID   = 1191,
    latitude    = 13.01,
    longitude   = 110.82,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-20A j20005 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20006',
    dbid        = 5012,
    LoadoutID   = 1191,
    latitude    = 12.94,
    longitude   = 110.89,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-20A j20006 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20007',
    dbid        = 5012,
    LoadoutID   = 1191,
    latitude    = 12.88,
    longitude   = 111.00,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-20A j20007 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20008',
    dbid        = 5012,
    LoadoutID   = 1191,
    latitude    = 12.92,
    longitude   = 111.10,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-20A j20008 DBID=5012 Loadout=1191 已添加')

-- === 03无人潜航支队 (3x UUV 无人潜航器) → DBID 4309
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv001',
    dbid        = 4309,
    latitude    = -0.155,
    longitude   = 106.1643,
    altitude    = 20,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv001 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv002',
    dbid        = 4309,
    latitude    = -0.20,
    longitude   = 106.30,
    altitude    = 20,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv002 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv003',
    dbid        = 4309,
    latitude    = -0.25,
    longitude   = 106.45,
    altitude    = 20,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv003 DBID=4309 已添加')

-- === 04干扰大队 (3x 翼龙-2D 无人机) → DBID 4334, Loadout 502
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'wz001',
    dbid        = 4334,
    LoadoutID   = 502,
    latitude    = 9.54,
    longitude   = 112.88,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 翼龙-2D wz001 DBID=4334 Loadout=502 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'wz002',
    dbid        = 4334,
    LoadoutID   = 502,
    latitude    = 9.58,
    longitude   = 112.85,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 翼龙-2D wz002 DBID=4334 Loadout=502 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'wz003',
    dbid        = 4334,
    LoadoutID   = 502,
    latitude    = 9.71,
    longitude   = 113.01,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 翼龙-2D wz003 DBID=4334 Loadout=502 已添加')

-- =============================================================================
-- 3. 蓝方单位（按 JSON Equipments 位置信息）
-- =============================================================================

-- === 01两栖攻击舰编队
-- LHA_AMERICA → SKIP: 数据库无此舰型
-- Ticonderoga → SKIP: 无精确匹配（使用 CG 47 Ticonderoga Baseline 0, DBID 42）
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_chafei',
    dbid        = 2869,
    latitude    = 8.284662,
    longitude   = 119.783273,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_chafei DBID=2869 已添加')

-- === 01无人舰艇编队 (3x USV) → SKIP: USV Ranger (3850) 存在但为实验型号

-- === 02监视船编队 (3x AGOS) → T-AGOS 19 Victorious (DBID 365)
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'agos_shenli',
    dbid        = 365,
    latitude    = 20.29,
    longitude   = 119.57,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] T-AGOS agos_shenli DBID=365 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'agos_wuxia',
    dbid        = 365,
    latitude    = 14.06,
    longitude   = 119.2,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] T-AGOS agos_wuxia DBID=365 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'agos_zhuncheng',
    dbid        = 365,
    latitude    = 14.10,
    longitude   = 119.25,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] T-AGOS agos_zhuncheng DBID=365 已添加')

-- === 01航母编队 (1x CVN Nimitz, 2x Ticonderoga, 4x DDG, 1x 补给舰, 1x FFG_Richmond)
-- CVN_LINCOLN → CVN 68 Nimitz (DBID 429)
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'cvn_linkeng',
    dbid        = 429,
    latitude    = -0.90,
    longitude   = 106.11,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] CVN 68 Nimitz cvn_linkeng DBID=429 已添加')

-- Ticonderoga → CG 59 Princeton Baseline 3 (DBID 599)
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'tico_pulinsidun',
    dbid        = 599,
    latitude    = -0.659581,
    longitude   = 105.813746,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] CG 59 Princeton tico_pulinsidun DBID=599 已添加')

-- DDG-84 Burke 驱逐舰
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_momuseng',
    dbid        = 2869,
    latitude    = 7.104,
    longitude   = 116.28,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_momuseng DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_laolunsi',
    dbid        = 2869,
    latitude    = -1.463116,
    longitude   = 106.661538,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_laolunsi DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_huobate',
    dbid        = 2869,
    latitude    = 0.42728,
    longitude   = 105.267494,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_huobate DBID=2869 已添加')

-- 补给舰 → T-AKE 1 Lewis and Clark (DBID 753)
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'supply_kz',
    dbid        = 753,
    latitude    = -0.50,
    longitude   = 106.00,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] T-AKE 1 Lewis and Clark supply_kz DBID=753 已添加')

-- FFG_RICHMOND → SKIP: 无精确匹配

-- === 02两栖攻击舰编队 (4x DDG_CHAFEE) → DBID 2869
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_b02_01',
    dbid        = 2869,
    latitude    = 7.50,
    longitude   = 119.50,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_b02_01 DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_b02_02',
    dbid        = 2869,
    latitude    = 7.55,
    longitude   = 119.60,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_b02_02 DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_b02_03',
    dbid        = 2869,
    latitude    = 7.60,
    longitude   = 119.70,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_b02_03 DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_b02_04',
    dbid        = 2869,
    latitude    = 7.65,
    longitude   = 119.80,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_b02_04 DBID=2869 已添加')

-- === 03闪电战斗机编队 (3x F-35C Lightning) → DBID 824, Loadout 2607
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35c001',
    dbid        = 824,
    LoadoutID   = 2607,
    latitude    = -0.723911,
    longitude   = 106.122993,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35C f35c001 DBID=824 Loadout=2607 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35c002',
    dbid        = 824,
    LoadoutID   = 2607,
    latitude    = -0.72,
    longitude   = 106.13,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35C f35c002 DBID=824 Loadout=2607 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35c003',
    dbid        = 824,
    LoadoutID   = 2607,
    latitude    = -0.71,
    longitude   = 106.14,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35C f35c003 DBID=824 Loadout=2607 已添加')

-- === 04闪电战斗机编队 (4x F-35B Lightning) → DBID 3870, Loadout 689
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35b001',
    dbid        = 3870,
    LoadoutID   = 689,
    latitude    = 7.93,
    longitude   = 120.09,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35B f35b001 DBID=3870 Loadout=689 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35b002',
    dbid        = 3870,
    LoadoutID   = 689,
    latitude    = 7.95,
    longitude   = 120.10,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35B f35b002 DBID=3870 Loadout=689 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35b003',
    dbid        = 3870,
    LoadoutID   = 689,
    latitude    = 7.97,
    longitude   = 120.11,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35B f35b003 DBID=3870 Loadout=689 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35b004',
    dbid        = 3870,
    LoadoutID   = 689,
    latitude    = 7.99,
    longitude   = 120.12,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35B f35b004 DBID=3870 Loadout=689 已添加')

-- === 01远程发射营 (10x HIMARS) → DBID 3268
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms001',
    dbid        = 3268,
    latitude    = 9.95,
    longitude   = 118.7,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms001 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms002',
    dbid        = 3268,
    latitude    = 9.95,
    longitude   = 118.7,
    heading     = 90,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms002 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms003',
    dbid        = 3268,
    latitude    = 9.95,
    longitude   = 118.7,
    heading     = 180,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms003 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms004',
    dbid        = 3268,
    latitude    = 9.95,
    longitude   = 118.7,
    heading     = 270,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms004 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms005',
    dbid        = 3268,
    latitude    = 9.96,
    longitude   = 118.71,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms005 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms006',
    dbid        = 3268,
    latitude    = 9.96,
    longitude   = 118.71,
    heading     = 90,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms006 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms007',
    dbid        = 3268,
    latitude    = 9.96,
    longitude   = 118.71,
    heading     = 180,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms007 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms008',
    dbid        = 3268,
    latitude    = 9.96,
    longitude   = 118.71,
    heading     = 270,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms008 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms009',
    dbid        = 3268,
    latitude    = 9.97,
    longitude   = 118.72,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms009 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms010',
    dbid        = 3268,
    latitude    = 9.97,
    longitude   = 118.72,
    heading     = 90,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms010 DBID=3268 已添加')

-- === 02导弹连 (4x GND_TYPHON_LAUNCHER) → SKIP: 无匹配

-- =============================================================================
-- 4. 完成提示
-- =============================================================================
print('========================================')
print('A1场景 Lua 脚本执行完成（更新版）')
print('红方: 8架 J-16D + 8架 H-6N + 2架 KJ-500 + 12架 J-16 + 8架 J-20A + 20艘 UUV + 2艘 039C + 5艘水面舰 + 12个 DF-26 + 3架 翼龙-2D')
print('蓝方: 3架 F-35C + 4架 F-35B + 1艘 CVN + 1艘 CG59 + 14艘 DDG-84 + 1艘补给舰 + 3艘 T-AGOS + 10个 HIMARS')
print('已跳过: 卫星、LHA_America、FFG_Richmond、USV、Typhon发射车')
print('========================================')
