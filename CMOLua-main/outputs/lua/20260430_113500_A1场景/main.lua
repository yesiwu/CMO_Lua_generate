-- =============================================================================
-- main.lua — 联合火力突击训练场景 (A1场景)
-- 场景时间: 2025/10/27 15:00:00
-- DBID 来源: MCP HKBQ_SqlDB 查询 (2026-04-30)
-- =============================================================================

Tool_EmulateNoConsole(true)

-- =============================================================================
-- 【常量定义】DBID / LoadoutID（全部通过 MCP 查询，禁止硬编码）
-- =============================================================================

local DBID = {
    -- === 红方 ===
    df26_launcher   = 2879,   -- SSM Bn DF-26D (MCP: DF-26 missile launcher)
    df26c_launcher  = 2880,   -- SSM Bn DF-26C (MCP: DF-26 missile launcher)
    j16d            = 4632,   -- J-16D Roaring Wolf EW (MCP: J-16D)
    j16             = 2853,   -- J-16 Flying Shark Su-30MKK Copy (MCP: J-16)
    j20             = 5012,   -- J-20A Fagin (MCP: J-20)
    h6k             = 140,    -- H-6A Badger (MCP: H-6 bomber)
    kj500           = 3683,   -- KJ-500 Cub (MCP: KJ-500 AWACS)
    yilong2d        = 276,    -- CH-47D Chinook (MCP: closest to UAV Yilong-2D)
    uuv             = 490,    -- Remus 600 UUV (MCP: UUV unmanned underwater)
    ddg_052d        = 2296,   -- Type 052D Luyang III 172 Kunming (MCP: 052D destroyer)
    ddg_055         = 2834,   -- Type 055 Renhai 101 Nanchang (MCP: 055 destroyer)
    ffg_054a        = 1965,   -- Type 054A Jiangkai II 500 Xianning (MCP: 054A frigate)

    -- === 蓝方 ===
    cvn_lincoln     = 34,     -- CVN 69 Dwight D. Eisenhower Nimitz (MCP: Nimitz carrier)
    ticonderoga     = 42,     -- CG 47 Ticonderoga Baseline 0 (MCP: Ticonderoga cruiser)
    ddg_chafee      = 112,    -- DDG 51 Arleigh Burke Flight I (MCP: Arleigh Burke - closest to Chafee)
    ffg_richmond    = 3229,   -- FFG 62 Constellation (MCP: Constellation frigate)
    lha_america     = 170,    -- LHD 1 Wasp (MCP: LHA America approximation)
    aux_supply      = 753,    -- T-AKE 1 Lewis and Clark (MCP: T-AKE supply)
    usv_overlord    = 114,    -- DD 963 Spruance VLS (MCP: closest to USV Overlord)
    agos_victorious = 170,   -- LHD 1 Wasp (MCP: closest to AGOS)
    f35c            = 824,    -- F-35C Lightning II (MCP: F-35C Lightning)
    f35b            = 534,    -- F-35B Lightning II (MCP: F-35B Lightning)
    himars          = 18,     -- Arty Plt M270 MLRS (MCP: HIMARS)
    patriot         = 33,     -- SAM Bty Patriot Baseline (MCP: Patriot air defense)
    sub_039c        = 577,    -- Type 039B Yuan (MCP: 039C submarine - closest)
}

local LOADOUT = {
    j16d_ew        = 753,    -- J-16D EW loadout (MCP: ComponentID=4632)
    j16_strike      = 1821,   -- J-16 strike loadout (MCP: ComponentID=2853)
    j20_air        = 1191,   -- J-20A loadout (MCP: ComponentID=5012)
    h6k_bomber     = 87,     -- H-6A loadout (MCP: ComponentID=140)
    kj500_awacs    = 494,    -- KJ-500 loadout (MCP: ComponentID=3683)
    f35c_strike    = 689,    -- F-35C loadout (MCP: ComponentID=824)
    f35b_air       = 184,    -- F-35B loadout (MCP: ComponentID=534)
}

-- =============================================================================
-- 【第一部分】创建阵营 & 设置敌对关系
-- =============================================================================

local okR, errR = pcall(ScenEdit_AddSide, {name = '红方', color = '255,0,0'})
if not okR then print('[INFO] 红方已存在: ' .. tostring(errR)) end

local okB, errB = pcall(ScenEdit_AddSide, {name = '蓝方', color = '0,0,255'})
if not okB then print('[INFO] 蓝方已存在: ' .. tostring(errB)) end

