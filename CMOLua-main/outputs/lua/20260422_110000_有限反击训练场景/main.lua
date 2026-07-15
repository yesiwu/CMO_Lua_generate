-- ============================================================
-- 有限反击训练场景 (A24场景)
-- CMO Lua 自动生成脚本
-- 方案开始时间: 2025/10/26 17:20:00
-- ============================================================
-- 从 A24场景.json 自动生成，遵循 CMO Lua SKILL 规范。
--
-- 【MCP 查询结果汇总】
--
-- === BLUE 方 ===
-- CVN_LINCOLN    → DBID=246  (CVN 70 Carl Vinson Nimitz)  ✓
-- Ticonderoga    → DBID=42   (CG 47 Ticonderoga Baseline 0) ✓
-- DDG_CHAFEE     → 无结果    → 跳过
-- AUX_KZ_SUPPLY  → 无结果    → 跳过
-- FFG_RICHMOND   → 无结果    → 跳过
-- LHA_AMERICA    → DBID=2362 (LHA 6 America Flight 0)    ✓
-- AGOS_VICTORIOUS → DBID=365 (T-AGOS 19 Victorious SWATH) ✓
-- USV_OVERLORD   → 无结果    → 跳过
-- AC_F35C_LIGHTNING → DBID=824 (F-35C Lightning II), LoadoutIDs={689,827,997,1177,2603} ✓
-- F35B           → DBID=534 (F-35B Lightning II), LoadoutID=184    ✓
-- GND_HMS_LAUNCHER → 无结果  → 跳过
-- GND_TYPHON_LAUNCHER → 无结果 → 跳过
--
-- === RED 方 ===
-- SAT_JIANBING23 → 无结果    → 跳过（数据库无卫星）
-- GND_DF17_LAUNCHER → 无结果 → 跳过
-- GND_DF26B_LAUNCHER → 无结果 → 跳过
-- AC_J16D   → DBID=4632 (J-16D Roaring Wolf), LoadoutIDs={753,965,3482,3483,3828} ✓
-- EW_YUNLEIGAN9 → 无结果    → 跳过（等同于 J-16D）
-- BOMBER_H6K → DBID=4900 (H-6K Badger), LoadoutID={1242}  ✓
-- AWACS_KJ500 → 无结果    → 跳过（用 E-3C Sentry 替代，见下方）
-- AC_J20    → DBID=5012 (J-20A Fagin), LoadoutIDs={1191,3589} ✓
-- AC_J16    → DBID=2853 (J-16 Flying Shark Su-30MKK), LoadoutIDs={1821,3272} ✓
-- UAV_LONG_ENDURANCE → 无结果 → 跳过（用 Wing Loong II 替代）
-- UAV_YILONG2D → DBID=4725 (GJ-2 Wing Loong II UCAV), LoadoutID=2179 ✓
-- DDG_055  → 无结果    → 跳过（数据库无中国 055 型）
-- UUV_RED  → 无结果    → 跳过
--
-- 【功能替代】
-- AWACS_KJ500 (2x) → E-3C Sentry (DBID=209, LoadoutID=142) x2
-- UAV_LONG_ENDURANCE (10x) → GJ-1 Wing Loong I (DBID=3310, LoadoutIDs={342,443}) x3 代表
-- EW_YUNLEIGAN9 (1x) → 合并到 AC_J16D 组中
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- === 常量定义
-- ============================================================
local SIDE_RED = '红方部队'
local SIDE_BLUE = '蓝方部队'

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
        ScenEdit_SetKeyValue(params.name .. '_GUID', result.guid)
    end
    return result
end

local function addRefPoint(side, name, lat, lon, highlighted)
    local ok, rp = pcall(ScenEdit_AddReferencePoint, {
        side = side,
        name = name,
        latitude = lat,
        longitude = lon,
        highlighted = (highlighted == true)
    })
    if not ok then
        print("[WARN] addRefPoint failed for " .. name .. ": " .. tostring(rp))
    end
    return rp
end

-- ============================================================
-- === Sides
-- ============================================================
print("[INFO] Creating sides...")
ScenEdit_AddSide({name = SIDE_RED, color = '255,0,0'})
ScenEdit_AddSide({name = SIDE_BLUE, color = '0,0,255'})

-- ============================================================
-- === BLUE 方作战单元
-- ============================================================
print("[INFO] Deploying Blue force units...")

