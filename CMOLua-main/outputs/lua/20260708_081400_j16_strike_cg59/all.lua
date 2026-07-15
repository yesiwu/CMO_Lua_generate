-- ============================================================
-- all.lua — 最小验证场景 v2: 1×055 + 1×J-16 起飞 + 打击 CG-59
-- 用途: 验证 Aircraft 在 Ship 上起飞 → 投放 Loadout 弹 → 命中 CG-59
-- 数据:
--   055   dbid=3883  (Type 055 Renhai)
--   J-16  dbid=2853  (Flying Shark)
--   CG-59 dbid=2862  (Ticonderoga Princeton, SM-3 Blk IIA)
--   武器  dbid=2868  (YJ-18 反舰 — 兼容 SKU，LoadoutID 预装优先)
-- 在 CMO Alt+F9 一次执行全部流程
-- ============================================================

print("===== minimal strike scenario START =====")

-- ============================================================
-- §0 全局配置
-- ============================================================
_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"
_WPN_ASM   = 2868            -- 反舰弹 (YJ-18 SKU 兼容)
_J16_LOADOUT = 14059         -- YJ-83K 反舰挂载
_CONTACT_SETTLE_DELAY = 15   -- 必须 >= 15

-- ============================================================
-- §1 单位配置
-- ============================================================

-- 055 母舰位置（东海）
SHIP_055 = {
    side       = _SIDE_RED,
    type       = "Ship",
    name       = "ship_055",
    dbid       = 3883,
    latitude   = 30.316,
    longitude  = 122.650,
    heading    = 90,
    speed      = 0,
    proficiency= "Veteran",
    autodetectable = false,
}

-- 蓝方 CG-59 巡洋舰目标（关键: autodetectable = true）
TARGET_CG59 = {
    side       = _SIDE_BLUE,
    type       = "Ship",
    name       = "cg59_target",
    dbid       = 2862,
    latitude   = 30.400,
    longitude  = 124.500,        -- ~175km 东北方向
    heading    = 0,
    speed      = 14,
    proficiency= "Veteran",
    autodetectable = true,       -- ★ 红方能否获得 contact 的关键
}

-- J-16（与 055 同坐标 = 在 055 甲板上）
AIR_J16 = {
    side       = _SIDE_RED,
    type       = "Aircraft",
    name       = "air_j16",
    dbid       = 2853,
    latitude   = 30.316,         -- ★ 与 SHIP_055 相同
    longitude  = 122.650,        -- ★ 与 SHIP_055 相同
    altitude   = 0,              -- ★ 必须 0
    heading    = 90,
    speed      = 0,
    proficiency= "Veteran",
    autodetectable = false,
    loadout_id = _J16_LOADOUT,   -- 预装 YJ-83K
    launch_mission = {
        type      = "ASW",
        latitude  = 30.484,
        longitude = 123.100,     -- 起飞后先去中继点
        altitude  = 8000,
        Throttle  = "Cruise",
    },
}

-- 打击任务：J-16 → CG-59
STRIKE = {
    {
        attacker = "air_j16",
        target   = "cg59_target",
        weapon   = _WPN_ASM,
        quantity = 2,             -- Loadout 里有 2 枚
        startDelay = 60,          -- 60 秒后启动 TOT（给飞机起飞 + 飞向目标区时间）
        interval   = 5,
        intent     = "J-16 投放 YJ-83K 打 CG-59",
    },
}

-- ============================================================
-- §2 工具函数
-- ============================================================
local function info(msg) print("[INFO] "  .. msg) end
local function warn(msg) print("[WARN] "  .. msg) end
local function ok(msg)   print("[OK] "    .. msg) end
local function err(msg)  print("[ERROR] " .. msg) end

local function unitExists(side, name)
    local ok2, u = pcall(ScenEdit_GetUnit, { side = side, name = name })
    return ok2 and u and u.guid
end

local function ensureAutodetectable(targetName)
    local u = ScenEdit_GetUnit({ side = _SIDE_BLUE, name = targetName })
    if not u or not u.guid then return nil end
    pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
    return u
end

-- ============================================================
-- §3 Unix 秒 → .NET Ticks（CMO Time Trigger 时间格式）
-- ============================================================
local function unixToTicks(unixSec)
    local T0 = 621355968000000000   -- .NET ticks at 1970-01-01
    return T0 + math.floor(unixSec * 10000000)
end

