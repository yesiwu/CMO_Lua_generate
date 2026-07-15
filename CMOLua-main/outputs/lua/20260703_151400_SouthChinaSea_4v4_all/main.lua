-- ============================================================
-- main.lua: 4V4 场景初始化（南海）
-- 红方全知 OMNI；蓝方传感器默认 Active；autodetectable=true
-- 红方 055-1   -> 蓝方 DDG-113-1
-- 红方 055-2   -> 蓝方 DDG-113-2
-- 红方 052D-1  -> 蓝方 CVN-70
-- 红方 052D-2  -> 蓝方 CG-59
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 配置区 ----------
local CFG = {
    -- 单位 DBID（用户指定）
    dbid_055    = 3883,
    dbid_052d1  = 2296,
    dbid_052d2  = 3586,
    dbid_ddg113 = 4299,
    dbid_cvn70  = 3551,
    dbid_cg59   = 2862,
    dbid_yj18   = 2868,

    -- 坐标（南海海域）
    lat_055_1    = 15.0, lon_055_1    = 112.5,
    lat_055_2    = 15.5, lon_055_2    = 112.8,
    lat_052d1    = 16.0, lon_052d1    = 112.0,
    lat_052d2    = 16.5, lon_052d2    = 113.0,
    lat_ddg113_1 = 19.0, lon_ddg113_1 = 117.5,
    lat_ddg113_2 = 19.3, lon_ddg113_2 = 117.8,
    lat_cvn70    = 19.5, lon_cvn70    = 117.0,
    lat_cg59     = 19.5, lon_cg59     = 118.0,

    side_red  = "红方",
    side_blue = "蓝方",

    blue_autodetectable = true,
    blue_sensor_default = "Active",  -- 蓝方传感器默认开启
}

-- ---------- 工具函数 ----------
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

-- 强制蓝方目标 autodetectable（双保险）
local function forceBlueAutodetectable(name)
    local u = ScenEdit_GetUnit({ side = CFG.side_blue, name = name })
    if not (u and u.guid) then
        warn("找不到蓝方目标: " .. tostring(name))
        return false
    end
    return pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
end

-- ---------- 执行 ----------
print("")
print("========================================")
print("       南海 4V4 场景初始化")
print("========================================")
print("")

-- 阵营
ensureSide(CFG.side_blue, "128,128,255")
ensureSide(CFG.side_red,  "255,64,64")
setHostile(CFG.side_red,  CFG.side_blue)
setHostile(CFG.side_blue, CFG.side_red)

-- ========== 蓝方目标 ==========
info("创建蓝方目标...")
createOrReuse(CFG.side_blue, "DDG-113-1", {
    side = CFG.side_blue, type = "Ship", name = "DDG-113-1",
    dbid = CFG.dbid_ddg113,
    latitude = CFG.lat_ddg113_1, longitude = CFG.lon_ddg113_1,
    heading  = clampHeading(200), speed = 0,
    proficiency = "Veteran",
    autodetectable = CFG.blue_autodetectable,
})
createOrReuse(CFG.side_blue, "DDG-113-2", {
    side = CFG.side_blue, type = "Ship", name = "DDG-113-2",
    dbid = CFG.dbid_ddg113,
    latitude = CFG.lat_ddg113_2, longitude = CFG.lon_ddg113_2,
    heading  = clampHeading(210), speed = 0,
    proficiency = "Veteran",
    autodetectable = CFG.blue_autodetectable,
})
createOrReuse(CFG.side_blue, "CVN-70", {
    side = CFG.side_blue, type = "Ship", name = "CVN-70",
    dbid = CFG.dbid_cvn70,
    latitude = CFG.lat_cvn70, longitude = CFG.lon_cvn70,
    heading  = clampHeading(220), speed = 0,
    proficiency = "Veteran",
    autodetectable = CFG.blue_autodetectable,
})
createOrReuse(CFG.side_blue, "CG-59", {
    side = CFG.side_blue, type = "Ship", name = "CG-59",
    dbid = CFG.dbid_cg59,
    latitude = CFG.lat_cg59, longitude = CFG.lon_cg59,
    heading  = clampHeading(215), speed = 0,
    proficiency = "Veteran",
    autodetectable = CFG.blue_autodetectable,
})