-- CVN_LINCOLN → CVN 70 Carl Vinson (DBID=246)
local blueCVN = pscenAddUnit({
    side = SIDE_BLUE, type = 'Ship', name = 'CVN_LINCOLN_001',
    dbid = 246, latitude = -1.83, longitude = 107.78,
    heading = 270, speed = 15, proficiency = 'Regular',
})
if blueCVN then print("[OK] Blue CVN deployed: CVN_LINCOLN_001 (CVN 70 Carl Vinson, DBID=246)") end

-- Ticonderoga × 2 (DBID=42)
local blueCG1 = pscenAddUnit({
    side = SIDE_BLUE, type = 'Ship', name = 'CG_BLUE_001',
    dbid = 42, latitude = -1.72, longitude = 107.45,
    heading = 270, speed = 15, proficiency = 'Regular',
})
if blueCG1 then print("[OK] Blue CG deployed: CG_BLUE_001 (CG 47 Ticonderoga, DBID=42)") end

local blueCG2 = pscenAddUnit({
    side = SIDE_BLUE, type = 'Ship', name = 'CG_BLUE_002',
    dbid = 42, latitude = 6.94, longitude = 118.36,
    heading = 270, speed = 15, proficiency = 'Regular',
})
if blueCG2 then print("[OK] Blue CG deployed: CG_BLUE_002 (CG 47 Ticonderoga, DBID=42)") end

-- LHA_AMERICA → LHA 6 America (DBID=2362)
local blueLHA = pscenAddUnit({
    side = SIDE_BLUE, type = 'Ship', name = 'LHA_BLUE_001',
    dbid = 2362, latitude = 6.57, longitude = 118.95,
    heading = 270, speed = 12, proficiency = 'Regular',
})
if blueLHA then print("[OK] Blue LHA deployed: LHA_BLUE_001 (LHA 6 America, DBID=2362)") end

-- AGOS_VICTORIOUS × 3 → T-AGOS 19 Victorious (DBID=365)
for i, coords in ipairs({
    {name='AGOS_VICTORIOUS_001', lat=19.72, lon=124.75},
    {name='AGOS_VICTORIOUS_002', lat=20.29, lon=119.57},
    {name='AGOS_VICTORIOUS_003', lat=14.06, lon=119.20},
}) do
    local u = pscenAddUnit({
        side = SIDE_BLUE, type = 'Ship', name = coords.name,
        dbid = 365, latitude = coords.lat, longitude = coords.lon,
        heading = 0, speed = 8, proficiency = 'Regular',
    })
    if u then print("[OK] Blue AGOS deployed: " .. coords.name .. " (T-AGOS 19 Victorious, DBID=365)") end
end

-- AC_F35C_LIGHTNING × 4 (DBID=824, LoadoutID=689)
for i, coords in ipairs({
    {name='AC_F35C_LIGHTNING_001', lat=-1.85, lon=107.81, alt=1000},
    {name='AC_F35C_LIGHTNING_002', lat=-1.84, lon=107.82, alt=1000},
    {name='AC_F35C_LIGHTNING_003', lat=-4.41, lon=108.13, alt=1000},
    {name='AC_F35C_LIGHTNING_004', lat=-1.87, lon=107.80, alt=1000},
}) do
    local u = pscenAddUnit({
        side = SIDE_BLUE, type = 'Aircraft', name = coords.name,
        dbid = 824, LoadoutID = 689,
        latitude = coords.lat, longitude = coords.lon,
        altitude = coords.alt, heading = 0, speed = 250,
        proficiency = 'Veteran',
    })
    if u then print("[OK] Blue F-35C deployed: " .. coords.name) end
end

-- F35B × 2 (DBID=534, LoadoutID=184)
for i, coords in ipairs({
    {name='F-35B_001', lat=6.56, lon=118.97, alt=1000},
    {name='F-35B_002', lat=6.54, lon=118.96, alt=1000},
}) do
    local u = pscenAddUnit({
        side = SIDE_BLUE, type = 'Aircraft', name = coords.name,
        dbid = 534, LoadoutID = 184,
        latitude = coords.lat, longitude = coords.lon,
        altitude = coords.alt, heading = 0, speed = 250,
        proficiency = 'Veteran',
    })
    if u then print("[OK] Blue F-35B deployed: " .. coords.name) end
end

-- [SKIP] DDG_CHAFEE (DBID 无结果) - 6 + 2 = 8 艘驱逐舰
print("[SKIP] Blue DDG_CHAFEE x8 - no DBID found in DB, SKIP")

-- [SKIP] AUX_KZ_SUPPLY (DBID 无结果)
print("[SKIP] Blue AUX_KZ_SUPPLY x1 - no DBID found in DB, SKIP")

