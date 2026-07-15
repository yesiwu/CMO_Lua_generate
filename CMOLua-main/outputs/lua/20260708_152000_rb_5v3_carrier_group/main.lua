-- ============================================================
-- main.lua: 建单位（红方5V3 辽宁舰+J-15×2 vs CVN-70编队）
-- 数据来源: JSON red_blue_5v3_liaoning.json
-- ============================================================

print("[CMO] [INFO] ============ main.lua 开始 ============")

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

local function clampHeading(h)
    if type(h) ~= "number" then return 0 end
    return ((h % 360) + 360) % 360
end

local function sideExists(name)
    return pcall(VP_GetSide, { Side = name })
end

local function ensureSide(name, color)
    if sideExists(name) then
        info("阵营已存在: " .. name)
        return true
    end
    local ok2 = pcall(ScenEdit_AddSide, { name = name, color = color })
    if ok2 then ok("阵营创建成功: " .. name) end
    return ok2
end

local function setHostile(from, to)
    pcall(ScenEdit_SetSidePosture, from, to, "H")
end

local function findUnit(side, name)
    local ok2, s = pcall(VP_GetSide, { Side = side })
    if not ok2 or not (s and s.units) then return nil end
    for _, u in ipairs(s.units) do
        if u.name == name then return u end
    end
    return nil
end

local function safeAddUnit(props)
    local ok2, r = pcall(ScenEdit_AddUnit, props)
    if not ok2 then err("AddUnit 失败: " .. tostring(r)); return nil end
    return r
end

local function createOrReuse(side, name, props)
    local exist = findUnit(side, name)
    if exist then
        info(side .. "/" .. name .. " 已存在，复用")
        return exist
    end
    local u = safeAddUnit(props)
    if u then ok("[" .. side .. "] " .. name .. " dbid=" .. tostring(props.dbid)) end
    return u
end

