-- ============================================================
-- 联合打击方案 (Plan 2026B)
-- CMO Lua 自动生成脚本
-- 方案时间: 2025-10-27 13:30:00 (UTC+8)
-- ============================================================
-- 本脚本将红方、蓝方作战单元部署到场景中，并设置基于时间轴的打击链事件。
--
-- 【MCP 查询说明】
-- 所有 DBID/LoadoutID 均通过 MCP HKBQ_SqlDB 服务查询验证。
-- 以下原始单元在数据库中无匹配，采用功能近似替代：
--
--   | 原始单元          | 替代方案                   | DBID  |
--   | GND_DF26B/26D    | SSN 688 Los Angeles (潜艇) | 22    |
--   | UUV_RED           | SSN 688 Los Angeles (潜艇) | 22    |
--   | AWACS_KJ500       | E-3C Sentry AWACS          | 209   |
--   | supply_kz (补给舰)| DDG 51 Arleigh Burke       | 112   |
--
-- 以下单元无等效替代，已跳过：
--   | SAT_JIANBING23 (wxjb) — 数据库无卫星条目
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- === 常量定义
-- ============================================================
local SIDE_RED = '红方部队'
local SIDE_BLUE = '蓝方部队'

local SCENARIO_START = "2025-10-27 13:30:00!yyyy-MM-dd HH:mm:ss"

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
    -- Parse ISO 8601 duration like "PT1H30M", "PT2H30M", "PT0S" etc.
    -- Returns seconds from T0
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
end

-- ============================================================
-- === Sides
-- ============================================================
print("[INFO] Creating sides...")
ScenEdit_AddSide({name = SIDE_RED, color = '255,0,0'})
ScenEdit_AddSide({name = SIDE_BLUE, color = '0,0,255'})

-- ============================================================
-- === Blue 方目标单元（DBID 通过 MCP 查询验证）
-- ============================================================
-- MCP 查询结果：
--   CG 47 Ticonderoga [Baseline 0, Mk26]:  DBID=42
--   DDG 51 Arleigh Burke [Flight I]:         DBID=112
--   DDG 51 Arleigh Burke [Flight I] BMD:     DBID=438
--   LHA 1 Tarawa:                            DBID=502
--   LHA 6 America [Flight 0]:               DBID=2362
-- 以下单元 MCP 未查到，跳过：
--   supply_kz: "US Navy supply ship" 无结果
-- ============================================================
print("[INFO] Deploying Blue target units...")

-- tico_simoer → CG 47 Ticonderoga Baseline 0 (DBID=42, country=2101)
local unitTico = pscenAddUnit({
    side        = SIDE_BLUE,
    type        = 'Ship',
    name        = 'tico_simoer',
    dbid        = 42,
    latitude    = 7.970356,
    longitude   = 119.503844,
    heading     = 270,
    speed       = 15,
    proficiency = 'Regular',
})
if unitTico then
    print("[OK] Blue ship deployed: tico_simoer (CG 47 Ticonderoga, DBID=42)")
end

-- ddg_chafei → DDG 51 Arleigh Burke Flight I (DBID=112)
local unitDdgChafei = pscenAddUnit({
    side        = SIDE_BLUE,
    type        = 'Ship',
    name        = 'ddg_chafei',
    dbid        = 112,
    latitude    = 8.284662,
    longitude   = 119.783273,
    heading     = 270,
    speed       = 15,
    proficiency = 'Regular',
})
if unitDdgChafei then
    print("[OK] Blue ship deployed: ddg_chafei (DDG 51 Arleigh Burke, DBID=112)")
end

-- lha_meiguo → LHA 1 Tarawa (DBID=502) — 用最接近 LHA 的数据库条目
local unitLha = pscenAddUnit({
    side        = SIDE_BLUE,
    type        = 'Ship',
    name        = 'lha_meiguo',
    dbid        = 502,
    latitude    = 7.922858,
    longitude   = 120.093579,
    heading     = 270,
    speed       = 12,
    proficiency = 'Regular',
})
if unitLha then
    print("[OK] Blue ship deployed: lha_meiguo (LHA 1 Tarawa, DBID=502)")
end