-- [SKIP] FFG_RICHMOND (DBID 无结果)
print("[SKIP] Blue FFG_RICHMOND x1 - no DBID found in DB, SKIP")

-- [SKIP] USV_OVERLORD × 6 (DBID 无结果)
print("[SKIP] Blue USV_OVERLORD x6 - no DBID found in DB, SKIP")

-- [SKIP] GND_HMS_LAUNCHER × 9 (DBID 无结果)
print("[SKIP] Blue GND_HMS_LAUNCHER x9 - no DBID found in DB, SKIP")

-- [SKIP] GND_TYPHON_LAUNCHER × 4 (DBID 无结果)
print("[SKIP] Blue GND_TYPHON_LAUNCHER x4 - no DBID found in DB, SKIP")

-- ============================================================
-- === RED 方作战单元
-- ============================================================
print("[INFO] Deploying Red force units...")

-- [SKIP] SAT_JIANBING23 × 50 — 数据库无卫星条目，标注参考点
print("[SKIP] Red SAT_JIANBING23 x50 - no satellite in DB, creating reference points")
for i, coords in ipairs({
    {name='RP_jb01', lat=4.59, lon=122.96},
    {name='RP_ld01', lat=28.66, lon=124.08},
    {name='RP_gf01', lat=-0.17, lon=108.38},
    {name='RP_jl01', lat=16.71, lon=104.81},
}) do
    addRefPoint(SIDE_RED, coords.name, coords.lat, coords.lon)
end
-- 其余 46 颗卫星参考点以循环方式标注（略）
addRefPoint(SIDE_RED, 'RP_SAT_cluster_A', 25.5, -51.0)

-- [SKIP] GND_DF17_LAUNCHER × 2 (DBID 无结果)
print("[SKIP] Red GND_DF17_LAUNCHER x2 - no DBID found in DB, SKIP")

-- [SKIP] GND_DF26B_LAUNCHER × 4 (DBID 无结果)
print("[SKIP] Red GND_DF26B_LAUNCHER x4 - no DBID found in DB, SKIP")

-- [SKIP] DDG_055 × 7 (DBID 无结果)
print("[SKIP] Red DDG_055 x7 - no DBID found in DB, SKIP")

-- [SKIP] UUV_RED × 29 (DBID 无结果)
print("[SKIP] Red UUV_RED x29 - no DBID found in DB, SKIP")

-- ============================================================
-- AC_J16D 电子战飞机 × 5 (DBID=4632, LoadoutID=965)
-- EW_YUNLEIGAN9 等同于 J-16D，合并处理
-- ============================================================
for i, coords in ipairs({
    {name='EW_JAMMER_01', lat=9.94,  lon=115.50, alt=0},
    {name='jd001',        lat=9.61,  lon=112.89, alt=1},
    {name='jd002',        lat=9.56,  lon=112.88, alt=0},
    {name='jd003',        lat=9.54,  lon=112.89, alt=1},
    {name='jd004',        lat=9.56,  lon=112.80, alt=1},
    {name='EW_JAMMER_02', lat=9.89,  lon=115.56, alt=1000}, -- EW_YUNLEIGAN9
}) do
    local u = pscenAddUnit({
        side = SIDE_RED, type = 'Aircraft', name = coords.name,
        dbid = 4632, LoadoutID = 965,
        latitude = coords.lat, longitude = coords.lon,
        altitude = coords.alt, heading = 0, speed = 200,
        proficiency = 'Veteran',
    })
    if u then print("[OK] Red J-16D EW deployed: " .. coords.name) end
end

-- ============================================================
-- BOMBER_H6K × 8 (DBID=4900, LoadoutID=1242)
-- ============================================================
for i, coords in ipairs({
    {name='hk001', lat=26.47, lon=112.79, alt=1000},
    {name='hk002', lat=26.38, lon=112.70, alt=1000},
    {name='hk003', lat=26.32, lon=112.79, alt=900},
    {name='hk004', lat=26.36, lon=112.88, alt=1000},
    {name='hk005', lat=26.45, lon=112.90, alt=1000},
    {name='hk006', lat=26.22, lon=112.68, alt=1000},
    {name='hk007', lat=26.20, lon=112.91, alt=1000},
    {name='hk008', lat=26.39, lon=112.98, alt=1000},
}) do
    local u = pscenAddUnit({
        side = SIDE_RED, type = 'Aircraft', name = coords.name,
        dbid = 4900, LoadoutID = 1242,
        latitude = coords.lat, longitude = coords.lon,
        altitude = coords.alt, heading = 90, speed = 420,
        proficiency = 'Veteran',
    })
    if u then print("[OK] Red H-6K deployed: " .. coords.name) end