local function forceBlueAutodetectable(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not (u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
end

-- ============================================================
-- 配置常量（来自 JSON）
-- ============================================================
local CFG = {
    dbid_055      = 3883,
    dbid_052d1    = 2296,
    dbid_052d2    = 3586,
    dbid_liaoning = 2007,
    dbid_j15      = 2496,
    dbid_loadout_j15 = 9682,
    dbid_cvn70    = 3551,
    dbid_cg59     = 2862,
    dbid_ddg113   = 4299,

    -- 红方位置（JSON §platforms）
    lat_055_1      = 24.8324, lon_055_1      = 128.5830,
    lat_052d1      = 21.1437, lon_052d1      = 123.4510,
    lat_052d2      = 18.2035, lon_052d2      = 123.9880,
    lat_liaoning   = 25.0000, lon_liaoning   = 130.0000,

    -- 蓝方位置（JSON §killWebs targets）
    lat_cvn70      = 21.5419, lon_cvn70      = 129.9125,
    lat_cg59       = 21.6100, lon_cg59       = 130.1791,
    lat_ddg113_1   = 21.4200, lon_ddg113_1   = 130.1713,
    lat_ddg113_2   = 21.6000, lon_ddg113_2   = 130.2000,

    side_red  = "红方",
    side_blue = "蓝方",
}

print("========================================")
print("       STEP 1/4: 建单位")
print("========================================")

ensureSide(CFG.side_blue, "128,128,255")
ensureSide(CFG.side_red,  "255,64,64")
setHostile(CFG.side_red,  CFG.side_blue)
setHostile(CFG.side_blue, CFG.side_red)

-- 蓝方目标
local BLUE_NAMES = {
    "蓝方CVN-70卡尔文森",
    "蓝方CG-59普林斯顿",
    "蓝方DDG-113-1约翰芬恩",
    "蓝方DDG-113-2约翰芬恩",
}
local BLUE_DBDID = {
    ["蓝方CVN-70卡尔文森"]     = CFG.dbid_cvn70,
    ["蓝方CG-59普林斯顿"]       = CFG.dbid_cg59,
    ["蓝方DDG-113-1约翰芬恩"]  = CFG.dbid_ddg113,
    ["蓝方DDG-113-2约翰芬恩"]  = CFG.dbid_ddg113,
}
local BLUE_LOC = {
    ["蓝方CVN-70卡尔文森"]     = {lat=CFG.lat_cvn70,    lon=CFG.lon_cvn70},
    ["蓝方CG-59普林斯顿"]       = {lat=CFG.lat_cg59,     lon=CFG.lon_cg59},
    ["蓝方DDG-113-1约翰芬恩"]  = {lat=CFG.lat_ddg113_1, lon=CFG.lon_ddg113_1},
    ["蓝方DDG-113-2约翰芬恩"]  = {lat=CFG.lat_ddg113_2, lon=CFG.lon_ddg113_2},
}
local BLUE_HEADING = {
    ["蓝方CVN-70卡尔文森"]     = 294,
    ["蓝方CG-59普林斯顿"]       = 295,
    ["蓝方DDG-113-1约翰芬恩"]  = 293,
    ["蓝方DDG-113-2约翰芬恩"]  = 293,
}

for _, name in ipairs(BLUE_NAMES) do
    local loc = BLUE_LOC[name]
    createOrReuse(CFG.side_blue, name, {
        side = CFG.side_blue, type = "Ship", name = name,
        dbid = BLUE_DBDID[name],
        latitude = loc.lat, longitude = loc.lon,
        heading = clampHeading(BLUE_HEADING[name]), speed = 0,
        proficiency = "Veteran",
        autodetectable = true,
    })
end

pcall(ScenEdit_SetDoctrine, { side = CFG.side_blue }, {
    weapon_control_status_air         = 0,
    weapon_control_status_subsurface  = 2,
    weapon_control_status_surface     = 2,
})
ok("蓝方 Doctrine: Air=Free, Surface/Subsurface=Hold")

-- 蓝方传感器 Active
info("蓝方 EMCON=Active")
for _, name in ipairs(BLUE_NAMES) do
    local u = findUnit(CFG.side_blue, name)
    if u and u.guid then
        pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active;Sonar=Active;OECM=Active")
    end
end

-- 蓝方 autodetectable 双保险
for _, name in ipairs(BLUE_NAMES) do
    if forceBlueAutodetectable(CFG.side_blue, name) then
        ok("autodetectable=true: " .. name)
    end
end

-- 红方舰艇
local RED_SHIP_NAMES = {
    "红方055南昌舰",
    "红方052D-1昆明舰",
    "红方052D-2南京舰",
    "红方辽宁舰",
}
local RED_SHIP_DBDID = {
    ["红方055南昌舰"]    = CFG.dbid_055,
    ["红方052D-1昆明舰"] = CFG.dbid_052d1,
    ["红方052D-2南京舰"] = CFG.dbid_052d2,
    ["红方辽宁舰"]       = CFG.dbid_liaoning,
}
local RED_SHIP_LOC = {
    ["红方055南昌舰"]    = {lat=CFG.lat_055_1,  lon=CFG.lon_055_1},
    ["红方052D-1昆明舰"] = {lat=CFG.lat_052d1,  lon=CFG.lon_052d1},
    ["红方052D-2南京舰"] = {lat=CFG.lat_052d2,  lon=CFG.lon_052d2},
    ["红方辽宁舰"]       = {lat=CFG.lat_liaoning, lon=CFG.lon_liaoning},
}
for _, name in ipairs(RED_SHIP_NAMES) do
    local loc = RED_SHIP_LOC[name]
    createOrReuse(CFG.side_red, name, {
        side = CFG.side_red, type = "Ship", name = name,
        dbid = RED_SHIP_DBDID[name],
        latitude = loc.lat, longitude = loc.lon,
        heading = 45, speed = 20, proficiency = "Veteran",
    })
end

-- 红方舰载机（loadoutid=9682，含 YJ-83K）
local RED_AIR_NAMES = { "J-15-1", "J-15-2" }
for _, name in ipairs(RED_AIR_NAMES) do
    if not findUnit(CFG.side_red, name) then
        _errnum_ = 0
        local ok2 = pcall(ScenEdit_AddUnit, {
            type = "Aircraft", side = CFG.side_red, name = name,
            dbid = CFG.dbid_j15,
            loadoutid = CFG.dbid_loadout_j15,
            base = "红方辽宁舰", proficiency = "Veteran",
        })
        if ok2 then
            ok("[" .. CFG.side_red .. "] " .. name .. " dbid=" .. CFG.dbid_j15 .. " loadoutid=" .. CFG.dbid_loadout_j15)
        else
            warn("带 loadoutid 建机失败，裸机重试: " .. name)
            _errnum_ = 0
            ok2 = pcall(ScenEdit_AddUnit, {
                type = "Aircraft", side = CFG.side_red, name = name,
                dbid = CFG.dbid_j15,
                base = "红方辽宁舰", proficiency = "Veteran",
            })
            ok("[" .. CFG.side_red .. "] " .. name .. " [后备裸机] ok=" .. tostring(ok2))
        end
    else
        info(CFG.side_red .. "/" .. name .. " 已存在，复用")
    end
    local u = findUnit(CFG.side_red, name)
    if u and u.guid then
        pcall(ScenEdit_SetUnit, {side = CFG.side_red, unitname = name, timetoready_minutes = 0})
        pcall(ScenEdit_SetUnit, {side = CFG.side_red, unitname = name, launch = true})
        pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active;Sonar=Active;OECM=Active")
    end
end

-- 红方 OMNI
do
    _errnum_ = 0
    local a = ScenEdit_SetSideOptions({ side = CFG.side_red, awareness = "OMNI" })
    if (_errnum_ or 0) == 0 then
        ok("红方 awareness = " .. tostring(a and a.awareness or "OMNI"))
    else
        warn("OMNI 失败: " .. tostring(_errmsg_))
    end
end

pcall(ScenEdit_SetDoctrine, { side = CFG.side_red }, {
    weapon_control_status_air        = 0,
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 0,
})
ok("红方 Doctrine: WCS=Free")
ok("STEP 1 完成: 单位已就绪")