-- ddg_momuseng → DDG 51 Arleigh Burke Flight I BMD (DBID=438)
local unitDdgMomu = pscenAddUnit({
    side        = SIDE_BLUE,
    type        = 'Ship',
    name        = 'ddg_momuseng',
    dbid        = 438,
    latitude    = 7.104,
    longitude   = 116.28,
    heading     = 270,
    speed       = 15,
    proficiency = 'Regular',
})
if unitDdgMomu then
    print("[OK] Blue ship deployed: ddg_momuseng (DDG 51 Arleigh Burke BMD, DBID=438)")
end

-- supply_kz → 用 DDG 51 Arleigh Burke 替代补给舰角色
local unitSupply = pscenAddUnit({
    side        = SIDE_BLUE,
    type        = 'Ship',
    name        = 'supply_kz',
    dbid        = 112,
    latitude    = -0.101186,
    longitude   = 106.164261,
    heading     = 270,
    speed       = 12,
    proficiency = 'Regular',
})
if unitSupply then
    print("[OK] Blue ship deployed: supply_kz (DDG 51 Arleigh Burke as supply proxy, DBID=112)")
end

-- ============================================================
-- === Red 方作战单元（DBID 通过 MCP 查询验证）
-- ============================================================
-- MCP 查询结果汇总：
--   J-16D Roaring Wolf (AC_J16D):     DBID=4632, LoadoutIDs={753,965,3482,3483,3828}
--   J-20A Fagin (AC_J20):              DBID=5012, LoadoutIDs={1191,3589}
--   H-6K Badger (BOMBER_H6K):           DBID=4900, LoadoutID={1242}
-- 功能替代：
--   GND_DF26B/D → SSN 688 LA (DBID=22, Submarine)
--   UUV_RED     → SSN 688 LA (DBID=22, Submarine)
--   AWACS_KJ500 → E-3C Sentry (DBID=209, LoadoutID=142)
-- ============================================================

print("[INFO] Deploying Red force units...")

-- ============================================================
-- === 网电集群：J-16D 电子战飞机（干扰）
-- DBID 4632 | LoadoutID 965（使用第一可用负载）
-- ============================================================
local JD_UNITS = {
    {name='jd002', lat=9.91,  lon=115.53, alt=1500, heading=0, speed=200, loadout=965},
    {name='jd003', lat=9.91,  lon=115.50, alt=1500, heading=0, speed=200, loadout=965},
    {name='jd004', lat=9.90,  lon=115.49, alt=1500, heading=0, speed=200, loadout=965},
    {name='jd007', lat=9.94,  lon=115.52, alt=1500, heading=0, speed=200, loadout=965},
}

for _, u in ipairs(JD_UNITS) do
    local unit = pscenAddUnit({
        side       = SIDE_RED,
        type       = 'Aircraft',
        name       = u.name,
        dbid       = 4632,
        LoadoutID  = u.loadout,
        latitude   = u.lat,
        longitude  = u.lon,
        altitude   = u.alt,
        heading    = u.heading,
        speed      = u.speed,
        proficiency = 'Veteran',
    })
    if unit then
        print("[OK] J-16D deployed: " .. u.name)
    end
end

-- ============================================================
-- === 空中作战集群：J-20A 隐身战斗机
-- DBID 5012 | LoadoutID 1191
-- ============================================================
local J20_UNITS = {
    {name='zds001', lat=18.50, lon=109.97, alt=1000, heading=0, speed=300, loadout=1191},
    {name='zds002', lat=18.50, lon=109.98, alt=1000, heading=0, speed=300, loadout=1191},
    {name='zds003', lat=18.49, lon=109.98, alt=1000, heading=0, speed=300, loadout=1191},
    {name='zds004', lat=18.49, lon=109.99, alt=1000, heading=0, speed=300, loadout=1191},
}

for _, u in ipairs(J20_UNITS) do
    local unit = pscenAddUnit({
        side       = SIDE_RED,
        type       = 'Aircraft',
        name       = u.name,
        dbid       = 5012,
        LoadoutID  = u.loadout,
        latitude   = u.lat,
        longitude  = u.lon,
        altitude   = u.alt,
        heading    = u.heading,
        speed      = u.speed,
        proficiency = 'Veteran',
    })
    if unit then
        print("[OK] J-20A deployed: " .. u.name)
    end
end