-- ============================================================
-- §4 fireAt — 全局（不能在 local 块内！事件沙箱无法访问 local）
--   流程: 找目标 contact → AttackContact (mode="1")；找不到再降级 BOL
-- ============================================================
function fireAt(attackerName, targetName, wpnDbid, qty)
    local a = ScenEdit_GetUnit({ side = _SIDE_RED, name = attackerName })
    if not a or not a.guid then
        err("fireAt: 攻击方 " .. attackerName .. " 不存在")
        return false
    end

    -- 双保险：发射前再 set 一次 autodetectable
    local t = ScenEdit_GetUnit({ side = _SIDE_BLUE, name = targetName })
    if t and t.guid then
        ScenEdit_SetUnit({ guid = t.guid, autodetectable = true })
    else
        err("fireAt: 目标 " .. targetName .. " 不存在")
        return false
    end

    -- 在 contact 列表中查目标
    local contacts = ScenEdit_GetContactList({ side = _SIDE_RED })
    if not contacts or type(contacts) ~= "table" then
        err("fireAt: 拿不到 contact 列表")
        return false
    end

    local contactGuid = nil
    for _, c in ipairs(contacts) do
        if (c.side or c.Side or "") == _SIDE_BLUE
            and (tostring(c.unitname or c.UnitName or "") == targetName
             or tostring(c.guid or c.GUID or "") == t.guid) then
            contactGuid = c.guid or c.GUID
            break
        end
    end

    local r
    if contactGuid then
        info(("fireAt: %s → contact(%s) weapon=%d qty=%d"):format(
            attackerName, contactGuid, wpnDbid, qty))
        r = ScenEdit_AttackContact(a.guid, contactGuid, {
            latitude  = t.latitude,
            longitude = t.longitude,
            mode      = "1",     -- ★ 必须字符串 "1"，不是数字 1
            weapon    = wpnDbid,
            qty       = qty,
        })
    else
        -- BOL 兜底（移动目标会脱靶，但能保证有动作）
        warn("fireAt: 找不到 contact，降级 BOL（移动目标可能脱靶）")
        r = ScenEdit_AttackContact(a.guid, t.guid, {
            latitude  = t.latitude,
            longitude = t.longitude,
            mode      = "1",
            weapon    = wpnDbid,
            qty       = qty,
        })
    end

    if r then
        ok(("fireAt OK: %s → %s qty=%d"):format(attackerName, targetName, qty))
        return true
    else
        err("fireAt FAIL: 无返回值")
        return false
    end
end

-- ============================================================
-- §5 scheduleOne — 把每枚弹做成独立 Time 触发器
-- ============================================================
local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    local actualDelay = delay + _CONTACT_SETTLE_DELAY

    local evName = "Evt_J16CG59_" .. tag .. "_" .. tostring(math.random(1, 99999))
    local trName = "Trg_J16CG59_" .. tag
    local acName = "Act_J16CG59_" .. tag

    local fireTime = unixToTicks(ScenEdit_CurrentTime() + actualDelay)

    -- ★ 脚本内容：完整自含，可访问全局 fireAt
    local scriptBody = string.format([[
-- 自包含调用（沙箱中只有全局可见）
fireAt(%q, %q, %d, 1)
-- 清理
pcall(ScenEdit_SetEvent,   %q, { mode = "remove" })
pcall(ScenEdit_SetTrigger, { mode = "remove", name = %q })
pcall(ScenEdit_SetAction,  { mode = "remove", name = %q })
]], atkName, tgtName, wpn, evName, trName, acName)

    pcall(ScenEdit_SetTrigger, { mode = "add", type = "Time",
                                   name = trName, Time = fireTime })
    pcall(ScenEdit_SetAction,  { mode = "add", type = "LuaScript",
                                   name = acName, ScriptText = scriptBody })
    pcall(ScenEdit_SetEvent,   evName, { mode = "add",
                                           IsActive = true,
                                           IsRepeatable = false })
    pcall(ScenEdit_SetEventTrigger, evName, { mode = "add", name = trName })
    pcall(ScenEdit_SetEventAction,  evName, { mode = "add", name = acName })

    ok(("scheduled: %s → %s qty=1 delay=%.1fs (含 settle %ds)"):format(
        atkName, tgtName, actualDelay, _CONTACT_SETTLE_DELAY))
end

-- ============================================================
-- §6 创建阵营
-- ============================================================
print("\n===== PART 1: 阵营 + Doctrine =====")
pcall(ScenEdit_AddSide, { name = _SIDE_RED,  color = "255,0,0" })
pcall(ScenEdit_AddSide, { name = _SIDE_BLUE, color = "0,0,255" })
pcall(ScenEdit_SetSideOptions, { side = _SIDE_RED, awareness = "OMNI" })

-- 红方 WCS = Free (0)，确保主动发射不被压
pcall(ScenEdit_SetDoctrine, { side = _SIDE_RED }, {
    weapon_control_status_surface = 0,
    weapon_control_status_air     = 0,
})
-- 蓝方 WCS = Hold (2)，不让 DDG 反扑污染数据
pcall(ScenEdit_SetDoctrine, { side = _SIDE_BLUE }, {
    weapon_control_status_surface = 2,
    weapon_control_status_air     = 2,
})
ok("阵营就绪: " .. _SIDE_RED .. "=OMNI/Free, " .. _SIDE_BLUE .. "=Hold")

-- ============================================================
-- §7 创建 055 母舰
-- ============================================================
print("\n===== PART 2: 055 母舰 =====")
if unitExists(SHIP_055.side, SHIP_055.name) then
    warn("055 已存在，跳过")
