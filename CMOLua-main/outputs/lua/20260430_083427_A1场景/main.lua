-- =============================================================================
-- main.lua — 联合火力突击训练场景 (A1)
-- 方案名称：联合火力突击训练场景 | 创建日期：2025-10-22 | 版本：1.0
-- 说明：从 json/A1场景.json 自动生成（重新完整生成版）
-- =============================================================================

-- 【DBID 查询说明】
-- 通过 MCP (HKBQ_SqlDB) 连接 DB3K_504.db3 查询，所有 DBID 均来自真实数据库
-- 以下装备类型在 CMO 数据库中未找到对应条目，已跳过：
--   SAT_JIANBING23        (卫星)              — CMO 数据库无卫星数据
--   LHA_AMERICA          (两栖攻击舰)        — 无此舰型
--   USV_OVERLORD         (无人水面艇)         — 无此装备
--   GND_TYPHON_LAUNCHER  (标准导弹发射车)    — 无此装备

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
-- === 北部卫星测控站 → SKIP: SAT_JIANBING23 (51x) — 数据库无此装备

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb001',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB001 dfb001 DBID=2879 已添加')

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
print('[红方] DFB002 dfb002 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb003',
    dbid        = 2879,
    latitude    = 18.55,
    longitude   = 110.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB003 dfb003 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb004',
    dbid        = 2879,
    latitude    = 18.55,
    longitude   = 110.01,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB004 dfb004 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb005',
    dbid        = 2879,
    latitude    = 18.55,
    longitude   = 110.01,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB005 dfb005 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb006',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.01,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB006 dfb006 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb007',
    dbid        = 2879,
    latitude    = 18.55,
    longitude   = 110.01,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB007 dfb007 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb008',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.02,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB008 dfb008 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb009',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.03,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB009 dfb009 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb010',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.035,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB010 dfb010 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb011',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.03,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB011 dfb011 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb012',
    dbid        = 2879,
    latitude    = 18.53,
    longitude   = 110.03,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB012 dfb012 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb013',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB013 dfb013 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb014',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB014 dfb014 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb015',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB015 dfb015 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb016',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB016 dfb016 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb017',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB017 dfb017 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb018',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB018 dfb018 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb019',
    dbid        = 2879,
    latitude    = 18.54,
    longitude   = 110.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB019 dfb019 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfb020',
    dbid        = 2879,
    latitude    = 18.5,
    longitude   = 110.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFB020 dfb020 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd001',
    dbid        = 2879,
    latitude    = 23.67,
    longitude   = 113.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD001 dfd001 DBID=2879 已添加')

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
print('[红方] DFD002 dfd002 DBID=2879 已添加')

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
print('[红方] DFD003 dfd003 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd004',
    dbid        = 2879,
    latitude    = 23.66,
    longitude   = 112.98,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD004 dfd004 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd005',
    dbid        = 2879,
    latitude    = 23.65,
    longitude   = 112.97,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD005 dfd005 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd006',
    dbid        = 2879,
    latitude    = 23.65,
    longitude   = 112.99,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD006 dfd006 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd007',
    dbid        = 2879,
    latitude    = 23.64,
    longitude   = 112.97,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD007 dfd007 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd008',
    dbid        = 2879,
    latitude    = 23.64,
    longitude   = 112.99,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD008 dfd008 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd009',
    dbid        = 2879,
    latitude    = 23.65,
    longitude   = 112.99,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD009 dfd009 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd010',
    dbid        = 2879,
    latitude    = 23.65,
    longitude   = 113.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD010 dfd010 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd011',
    dbid        = 2879,
    latitude    = 23.65,
    longitude   = 113.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD011 dfd011 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd012',
    dbid        = 2879,
    latitude    = 23.64,
    longitude   = 112.99,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD012 dfd012 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd013',
    dbid        = 2879,
    latitude    = 23.64,
    longitude   = 112.97,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD013 dfd013 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd014',
    dbid        = 2879,
    latitude    = 23.64,
    longitude   = 112.98,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD014 dfd014 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd015',
    dbid        = 2879,
    latitude    = 23.63,
    longitude   = 112.97,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD015 dfd015 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd016',
    dbid        = 2879,
    latitude    = 23.63,
    longitude   = 112.98,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD016 dfd016 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd017',
    dbid        = 2879,
    latitude    = 23.63,
    longitude   = 112.97,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD017 dfd017 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd018',
    dbid        = 2879,
    latitude    = 23.63,
    longitude   = 112.98,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD018 dfd018 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd019',
    dbid        = 2879,
    latitude    = 23.63,
    longitude   = 112.97,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD019 dfd019 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Facility',
    name        = 'dfd020',
    dbid        = 2879,
    latitude    = 23.63,
    longitude   = 112.98,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DFD020 dfd020 DBID=2879 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'wz001',
    dbid        = 4334,, LoadoutID = 502
    latitude    = 9.54,
    longitude   = 112.88,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WZ001 wz001 DBID=4334 Loadout=502 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'wz002',
    dbid        = 4334,, LoadoutID = 502
    latitude    = 9.58,
    longitude   = 112.85,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WZ002 wz002 DBID=4334 Loadout=502 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'wz003',
    dbid        = 4334,, LoadoutID = 502
    latitude    = 9.71,
    longitude   = 113.01,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WZ003 wz003 DBID=4334 Loadout=502 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd001',
    dbid        = 4632,, LoadoutID = 753
    latitude    = 9.93,
    longitude   = 115.51,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] JD001 jd001 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd002',
    dbid        = 4632,, LoadoutID = 753
    latitude    = 9.91,
    longitude   = 115.53,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] JD002 jd002 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd003',
    dbid        = 4632,, LoadoutID = 753
    latitude    = 9.91,
    longitude   = 115.5,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] JD003 jd003 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd004',
    dbid        = 4632,, LoadoutID = 753
    latitude    = 9.9,
    longitude   = 115.49,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] JD004 jd004 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd005',
    dbid        = 4632,, LoadoutID = 753
    latitude    = 9.89,
    longitude   = 115.5,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] JD005 jd005 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd006',
    dbid        = 4632,, LoadoutID = 753
    latitude    = 9.94,
    longitude   = 115.52,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] JD006 jd006 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'jd007',
    dbid        = 4632,, LoadoutID = 753
    latitude    = 9.94,
    longitude   = 115.52,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] JD007 jd007 DBID=4632 Loadout=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk001',
    dbid        = 4837,
    latitude    = 13.0,
    longitude   = 111.04,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] HK001 hk001 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk002',
    dbid        = 4837,
    latitude    = 26.38,
    longitude   = 112.7,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] HK002 hk002 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk003',
    dbid        = 4837,
    latitude    = 26.32,
    longitude   = 112.79,, altitude = 900
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] HK003 hk003 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk004',
    dbid        = 4837,
    latitude    = 26.3,
    longitude   = 112.91,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] HK004 hk004 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk005',
    dbid        = 4837,
    latitude    = 26.45,
    longitude   = 112.9,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] HK005 hk005 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk006',
    dbid        = 4837,
    latitude    = 26.22,
    longitude   = 112.68,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] HK006 hk006 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk007',
    dbid        = 4837,
    latitude    = 26.2,
    longitude   = 112.91,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] HK007 hk007 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'hk008',
    dbid        = 4837,
    latitude    = 26.39,
    longitude   = 112.98,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] HK008 hk008 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'kj001',
    dbid        = 3683,, LoadoutID = 494
    latitude    = 13.02,
    longitude   = 110.95,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] KJ001 kj001 DBID=3683 Loadout=494 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'kja001',
    dbid        = 3683,, LoadoutID = 494
    latitude    = 26.32,
    longitude   = 112.63,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] KJA001 kja001 DBID=3683 Loadout=494 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'zds001',
    dbid        = 5012,, LoadoutID = 1191
    latitude    = 18.5,
    longitude   = 109.97,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] ZDS001 zds001 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'zds002',
    dbid        = 5012,, LoadoutID = 1191
    latitude    = 18.5,
    longitude   = 109.98,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] ZDS002 zds002 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'zds003',
    dbid        = 5012,, LoadoutID = 1191
    latitude    = 18.49,
    longitude   = 109.98,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] ZDS003 zds003 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'zds004',
    dbid        = 5012,, LoadoutID = 1191
    latitude    = 18.49,
    longitude   = 109.99,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] ZDS004 zds004 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16001',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 10.91,
    longitude   = 114.02,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16001 j16001 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16002',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 10.94,
    longitude   = 114.14,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16002 j16002 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16003',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 9.46,
    longitude   = 113.14,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16003 j16003 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16004',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 10.9,
    longitude   = 114.07,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16004 j16004 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16005',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 10.91,
    longitude   = 114.11,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16005 j16005 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'J16006',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 10.93,
    longitude   = 114.08,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16006 J16006 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16007',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 9.61,
    longitude   = 113.13,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16007 j16007 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16008',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 9.61,
    longitude   = 113.13,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16008 j16008 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16009',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 9.65,
    longitude   = 113.05,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16009 j16009 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16010',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 9.64,
    longitude   = 112.94,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16010 j16010 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16011',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 9.72,
    longitude   = 113.1,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16011 j16011 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j16012',
    dbid        = 2853,, LoadoutID = 1821
    latitude    = 9.64,
    longitude   = 113.0,, altitude = 1500
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J16012 j16012 DBID=2853 Loadout=1821 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20001',
    dbid        = 5012,, LoadoutID = 1191
    latitude    = 13.01,
    longitude   = 110.82,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J20001 j20001 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j02002',
    dbid        = 5012,, LoadoutID = 1191
    latitude    = 12.94,
    longitude   = 110.89,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J02002 j02002 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20003',
    dbid        = 5012,, LoadoutID = 1191
    latitude    = 12.88,
    longitude   = 111.0,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J20003 j20003 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'j20004',
    dbid        = 5012,, LoadoutID = 1191
    latitude    = 12.92,
    longitude   = 111.1,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] J20004 j20004 DBID=5012 Loadout=1191 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv001',
    dbid        = 4309,
    latitude    = -0.155,
    longitude   = 106.1643,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV001 wruuv001 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv002',
    dbid        = 4309,
    latitude    = 0.2,
    longitude   = 105.93,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV002 wruuv002 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv003',
    dbid        = 4309,
    latitude    = 0.06,
    longitude   = 105.65,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV003 wruuv003 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv004',
    dbid        = 4309,
    latitude    = 0.12,
    longitude   = 106.03,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV004 wruuv004 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv005',
    dbid        = 4309,
    latitude    = 0.21,
    longitude   = 106.16,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV005 wruuv005 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv006',
    dbid        = 4309,
    latitude    = 5.69,
    longitude   = 106.98,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV006 wruuv006 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv007',
    dbid        = 4309,
    latitude    = 5.5,
    longitude   = 107.16,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV007 wruuv007 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv008',
    dbid        = 4309,
    latitude    = 5.15,
    longitude   = 107.87,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV008 wruuv008 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv009',
    dbid        = 4309,
    latitude    = 5.11,
    longitude   = 108.28,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV009 wruuv009 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv010',
    dbid        = 4309,
    latitude    = 5.0,
    longitude   = 108.54,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV010 wruuv010 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv011',
    dbid        = 4309,
    latitude    = 7.7,
    longitude   = 116.14,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV011 wruuv011 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv012',
    dbid        = 4309,
    latitude    = 13.38,
    longitude   = 119.12,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV012 wruuv012 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv013',
    dbid        = 4309,
    latitude    = 7.49,
    longitude   = 116.11,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV013 wruuv013 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv014',
    dbid        = 4309,
    latitude    = 12.78,
    longitude   = 118.95,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV014 wruuv014 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wruuv015',
    dbid        = 4309,
    latitude    = 12.63,
    longitude   = 118.93,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRUUV015 wruuv015 DBID=4309 已添加')

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
print('[红方] WRT001 wrt001 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt002',
    dbid        = 4309,
    latitude    = 5.37,
    longitude   = 108.0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRT002 wrt002 DBID=4309 已添加')

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
print('[红方] WRT003 wrt003 DBID=4309 已添加')

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
print('[红方] WRT004 wrt004 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt005',
    dbid        = 4309,
    latitude    = 7.8,
    longitude   = 116.29,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRT005 wrt005 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'wrt006',
    dbid        = 4309,
    latitude    = 7.39,
    longitude   = 115.77,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] WRT006 wrt006 DBID=4309 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_01073',
    dbid        = 4354,
    latitude    = 5.68,
    longitude   = 108.9,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DDG 01073 ddg_01073 DBID=4354 已添加')

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
print('[红方] DDG 09006 ddg_09006 DBID=4354 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_01005',
    dbid        = 4352,
    latitude    = 6.14,
    longitude   = 108.6,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DDG 01005 ddg_01005 DBID=4352 已添加')

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
print('[红方] FFG 05005 ffg_05005 DBID=4361 已添加')

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
print('[红方] FFG 05075 ffg_05075 DBID=4361 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ddg_01007',
    dbid        = 4354,
    latitude    = 7.9,
    longitude   = 115.41,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] DDG 01007 ddg_01007 DBID=4354 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ffg_06006',
    dbid        = 4361,
    latitude    = 7.54,
    longitude   = 115.28,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] FFG 06006 ffg_06006 DBID=4361 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Ship',
    name        = 'ffg_05019',
    dbid        = 4361,
    latitude    = 13.3,
    longitude   = 118.24,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] FFG 05019 ffg_05019 DBID=4361 已添加')

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
print('[红方] SUBC001 subc001 DBID=4260 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Submarine',
    name        = 'subc002',
    dbid        = 4260,
    latitude    = 12.86,
    longitude   = 118.72,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] SUBC002 subc002 DBID=4260 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'h6k011',
    dbid        = 4837,
    latitude    = 13.04,
    longitude   = 114.05,, altitude = 300
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H6K011 h6k011 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'h6k012',
    dbid        = 4837,
    latitude    = 13.04,
    longitude   = 114.05,, altitude = 300
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H6K012 h6k012 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'h6k013',
    dbid        = 4837,
    latitude    = 13.04,
    longitude   = 114.05,, altitude = 300
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H6K013 h6k013 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'h6k014',
    dbid        = 4837,
    latitude    = 13.056,
    longitude   = 114.05,, altitude = 300
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H6K014 h6k014 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'h6k015',
    dbid        = 4837,
    latitude    = 13.05,
    longitude   = 114.05,, altitude = 300
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H6K015 h6k015 DBID=4837 已添加')