-- ============================================================
-- === 空中作战集群：H-6K 轰炸机（发射巡航导弹）
-- DBID 4900 | LoadoutID 1242
-- ============================================================
local HK_UNITS = {
    {name='hk003', lat=26.32, lon=112.79, alt=900,  heading=90, speed=420, loadout=1242},
    {name='hk004', lat=26.30, lon=112.91, alt=1000, heading=90, speed=420, loadout=1242},
    {name='hk005', lat=26.45, lon=112.90, alt=1000, heading=90, speed=420, loadout=1242},
    {name='hk006', lat=26.22, lon=112.68, alt=1000, heading=90, speed=420, loadout=1242},
    {name='hk007', lat=26.20, lon=112.91, alt=1000, heading=90, speed=420, loadout=1242},
    {name='hk008', lat=26.39, lon=112.98, alt=1000, heading=90, speed=420, loadout=1242},
}

for _, u in ipairs(HK_UNITS) do
    local unit = pscenAddUnit({
        side       = SIDE_RED,
        type       = 'Aircraft',
        name       = u.name,
        dbid       = 4900,
        LoadoutID  = u.loadout,
        latitude   = u.lat,
        longitude  = u.lon,
        altitude   = u.alt,
        heading    = u.heading,
        speed      = u.speed,
        proficiency = 'Veteran',
    })
    if unit then
        print("[OK] H-6K deployed: " .. u.name)
    end
end

-- ============================================================
-- === Red 方功能替代单元（DBID 通过 MCP 查询验证）
-- 以下 Red 方原始单元 MCP 数据库无匹配，功能近似替代：
--   GND_DF26B_LAUNCHER / GND_DF26D_LAUNCHER → SSN 688 Los Angeles (潜艇打击平台) DBID=22
--   UUV_RED → SSN 688 Los Angeles (水下作战) DBID=22
--   SAT_JIANBING23 → [SKIP] 数据库无卫星，无等效替代
--   AWACS_KJ500 → E-3C Sentry AWACS DBID=209, LoadoutID=142
-- ============================================================
print("[INFO] Deploying Red substitute force units...")

-- 作战集群：DF-26B 发射车替代 → SSN 688 Los Angeles (dbid=22)
-- 12台 dfb001~dfb012 替代为 3 艘潜艇（选取有代表性位置）
local DFB_UNITS = {
    {name='dfb001', lat=18.54, lon=110.00, heading=0,  speed=10},
    {name='dfb002', lat=18.54, lon=110.01, heading=90, speed=10},
    {name='dfb003', lat=18.55, lon=110.00, heading=180, speed=10},
}
for _, u in ipairs(DFB_UNITS) do
    local unit = pscenAddUnit({
        side        = SIDE_RED,
        type        = 'Submarine',
        name        = u.name,
        dbid        = 22,
        latitude    = u.lat,
        longitude   = u.lon,
        heading     = u.heading,
        speed       = u.speed,
        proficiency = 'Veteran',
    })
    if unit then
        print("[OK] Red SSN (DF-26B proxy) deployed: " .. u.name .. " (SSN 688 LA, DBID=22)")
    end
end

-- 作战集群：DF-26D 发射车替代 → SSN 688 Los Angeles (dbid=22)
-- 12台 dfd001~dfd012 替代为 3 艘潜艇
local DFD_UNITS = {
    {name='dfd001', lat=23.67, lon=113.00, heading=0,  speed=10},
    {name='dfd002', lat=23.67, lon=112.99, heading=90, speed=10},
    {name='dfd003', lat=23.65, lon=112.99, heading=180, speed=10},
}
for _, u in ipairs(DFD_UNITS) do
    local unit = pscenAddUnit({
        side        = SIDE_RED,
        type        = 'Submarine',
        name        = u.name,
        dbid        = 22,
        latitude    = u.lat,
        longitude   = u.lon,
        heading     = u.heading,
        speed       = u.speed,
        proficiency = 'Veteran',
    })
    if unit then
        print("[OK] Red SSN (DF-26D proxy) deployed: " .. u.name .. " (SSN 688 LA, DBID=22)")
    end
end

-- 海上集群：UUV 替代 → SSN 688 Los Angeles (dbid=22)
-- 5台 wruuv001~wruuv005 替代为 3 艘潜艇
local UUV_UNITS = {
    {name='wruuv001', lat=0.11,  lon=105.82, heading=0,  speed=8},
    {name='wruuv002', lat=0.20,  lon=105.93, heading=45, speed=8},
    {name='wruuv003', lat=0.06,  lon=105.65, heading=90, speed=8},
}
for _, u in ipairs(UUV_UNITS) do
    local unit = pscenAddUnit({
        side        = SIDE_RED,
        type        = 'Submarine',
        name        = u.name,
        dbid        = 22,
        latitude    = u.lat,
        longitude   = u.lon,
        heading     = u.heading,
        speed       = u.speed,
        proficiency = 'Veteran',
    })
    if unit then
        print("[OK] Red SSN (UUV proxy) deployed: " .. u.name .. " (SSN 688 LA, DBID=22)")
    end
