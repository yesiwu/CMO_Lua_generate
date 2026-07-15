-- =============================================================================
-- A24场景.lua  — 有限反击训练场景 (A24)
-- 方案名称：有限反击训练场景 | 创建日期：2025-10-22 | 版本：1.0
-- 说明：从 json/A24场景.json 自动生成
-- =============================================================================
-- 【DBID 查询说明】
-- 以下装备类型在 CMO 数据库中未找到对应条目，按 SKILL 规范跳过：
--   SAT_JIANBING23        (卫星)           — CMO 数据库无卫星数据
--   EW_YUNLEIGAN9       (运雷干-9 电子战) — 无精确匹配
--   LHA_AMERICA          (两栖攻击舰)     — 无匹配
--   USV_OVERLORD        (无人水面艇)      — USV Ranger (3850) 存在但不通用
--   AGOS_VICTORIOUS      (监视船)         — T-AGOS 19 Victorious (365) 存在
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

-- === 02打击大队 (2x DF-17 发射车) → DBID 3205
local unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'df17001',
    dbid        = 3205,
    latitude    = 23.28,
    longitude   = 116.40,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-17 df17001 DBID=3205 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'df17002',
    dbid        = 3205,
    latitude    = 23.28,
    longitude   = 116.39,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-17 df17002 DBID=3205 已添加')

-- === 03打击大队 (4x DF-26B 发射车) → DBID 2879
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb001',
    dbid        = 2879,
    latitude    = 23.30,
    longitude   = 116.35,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26B dfb001 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb002',
    dbid        = 2879,
    latitude    = 23.28,
    longitude   = 116.33,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26B dfb002 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb003',
    dbid        = 2879,
    latitude    = 23.26,
    longitude   = 116.31,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26B dfb003 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb004',
    dbid        = 2879,
    latitude    = 23.24,
    longitude   = 116.29,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26B dfb004 DBID=2879 已添加')

-- === 04打击大队 (4x DF-26B 发射车) → DBID 2879
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb005',
    dbid        = 2879,
    latitude    = 23.22,
    longitude   = 116.27,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26B dfb005 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb006',
    dbid        = 2879,
    latitude    = 23.20,
    longitude   = 116.25,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26B dfb006 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb007',
    dbid        = 2879,
    latitude    = 23.18,
    longitude   = 116.23,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26B dfb007 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb008',
    dbid        = 2879,
    latitude    = 23.16,
    longitude   = 116.21,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SSM Bn DF-26B dfb008 DBID=2879 已添加')

-- === 05干扰大队 (1x J-16D 电子战) → DBID 4632, Loadout 753
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd001',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.61,
    longitude   = 112.89,
    altitude    = 1,
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
    latitude    = 9.56,
    longitude   = 112.88,
    altitude    = 0,
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
    latitude    = 9.51,
    longitude   = 112.87,
    altitude    = 1,
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
    latitude    = 9.46,
    longitude   = 112.86,
    altitude    = 1,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16D jd004 DBID=4632 Loadout=753 已添加')

-- === 电子战群01 (1x J-16D 电子战) → DBID 4632, Loadout 753
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'EW_JAMMER_01',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.94,
    longitude   = 115.50,
    altitude    = 0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16D EW_JAMMER_01 DBID=4632 Loadout=753 已添加')

-- === 03电子干扰大队 (3x Wing Loong II) → DBID 4725, Loadout 2179
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'wz001',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.9,
    longitude   = 115.5,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II wz001 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'wz002',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.96,
    longitude   = 115.58,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II wz002 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'wz003',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.94,
    longitude   = 115.53,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II wz003 DBID=4725 Loadout=2179 已添加')

-- === 06轰炸机大队 (8x H-6N 轰炸机) → DBID 4837
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk001',
    dbid        = 4837,
    latitude    = 26.47,
    longitude   = 112.79,
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
    latitude    = 26.28,
    longitude   = 112.71,
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
    latitude    = 26.24,
    longitude   = 112.63,
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
    latitude    = 26.20,
    longitude   = 112.55,
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
    latitude    = 26.16,
    longitude   = 112.47,
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
    latitude    = 26.12,
    longitude   = 112.39,
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
    latitude    = 26.20,
    longitude   = 112.79,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] KJ-500 kj001 DBID=3683 Loadout=494 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'kjh001',
    dbid        = 3683,
    LoadoutID   = 494,
    latitude    = 9.55,
    longitude   = 113.00,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] KJ-500 kjh001 DBID=3683 Loadout=494 已添加')

