-- ============================================================
-- 方案: 2026B 联合打击
-- 来源: plan_a1_001_legacy.json
-- 生成时间: 2026-04-20
-- 说明:
--   - 蓝方: 5个敌方舰艇目标 (ticonderoga/DDG/LHA/T-AKE)
--   - 红方: 24个地面发射车 + 15架飞机 + 5艘UUV
--   - 卫星单位(wxjb/SAT_JIANBING23)已跳过
--   - DF-26B DBID 未查到，以 DF-26C(2879)/DF-26D(2880) 替代
--   - H-6K LoadoutID: 2322 不被 CMO 认可，改用 4100
-- ============================================================

-- === 添加蓝方 (Blue Side — 敌方目标) ========================

-- Tico Simoer (CG-47 Ticonderoga Baseline 0) @ 7.97N, 119.50E
local unit = ScenEdit_AddUnit({
    side       = 'Blue',
    type       = 'Ship',
    name       = 'tico_simoer',
    dbid       = 42,
    latitude   = 7.970356,
    longitude  = 119.503844,
    proficiency = 'Veteran',
    heading    = 0,
    speed      = 0,
})
if unit then ScenEdit_SetKeyValue('TICO_SIMOER_GUID', unit.guid) end

-- DDG Chafei (DDG-51 Arleigh Burke Flight I) @ 8.28N, 119.78E
unit = ScenEdit_AddUnit({
    side       = 'Blue',
    type       = 'Ship',
    name       = 'ddg_chafei',
    dbid       = 112,
    latitude   = 8.284662,
    longitude  = 119.783273,
    proficiency = 'Veteran',
    heading    = 0,
    speed      = 0,
})
if unit then ScenEdit_SetKeyValue('DDG_CHAFEI_GUID', unit.guid) end

-- LHA Meiguo (LHD-1 Wasp) @ 7.92N, 120.09E
unit = ScenEdit_AddUnit({
    side       = 'Blue',
    type       = 'Ship',
    name       = 'lha_meiguo',
    dbid       = 170,
    latitude   = 7.922858,
    longitude  = 120.093579,
    proficiency = 'Veteran',
    heading    = 0,
    speed      = 0,
})
if unit then ScenEdit_SetKeyValue('LHA_MEIGUO_GUID', unit.guid) end

-- Supply KZ (T-AKE 1 Lewis and Clark) @ 0.10S, 106.16E
unit = ScenEdit_AddUnit({
    side       = 'Blue',
    type       = 'Ship',
    name       = 'supply_kz',
    dbid       = 753,
    latitude   = -0.101186,
    longitude  = 106.164261,
    proficiency = 'Veteran',
    heading    = 0,
    speed      = 0,
})
if unit then ScenEdit_SetKeyValue('SUPPLY_KZ_GUID', unit.guid) end

-- DDG Mo Museng (DDG-51 Arleigh Burke Flight I) @ 7.10N, 116.28E
unit = ScenEdit_AddUnit({
    side       = 'Blue',
    type       = 'Ship',
    name       = 'ddg_momuseng',
    dbid       = 112,
    latitude   = 7.104,
    longitude  = 116.28,
    proficiency = 'Veteran',
    heading    = 0,
    speed      = 0,
})
if unit then ScenEdit_SetKeyValue('DDG_MOMUSENG_GUID', unit.guid) end

-- === 添加红方 (Red Side — 我方作战力量) ====================

-- ---- 02打击大队: DF-26B 发射车 (DBID=2879, SSM Bn DF-26C) --------
-- 注: MCP 仅查到 DF-26C(2879)/DF-26D(2880)，未查到 DF-26B，用 DF-26C 替代
local d26b_positions = {
    {lat=18.54, lon=110.00}, {lat=18.54, lon=110.01}, {lat=18.55, lon=110.00},
    {lat=18.55, lon=110.01}, {lat=18.55, lon=110.01}, {lat=18.54, lon=110.01},
    {lat=18.55, lon=110.01}, {lat=18.54, lon=110.02}, {lat=18.54, lon=110.03},
    {lat=18.54, lon=110.03}, {lat=18.54, lon=110.03}, {lat=18.53, lon=110.03},
}
for i, pos in ipairs(d26b_positions) do
    local name = string.format('dfb%03d', i)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Facility',
        name       = name,
        dbid       = 2879,
        latitude   = pos.lat,
        longitude  = pos.lon,
        proficiency = 'Veteran',
        heading    = 90,
        speed      = 0,
    })
    if u then ScenEdit_SetKeyValue(string.format('DFB%03d_GUID', i), u.guid) end
end