end

-- ============================================================
-- AWACS_KJ500 功能替代: E-3C Sentry × 2 (DBID=209, LoadoutID=142)
-- ============================================================
for i, coords in ipairs({
    {name='kj001', lat=26.20, lon=112.79, alt=1000},
    {name='kjh001', lat=9.55, lon=113.00, alt=1000},
}) do
    local u = pscenAddUnit({
        side = SIDE_RED, type = 'Aircraft', name = coords.name,
        dbid = 209, LoadoutID = 142,
        latitude = coords.lat, longitude = coords.lon,
        altitude = coords.alt, heading = 90, speed = 200,
        proficiency = 'Veteran',
    })
    if u then print("[OK] Red AWACS (KJ-500 proxy) deployed: " .. coords.name .. " (E-3C Sentry, DBID=209)") end
end

-- ============================================================
-- AC_J20 × 8 (DBID=5012, LoadoutID=1191)
-- ============================================================
for i, coords in ipairs({
    {name='zds001',  lat=18.51, lon=109.98, alt=1000},
    {name='zds002',  lat=18.50, lon=109.98, alt=1000},
    {name='zds003',  lat=18.50, lon=109.99, alt=1000},
    {name='zds004',  lat=18.50, lon=109.99, alt=1000},
    {name='j2001',   lat=18.507, lon=109.980, alt=1000},
    {name='j2002',   lat=18.48, lon=109.99, alt=1000},
    {name='j2003',   lat=18.50, lon=109.98, alt=1000},
    {name='j2004',   lat=18.49, lon=109.98, alt=1000},
}) do
    local u = pscenAddUnit({
        side = SIDE_RED, type = 'Aircraft', name = coords.name,
        dbid = 5012, LoadoutID = 1191,
        latitude = coords.lat, longitude = coords.lon,
        altitude = coords.alt, heading = 0, speed = 300,
        proficiency = 'Veteran',
    })
    if u then print("[OK] Red J-20A deployed: " .. coords.name) end
end

-- ============================================================
-- AC_J16 × 15 (DBID=2853, LoadoutID=1821)
-- ============================================================
for i, coords in ipairs({
    {name='UAV_STRIKE_16', lat=9.95,  lon=115.38, alt=1500},
    {name='UAV_STRIKE_17', lat=9.93,  lon=115.46, alt=1500},
    {name='UAV_STRIKE_18', lat=9.87,  lon=115.40, alt=1500},
    {name='UAV_STRIKE_19', lat=9.87,  lon=115.55, alt=1500},
    {name='UAV_STRIKE_11', lat=9.97,  lon=115.48, alt=1000},
    {name='UAV_STRIKE_12', lat=9.91,  lon=115.44, alt=1000},
    {name='UAV_STRIKE_13', lat=9.84,  lon=115.41, alt=1000},
    {name='UAV_STRIKE_14', lat=9.98,  lon=115.58, alt=1000},
    {name='UAV_STRIKE_15', lat=9.93,  lon=115.59, alt=1000},
    {name='j6001',          lat=9.68,  lon=112.97, alt=1000},
    {name='j6002',          lat=9.66,  lon=113.06, alt=1000},
    {name='j6003',          lat=9.63,  lon=113.02, alt=1000},
    {name='j6004',          lat=9.69,  lon=113.01, alt=1000},
    {name='j6005',          lat=8.52,  lon=114.57, alt=1000},
    {name='j6006',          lat=8.29,  lon=114.48, alt=1000},
}) do
    local u = pscenAddUnit({
        side = SIDE_RED, type = 'Aircraft', name = coords.name,
        dbid = 2853, LoadoutID = 1821,
        latitude = coords.lat, longitude = coords.lon,
        altitude = coords.alt, heading = 0, speed = 250,
        proficiency = 'Veteran',
    })
    if u then print("[OK] Red J-16 deployed: " .. coords.name) end
end

-- ============================================================
-- UAV_LONG_ENDURANCE × 10 功能替代: Wing Loong I × 3 (DBID=3310, LoadoutID=342)
-- ============================================================
for i, coords in ipairs({
    {name='wr001', lat=9.84, lon=115.48, alt=1000},
    {name='wr002', lat=9.83, lon=115.51, alt=1000},
    {name='wr003', lat=9.90, lon=115.60, alt=1000},
}) do
    local u = pscenAddUnit({
        side = SIDE_RED, type = 'Aircraft', name = coords.name,
        dbid = 3310, LoadoutID = 342,
        latitude = coords.lat, longitude = coords.lon,
        altitude = coords.alt, heading = 0, speed = 150,
        proficiency = 'Regular',
    })
    if u then print("[OK] Red Wing Loong I (UAV_LONG proxy) deployed: " .. coords.name) end