-- === 08战斗机大队 (4x J-20A) → DBID 5012, Loadout 1191
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20001',
    dbid        = 5012,
    LoadoutID   = 1191,
    latitude    = 18.51,
    longitude   = 109.98,
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
    latitude    = 18.50,
    longitude   = 109.98,
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
    latitude    = 18.50,
    longitude   = 109.99,
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
    latitude    = 18.49,
    longitude   = 110.00,
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
    latitude    = 18.50708,
    longitude   = 109.98021,
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
    latitude    = 18.48,
    longitude   = 109.99,
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
    latitude    = 18.50,
    longitude   = 109.98,
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
    latitude    = 18.49,
    longitude   = 109.98,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-20A j20008 DBID=5012 Loadout=1191 已添加')

-- === 05战斗机大队 (4x J-16) → DBID 2853, Loadout 1821
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16001',
    dbid        = 2853,
    LoadoutID   = 1821,
    latitude    = 9.95,
    longitude   = 115.38,
    altitude    = 1500,
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
    latitude    = 9.93,
    longitude   = 115.46,
    altitude    = 1500,
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
    latitude    = 9.87,
    longitude   = 115.40,
    altitude    = 1500,
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
    latitude    = 9.87,
    longitude   = 115.55,
    altitude    = 1500,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J-16 j16004 DBID=2853 Loadout=1821 已添加')

-- === 01僚机大队 (10x Wing Loong II) → DBID 4725, Loadout 2179
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'uav001',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.84,
    longitude   = 115.48,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II uav001 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'uav002',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.86,
    longitude   = 115.50,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II uav002 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'uav003',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.88,
    longitude   = 115.52,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II uav003 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'uav004',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.90,
    longitude   = 115.54,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II uav004 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'uav005',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.92,
    longitude   = 115.56,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II uav005 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'uav006',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.94,
    longitude   = 115.58,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II uav006 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'uav007',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.96,
    longitude   = 115.60,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II uav007 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'uav008',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 9.98,
    longitude   = 115.62,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II uav008 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'uav009',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 10.00,
    longitude   = 115.64,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II uav009 DBID=4725 Loadout=2179 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'uav010',
    dbid        = 4725,
    LoadoutID   = 2179,
    latitude    = 10.02,
    longitude   = 115.66,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] Wing Loong II uav010 DBID=4725 Loadout=2179 已添加')

-- === 水下特遣队01 (22x UUV) → DBID 4309
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv001',
    dbid        = 4309,
    latitude    = 7.79,
    longitude   = 118.68,
    altitude    = -300,
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
    latitude    = 7.84,
    longitude   = 118.72,
    altitude    = -300,
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
    latitude    = 7.83,
    longitude   = 118.76,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv003 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv004',
    dbid        = 4309,
    latitude    = 7.85,
    longitude   = 118.78,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv004 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv005',
    dbid        = 4309,
    latitude    = 7.80,
    longitude   = 118.65,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv005 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv006',
    dbid        = 4309,
    latitude    = 7.75,
    longitude   = 118.60,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv006 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv007',
    dbid        = 4309,
    latitude    = 7.70,
    longitude   = 118.55,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv007 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv008',
    dbid        = 4309,
    latitude    = 7.65,
    longitude   = 118.50,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv008 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv009',
    dbid        = 4309,
    latitude    = 7.60,
    longitude   = 118.45,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv009 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv010',
    dbid        = 4309,
    latitude    = 7.55,
    longitude   = 118.40,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv010 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv011',
    dbid        = 4309,
    latitude    = 7.50,
    longitude   = 118.35,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv011 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv012',
    dbid        = 4309,
    latitude    = 7.45,
    longitude   = 118.30,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv012 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv013',
    dbid        = 4309,
    latitude    = 7.40,
    longitude   = 118.25,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv013 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv014',
    dbid        = 4309,
    latitude    = 7.35,
    longitude   = 118.20,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv014 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv015',
    dbid        = 4309,
    latitude    = 7.30,
    longitude   = 118.15,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv015 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv016',
    dbid        = 4309,
    latitude    = 7.25,
    longitude   = 118.10,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv016 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv017',
    dbid        = 4309,
    latitude    = 7.20,
    longitude   = 118.05,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv017 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv018',
    dbid        = 4309,
    latitude    = 7.15,
    longitude   = 118.00,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv018 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv019',
    dbid        = 4309,
    latitude    = 7.10,
    longitude   = 117.95,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv019 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv020',
    dbid        = 4309,
    latitude    = 7.05,
    longitude   = 117.90,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv020 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv021',
    dbid        = 4309,
    latitude    = 7.00,
    longitude   = 117.85,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv021 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'uuv022',
    dbid        = 4309,
    latitude    = 6.95,
    longitude   = 117.80,
    altitude    = -300,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] UUV uuv022 DBID=4309 已添加')

