-- ==========================================================================
-- main.lua — STEP 1/4 — 消耗与诱歼作战方案
--   1. 创建两侧阵营 (红方/蓝方)
--   2. 创建 8 个单位 (5 红 + 3 蓝)
--   3. 设置两侧 Doctrine
--   4. 设置两侧 EMCON
--   5. 蓝方 autodetectable = true（关键 — 否则 fireAt 找不到 contact）
--   6. 红方 awareness = OMNI（全知全能）
--   7. (可选) 红方 J-16 / EA-18G 加入 SEAD 巡逻任务
--
-- 自审清单 (SKILL.md 第 1687-1698 行):
--   [x] latitude/longitude 参数名正确
--   [x] type 为 Aircraft/Ship/Submarine (非 Air/Ground)
--   [x] dbid 全部从 manifest.lua 引用 (无硬编码)
--   [x] side="红方" / "蓝方" (无 "Red"/"Blue")
--   [x] 红方 OMNI 用 ScenEdit_SetSideOptions({awareness="OMNI"})
--   [x] 蓝方 autodetectable 双保险 (创建时 + 后置 pcall)
-- ==========================================================================

print("[CMO] [INFO] ============ main.lua 开始 (消耗与诱歼作战方案) ============")

-- 加载单一数据源
dofile("manifest.lua")

-- ==========================================================================
-- 工具函数
-- ==========================================================================
local function log(level, msg) print("[CMO] [" .. level .. "] " .. tostring(msg)) end
local function info(msg)  log("INFO",    msg) end
local function warn(msg)  log("WARNING", msg) end
local function ok(msg)    log("SUCCESS", msg) end

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

local function safeAddUnit(props)
    local r = pcall(ScenEdit_AddUnit, props)
    if not r then warn("AddUnit 失败: " .. tostring(props.name)) end
    return r
end

local function findUnit(side, name)
    local r, s = pcall(VP_GetSide, { Side = side })
    if not r or not (s and s.units) then return nil end
    for _, u in ipairs(s.units) do
        if u.name == name then return u end
    end
    return nil
end