-- ---- 03打击大队: DF-26D 发射车 (DBID=2880, SSM Bn DF-26D) --------
local d26d_positions = {
    {lat=23.67, lon=113.00}, {lat=23.67, lon=112.99}, {lat=23.65, lon=112.99},
    {lat=23.66, lon=112.98}, {lat=23.65, lon=112.97}, {lat=23.65, lon=112.99},
    {lat=23.64, lon=112.97}, {lat=23.64, lon=112.99}, {lat=23.65, lon=112.99},
    {lat=23.65, lon=113.00}, {lat=23.65, lon=113.00}, {lat=23.64, lon=112.99},
}
for i, pos in ipairs(d26d_positions) do
    local name = string.format('dfd%03d', i)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Facility',
        name       = name,
        dbid       = 2880,
        latitude   = pos.lat,
        longitude  = pos.lon,
        proficiency = 'Veteran',
        heading    = 90,
        speed      = 0,
    })
    if u then ScenEdit_SetKeyValue(string.format('DFD%03d_GUID', i), u.guid) end
end

-- ---- 05干扰大队: J-16D 电子战飞机 (DBID=4632, LoadoutID=965) --------
local j16d_positions = {
    {lat=9.91,  lon=115.53},
    {lat=9.91,  lon=115.50},
    {lat=9.90,  lon=115.49},
    {lat=9.94,  lon=115.52},
}
for i, pos in ipairs(j16d_positions) do
    local name = string.format('jd%03d', i + 1)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Aircraft',
        name       = name,
        dbid       = 4632,
        LoadoutID  = 965,
        latitude   = pos.lat,
        longitude  = pos.lon,
        altitude   = 1500,
        proficiency = 'Veteran',
        heading    = 90,
        speed      = 400,
    })
    if u then ScenEdit_SetKeyValue(string.format('JD%03d_GUID', i + 1), u.guid) end
end

-- ---- 06轰炸机大队: H-6K 轰炸机 (DBID=1731, LoadoutID=4100) --------
local h6k_positions = {
    {lat=26.32, lon=112.79, alt=900},
    {lat=26.30, lon=112.91, alt=1000},
    {lat=26.45, lon=112.90, alt=1000},
    {lat=26.22, lon=112.68, alt=1000},
    {lat=26.20, lon=112.91, alt=1000},
    {lat=26.39, lon=112.98, alt=1000},
}
for i, pos in ipairs(h6k_positions) do
    local name = string.format('hk%03d', i + 2)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Aircraft',
        name       = name,
        dbid       = 1731,
        LoadoutID  = 4100,
        latitude   = pos.lat,
        longitude  = pos.lon,
        altitude   = pos.alt,
        proficiency = 'Veteran',
        heading    = 90,
        speed      = 500,
    })
    if u then ScenEdit_SetKeyValue(string.format('HK%03d_GUID', i + 2), u.guid) end
end

-- ---- 07预警大队: KJ-500A 预警机 (DBID=6004, LoadoutID=494) --------
unit = ScenEdit_AddUnit({
    side       = 'Red',
    type       = 'Aircraft',
    name       = 'kja001',
    dbid       = 6004,
    LoadoutID  = 494,
    latitude   = 26.32,
    longitude  = 112.63,
    altitude   = 1000,
    proficiency = 'Veteran',
    heading    = 90,
    speed      = 240,
})
if unit then ScenEdit_SetKeyValue('KJA001_GUID', unit.guid) end

-- ---- 08战斗机大队: J-20A 战斗机 (DBID=5012, LoadoutID=3589) --------
local j20a_positions = {
    {lat=18.50, lon=109.97},
    {lat=18.50, lon=109.98},
    {lat=18.49, lon=109.98},
    {lat=18.49, lon=109.99},
}
for i, pos in ipairs(j20a_positions) do
    local name = string.format('zds%03d', i)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Aircraft',
        name       = name,
        dbid       = 5012,
        LoadoutID  = 3589,
        latitude   = pos.lat,
        longitude  = pos.lon,
        altitude   = 1000,
        proficiency = 'Veteran',
        heading    = 90,
        speed      = 520,
    })
    if u then ScenEdit_SetKeyValue(string.format('ZDS%03d_GUID', i), u.guid) end
end

-- ---- 03无人潜航支队: Remus 600 UUV (DBID=490, Submarine) --------
local uuv_positions = {
    {lat=0.11, lon=105.82},
    {lat=0.20, lon=105.93},
    {lat=0.06, lon=105.65},
    {lat=0.12, lon=106.03},
    {lat=0.21, lon=106.16},
}
for i, pos in ipairs(uuv_positions) do
    local name = string.format('wruuv%03d', i)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Submarine',
        name       = name,
        dbid       = 490,
        latitude   = pos.lat,
        longitude  = pos.lon,
        proficiency = 'Veteran',
        heading    = 0,
        speed      = 0,
    })
    if u then ScenEdit_SetKeyValue(string.format('WRUUV%03d_GUID', i), u.guid) end
end

-- === 阵营敌对关系 ==========================================
ScenEdit_SetSidePosture('Red', 'Blue', 'H')
ScenEdit_SetSidePosture('Blue', 'Red', 'H')

-- === 场景完成 ==============================================
ScenEdit_SpecialMessage('Red', '方案 2026B 单位生成完毕 — 5个蓝方舰艇目标 + 24个发射车 + 15架飞机 + 5艘UUV')