-- === 03驱逐舰大队 (2x 055 驱逐舰) → DBID 4352
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_055_01',
    dbid        = 4352,
    latitude    = 5.80,
    longitude   = 108.51,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_055_01 DBID=4352 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_055_02',
    dbid        = 4352,
    latitude    = 5.90,
    longitude   = 108.60,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_055_02 DBID=4352 已添加')

-- === 04护卫舰大队 (4x 055 驱逐舰) → DBID 4352
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_055_03',
    dbid        = 4352,
    latitude    = 5.40,
    longitude   = 108.59,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_055_03 DBID=4352 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_055_04',
    dbid        = 4352,
    latitude    = 6.13,
    longitude   = 107.80,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_055_04 DBID=4352 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_055_05',
    dbid        = 4352,
    latitude    = 12.59,
    longitude   = 118.09,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_055_05 DBID=4352 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_055_06',
    dbid        = 4352,
    latitude    = 12.50,
    longitude   = 118.00,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_055_06 DBID=4352 已添加')

-- === 05驱逐舰大队 (1x 055 驱逐舰) → DBID 4352
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_055_07',
    dbid        = 4352,
    latitude    = 5.80,
    longitude   = 108.51,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_055_07 DBID=4352 已添加')

-- === 06护卫舰支队 (3x 055 驱逐舰) → DBID 4352
unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_055_08',
    dbid        = 4352,
    latitude    = 5.40,
    longitude   = 108.59,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_055_08 DBID=4352 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_055_09',
    dbid        = 4352,
    latitude    = 6.13,
    longitude   = 107.80,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_055_09 DBID=4352 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_055_10',
    dbid        = 4352,
    latitude    = 12.59,
    longitude   = 118.09,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] 055 ddg_055_10 DBID=4352 已添加')

-- =============================================================================
-- 3. 蓝方单位（按 JSON Equipments 位置信息）
-- =============================================================================

-- === 10号编队 (1x CVN Nimitz, 2x Ticonderoga, 3x DDG, 1x 补给舰)
-- CVN_LINCOLN → CVN 68 Nimitz (DBID 429)
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'cvn_linking',
    dbid        = 429,
    latitude    = -1.83,
    longitude   = 107.78,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] CVN 68 Nimitz cvn_linking DBID=429 已添加')

-- CG 59 Princeton Baseline 3 (DBID 599)
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'cg_blue_001',
    dbid        = 599,
    latitude    = -1.72,
    longitude   = 107.45,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] CG 59 Princeton cg_blue_001 DBID=599 已添加')

-- DDG-84 Burke 驱逐舰
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_chafee_001',
    dbid        = 2869,
    latitude    = 3.68,
    longitude   = 112.57,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_chafee_001 DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_chafee_002',
    dbid        = 2869,
    latitude    = 0.16,
    longitude   = 107.27,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_chafee_002 DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_chafee_003',
    dbid        = 2869,
    latitude    = -1.31,
    longitude   = 107.82,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_chafee_003 DBID=2869 已添加')

-- 补给舰 → T-AKE 1 Lewis and Clark (DBID 753)
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'supply_kz',
    dbid        = 753,
    latitude    = -1.00,
    longitude   = 107.50,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] T-AKE 1 Lewis and Clark supply_kz DBID=753 已添加')