unit = ScenEdit_AddUnit({
    side        = '红方',
    type        = 'Aircraft',
    name        = 'h6k016',
    dbid        = 4837,
    latitude    = 13.05,
    longitude   = 114.06,, altitude = 300
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[红方] H6K016 h6k016 DBID=4837 已添加')

-- =============================================================================
-- 2. 3. 蓝方单位（按 JSON Equipments 位置信息）
-- =============================================================================

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'cvn_linkeng',
    dbid        = 429,
    latitude    = -0.9,
    longitude   = 106.11,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] CVN LINKENG cvn_linkeng DBID=429 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'tico_pulinsidun',
    dbid        = 42,
    latitude    = -0.659581,
    longitude   = 105.813746,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] TICO PULINSIDUN tico_pulinsidun DBID=42 已添加')

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
print('[蓝方] DDG MOMUSENG ddg_momuseng DBID=2869 已添加')

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
print('[蓝方] DDG LAOLUNSI ddg_laolunsi DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ddg_sitelei',
    dbid        = 2869,
    latitude    = -0.040782,
    longitude   = 106.369201,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] DDG SITELEI ddg_sitelei DBID=2869 已添加')

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
print('[蓝方] DDG HUOBATE ddg_huobate DBID=2869 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'supply_kz',
    dbid        = 753,
    latitude    = -0.101186,
    longitude   = 106.164261,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] SUPPLY KZ supply_kz DBID=753 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'ffg_lishiman',
    dbid        = 4334,
    latitude    = 0.695643,
    longitude   = 105.206647,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] FFG LISHIMAN ffg_lishiman DBID=4334 已添加')
