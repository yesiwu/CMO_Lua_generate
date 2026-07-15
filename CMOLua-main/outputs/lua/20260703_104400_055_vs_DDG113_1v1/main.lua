-- ============================================================
-- main.lua: 055 vs DDG-113 1v1 场景初始化
-- 红方全知全能，蓝方目标 autodetectable=true
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 配置区 ----------
local CFG = {
    -- 单位 DBID（用户提供）
    dbid_055   = 3883,    -- Type 055 Nanchang
    dbid_ddg113 = 4299,   -- DDG 113 John Finn

    -- 武器 DBID
    dbid_yj18 = 2868,     -- YJ-18

    -- 阵营
    side_red  = "红方",
    side_blue = "蓝方",

    -- contact 稳定等待时间（必须 >= 15 秒）
    contact_settle_delay = 15,
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
        info("Side exists: " .. name)
        return true
    end
    local ok2 = pcall(ScenEdit_AddSide, { name = name, color = color })
    if ok2 then ok("Side created: " .. name) end
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
    if not ok2 then
        err("AddUnit failed: " .. tostring(r))
        return nil
    end
    return r
end

local function createOrReuse(side, name, props)
    local exist = findUnit(side, name)
    if exist then
        info(side .. "/" .. name .. " exists, reuse")
        return exist
    end
    local u = safeAddUnit(props)
    if u then
        ok("[" .. side .. "] " .. name .. " dbid=" .. tostring(props.dbid))
    end
    return u
end

-- 强制蓝方目标 autodetectable=true（三个时间点之一）
local function forceBlueAutodetectable(name)
    local u = ScenEdit_GetUnit({ side = CFG.side_blue, name = name })
    if not (u and u.guid) then
        warn("Cannot set autodetectable; blue target not found: " .. tostring(name))
        return false
    end
    local okAuto = pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
    if okAuto then
        ok("Blue target autodetectable=true: " .. tostring(name))
    else
        warn("Set autodetectable failed: " .. tostring(name))
    end
    return okAuto
end

-- ---------- 场景初始化 ----------
info("========================================")
info("055 vs DDG-113 1v1 场景初始化")
info("========================================")

-- 1. 创建红蓝方
ensureSide(CFG.side_blue, "128,128,255")
ensureSide(CFG.side_red,  "255,64,64")
setHostile(CFG.side_red,  CFG.side_blue)
setHostile(CFG.side_blue, CFG.side_red)
ok("红蓝方敌对关系设定完成")

-- 2. Doctrine：WCS=Free
for _, side in ipairs({ CFG.side_blue, CFG.side_red }) do
    pcall(ScenEdit_SetDoctrine, { side = side }, {
        weapon_control_status_air        = 0,
        weapon_control_status_surface    = 0,
        weapon_control_status_subsurface = 0,
    })
end
ok("Doctrine WCS = Free")

-- ---------- 创建蓝方单位 ----------
info("Create blue units...")

-- 东海附近：DDG-113 John Finn
createOrReuse(CFG.side_blue, "DDG-113", {
    side          = CFG.side_blue,
    type          = "Ship",
    name          = "DDG-113",
    dbid          = CFG.dbid_ddg113,
    latitude      = 26.5,
    longitude     = 127.5,
    heading       = clampHeading(270),
    speed         = 0,
    proficiency   = "Veteran",
    autodetectable = true,  -- 关键：创建时设 autodetectable
})

-- 蓝方雷达关闭，被动防御
local blueUnit = findUnit(CFG.side_blue, "DDG-113")
if blueUnit and blueUnit.guid then
    pcall(ScenEdit_SetEMCON, "Unit", blueUnit.guid, "Radar=Off")
end

-- ---------- 创建红方单位 ----------
info("Create red units...")

-- 东海附近：055 Nanchang
createOrReuse(CFG.side_red, "055-Nanchang", {
    side        = CFG.side_red,
    type        = "Ship",
    name        = "055-Nanchang",
    dbid        = CFG.dbid_055,
    latitude    = 28.0,
    longitude   = 125.0,
    heading     = clampHeading(90),
    speed       = 15,
    proficiency = "Veteran",
})

-- 红方雷达开启
local redUnit = findUnit(CFG.side_red, "055-Nanchang")
if redUnit and redUnit.guid then
    pcall(ScenEdit_SetEMCON, "Unit", redUnit.guid, "Radar=Active")
end

-- ---------- 红方全知全能（关键！） ----------
info("Set red awareness=OMNI...")
do
    _errnum_ = 0
    local a = ScenEdit_SetSideOptions({ side = CFG.side_red, awareness = "OMNI" })
    if (_errnum_ or 0) == 0 then
        ok("Red awareness = " .. tostring(a and a.awareness or "OMNI"))
    else
        warn("Set OMNI failed: " .. tostring(_errmsg_))
    end
end

-- ---------- 第二次强制 autodetectable（三个时间点之二） ----------
info("Force blue targets autodetectable=true...")
for _, name in ipairs({ "DDG-113" }) do
    forceBlueAutodetectable(name)
end

-- ---------- 自检：055 待发弹 ----------
info("Self-check 055-Nanchang ready weapons...")
do
    local u = ScenEdit_GetUnit({ side = CFG.side_red, name = "055-Nanchang" })
    if u then
        local total = 0
        for i, m in ipairs(u.mounts or {}) do
            for _, w in ipairs(m.mount_weapons or {}) do
                local c = tonumber(w.wpn_current) or 0
                if c > 0 then
                    info(("  MOUNT %d dbid=%s cur=%d"):format(i, tostring(w.wpn_dbid), c))
                    total = total + c
                end
            end
        end
        ok("055-Nanchang ready weapon total = " .. tostring(total))
    end
end

ok("main.lua 执行完毕")