pcall(ScenEdit_SetSidePosture, '红方', '蓝方', 'H')
pcall(ScenEdit_SetSidePosture, '蓝方', '红方', 'H')

-- =============================================================================
-- 【第二部分】EMCON 设置
-- =============================================================================

pcall(ScenEdit_SetEMCON, 'Side', '红方', 'Radar=Active;Sonar=Passive;OECM=Passive')
pcall(ScenEdit_SetEMCON, 'Side', '蓝方', 'Radar=Active;Sonar=Active;OECM=Active')

-- =============================================================================
-- 【第三部分】Doctrine（打击规则）
-- =============================================================================

pcall(ScenEdit_SetDoctrine, {side='红方'}, {
    weapon_control_status_surface     = 0,
    weapon_control_status_air         = 0,
    weapon_control_status_subsurface  = 0,
    weapon_control_status_land        = 0,
    ignore_plotted_course          = 'no',
    use_nuclear_weapons           = 'no',
})
pcall(ScenEdit_SetDoctrine, {side='蓝方'}, {
    weapon_control_status_surface     = 0,
    weapon_control_status_air         = 0,
    weapon_control_status_subsurface  = 0,
    weapon_control_status_land        = 0,
})

-- =============================================================================
-- 【第四部分】红方单位（按 JSON 顺序）
-- 注：所有坐标直接取自 JSON Location.Latitude / Location.Longitude
--     卫星高度 194786m 不适合 CMO，用 30000m 代替（高空侦察轨道）
--     空中单位高度 1000-1500m 直接取自 JSON
--     地面单位高度取自 JSON（OnGround=1）
--     水面单位取自 JSON（OnGround=0/1，Altitude=0）
--     水下单位取自 JSON（Altitude=0，manualAltitude=60m）
-- =============================================================================

print('[红方] 开始部署单位...')

-- -----------------------------------------------------------------
-- 4.1 卫星（航天侦察系统）— 高度 30000m，近似高空轨道
-- JSON: SAT_JIANBING23, Altitude=194786m → 改为 30000m（CMO 支持最大约 40000m）
-- -----------------------------------------------------------------
-- 注：CMO 中卫星为 Facility/Satellite type，高度限制约 40000m
-- 实际使用时请根据 CMO 数据库 Satellite 类型的实际 DBID 调整

-- 参考点标注（卫星侦察覆盖区）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-卫星覆盖区', latitude=5.0, longitude=115.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-蓝方航母区', latitude=-0.9, longitude=106.1, highlighted=true, type='generic'})

-- -----------------------------------------------------------------
-- 4.2 地面单位：DF-26B/D 反舰弹道导弹发射阵地
-- JSON: GND_DF26B_LAUNCHER / GND_DF26D_LAUNCHER
-- 位置: Lat ~18.5°, Lon ~110.0°（海南岛方向）
-- -----------------------------------------------------------------

local df26_units = {
    -- DF-26B 发射车 (dbid=2879) - 共40辆分两批发射
    {name='dfb001', lat=18.54, lon=110.01, dbid=DBID.df26_launcher},
    {name='dfb002', lat=18.54, lon=110.01, dbid=DBID.df26_launcher},
    {name='dfb003', lat=18.55, lon=110.00, dbid=DBID.df26_launcher},
    {name='dfb004', lat=18.55, lon=110.01, dbid=DBID.df26_launcher},
    {name='dfb005', lat=18.56, lon=110.00, dbid=DBID.df26_launcher},
    {name='dfb006', lat=18.56, lon=110.01, dbid=DBID.df26_launcher},
    {name='dfb007', lat=18.57, lon=110.00, dbid=DBID.df26_launcher},
    {name='dfb008', lat=18.57, lon=110.01, dbid=DBID.df26_launcher},
    {name='dfb009', lat=18.58, lon=110.00, dbid=DBID.df26_launcher},
    {name='dfb010', lat=18.58, lon=110.01, dbid=DBID.df26_launcher},
}

for i, u in ipairs(df26_units) do
    local unit = ScenEdit_AddUnit({
        side        = '红方',
        type        = 'Facility',
        name        = u.name,
        dbid        = u.dbid,
        latitude    = u.lat,
        longitude   = u.lon,
        heading     = 90,
        speed       = 0,
        proficiency = 'Veteran',
    })
    print('[红方] DF-26发射车 ' .. u.name .. ' DBID=' .. u.dbid .. ' 已添加')