-- === 01两栖攻击舰编队 → SKIP: LHA_AMERICA (1x) — 数据库无此装备

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'tico_simoer',
    dbid        = 42,
    latitude    = 7.970356,
    longitude   = 119.503844,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] TICO SIMOER tico_simoer DBID=42 已添加')

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
print('[蓝方] DDG CHAFEI ddg_chafei DBID=2869 已添加')
-- === 01无人舰艇编队 → SKIP: USV_OVERLORD (3x) — 数据库无此装备

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'agos_shenli',
    dbid        = 365,
    latitude    = 19.72,
    longitude   = 124.75,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] AGOS SHENLI agos_shenli DBID=365 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'agos_wuxia',
    dbid        = 365,
    latitude    = 20.29,
    longitude   = 119.57,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] AGOS WUXIA agos_wuxia DBID=365 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Ship',
    name        = 'agos_zhuncheng',
    dbid        = 365,
    latitude    = 14.06,
    longitude   = 119.2,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] AGOS ZHUNCHENG agos_zhuncheng DBID=365 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35c001',
    dbid        = 824,, LoadoutID = 2607
    latitude    = -0.723911,
    longitude   = 106.122993,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F35C001 f35c001 DBID=824 Loadout=2607 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35c002',
    dbid        = 824,, LoadoutID = 2607
    latitude    = -0.792082,
    longitude   = 106.185909,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F35C002 f35c002 DBID=824 Loadout=2607 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35c003',
    dbid        = 824,, LoadoutID = 2607
    latitude    = -0.752938,
    longitude   = 106.05896,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F35C003 f35c003 DBID=824 Loadout=2607 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35b001',
    dbid        = 3870,, LoadoutID = 689
    latitude    = 7.92,
    longitude   = 120.093579,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F35B001 f35b001 DBID=3870 Loadout=689 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35b002',
    dbid        = 3870,, LoadoutID = 689
    latitude    = 7.89,
    longitude   = 120.093579,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F35B002 f35b002 DBID=3870 Loadout=689 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35b003',
    dbid        = 3870,, LoadoutID = 689
    latitude    = 7.9215,
    longitude   = 120.129358,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F35B003 f35b003 DBID=3870 Loadout=689 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Aircraft',
    name        = 'f35b004',
    dbid        = 3870,, LoadoutID = 689
    latitude    = 7.9178,
    longitude   = 120.093579,, altitude = 1000
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] F35B004 f35b004 DBID=3870 Loadout=689 已添加')

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
print('[蓝方] HMS001 hms001 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms002',
    dbid        = 3268,
    latitude    = 9.95,
    longitude   = 118.7,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HMS002 hms002 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms003',
    dbid        = 3268,
    latitude    = 9.95,
    longitude   = 118.7,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HMS003 hms003 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms004',
    dbid        = 3268,
    latitude    = 9.95,
    longitude   = 118.7,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HMS004 hms004 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms005',
    dbid        = 3268,
    latitude    = 9.95,
    longitude   = 118.7,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HMS005 hms005 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms006',
    dbid        = 3268,
    latitude    = 8.539521,
    longitude   = 117.323625,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HMS006 hms006 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms007',
    dbid        = 3268,
    latitude    = 8.603141,
    longitude   = 117.327882,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HMS007 hms007 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms008',
    dbid        = 3268,
    latitude    = 8.538925,
    longitude   = 117.261165,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HMS008 hms008 DBID=3268 已添加')

unit = ScenEdit_AddUnit({
    side        = '蓝方',
    type        = 'Facility',
    name        = 'hms009',
    dbid        = 3268,
    latitude    = 8.471862,
    longitude   = 117.264859,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
print('[蓝方] HMS009 hms009 DBID=3268 已添加')
-- === 02导弹连 → SKIP: GND_TYPHON_LAUNCHER (4x) — 数据库无此装备

-- =============================================================================
-- 4. 完成提示
-- =============================================================================
print('========================================')
print('A1场景 Lua 脚本执行完成（重新完整生成版）')
print('跳过单位: 卫星 x51 + LHA x1 + USV x3 + Typhon x4')
print('========================================')