end

-- 预警机：KJ-500 → E-3C Sentry AWACS 替代 (DBID=209, LoadoutID=142)
-- 1 架 kja001
local unitKja001 = pscenAddUnit({
    side        = SIDE_RED,
    type        = 'Aircraft',
    name        = 'kja001',
    dbid        = 209,
    LoadoutID   = 142,
    latitude    = 26.32,
    longitude   = 112.63,
    altitude    = 1000,
    heading     = 90,
    speed       = 200,
    proficiency = 'Veteran',
})
if unitKja001 then
    print("[OK] Red AWACS deployed: kja001 (E-3C Sentry, DBID=209, LoadoutID=142)")
end

-- [SKIP] wxjb (SAT_JIANBING23): 数据库无卫星条目，无法替代
print("[SKIP] Red wxjb (SAT_JIANBING23) - no satellite entries in DB, cannot substitute")
-- 卫星以参考点代替，作为情报来源标注
addRefPoint(SIDE_RED, 'RP_wxjb', 8.71, 119.90)

-- ============================================================
-- === 打击链事件 (Kill Chain Events — TCA Pattern)
-- 方案开始时间: 2025-10-27 13:30:00 (UTC+8)
-- T0 = SCENARIO_START offset
-- ============================================================
print("[INFO] Setting up kill-chain events...")

-- Helper: get target RP coordinates from name
local TARGET_COORDS = {
    ['tico_simoer']  = {lat = 7.970356, lon = 119.503844},
    ['ddg_chafei']   = {lat = 8.284662, lon = 119.783273},
    ['lha_meiguo']   = {lat = 7.922858, lon = 120.093579},
    ['supply_kz']    = {lat = -0.101186, lon = 106.164261},
    ['ddg_momuseng'] = {lat = 7.104,     lon = 116.28},
}

-- ============================================================
-- Kill Chain: ST-01-002 打击 tico_simoer
-- 打击链时间窗口: T0+0s ~ T0+2h30m (9000s)
-- 打击平台: jd003, jd004 (电磁干扰), hk005, hk006 (巡航导弹)
-- 发现/定位/跟踪/瞄准: gf01 (W003) - 平台未查到，跳过，仅保留打击触发
-- ============================================================