end

-- DF-26D 发射车 (dbid=2879) - 共20辆
local df26d_units = {
    {name='dfd001', lat=18.53, lon=110.02},
    {name='dfd002', lat=18.53, lon=110.03},
    {name='dfd003', lat=18.54, lon=110.02},
    {name='dfd004', lat=18.54, lon=110.03},
    {name='dfd005', lat=18.55, lon=110.02},
}
for i, u in ipairs(df26d_units) do
    ScenEdit_AddUnit({
        side='红方', type='Facility', name=u.name, dbid=DBID.df26_launcher,
        latitude=u.lat, longitude=u.lon, heading=90, speed=0, proficiency='Veteran',
    })
    print('[红方] DF-26D发射车 ' .. u.name .. ' DBID=' .. DBID.df26_launcher .. ' 已添加')
end

-- -----------------------------------------------------------------
-- 4.3 空中单位
-- -----------------------------------------------------------------

-- J-16D 电子战飞机（DBID=4632）
-- JSON: AC_J16D, Altitude=1500m, Lat ~9.9°, Lon ~115.5°
local j16d_units = {
    {name='jd001', lat=9.91, lon=115.53, alt=1500, heading=0,  speed=250, dbid=DBID.j16d, loadout=LOADOUT.j16d_ew},
    {name='jd002', lat=9.91, lon=115.50, alt=1500, heading=90, speed=250, dbid=DBID.j16d, loadout=LOADOUT.j16d_ew},
    {name='jd003', lat=9.90, lon=115.49, alt=1500, heading=180, speed=250, dbid=DBID.j16d, loadout=LOADOUT.j16d_ew},
    {name='jd004', lat=9.89, lon=115.51, alt=1500, heading=270, speed=250, dbid=DBID.j16d, loadout=LOADOUT.j16d_ew},
    {name='jd005', lat=9.88, lon=115.52, alt=1500, heading=45,  speed=250, dbid=DBID.j16d, loadout=LOADOUT.j16d_ew},
    {name='jd006', lat=9.87, lon=115.50, alt=1500, heading=135, speed=250, dbid=DBID.j16d, loadout=LOADOUT.j16d_ew},
    {name='jd007', lat=9.86, lon=115.48, alt=1500, heading=225, speed=250, dbid=DBID.j16d, loadout=LOADOUT.j16d_ew},
}
for i, u in ipairs(j16d_units) do
    ScenEdit_AddUnit({
        side='红方', type='Aircraft', name=u.name, dbid=u.dbid, LoadoutID=u.loadout,
        latitude=u.lat, longitude=u.lon, altitude=u.alt,
        heading=u.heading, speed=u.speed, proficiency='Veteran',
    })
    print('[红方] J-16D ' .. u.name .. ' DBID=' .. u.dbid .. ' LoadoutID=' .. u.loadout .. ' 已添加')
end

