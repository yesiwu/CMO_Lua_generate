-- ============================================================
-- main.lua — A1 YJ-18 联合反舰打击 (生成红蓝方单位)
-- 数据全部来自 manifest.lua 的 UNITS / SCENARIO
-- 红方全知全能 (OMNI)；蓝方目标 autodetectable=true（红线 #8）
-- 蓝方单位传感器默认开启（用户要求）
-- ============================================================

dofile("manifest.lua")

-- ---------- 工具函数 ----------
local LOG = "[main]"

local function info(msg)  print(LOG .. " [INFO] "  .. msg) end
local function warn(msg)  print(LOG .. " [WARN] "  .. msg) end
local function err(msg)   print(LOG .. " [ERROR] " .. msg) end
local function ok(msg)    print(LOG .. " [OK] "    .. msg) end

-- 幂等性：单位已存在则跳过（红线 #11）
local function unitExists(side, name)
    local ok2, u = pcall(ScenEdit_GetUnit, { side = side, name = name })
    return ok2 and u and u.guid
end

-- 安全 AddUnit（捕获错误 + 幂等）
local function safeAddUnit(spec)
    if unitExists(spec.side, spec.name) then
        warn(("单位已存在，跳过: %s/%s"):format(spec.side, spec.name))
        return ScenEdit_GetUnit({ side = spec.side, name = spec.name })
    end
    local args = {
        side           = spec.side,
        type           = spec.type,
        name           = spec.name,
        dbid           = spec.dbid,
        latitude       = spec.latitude,
        longitude      = spec.longitude,
        heading        = spec.heading,
        speed          = spec.speed,
        proficiency    = spec.proficiency,
        autodetectable = spec.autodetectable,
    }
    _errnum_ = 0
    local ok2, u = pcall(ScenEdit_AddUnit, args)
    if not ok2 or not u or not u.guid then
        err(("AddUnit 失败: %s/%s dbid=%s err=%s"):format(
            spec.side, spec.name, tostring(spec.dbid), tostring(_errmsg_)))
        return nil
    end
    -- 二次强制设置 autodetectable（双保险，红线 #8）
    pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = spec.autodetectable })
    ok(("创建: %s/%s dbid=%s → guid=%s"):format(
        spec.side, spec.name, tostring(spec.dbid), tostring(u.guid)))
    return u
end

-- ============================================================
-- §1 创建阵营
-- ============================================================
info("=== 创建阵营 ===")
local function ensureSide(name, color)
    local ok2, _ = pcall(ScenEdit_AddSide, { name = name, color = color })
    if ok2 then
        ok("阵营已存在或创建: " .. name)
    else
        warn("阵营可能已存在: " .. name)
    end
end

ensureSide("红方", "255,0,0")
ensureSide("蓝方", "0,0,255")

-- ============================================================
-- §2 阵营设置
-- ============================================================
info("=== 阵营设置 ===")
-- 红方全知全能（红线 #6：必须用 SetSideOptions，不能用 EMCON/Doctrine 伪装）
pcall(ScenEdit_SetSideOptions, { side = "红方", awareness = "OMNI" })
ok("红方 awareness = OMNI")

-- 蓝方默认 sensors 开启（用户要求：默认开启，蓝方不主动开火）
pcall(ScenEdit_SetDoctrine, { side = "蓝方" }, {
    weapon_control_status_air        = 2,  -- Hold（不主动还击）
    weapon_control_status_surface    = 2,
    weapon_control_status_subsurface = 2,
})
ok("蓝方 WCS = Hold(2)，不主动攻击，仅传感器被动探测")

-- 红方 WCS = Free（红线 #12，避免导弹发射后立即消失）
pcall(ScenEdit_SetDoctrine, { side = "红方" }, {
    weapon_control_status_air        = 0,  -- Free
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 0,
})
ok("红方 WCS = Free(0)，可主动开火")

-- 敌对关系（双向）
pcall(ScenEdit_SetSidePosture, "红方", "蓝方", "H")
pcall(ScenEdit_SetSidePosture, "蓝方", "红方", "H")
ok("红蓝双方敌对 (H)")

-- ============================================================
-- §3 创建所有单位（UNITS dict-keyed）
-- ============================================================
info("=== 创建单位 ===")
local created = {}
for uid, spec in pairs(UNITS) do
    local u = safeAddUnit(spec)
    if u and u.guid then
        created[#created + 1] = { name = spec.name, side = spec.side, guid = u.guid }
    end
end
ok("成功创建 " .. #created .. " / " .. tostring((function()
    local n = 0
    for _ in pairs(UNITS) do n = n + 1 end
    return n
end)()) .. " 单位")

-- ============================================================
-- §4 蓝方单位 autodetectable 二次确认（遍历强制）
-- ============================================================
info("=== 蓝方 autodetectable 二次确认 ===")
local blueCount = 0
for uid, spec in pairs(UNITS) do
    if spec.side == "蓝方" then
        local ok2, u = pcall(ScenEdit_GetUnit, { side = spec.side, name = spec.name })
        if ok2 and u and u.guid then
            pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
            blueCount = blueCount + 1
        end
    end
end
ok("蓝方 " .. blueCount .. " 个单位已强制设置 autodetectable = true")

-- ============================================================
-- §5 蓝方传感器默认开启（用户要求）
-- ============================================================
info("=== 蓝方传感器默认开启 ===")
for uid, spec in pairs(UNITS) do
    if spec.side == "蓝方" then
        local ok2, u = pcall(ScenEdit_GetUnit, { side = spec.side, name = spec.name })
        if ok2 and u and u.guid then
            pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active;Sonar=Active;OECM=Passive")
        end
    end
end
ok("蓝方所有单位 EMCON = Radar=Active;Sonar=Active;OECM=Passive")

-- ============================================================
-- §6 完成
-- ============================================================
info("=== main.lua 完成 ===")
print(LOG .. " [INFO] 下一步: 运行 clear.lua → reload.lua → attack.lua")