else
    _errnum_ = 0
    local ok2, u = pcall(ScenEdit_AddUnit, SHIP_055)
    if ok2 and u and u.guid then
        ok("055 已创建 guid=" .. tostring(u.guid))
    else
        err("055 创建失败: " .. tostring(_errmsg_))
    end
end

-- ============================================================
-- §8 创建蓝方 CG-59
-- ============================================================
print("\n===== PART 3: CG-59 目标 =====")
if unitExists(TARGET_CG59.side, TARGET_CG59.name) then
    warn("CG-59 已存在，跳过")
else
    _errnum_ = 0
    local ok2, u = pcall(ScenEdit_AddUnit, TARGET_CG59)
    if ok2 and u and u.guid then
        ok("CG-59 已创建 guid=" .. tostring(u.guid))
        pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
    else
        err("CG-59 创建失败: " .. tostring(_errmsg_))
    end
end

-- ============================================================
-- §9 创建 J-16 + 挂载 + 派任务
-- ============================================================
print("\n===== PART 4: J-16 飞机 =====")
if unitExists(AIR_J16.side, AIR_J16.name) then
    warn("J-16 已存在，跳过")
else
    -- 对齐坐标
    AIR_J16.latitude  = SHIP_055.latitude
    AIR_J16.longitude = SHIP_055.longitude

    _errnum_ = 0
    local ok2, u = pcall(ScenEdit_AddUnit, AIR_J16)
    if ok2 and u and u.guid then
        ok("J-16 已创建 guid=" .. tostring(u.guid))

        -- 二次 Loadout（保险）
        _errnum_ = 0
        if pcall(ScenEdit_LoadUnit, u.guid, AIR_J16.loadout_id) and (_errnum_ or 0) == 0 then
            ok("J-16 LoadoutID=" .. AIR_J16.loadout_id .. " 已应用")
        else
            warn("LoadoutID 应用失败: " .. tostring(_errmsg_) .. " —— 继续，弹可能为空")
        end

        -- 派任务（让飞机起飞）
        _errnum_ = 0
        if pcall(ScenEdit_AddMission, u.guid, AIR_J16.launch_mission) and (_errnum_ or 0) == 0 then
            ok("J-16 已派任务 ASW")
        else
            warn("派任务失败: " .. tostring(_errmsg_) .. " —— 飞机可能停在甲板")
        end
    else
        err("J-16 创建失败: " .. tostring(_errmsg_))
    end
end

-- ============================================================
-- §10 校验挂载
-- ============================================================
print("\n===== PART 5: 自检挂载 =====")
local j16 = ScenEdit_GetUnit({ side = _SIDE_RED, name = "air_j16" })
if j16 and j16.guid then
    local mounts = j16.mounts or {}
    local totalWpn = 0
    for _, m in ipairs(mounts) do
        for _, w in ipairs(m.mount_weapons or {}) do
            totalWpn = totalWpn + (tonumber(w.wpn_current) or 0)
        end
    end
    info(("J-16 mounts=%d  弹合计=%d"):format(#mounts, totalWpn))
    if totalWpn == 0 then
        warn("J-16 当前 0 弹 —— LoadoutID 可能无效，fireAt 会失败")
    end
end

local cg = ensureAutodetectable(TARGET_CG59.name)
if cg and cg.guid then
    ok("CG-59 guid=" .. tostring(cg.guid) .. " autodetectable=true 已确认")
else
    err("CG-59 自检失败")
end

-- ============================================================
-- §11 真延时 TOT 调度
-- ============================================================
print("\n===== PART 6: 真延时 TOT 调度 =====")
local function runStrike(strike)
    local qty = strike.quantity or 1
    for k = 1, qty do
        local perMissileDelay = (strike.startDelay or 0) + (k - 1) * (strike.interval or 0)
        local tag = string.format("%s_to_%s_k%d", strike.attacker, strike.target, k)
        scheduleOne(strike.attacker, strike.target, strike.weapon, perMissileDelay, tag)
    end
    ok(("全部 %d 个 trigger 已下发：[%s]"):format(qty, strike.intent or ""))
end

for _, s in ipairs(STRIKE) do
    runStrike(s)
end

-- ============================================================
-- §12 完成
-- ============================================================
print("\n===== COMPLETE =====")
print("时间线:")
print("  T+0      : 055 / CG-59 / J-16 已建，事件已下发")
print("  T+0~30s  : 在 CMO 按 ▶ Play 推进仿真，飞机起飞")
print("  T+60s+15 : 第一枚弹 contact settle 完成，触发放")
print("  T+60s+20 : 第二枚弹触发放")
print("")
print("验收点:")
print("  • J-16 是否从 055 甲板上起飞？")
print("  • T+75s 后是否看到 YJ-83K 飞向 CG-59？")
print("  • CG-59 是否被命中/受损？")
print("")
print("若 LoadoutID=14059 警告出现，仍能跑但弹为 0 —— 告诉我，换 manual 装弹 SKU")