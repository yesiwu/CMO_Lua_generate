-- ============================================================
-- all.lua — 最小验证场景: 1×055 + 1×J-16 (从 055 起飞)
-- 用途: 验证 Aircraft 在 Ship 上创建的可行性
-- 数据: 055 dbid=3883 (Type 055 Renhai)
--       J-16 dbid=2853 (Flying Shark)
-- 在 CMO Alt+F9 一次执行全部流程
-- ============================================================

print("===== minimal launch scenario START =====")

-- ============================================================
-- §1 配置
-- ============================================================
_SIDE_RED = "红方"

-- 055 母舰位置（东海）
SHIP = {
    side       = _SIDE_RED,
    type       = "Ship",
    name       = "ship_055",
    dbid       = 3883,           -- Type 055 Renhai [101 Nanchang]
    latitude   = 30.316,
    longitude  = 122.650,
    heading    = 90,
    speed      = 0,              -- 母舰停泊
    proficiency= "Veteran",
    autodetectable = false,
}

-- J-16 飞机（从 055 上起飞 = 055 飞行甲板）
-- ★ 关键: Aircraft 必须 altitude=0，且必须在 Ship 半径内才会被认作从舰上起飞
AIR = {
    side       = _SIDE_RED,
    type       = "Aircraft",
    name       = "air_j16",
    dbid       = 2853,           -- J-16 Flying Shark
    latitude   = 30.316,         -- ★ 与 055 完全相同
    longitude  = 122.650,        -- ★ 与 055 完全相同
    altitude   = 0,              -- ★ 必须 0
    heading    = 90,
    speed      = 0,              -- 创建时静止，mission 启动后自动起飞
    proficiency= "Veteran",
    autodetectable = false,
    -- 起飞后去巡逻点（055 前方 30km，8000m）
    launch_mission = {
        type      = "ASW",       -- 用 ASW 任务，飞行模式
        latitude  = 30.476,      -- 约 +16km 北向
        longitude = 122.950,
        altitude  = 8000,
        Throttle  = "Cruise",
    },
}

-- ============================================================
-- §2 工具
-- ============================================================
local function info(msg) print("[INFO] "  .. msg) end
local function warn(msg) print("[WARN] "  .. msg) end
local function ok(msg)   print("[OK] "    .. msg) end
local function err(msg)  print("[ERROR] " .. msg) end

local function unitExists(side, name)
    local ok2, u = pcall(ScenEdit_GetUnit, { side = side, name = name })
    return ok2 and u and u.guid
end

-- ============================================================
-- §3 创建阵营
-- ============================================================
print("\n===== PART 1: 阵营 =====")
pcall(ScenEdit_AddSide, { name = _SIDE_RED, color = "255,0,0" })
pcall(ScenEdit_SetSideOptions, { side = _SIDE_RED, awareness = "OMNI" })
ok("阵营 " .. _SIDE_RED .. " 就绪 + OMNI")

-- ============================================================
-- §4 创建 055 母舰
-- ============================================================
print("\n===== PART 2: 创建 055 母舰 =====")

if unitExists(SHIP.side, SHIP.name) then
    warn("055 已存在，跳过")
else
    _errnum_ = 0
    local ok2, u = pcall(ScenEdit_AddUnit, SHIP)
    if ok2 and u and u.guid then
        ok("055 已创建 guid=" .. tostring(u.guid))
    else
        err("055 创建失败: " .. tostring(_errmsg_))
    end
end

-- ============================================================
-- §5 创建 J-16（在 055 位置上）
-- ============================================================
print("\n===== PART 3: 创建 J-16 =====")

if unitExists(AIR.side, AIR.name) then
    warn("J-16 已存在，跳过")
else
    -- 关键: 把飞机的 lat/lon 强制对齐到 055
    AIR.latitude  = SHIP.latitude
    AIR.longitude = SHIP.longitude

    _errnum_ = 0
    local ok2, u = pcall(ScenEdit_AddUnit, AIR)
    if ok2 and u and u.guid then
        ok("J-16 已创建 guid=" .. tostring(u.guid))

        -- 给 J-16 派"起飞"任务：让它从甲板上飞到巡逻点
        _errnum_ = 0
        local okMis = pcall(ScenEdit_AddMission, u.guid, AIR.launch_mission)
        if okMis and (_errnum_ or 0) == 0 then
            ok("J-16 已派任务 ASW → (" .. AIR.launch_mission.latitude
                .. ", " .. AIR.launch_mission.longitude
                .. ") alt=" .. AIR.launch_mission.altitude .. "m")
        else
            warn("J-16 派任务失败: " .. tostring(_errmsg_)
                .. " — 飞机可能停在甲板/机场，需手动 Launch")
        end
    else
        err("J-16 创建失败: " .. tostring(_errmsg_))
    end
end

-- ============================================================
-- §6 自检
-- ============================================================
print("\n===== PART 4: 自检 =====")
local s055 = ScenEdit_GetUnit({ side = _SIDE_RED, name = "ship_055" })
local j16  = ScenEdit_GetUnit({ side = _SIDE_RED, name = "air_j16" })

if s055 and s055.guid then
    ok(("055: guid=%s lat=%.4f lon=%.4f speed=%s"):format(
        tostring(s055.guid), s055.latitude or 0, s055.longitude or 0, tostring(s055.speed)))
end
if j16 and j16.guid then
    ok(("J-16: guid=%s lat=%.4f lon=%.4f alt=%s"):format(
        tostring(j16.guid), j16.latitude or 0, j16.longitude or 0, tostring(j16.altitude)))

    -- 检查挂载
    local mountCount = 0
    local weaponCount = 0
    for _, m in ipairs(j16.mounts or {}) do
        mountCount = mountCount + 1
        for _, w in ipairs(m.mount_weapons or {}) do
            weaponCount = weaponCount + (tonumber(w.wpn_current) or 0)
        end
    end
    info(("  mounts=%d 挂载总数, 当前挂弹合计=%d"):format(mountCount, weaponCount))
end

-- 计算 055 与 J-16 的距离（验证飞机确实在甲板上）
if s055 and s055.guid and j16 and j16.guid then
    local distKm = ScenEdit_GetDistance({ side = _SIDE_RED, name = "ship_055" },
                                       { side = _SIDE_RED, name = "air_j16" })
    info(("055↔J-16 距离 = %.1f km"):format((distKm or 0)))
    if distKm and distKm > 0.5 then
        warn(("距离 > 0.5 km，飞机可能不在甲板上！距离=%.2f"):format(distKm))
    end
end

print("\n===== minimal scenario COMPLETE =====")
print("下一步:")
print("  1. 回到 CMO 主界面，点 ▶ Play 推进仿真时间")
print("  2. 看 J-16 是否自动从 055 甲板上起飞")
print("  3. 如果没起飞，按 H 打开 J-16，右键 → Launch")