-- 蓝方 Doctrine：纯防御，对海/对潜 Hold，对空 Free
pcall(ScenEdit_SetDoctrine, { side = CFG.side_blue }, {
    weapon_control_status_air         = 0,
    weapon_control_status_subsurface  = 2,
    weapon_control_status_surface     = 2,
})
ok("蓝方 Doctrine：Air=Free, Surface/Subsurface=Hold")

-- 蓝方传感器默认开启（创建时已是 Active，再遍历一次确认）
info("蓝方传感器开启: " .. CFG.blue_sensor_default)
for _, name in ipairs({ "DDG-113-1", "DDG-113-2", "CVN-70", "CG-59" }) do
    local u = findUnit(CFG.side_blue, name)
    if u and u.guid then
        pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=" .. CFG.blue_sensor_default
            .. ";Sonar=" .. CFG.blue_sensor_default
            .. ";OECM="  .. CFG.blue_sensor_default)
    end
end

-- 强制 autodetectable（双保险：创建时设 + 创建后再设）
if CFG.blue_autodetectable then
    info("强制蓝方 autodetectable=true...")
    for _, name in ipairs({ "DDG-113-1", "DDG-113-2", "CVN-70", "CG-59" }) do
        if forceBlueAutodetectable(name) then
            ok("蓝方目标 autodetectable=true: " .. name)
        end
    end
end

-- ========== 红方单位 ==========
info("创建红方单位...")
createOrReuse(CFG.side_red, "055-1", {
    side = CFG.side_red, type = "Ship", name = "055-1",
    dbid = CFG.dbid_055,
    latitude = CFG.lat_055_1, longitude = CFG.lon_055_1,
    heading  = clampHeading(45), speed = 20,
    proficiency = "Veteran",
})
createOrReuse(CFG.side_red, "055-2", {
    side = CFG.side_red, type = "Ship", name = "055-2",
    dbid = CFG.dbid_055,
    latitude = CFG.lat_055_2, longitude = CFG.lon_055_2,
    heading  = clampHeading(45), speed = 20,
    proficiency = "Veteran",
})
createOrReuse(CFG.side_red, "052D-1", {
    side = CFG.side_red, type = "Ship", name = "052D-1",
    dbid = CFG.dbid_052d1,
    latitude = CFG.lat_052d1, longitude = CFG.lon_052d1,
    heading  = clampHeading(45), speed = 20,
    proficiency = "Veteran",
})
createOrReuse(CFG.side_red, "052D-2", {
    side = CFG.side_red, type = "Ship", name = "052D-2",
    dbid = CFG.dbid_052d2,
    latitude = CFG.lat_052d2, longitude = CFG.lon_052d2,
    heading  = clampHeading(45), speed = 20,
    proficiency = "Veteran",
})

-- 红方传感器主动
info("红方 Radar/Sonar/OECM=Active...")
for _, name in ipairs({ "055-1", "055-2", "052D-1", "052D-2" }) do
    local u = findUnit(CFG.side_red, name)
    if u and u.guid then
        pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active;Sonar=Active;OECM=Active")
    end
end
ok("红方 EMCON=Active")

-- 红方全知（必须使用 ScenEdit_SetSideOptions，不得用 Doctrine/EMCON 伪装）
info("设置红方为全知 (OMNI)...")
do
    _errnum_ = 0
    local a = ScenEdit_SetSideOptions({ side = CFG.side_red, awareness = "OMNI" })
    if (_errnum_ or 0) == 0 then
        ok("红方 awareness = " .. tostring(a and a.awareness or "OMNI"))
    else
        warn("设置 OMNI 失败: " .. tostring(_errmsg_))
    end
end

-- 红方 Doctrine：WCS = Free（允许自主开火）
pcall(ScenEdit_SetDoctrine, { side = CFG.side_red }, {
    weapon_control_status_air        = 0,
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 0,
})
ok("红方 Doctrine：WCS = Free")

print("")
print("========================================")
print("场景初始化完成")
print("红方: 055-1, 055-2, 052D-1, 052D-2 (OMNI)")
print("蓝方: DDG-113-1, DDG-113-2, CVN-70, CG-59 (autodetectable)")
print("========================================")
print("")
ok("main.lua 执行完毕")