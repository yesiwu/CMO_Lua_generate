-- ============================================================
-- main.lua: 1V1 场景初始化（南海）
-- 红方: 055-1  (OMNI)
-- 蓝方: DDG-113-1  (autodetectable=true, 传感器 Active)
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
    dbid_ddg113 = 4299,

    -- 坐标（南海海域）
    lat_055     = 15.0, lon_055     = 112.5,
    lat_ddg113  = 19.0, lon_ddg113  = 117.5,

    side_red  = "红方",
    side_blue = "蓝方",

    blue_autodetectable = true,
    blue_sensor_default = "Active",
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

local function forceBlueAutodetectable(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not (u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
end

-- ---------- 执行 ----------
print("")
print("========================================")
print("       南海 1V1 场景初始化")
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
    latitude  = CFG.lat_ddg113, longitude = CFG.lon_ddg113,
    heading   = clampHeading(200), speed = 0,
    proficiency = "Veteran",
    autodetectable = CFG.blue_autodetectable,
})

-- 蓝方 Doctrine：纯防御，对海 Hold，对空 Free
pcall(ScenEdit_SetDoctrine, { side = CFG.side_blue }, {
    weapon_control_status_air        = 0,
    weapon_control_status_subsurface = 2,
    weapon_control_status_surface   = 2,
})
ok("蓝方 Doctrine: Air=Free, Surface/Subsurface=Hold")

-- 蓝方传感器默认 Active
info("蓝方 EMCON=Active")
local blueU = findUnit(CFG.side_blue, "DDG-113-1")
if blueU and blueU.guid then
    pcall(ScenEdit_SetEMCON, "Unit", blueU.guid, "Radar=Active;Sonar=Active;OECM=Active")
end

-- 蓝方 autodetectable 双保险
if CFG.blue_autodetectable then
    info("强制蓝方 autodetectable=true...")
    if forceBlueAutodetectable(CFG.side_blue, "DDG-113-1") then
        ok("DDG-113-1 autodetectable=true")
    end
end

-- ========== 红方单位 ==========
info("创建红方单位...")
createOrReuse(CFG.side_red, "055-1", {
    side = CFG.side_red, type = "Ship", name = "055-1",
    dbid = CFG.dbid_055,
    latitude  = CFG.lat_055, longitude = CFG.lon_055,
    heading   = clampHeading(45), speed = 20,
    proficiency = "Veteran",
})

-- 红方传感器主动
local redU = findUnit(CFG.side_red, "055-1")
if redU and redU.guid then
    pcall(ScenEdit_SetEMCON, "Unit", redU.guid, "Radar=Active;Sonar=Active;OECM=Active")
end
ok("红方 EMCON=Active")

-- 红方全知（必须用 ScenEdit_SetSideOptions）
info("设置红方为全知 (OMNI)...")
do
    _errnum_ = 0
    local a = ScenEdit_SetSideOptions({ side = CFG.side_red, awareness = "OMNI" })
    if (_errnum_ or 0) == 0 then
        ok("红方 awareness = " .. tostring(a and a.awareness or "OMNI"))
    else
        warn("OMNI 失败: " .. tostring(_errmsg_))
    end
end

-- 红方 Doctrine：WCS = Free
pcall(ScenEdit_SetDoctrine, { side = CFG.side_red }, {
    weapon_control_status_air        = 0,
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 0,
})
ok("红方 Doctrine: WCS=Free")

print("")
print("========================================")
print("场景初始化完成")
print("红方: 055-1  (OMNI, EMCON=Active)")
print("蓝方: DDG-113-1  (autodetectable, EMCON=Active)")
print("========================================")
print("")
ok("main.lua 执行完毕")