-- 打击开始触发 (T0+0s)
local evTico = ScenEdit_SetEvent('KC_ST01_002_打击tico_simoer', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evTico then
    local t0 = ScenEdit_CurrentTime()
    ScenEdit_SetTrigger({mode='add', type='Time', name='KC_ST01_002_T0',
        time = t0 + 0})
    ScenEdit_SetEventTrigger(evTico.guid, {mode='add', name='KC_ST01_002_T0'})

    ScenEdit_SetAction({
        mode = 'add',
        type = 'LuaScript',
        name = 'KC_ST01_002_Action',
        ScriptText = string.format(
            'ScenEdit_SpecialMessage("%s", "[打击链 ST-01-002] 开始打击 tico_simoer，目标坐标: %.4f, %.4f")',
            SIDE_RED, 7.970356, 119.503844
        )
    })
    ScenEdit_SetEventAction(evTico.guid, {mode='add', name='KC_ST01_002_Action'})

    -- 为 hk005, hk006 创建攻击航线事件 (指向目标坐标)
    -- 轰炸机 H-6K (hk005/hk006) 从基地飞向 tico_simoer 发射阵位
    -- 发射后原路返回（根据 missionProfile: single_pass，此处简化为通知）
    local cruiseMsg = string.format(
        'ScenEdit_SpecialMessage("%s", "[H-6K 打击] hk005/hk006 携带 BGM-109 巡航导弹飞向 tico_simoer (%.4f, %.4f)，准备发射")',
        SIDE_RED, 7.970356, 119.503844
    )
    ScenEdit_SetAction({
        mode = 'add', type = 'LuaScript',
        name = 'KC_ST01_002_CruiseMsg',
        ScriptText = cruiseMsg
    })
    ScenEdit_SetEventAction(evTico.guid, {mode='add', name='KC_ST01_002_CruiseMsg'})

    -- J-16D 电子战飞机干扰目标区域
    local ewMsg = string.format(
        'ScenEdit_SpecialMessage("%s", "[电子战] jd003/jd004 J-16D 电子战飞机开始对 tico_simoer 区域实施电磁压制")',
        SIDE_RED
    )
    ScenEdit_SetAction({
        mode = 'add', type = 'LuaScript',
        name = 'KC_ST01_002_EWMsg',
        ScriptText = ewMsg
    })
    ScenEdit_SetEventAction(evTico.guid, {mode='add', name='KC_ST01_002_EWMsg'})
end

-- T0+2h10m (7800s): 打击效果评估触发
local evTicoAssess = ScenEdit_SetEvent('KC_ST01_002_评估tico', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evTicoAssess then
    local t0 = ScenEdit_CurrentTime()
    ScenEdit_SetTrigger({mode='add', type='Time', name='KC_ST01_002_T2h10',
        time = t0 + 7800})
    ScenEdit_SetEventTrigger(evTicoAssess.guid, {mode='add', name='KC_ST01_002_T2h10'})

    local assessMsg = string.format(
        'ScenEdit_SpecialMessage("%s", "[打击链 ST-01-002] 打击完成时间点 (T0+2h10m)，请进行毁伤评估: tico_simoer")',
        SIDE_RED
    )
    ScenEdit_SetAction({
        mode = 'add', type = 'LuaScript',
        name = 'KC_ST01_002_AssessMsg',
        ScriptText = assessMsg
    })
    ScenEdit_SetEventAction(evTicoAssess.guid, {mode='add', name='KC_ST01_002_AssessMsg'})
end

-- ============================================================
-- Kill Chain: ST-01-003 打击 ddg_chafei
-- 打击平台: (无可用 DBID 打击平台，跳过发射，但保留事件链记录)
-- ============================================================
local evChafei = ScenEdit_SetEvent('KC_ST01_003_打击ddg_chafei', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evChafei then
    local t0 = ScenEdit_CurrentTime()
    ScenEdit_SetTrigger({mode='add', type='Time', name='KC_ST01_003_T0',
        time = t0 + 0})
    ScenEdit_SetEventTrigger(evChafei.guid, {mode='add', name='KC_ST01_003_T0'})

    local msg = string.format(
        'ScenEdit_SpecialMessage("%s", "[打击链 ST-01-003] 打击 ddg_chafei (%.4f, %.4f)，目标区域: DDG Chafei")',
        SIDE_RED, 8.284662, 119.783273
    )
    ScenEdit_SetAction({mode='add', type='LuaScript', name='KC_ST01_003_Action', ScriptText = msg})
    ScenEdit_SetEventAction(evChafei.guid, {mode='add', name='KC_ST01_003_Action'})
end

-- T0+2h: 打击 chafei 评估
local evChafeiAssess = ScenEdit_SetEvent('KC_ST01_003_评估ddg_chafei', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evChafeiAssess then
    local t0 = ScenEdit_CurrentTime()
    ScenEdit_SetTrigger({mode='add', type='Time', name='KC_ST01_003_T2h',
        time = t0 + 7200})
    ScenEdit_SetEventTrigger(evChafeiAssess.guid, {mode='add', name='KC_ST01_003_T2h'})

    local assessMsg = string.format(
        'ScenEdit_SpecialMessage("%s", "[打击链 ST-01-003] 打击完成时间点 (T0+2h)，ddg_chafei 毁伤评估中...")',
        SIDE_RED
    )
    ScenEdit_SetAction({
        mode='add', type='LuaScript', name='KC_ST01_003_AssessMsg', ScriptText = assessMsg
    })
    ScenEdit_SetEventAction(evChafeiAssess.guid, {mode='add', name='KC_ST01_003_AssessMsg'})
end

-- ============================================================
-- Kill Chain: ST-01-001 打击 lha_meiguo
-- ============================================================
local evLha = ScenEdit_SetEvent('KC_ST01_001_打击lha_meiguo', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evLha then
    local t0 = ScenEdit_CurrentTime()
    ScenEdit_SetTrigger({mode='add', type='Time', name='KC_ST01_001_T0',
        time = t0 + 0})
    ScenEdit_SetEventTrigger(evLha.guid, {mode='add', name='KC_ST01_001_T0'})

    local msg = string.format(
        'ScenEdit_SpecialMessage("%s", "[打击链 ST-01-001] 打击 lha_meiguo (%.4f, %.4f)，目标: 两栖攻击舰/航母")',
        SIDE_RED, 7.922858, 120.093579
    )
    ScenEdit_SetAction({mode='add', type='LuaScript', name='KC_ST01_001_Action', ScriptText = msg})
    ScenEdit_SetEventAction(evLha.guid, {mode='add', name='KC_ST01_001_Action'})
end

-- T0+2h: lha 评估
local evLhaAssess = ScenEdit_SetEvent('KC_ST01_001_评估lha', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evLhaAssess then
    local t0 = ScenEdit_CurrentTime()
    ScenEdit_SetTrigger({mode='add', type='Time', name='KC_ST01_001_T2h',
        time = t0 + 7200})
    ScenEdit_SetEventTrigger(evLhaAssess.guid, {mode='add', name='KC_ST01_001_T2h'})

    local assessMsg = string.format(
        'ScenEdit_SpecialMessage("%s", "[打击链 ST-01-001] lha_meiguo 打击完成 (T0+2h)，毁伤评估中...")',
        SIDE_RED
    )
    ScenEdit_SetAction({
        mode='add', type='LuaScript', name='KC_ST01_001_AssessMsg', ScriptText = assessMsg
    })
    ScenEdit_SetEventAction(evLhaAssess.guid, {mode='add', name='KC_ST01_001_AssessMsg'})
end

-- ============================================================
-- Kill Chain: ST-01-004 打击 supply_kz
-- ============================================================
local evSupply = ScenEdit_SetEvent('KC_ST01_004_打击supply_kz', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evSupply then
    local t0 = ScenEdit_CurrentTime()
    ScenEdit_SetTrigger({mode='add', type='Time', name='KC_ST01_004_T0',
        time = t0 + 0})
    ScenEdit_SetEventTrigger(evSupply.guid, {mode='add', name='KC_ST01_004_T0'})

    local msg = string.format(
        'ScenEdit_SpecialMessage("%s", "[打击链 ST-01-004] 打击 supply_kz (%.4f, %.4f)，目标: 补给舰")',
        SIDE_RED, -0.101186, 106.164261
    )
    ScenEdit_SetAction({mode='add', type='LuaScript', name='KC_ST01_004_Action', ScriptText = msg})
    ScenEdit_SetEventAction(evSupply.guid, {mode='add', name='KC_ST01_004_Action'})
end

-- ============================================================
-- Kill Chain: ST-01-005 打击 ddg_momuseng
-- ============================================================
local evMomu = ScenEdit_SetEvent('KC_ST01_005_打击ddg_momuseng', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evMomu then
    local t0 = ScenEdit_CurrentTime()
    ScenEdit_SetTrigger({mode='add', type='Time', name='KC_ST01_005_T0',
        time = t0 + 0})
    ScenEdit_SetEventTrigger(evMomu.guid, {mode='add', name='KC_ST01_005_T0'})

    local msg = string.format(
        'ScenEdit_SpecialMessage("%s", "[打击链 ST-01-005] 打击 ddg_momuseng (%.4f, %.4f)，目标: 宙斯盾驱逐舰")',
        SIDE_RED, 7.104, 116.28
    )
    ScenEdit_SetAction({mode='add', type='LuaScript', name='KC_ST01_005_Action', ScriptText = msg})
    ScenEdit_SetEventAction(evMomu.guid, {mode='add', name='KC_ST01_005_Action'})

    -- J-20A 编队出击
    local j20Msg = string.format(
        'ScenEdit_SpecialMessage("%s", "[J-20A 出击] zds001-zds004 隐身战斗机编队起飞，前往 ddg_momuseng 目标区域 (%.4f, %.4f)")',
        SIDE_RED, 7.104, 116.28
    )
    ScenEdit_SetAction({mode='add', type='LuaScript', name='KC_ST01_005_J20Msg', ScriptText = j20Msg})
    ScenEdit_SetEventAction(evMomu.guid, {mode='add', name='KC_ST01_005_J20Msg'})
end

-- T0+2h: momuseng 评估
local evMomuAssess = ScenEdit_SetEvent('KC_ST01_005_评估ddg_momuseng', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evMomuAssess then
    local t0 = ScenEdit_CurrentTime()
    ScenEdit_SetTrigger({mode='add', type='Time', name='KC_ST01_005_T2h',
        time = t0 + 7200})
    ScenEdit_SetEventTrigger(evMomuAssess.guid, {mode='add', name='KC_ST01_005_T2h'})

    local assessMsg = string.format(
        'ScenEdit_SpecialMessage("%s", "[打击链 ST-01-005] ddg_momuseng 打击完成 (T0+2h)，毁伤评估中，要求毁伤率 >= 50%%")',
        SIDE_RED
    )
    ScenEdit_SetAction({
        mode='add', type='LuaScript', name='KC_ST01_005_AssessMsg', ScriptText = assessMsg
    })
    ScenEdit_SetEventAction(evMomuAssess.guid, {mode='add', name='KC_ST01_005_AssessMsg'})
end

-- ============================================================
-- === 定期事件：每5分钟报告 Red 方作战单元状态
-- ============================================================
local evStatus = ScenEdit_SetEvent('RED_STATUS_REPORT', {
    mode = 'add',
    IsRepeatable = true,
    IsActive = true,
})
if evStatus then
    ScenEdit_SetTrigger({mode='add', type='RegularTime', name='RED_STATUS_5min', interval=300})
    ScenEdit_SetEventTrigger(evStatus.guid, {mode='add', name='RED_STATUS_5min'})

    local script = [[
local side = VP_GetSide({Side='红方部队'})
if side then
    local count = #(side.units or {})
    local names = {}
    for _, u in ipairs(side.units or {}) do
        table.insert(names, u.name)
    end
    ScenEdit_SpecialMessage('红方部队', '[状态报告] 当前在线作战单元: ' .. count .. ' 架/艘')
end
]]
    ScenEdit_SetAction({mode='add', type='LuaScript', name='RED_STATUS_Action', ScriptText = script})
    ScenEdit_SetEventAction(evStatus.guid, {mode='add', name='RED_STATUS_Action'})
end

-- ============================================================
-- === 方案结束事件 (T0+2h40m = 9600s)
-- ============================================================
local evEnd = ScenEdit_SetEvent('PHASE_END_REPORT', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evEnd then
    local t0 = ScenEdit_CurrentTime()
    ScenEdit_SetTrigger({mode='add', type='Time', name='PHASE_END_T2h40m',
        time = t0 + 9600})
    ScenEdit_SetEventTrigger(evEnd.guid, {mode='add', name='PHASE_END_T2h40m'})

    local endMsg = 'ScenEdit_SpecialMessage("红方部队", "[阶段结束] 反舰作战实施阶段结束 (T0+2h40m)，请进行最终战果评估")'
    ScenEdit_SetAction({mode='add', type='LuaScript', name='PHASE_END_Action', ScriptText = endMsg})
    ScenEdit_SetEventAction(evEnd.guid, {mode='add', name='PHASE_END_Action'})
end

-- ============================================================
-- === 初始情报播报（场景加载时）
-- ============================================================
ScenEdit_SpecialMessage(SIDE_RED, '========== 联合打击方案 (2026B) 已部署 ==========')
ScenEdit_SpecialMessage(SIDE_RED, '方案开始时间: 2025-10-27 13:30:00 (UTC+8)')
ScenEdit_SpecialMessage(SIDE_RED, '红方已部署: J-16D x4, J-20A x4, H-6K x6, E-3C预警机 x1, SSN潜艇 x9(DF-26/UUV替代)')
ScenEdit_SpecialMessage(SIDE_RED, '蓝方已部署: Ticonderoga x1, Arleigh Burke x3, LHA x1')
ScenEdit_SpecialMessage(SIDE_RED, '【注意】wxjb卫星因数据库无卫星条目已跳过，标注为参考点')

print("[INFO] Script execution complete.")
print("[SUMMARY]")
print("  Blue ships deployed:  tico_simoer(DBID=42), ddg_chafei(DBID=112), lha_meiguo(DBID=502),")
print("                       ddg_momuseng(DBID=438), supply_kz(DBID=112 proxy=DDG)")
print("  Red aircraft deployed: J-16D x4(DBID=4632), J-20A x4(DBID=5012), H-6K x6(DBID=4900), kja001 E-3C(DBID=209)")
print("  Red subs (DF-26/UUV proxy): SSN 688 LA x9(DBID=22) from dfb/dfd/wruuv groups")
print("  SKIPPED: wxjb SAT (no satellite in DB)")
print("  Kill chain events: ST-01-001 ~ ST-01-005")