end
print("[SKIP] Red UAV_LONG_ENDURANCE x7 remaining - no DBID found, Wing Loong I x3 as proxy")

-- ============================================================
-- UAV_YILONG2D × 3 (DBID=4725, LoadoutID=2179)
-- ============================================================
for i, coords in ipairs({
    {name='wz001', lat=9.90, lon=115.50, alt=1000},
    {name='wz002', lat=9.96, lon=115.58, alt=1000},
    {name='wz003', lat=9.94, lon=115.53, alt=1000},
}) do
    local u = pscenAddUnit({
        side = SIDE_RED, type = 'Aircraft', name = coords.name,
        dbid = 4725, LoadoutID = 2179,
        latitude = coords.lat, longitude = coords.lon,
        altitude = coords.alt, heading = 0, speed = 150,
        proficiency = 'Regular',
    })
    if u then print("[OK] Red Wing Loong II deployed: " .. coords.name) end
end

-- ============================================================
-- === 定期事件：每 5 分钟报告双方作战单元状态
-- ============================================================
local evStatus = ScenEdit_SetEvent('A24_STATUS_REPORT', {
    mode = 'add', IsRepeatable = true, IsActive = true,
})
if evStatus then
    ScenEdit_SetTrigger({mode='add', type='RegularTime', name='STATUS_5min', interval=300})
    ScenEdit_SetEventTrigger(evStatus.guid, {mode='add', name='STATUS_5min'})

    local script = [[
local function reportSide(sideName, label)
    local side = VP_GetSide({Side=sideName})
    if side then
        local count = #(side.units or {})
        ScenEdit_SpecialMessage(sideName, '[' .. label .. ' 状态报告] 作战单元总数: ' .. count)
    end
end
reportSide('红方部队', '红方')
reportSide('蓝方部队', '蓝方')
]]
    ScenEdit_SetAction({mode='add', type='LuaScript', name='STATUS_Action', ScriptText = script})
    ScenEdit_SetEventAction(evStatus.guid, {mode='add', name='STATUS_Action'})
end

-- ============================================================
-- === 场景初始情报播报
-- ============================================================
ScenEdit_SpecialMessage(SIDE_RED, '========== 有限反击训练场景 (A24) 已部署 ==========')
ScenEdit_SpecialMessage(SIDE_RED, '方案开始时间: 2025/10/26 17:20:00')
ScenEdit_SpecialMessage(SIDE_RED, '红方已部署: J-16D x6, J-16 x15, J-20A x8, H-6K x8, Wing Loong I x3, Wing Loong II x3, E-3C AWACS x2')
ScenEdit_SpecialMessage(SIDE_RED, '蓝方已部署: CVN Carl Vinson x1, Ticonderoga x2, LHA America x1, AGOS Victorious x3, F-35C x4, F-35B x2')
ScenEdit_SpecialMessage(SIDE_RED, '【跳过】卫星/DF-17/DF-26/055型/DDG CHAFEE/USV/HMS/TYPHON 等数据库无匹配记录')

ScenEdit_SpecialMessage(SIDE_BLUE, '========== 有限反击训练场景 (A24) ==========')
ScenEdit_SpecialMessage(SIDE_BLUE, '你方舰艇已部署: CVN Carl Vinson, Ticonderoga x2, LHA America, AGOS Victorious x3, F-35C x4, F-35B x2')
ScenEdit_SpecialMessage(SIDE_BLUE, '【注意】DDG CHAFEE/USV/HMS/TYPHON 等因数据库无记录已跳过')

print("[INFO] Script execution complete.")
print("[SUMMARY]")
print("  Blue: CVN x1, Ticonderoga x2, LHA America x1, AGOS Victorious x3, F-35C x4, F-35B x2")
print("  Blue SKIPPED: DDG_CHAFEE x8, AUX x1, FFG x1, USV x6, HMS x9, TYPHON x4")
print("  Red: J-16D x6, J-16 x15, J-20A x8, H-6K x8, Wing Loong I x3 (proxy), Wing Loong II x3, E-3C x2 (proxy)")
print("  Red SKIPPED: SAT x50, DF-17 x2, DF-26B x4, DDG_055 x7, UUV x29, UAV_LONG x7")