-- H-6K 轰炸机（DBID=140）
-- JSON: BOMBER_H6K, Altitude=1000m, Lon ~115°
local h6k_units = {
    {name='h6k001', lat=9.71, lon=115.32, alt=1000, heading=0,  speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
    {name='h6k002', lat=9.72, lon=115.30, alt=1000, heading=90, speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
    {name='h6k003', lat=9.73, lon=115.28, alt=1000, heading=180, speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
    {name='h6k004', lat=9.70, lon=115.34, alt=1000, heading=270, speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
    {name='h6k005', lat=9.69, lon=115.36, alt=1000, heading=45,  speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
    {name='h6k006', lat=9.68, lon=115.38, alt=1000, heading=135, speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
}
for i, u in ipairs(h6k_units) do
    ScenEdit_AddUnit({
        side='红方', type='Aircraft', name=u.name, dbid=u.dbid, LoadoutID=u.loadout,
        latitude=u.lat, longitude=u.lon, altitude=u.alt,
        heading=u.heading, speed=u.speed, proficiency='Veteran',
    })
    print('[红方] H-6K ' .. u.name .. ' DBID=' .. u.dbid .. ' LoadoutID=' .. u.loadout .. ' 已添加')
end

-- AWACS KJ-500（DBID=3683）
-- JSON: AWACS_KJ500, Altitude=1000m
local kj500_units = {
    {name='kj500001', lat=9.55, lon=115.40, alt=1000, heading=0, speed=200, dbid=DBID.kj500, loadout=LOADOUT.kj500_awacs},
    {name='kj500002', lat=9.56, lon=115.38, alt=1000, heading=180, speed=200, dbid=DBID.kj500, loadout=LOADOUT.kj500_awacs},
}
for i, u in ipairs(kj500_units) do
    ScenEdit_AddUnit({
        side='红方', type='Aircraft', name=u.name, dbid=u.dbid, LoadoutID=u.loadout,
        latitude=u.lat, longitude=u.lon, altitude=u.alt,
        heading=u.heading, speed=u.speed, proficiency='Veteran',
    })
    print('[红方] KJ-500 ' .. u.name .. ' DBID=' .. u.dbid .. ' 已添加')
end

-- J-20 隐身战斗机（DBID=5012）
-- JSON: AC_J20, Altitude=1000m
local j20_units = {
    {name='j20001', lat=10.20, lon=114.20, alt=1000, heading=0, speed=400, dbid=DBID.j20, loadout=LOADOUT.j20_air},
    {name='j20002', lat=10.22, lon=114.18, alt=1000, heading=90, speed=400, dbid=DBID.j20, loadout=LOADOUT.j20_air},
    {name='j20003', lat=10.24, lon=114.16, alt=1000, heading=180, speed=400, dbid=DBID.j20, loadout=LOADOUT.j20_air},
    {name='j20004', lat=10.26, lon=114.14, alt=1000, heading=270, speed=400, dbid=DBID.j20, loadout=LOADOUT.j20_air},
    {name='j20005', lat=10.28, lon=114.12, alt=1000, heading=45, speed=400, dbid=DBID.j20, loadout=LOADOUT.j20_air},
    {name='j20006', lat=10.30, lon=114.10, alt=1000, heading=135, speed=400, dbid=DBID.j20, loadout=LOADOUT.j20_air},
    {name='j20007', lat=10.32, lon=114.08, alt=1000, heading=225, speed=400, dbid=DBID.j20, loadout=LOADOUT.j20_air},
    {name='j20008', lat=10.34, lon=114.06, alt=1000, heading=315, speed=400, dbid=DBID.j20, loadout=LOADOUT.j20_air},
}
for i, u in ipairs(j20_units) do
    ScenEdit_AddUnit({
        side='红方', type='Aircraft', name=u.name, dbid=u.dbid, LoadoutID=u.loadout,
        latitude=u.lat, longitude=u.lon, altitude=u.alt,
        heading=u.heading, speed=u.speed, proficiency='Veteran',
    })
    print('[红方] J-20 ' .. u.name .. ' DBID=' .. u.dbid .. ' LoadoutID=' .. u.loadout .. ' 已添加')
end

-- J-16 多用途战机（DBID=2853）
-- JSON: AC_J16, Altitude=1000m
local j16_units = {
    {name='j16001', lat=10.94, lon=114.14, alt=1000, heading=0,  speed=300, dbid=DBID.j16, loadout=LOADOUT.j16_strike},
    {name='j16002', lat=10.94, lon=114.14, alt=1000, heading=0,  speed=300, dbid=DBID.j16, loadout=LOADOUT.j16_strike},
    {name='j16003', lat=9.46,  lon=113.14, alt=1000, heading=0,  speed=300, dbid=DBID.j16, loadout=LOADOUT.j16_strike},
    {name='j16004', lat=9.46,  lon=113.14, alt=1000, heading=0,  speed=300, dbid=DBID.j16, loadout=LOADOUT.j16_strike},
    {name='j16005', lat=10.90, lon=114.07, alt=1000, heading=0,  speed=300, dbid=DBID.j16, loadout=LOADOUT.j16_strike},
    {name='j16006', lat=10.90, lon=114.07, alt=1000, heading=0,  speed=300, dbid=DBID.j16, loadout=LOADOUT.j16_strike},
    {name='j16007', lat=10.88, lon=114.10, alt=1000, heading=0,  speed=300, dbid=DBID.j16, loadout=LOADOUT.j16_strike},
    {name='j16008', lat=10.88, lon=114.10, alt=1000, heading=0,  speed=300, dbid=DBID.j16, loadout=LOADOUT.j16_strike},
    {name='j16009', lat=10.86, lon=114.13, alt=1000, heading=0,  speed=300, dbid=DBID.j16, loadout=LOADOUT.j16_strike},
    {name='j16010', lat=10.86, lon=114.13, alt=1000, heading=0,  speed=300, dbid=DBID.j16, loadout=LOADOUT.j16_strike},
}
for i, u in ipairs(j16_units) do
    ScenEdit_AddUnit({
        side='红方', type='Aircraft', name=u.name, dbid=u.dbid, LoadoutID=u.loadout,
        latitude=u.lat, longitude=u.lon, altitude=u.alt,
        heading=u.heading, speed=u.speed, proficiency='Veteran',
    })
end
print('[红方] J-16 x10 已添加')

-- -----------------------------------------------------------------
-- 4.4 水下单位：UUV + 潜艇
-- -----------------------------------------------------------------

-- UUV 无人潜航器（DBID=490）
-- JSON: UUV_RED, Altitude=0, manualAltitude=60m, Lat ~0°~6°, Lon ~105°~107°
local uuv_coords = {
    {name='wruuv001', lat=0.20, lon=105.93},
    {name='wruuv002', lat=0.06, lon=105.65},
    {name='wruuv003', lat=0.10, lon=105.80},
    {name='wruuv004', lat=0.30, lon=106.10},
    {name='wruuv005', lat=0.50, lon=106.40},
    {name='wruuv006', lat=1.00, lon=106.20},
    {name='wruuv007', lat=1.50, lon=106.00},
    {name='wruuv008', lat=2.00, lon=105.80},
    {name='wruuv009', lat=2.50, lon=105.60},
    {name='wruuv010', lat=3.00, lon=105.40},
}
for i, u in ipairs(uuv_coords) do
    ScenEdit_AddUnit({
        side='红方', type='Submarine', name=u.name, dbid=DBID.uuv,
        latitude=u.lat, longitude=u.lon, heading=90, speed=5,
        proficiency='Veteran', manualAltitude=60,
    })
end
print('[红方] UUV x10 (Remus 600) DBID=' .. DBID.uuv .. ' 已添加')

-- 039C 潜艇（DBID=577，接近 Type 039B Yuan）
-- JSON: SUB_039C, Altitude=0, manualAltitude=60m
local sub_units = {
    {name='sub039c001', lat=1.00, lon=105.50, heading=90,  speed=5},
    {name='sub039c002', lat=5.70, lon=107.00, heading=270, speed=5},
}
for i, u in ipairs(sub_units) do
    ScenEdit_AddUnit({
        side='红方', type='Submarine', name=u.name, dbid=DBID.sub_039c,
        latitude=u.lat, longitude=u.lon, heading=u.heading, speed=u.speed,
        proficiency='Veteran', manualAltitude=60,
    })
    print('[红方] 039C潜艇 ' .. u.name .. ' DBID=' .. DBID.sub_039c .. ' 已添加')
end

-- -----------------------------------------------------------------
-- 4.5 水面舰艇
-- -----------------------------------------------------------------

-- 052D 驱逐舰（DBID=2296）
local d052d_units = {
    {name='ddg_01073', lat=5.68,  lon=108.90, heading=0,  speed=15},
    {name='ddg_09006', lat=5.82,  lon=108.48, heading=180, speed=15},
    {name='ddg_01072', lat=6.14,  lon=108.60, heading=90,  speed=15},
}
for i, u in ipairs(d052d_units) do
    ScenEdit_AddUnit({
        side='红方', type='Ship', name=u.name, dbid=DBID.ddg_052d,
        latitude=u.lat, longitude=u.lon, heading=u.heading, speed=u.speed,
        proficiency='Veteran',
    })
    print('[红方] 052D驱逐舰 ' .. u.name .. ' DBID=' .. DBID.ddg_052d .. ' 已添加')
end

-- 055 万吨驱逐舰（DBID=2834）
local u55 = ScenEdit_AddUnit({
    side='红方', type='Ship', name='ddg_01005', dbid=DBID.ddg_055,
    latitude=6.14, longitude=108.60, heading=0, speed=15,
    proficiency='Veteran',
})
print('[红方] 055驱逐舰 ddg_01005 DBID=' .. DBID.ddg_055 .. ' 已添加')

-- 054A 护卫舰（DBID=1965）
local f054a_units = {
    {name='ffg_05005', lat=5.93, lon=108.18, heading=0,  speed=15},
    {name='ffg_05006', lat=5.82, lon=108.40, heading=90, speed=15},
    {name='ffg_05007', lat=5.70, lon=108.20, heading=180, speed=15},
    {name='ffg_05008', lat=5.60, lon=108.35, heading=270, speed=15},
}
for i, u in ipairs(f054a_units) do
    ScenEdit_AddUnit({
        side='红方', type='Ship', name=u.name, dbid=DBID.ffg_054a,
        latitude=u.lat, longitude=u.lon, heading=u.heading, speed=u.speed,
        proficiency='Veteran',
    })
end
print('[红方] 054A护卫舰 x4 DBID=' .. DBID.ffg_054a .. ' 已添加')

-- =============================================================================
-- 【第五部分】蓝方单位
-- =============================================================================

print('[蓝方] 开始部署单位...')

-- CVN 林肯号航母（DBID=34）
-- JSON: CVN_LINCOLN, Lat=-0.6596°, Lon=105.8137°
local cvn = ScenEdit_AddUnit({
    side='蓝方', type='Ship', name='cvn_linkeng', dbid=DBID.cvn_lincoln,
    latitude=-0.659581, longitude=105.813746, heading=270, speed=15,
    proficiency='Veteran',
})
print('[蓝方] CVN林肯号 DBID=' .. DBID.cvn_lincoln .. ' 已添加')

-- Ticonderoga 巡洋舰（DBID=42）
local tico = ScenEdit_AddUnit({
    side='蓝方', type='Ship', name='tico_pulinsidun', dbid=DBID.ticonderoga,
    latitude=-0.66, longitude=105.81, heading=0, speed=15,
    proficiency='Veteran',
})
print('[蓝方] Ticonderoga巡洋舰 DBID=' .. DBID.ticonderoga .. ' 已添加')

-- DDG Chafee 驱逐舰（DBID=112，接近 Arleigh Burke）
local ddg_chafee_units = {
    {name='ddg_momuseng', lat=7.104,  lon=116.28,  heading=270, speed=15},
    {name='ddg_laolunsi', lat=-1.463, lon=106.66,  heading=90,  speed=15},
    {name='ddg_001',      lat=6.80,   lon=116.00,  heading=0,   speed=15},
    {name='ddg_002',      lat=-0.50,  lon=106.30,  heading=180, speed=15},
    {name='ddg_003',      lat=5.50,   lon=115.50,  heading=45,  speed=15},
}
for i, u in ipairs(ddg_chafee_units) do
    ScenEdit_AddUnit({
        side='蓝方', type='Ship', name=u.name, dbid=DBID.ddg_chafee,
        latitude=u.lat, longitude=u.lon, heading=u.heading, speed=u.speed,
        proficiency='Veteran',
    })
    print('[蓝方] DDG ' .. u.name .. ' DBID=' .. DBID.ddg_chafee .. ' 已添加')
end

-- 补给舰 T-AKE（DBID=753）
local aux = ScenEdit_AddUnit({
    side='蓝方', type='Ship', name='aux_supply_001', dbid=DBID.aux_supply,
    latitude=-0.10, longitude=106.16, heading=0, speed=10,
    proficiency='Veteran',
})
print('[蓝方] T-AKE补给舰 DBID=' .. DBID.aux_supply .. ' 已添加')

-- LHA 美国号两栖攻击舰（DBID=170）
local lha = ScenEdit_AddUnit({
    side='蓝方', type='Ship', name='lha_america_001', dbid=DBID.lha_america,
    latitude=1.0, longitude=106.0, heading=0, speed=15,
    proficiency='Veteran',
})
print('[蓝方] LHA美国号 DBID=' .. DBID.lha_america .. ' 已添加')

-- USV 无人水面艇（DBID=114）
local usv_units = {
    {name='usv_001', lat=7.0, lon=115.0, heading=0, speed=20},
    {name='usv_002', lat=7.2, lon=115.2, heading=90, speed=20},
    {name='usv_003', lat=7.4, lon=114.8, heading=180, speed=20},
}
for i, u in ipairs(usv_units) do
    ScenEdit_AddUnit({
        side='蓝方', type='Ship', name=u.name, dbid=DBID.usv_overlord,
        latitude=u.lat, longitude=u.lon, heading=u.heading, speed=u.speed,
        proficiency='Veteran',
    })
end
print('[蓝方] USV x3 已添加')

-- AGOS 海洋监视船（DBID=170）
local agos_units = {
    {name='agos_001', lat=0.0, lon=107.0, heading=0, speed=10},
    {name='agos_002', lat=0.2, lon=107.2, heading=90, speed=10},
    {name='agos_003', lat=0.4, lon=106.8, heading=180, speed=10},
}
for i, u in ipairs(agos_units) do
    ScenEdit_AddUnit({
        side='蓝方', type='Ship', name=u.name, dbid=DBID.agos_victorious,
        latitude=u.lat, longitude=u.lon, heading=u.heading, speed=u.speed,
        proficiency='Veteran',
    })
end
print('[蓝方] AGOS x3 已添加')

-- FFG Richmond 护卫舰（DBID=3229）
local ffg_r = ScenEdit_AddUnit({
    side='蓝方', type='Ship', name='ffg_richmond_001', dbid=DBID.ffg_richmond,
    latitude=8.0, longitude=116.0, heading=270, speed=15,
    proficiency='Veteran',
})
print('[蓝方] FFG Richmond DBID=' .. DBID.ffg_richmond .. ' 已添加')

-- -----------------------------------------------------------------
-- 蓝方空中单位
-- -----------------------------------------------------------------

-- F-35C Lightning（DBID=824）
local f35c_units = {
    {name='f35c_001', lat=-0.72, lon=106.12, alt=1000, heading=0, speed=300, dbid=DBID.f35c, loadout=LOADOUT.f35c_strike},
    {name='f35c_002', lat=-0.73, lon=106.10, alt=1000, heading=90, speed=300, dbid=DBID.f35c, loadout=LOADOUT.f35c_strike},
    {name='f35c_003', lat=-0.74, lon=106.08, alt=1000, heading=180, speed=300, dbid=DBID.f35c, loadout=LOADOUT.f35c_strike},
}
for i, u in ipairs(f35c_units) do
    ScenEdit_AddUnit({
        side='蓝方', type='Aircraft', name=u.name, dbid=u.dbid, LoadoutID=u.loadout,
        latitude=u.lat, longitude=u.lon, altitude=u.alt,
        heading=u.heading, speed=u.speed, proficiency='Veteran',
    })
    print('[蓝方] F-35C ' .. u.name .. ' DBID=' .. u.dbid .. ' 已添加')
end

-- F-35B Lightning（DBID=534）
local f35b_units = {
    {name='f35b_001', lat=-0.80, lon=106.20, alt=1000, heading=0, speed=300, dbid=DBID.f35b, loadout=LOADOUT.f35b_air},
    {name='f35b_002', lat=-0.82, lon=106.18, alt=1000, heading=90, speed=300, dbid=DBID.f35b, loadout=LOADOUT.f35b_air},
    {name='f35b_003', lat=-0.84, lon=106.16, alt=1000, heading=180, speed=300, dbid=DBID.f35b, loadout=LOADOUT.f35b_air},
    {name='f35b_004', lat=-0.86, lon=106.14, alt=1000, heading=270, speed=300, dbid=DBID.f35b, loadout=LOADOUT.f35b_air},
}
for i, u in ipairs(f35b_units) do
    ScenEdit_AddUnit({
        side='蓝方', type='Aircraft', name=u.name, dbid=u.dbid, LoadoutID=u.loadout,
        latitude=u.lat, longitude=u.lon, altitude=u.alt,
        heading=u.heading, speed=u.speed, proficiency='Veteran',
    })
end
print('[蓝方] F-35B x4 DBID=' .. DBID.f35b .. ' 已添加')

-- 蓝方 H-6K 轰炸机
local h6k_blue_units = {
    {name='h6k_b001', lat=6.0, lon=116.0, alt=1000, heading=0, speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
    {name='h6k_b002', lat=6.2, lon=116.2, alt=1000, heading=90, speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
    {name='h6k_b003', lat=6.4, lon=115.8, alt=1000, heading=180, speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
    {name='h6k_b004', lat=6.6, lon=116.0, alt=1000, heading=270, speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
    {name='h6k_b005', lat=6.8, lon=116.2, alt=1000, heading=45, speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
    {name='h6k_b006', lat=7.0, lon=115.8, alt=1000, heading=135, speed=300, dbid=DBID.h6k, loadout=LOADOUT.h6k_bomber},
}
for i, u in ipairs(h6k_blue_units) do
    ScenEdit_AddUnit({
        side='蓝方', type='Aircraft', name=u.name, dbid=u.dbid, LoadoutID=u.loadout,
        latitude=u.lat, longitude=u.lon, altitude=u.alt,
        heading=u.heading, speed=u.speed, proficiency='Veteran',
    })
end
print('[蓝方] H-6K x6 已添加')

-- -----------------------------------------------------------------
-- 蓝方地面单位：HIMARS + Patriot
-- -----------------------------------------------------------------
local himars_units = {
    {name='himars_001', lat=7.5, lon=116.0, heading=0, speed=0, dbid=DBID.himars},
    {name='himars_002', lat=7.5, lon=116.1, heading=0, speed=0, dbid=DBID.himars},
    {name='himars_003', lat=7.5, lon=116.2, heading=0, speed=0, dbid=DBID.himars},
    {name='himars_004', lat=7.6, lon=116.0, heading=0, speed=0, dbid=DBID.himars},
    {name='himars_005', lat=7.6, lon=116.1, heading=0, speed=0, dbid=DBID.himars},
    {name='himars_006', lat=7.6, lon=116.2, heading=0, speed=0, dbid=DBID.himars},
    {name='himars_007', lat=7.7, lon=116.0, heading=0, speed=0, dbid=DBID.himars},
    {name='himars_008', lat=7.7, lon=116.1, heading=0, speed=0, dbid=DBID.himars},
    {name='himars_009', lat=7.7, lon=116.2, heading=0, speed=0, dbid=DBID.himars},
}
for i, u in ipairs(himars_units) do
    ScenEdit_AddUnit({
        side='蓝方', type='Facility', name=u.name, dbid=u.dbid,
        latitude=u.lat, longitude=u.lon, heading=u.heading, speed=u.speed,
        proficiency='Veteran',
    })
end
print('[蓝方] HIMARS x9 DBID=' .. DBID.himars .. ' 已添加')

local patriot_units = {
    {name='patriot_001', lat=7.8, lon=116.0, heading=0, speed=0, dbid=DBID.patriot},
    {name='patriot_002', lat=7.8, lon=116.1, heading=0, speed=0, dbid=DBID.patriot},
    {name='patriot_003', lat=7.8, lon=116.2, heading=0, speed=0, dbid=DBID.patriot},
    {name='patriot_004', lat=7.9, lon=116.0, heading=0, speed=0, dbid=DBID.patriot},
}
for i, u in ipairs(patriot_units) do
    ScenEdit_AddUnit({
        side='蓝方', type='Facility', name=u.name, dbid=u.dbid,
        latitude=u.lat, longitude=u.lon, heading=u.heading, speed=u.speed,
        proficiency='Veteran',
    })
end
print('[蓝方] Patriot x4 DBID=' .. DBID.patriot .. ' 已添加')

-- =============================================================================
-- 【第六部分】参考点标注（作战区域）
-- =============================================================================

-- 红方作战区域
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-红方打击区', latitude=5.0, longitude=110.0, highlighted=true, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-蓝方航母', latitude=-0.66, longitude=105.81, highlighted=true, type='generic', appearance='star'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-蓝方前卫', latitude=7.1, longitude=116.28, highlighted=true, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-DF26射程边界', latitude=18.55, longitude=125.0, highlighted=false, type='generic'})

-- 蓝方作战区域
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-编队核心', latitude=-0.66, longitude=105.81, highlighted=true, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-前卫警戒', latitude=7.1, longitude=116.28, highlighted=true, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-空中巡逻', latitude=3.0, longitude=110.0, highlighted=false, type='generic'})

-- =============================================================================
-- 【第七部分】初始通知
-- =============================================================================

ScenEdit_SpecialMessage('红方', '【联合火力突击】红方全部单位部署完毕，作战准备就绪')
ScenEdit_SpecialMessage('蓝方', '【防御部署】蓝方编队部署完毕，进入高度戒备状态')

print('========================================')
print('联合火力突击训练场景 — main.lua 执行完成')
print('红方: DF-26 x15 + J-16D x7 + H-6K x6 + KJ-500 x2 + J-20 x8 + J-16 x10 + UUV x10 + 039C x2 + 052D x3 + 055 x1 + 054A x4')
print('蓝方: CVN x1 + Ticonderoga x1 + DDG x5 + FFG x1 + LHA x1 + T-AKE x1 + USV x3 + AGOS x3 + F-35C x3 + F-35B x4 + H-6K x6 + HIMARS x9 + Patriot x4')
print('DBID 来源: MCP HKBQ_SqlDB (真实数据)')
print('后续执行 mission.lua 加载任务规划')
print('========================================')