-- === 11号两栖编队 (1x LHA, 1x Ticonderoga, 2x DDG) → LHA SKIP
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'cg_blue_002',
    dbid        = 599,
    latitude    = 6.94,
    longitude   = 118.36,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] CG 59 Princeton cg_blue_002 DBID=599 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_blue_001',
    dbid        = 2869,
    latitude    = 7.73,
    longitude   = 118.86,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_blue_001 DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_blue_002',
    dbid        = 2869,
    latitude    = 7.11,
    longitude   = 118.90,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG-84 ddg_blue_002 DBID=2869 已添加')

-- === 12无人舰艇编队 (6x USV) → SKIP: 无精确匹配

-- === 02监视船编队 (3x T-AGOS) → T-AGOS 19 Victorious (DBID 365)
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'agos_001',
    dbid        = 365,
    latitude    = 7.50,
    longitude   = 119.50,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] T-AGOS agos_001 DBID=365 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'agos_002',
    dbid        = 365,
    latitude    = 7.55,
    longitude   = 119.60,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] T-AGOS agos_002 DBID=365 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'agos_003',
    dbid        = 365,
    latitude    = 7.60,
    longitude   = 119.70,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] T-AGOS agos_003 DBID=365 已添加')

-- === 14闪电战斗机编队 (4x F-35C + 2x F-35B) → DBID 824/3870, Loadout 2607/689
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35c_001',
    dbid        = 824,
    LoadoutID   = 2607,
    latitude    = -1.85,
    longitude   = 107.81,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35C f35c_001 DBID=824 Loadout=2607 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35c_002',
    dbid        = 824,
    LoadoutID   = 2607,
    latitude    = -1.84,
    longitude   = 107.82,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35C f35c_002 DBID=824 Loadout=2607 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35c_003',
    dbid        = 824,
    LoadoutID   = 2607,
    latitude    = -4.41,
    longitude   = 108.13,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35C f35c_003 DBID=824 Loadout=2607 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35c_004',
    dbid        = 824,
    LoadoutID   = 2607,
    latitude    = -1.87,
    longitude   = 107.80,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35C f35c_004 DBID=824 Loadout=2607 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35b_001',
    dbid        = 3870,
    LoadoutID   = 689,
    latitude    = 6.56,
    longitude   = 118.97,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35B f35b_001 DBID=3870 Loadout=689 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35b_002',
    dbid        = 3870,
    LoadoutID   = 689,
    latitude    = 6.54,
    longitude   = 118.95,
    altitude    = 1000,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F-35B f35b_002 DBID=3870 Loadout=689 已添加')

-- === 15远程火力营 (10x HIMARS) → DBID 3268
unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms001',
    dbid        = 3268,
    latitude    = 9.951,
    longitude   = 118.702,
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
    latitude    = 9.950,
    longitude   = 118.700,
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
    latitude    = 9.950,
    longitude   = 118.700,
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
    latitude    = 9.950,
    longitude   = 118.700,
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
    latitude    = 9.950,
    longitude   = 118.700,
    heading     = 45,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms005 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms006',
    dbid        = 3268,
    latitude    = 9.950,
    longitude   = 118.700,
    heading     = 135,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms006 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms007',
    dbid        = 3268,
    latitude    = 9.950,
    longitude   = 118.700,
    heading     = 225,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms007 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms008',
    dbid        = 3268,
    latitude    = 9.950,
    longitude   = 118.700,
    heading     = 315,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms008 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms009',
    dbid        = 3268,
    latitude    = 9.950,
    longitude   = 118.700,
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
    latitude    = 9.950,
    longitude   = 118.700,
    heading     = 90,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HIMARS hms010 DBID=3268 已添加')

-- === 16导弹连 (4x GND_TYPHON_LAUNCHER) → SKIP: 无匹配

-- =============================================================================
-- 4. 完成提示
-- =============================================================================
print('========================================')
print('A24场景 Lua 脚本执行完成')
print('红方: 9架 J-16D + 8架 H-6N + 13架 Wing Loong II + 2架 KJ-500 + 8架 J-20A + 4架 J-16 + 22艘 UUV + 10艘 055')
print('蓝方: 4架 F-35C + 2架 F-35B + 1艘 CVN + 2艘 CG59 + 7艘 DDG-84 + 1艘补给舰 + 3艘 T-AGOS + 10个 HIMARS')
print('已跳过: 卫星、EW_YUNLEIGAN9、LHA_America、USV、Typhon发射车')
print('========================================')