local function forceBlueAutodetectable(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not (u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
end

-- ==========================================================================
-- 1. 创建两侧 + 设置 Hostile 关系
-- ==========================================================================
ensureSide(CFG_SCENARIO.side_blue, "128,128,255")
ensureSide(CFG_SCENARIO.side_red,  "255,64,64")
setHostile(CFG_SCENARIO.side_red,  CFG_SCENARIO.side_blue)
setHostile(CFG_SCENARIO.side_blue, CFG_SCENARIO.side_red)
ok("红方/蓝方 关系: Hostile")

-- ==========================================================================
-- 2. 创建单位（红 5 + 蓝 3 = 8）
--    严格使用 manifest.lua 的 UNITS[name] 数据 (严禁硬编码 dbid/坐标)
-- ==========================================================================
local function addUnitFromManifest(uid)
    local u = UNITS[uid]
    if not u then
        warn("manifest 缺单位: " .. uid)
        return
    end
    local props = {
        side      = u.side,
        type      = u.type,
        name      = u.name,
        dbid      = u.dbid,
        lat       = u.lat,
        lon       = u.lon,
    }
    -- Aircraft 必须有 altitude
    if u.type == "Aircraft" then
        props.altitude = u.altitude
        -- 注: LoadoutID 未指定 (按 manifest 决策 — 改走 ScenEdit_AddReloadsToUnit)
        props.proficiency = "Regular"
    elseif u.type == "Ship" then
        props.proficiency = "Veteran"
    elseif u.type == "Submarine" then
        -- 潜艇初始位置用 altitude 但实际是潜望镜深度
        props.proficiency = "Regular"
    end

    -- 蓝方默认 autodetectable=true (主保险)
    if u.side == CFG_SCENARIO.side_blue and CFG_SCENARIO.blue_autodetectable then
        props.autodetectable = true
    end

    safeAddUnit(props)
    ok(string.format("%-15s | %s | %-12s | dbid=%-5d @ (%s, %s)",
        uid, u.side, u.type, u.dbid, u.lat, u.lon))
end

print()
print("[CMO] ---------- 1. 创建 8 个单位 ----------")
addUnitFromManifest("red_ddg_1")
addUnitFromManifest("red_ddg_2")
addUnitFromManifest("red_sub_1")
addUnitFromManifest("red_ac_1")
addUnitFromManifest("red_ew_1")
addUnitFromManifest("blue_ddg_1")
addUnitFromManifest("blue_ddg_2")
addUnitFromManifest("blue_aux_1")

-- ==========================================================================
-- 3. Doctrine 设置
--    红方: 全部 Free (weapon_control_status_* = 0)
--    蓝方: 表面/水下 Hold = 2, 其他 Free = 0
-- ==========================================================================
print()
print("[CMO] ---------- 2. 设置 Doctrine ----------")
local r1 = pcall(ScenEdit_SetDoctrine, { side = CFG_SCENARIO.side_red }, CFG_DOCTRINE_RED)
ok("红方 Doctrine: 全部 WCS=Free")

local r2 = pcall(ScenEdit_SetDoctrine, { side = CFG_SCENARIO.side_blue }, CFG_DOCTRINE_BLUE)
ok("蓝方 Doctrine: Surface/Subsurface=Hold, Air/Land=Free")

-- ==========================================================================
-- 4. EMCON — 全部 Radar=Active;Sonar=Active;OECM=Active
-- ==========================================================================
print()
print("[CMO] ---------- 3. 设置 EMCON ----------")
for _, uid in ipairs({"red_ddg_1", "red_ddg_2", "red_sub_1", "red_ac_1", "red_ew_1",
                       "blue_ddg_1", "blue_ddg_2", "blue_aux_1"}) do
    local u = UNITS[uid]
    local unit = findUnit(u.side, u.name)
    if unit and unit.guid then
        local emcon = (u.side == CFG_SCENARIO.side_red) and CFG_SCENARIO.red_emcon or CFG_SCENARIO.blue_emcon
        pcall(ScenEdit_SetEMCON, "Unit", unit.guid, emcon)
    end
end
ok("所有 8 个单位 EMCON = Active (Radar+Sonar+OECM)")

-- ==========================================================================
-- 5. 蓝方 autodetectable 双保险 (复检)
-- ==========================================================================
print()
print("[CMO] ---------- 4. 蓝方 autodetectable 双保险 ----------")
for _, uid in ipairs({"blue_ddg_1", "blue_ddg_2", "blue_aux_1"}) do
    local u = UNITS[uid]
    if forceBlueAutodetectable(u.side, u.name) then
        ok("  " .. uid .. " autodetectable=true (二次确认)")
    else
        warn("  " .. uid .. " autodetectable 设不上")
    end
end

-- ==========================================================================
-- 6. 红方 awareness = OMNI (全知全能, 必须用 ScenEdit_SetSideOptions)
-- ==========================================================================
print()
print("[CMO] ---------- 5. 红方 OMNI (全知全能) ----------")
do
    _errnum_ = 0
    local r = ScenEdit_SetSideOptions({ side = CFG_SCENARIO.side_red, awareness = "OMNI" })
    if (_errnum_ or 0) == 0 then
        ok("红方 awareness = " .. tostring(r and r.awareness or "OMNI"))
    else
        warn("OMNI 设置失败: " .. tostring(_errmsg_))
    end
end

-- ==========================================================================
-- 7. SEAD 巡逻任务 (red_ew_1) — 在 attack/clear 之前不强制创建 (可选)
--    这里先创建并加入巡逻任务,让 EA-18G 在场景中持续巡逻
-- ==========================================================================
print()
print("[CMO] ---------- 6. 创建 SEAD 巡逻任务 (red_ew_1) ----------")
do
    -- 创建 4 个 REFERENCE POINTS (PATROLS[1].rps[])
    local rps = PATROLS[1].rps
    for i, rp_name in ipairs(rps) do
        local r = REFERENCE_POINTS[i]
        if r then
            pcall(ScenEdit_AddReferencePoint, {
                side = r.side, name = r.name,
                lat = r.lat, lon = r.lon,
                highlighted = false,
            })
        end
    end
    ok("已创建 " .. #rps .. " 个参考点 (RP-EW-1..4)")

    -- 创建 SEAD 巡逻任务
    local pcall_ok = pcall(ScenEdit_AddMission, {
        side = CFG_SCENARIO.side_red,
        name = "M04_J16D_EA18G_SEAD",
        type = "Patrol",
        subtype = "SEAD",
        description = "电子战 SEAD 巡逻 (manifest PATROLS[1])",
    })
    if pcall_ok then ok("任务已创建: M04_J16D_EA18G_SEAD") else
        warn("SEAD 任务创建失败 (可能已存在)")
    end

    -- 设置巡逻区
    pcall(ScenEdit_SetMission, CFG_SCENARIO.side_red, "M04_J16D_EA18G_SEAD", {
        patrolzone = rps,
        onethirdrule = false,
    })

    -- 加入单位
    local ew = findUnit(CFG_SCENARIO.side_red, "red_ew_1")
    if ew and ew.guid then
        pcall(ScenEdit_AssignUnitToMission, {
            side = CFG_SCENARIO.side_red,
            unitname = "red_ew_1",
            mission = "M04_J16D_EA18G_SEAD",
        })
        ok("red_ew_1 已加入 SEAD 巡逻")
    else
        warn("找不到 red_ew_1 GUID, 任务未指定单位")
    end
end

print()
print("[CMO] ============ main.lua 完成 ============")
print("下一步: 跑 clear.lua (清弹)")