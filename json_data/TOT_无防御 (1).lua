-- ============================================================
-- CMO 3v3 红蓝对抗 — 精简版（单位创建 + 清空待发弹 + 弹药补给）
-- 适用: CMO 公开版 / 专业版
-- Lua: 5.4（无全局 unpack；使用 table.unpack）
-- ============================================================

local CFG = {
    cmo_version      = "unknown",
    database_name    = "unknown",
    database_version = "unknown",

    -- 单位 DBID
    dbid_ddg113   = 4299,
    dbid_cg59     = 2862,
    dbid_cvn70    = 3551,
    dbid_052d_nj  = 4936,
    dbid_052d_xy  = 4936,
    dbid_055_nc   = 3883,

    -- 武器 DBID
    dbid_yj21 = 4058,
    dbid_yj18 = 2868,

    side_red  = "红方",
    side_blue = "蓝方",

    overwrite_existing = false,
}

-- ============================================================
-- 工具函数
-- ============================================================
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

local function safeAddUnit(props)
    local ok2, r = pcall(ScenEdit_AddUnit, props)
    if not ok2 then
        err("AddUnit 失败: " .. tostring(r))
        return nil
    end
    return r
end

local function findUnit(side, name)
    local ok2, s = pcall(VP_GetSide, { Side = side })
    if not ok2 or not (s and s.units) then return nil end
    for _, u in ipairs(s.units) do
        if u.name == name then return u end
    end
    return nil
end

local function clampHeading(h)
    if type(h) ~= "number" then return 0 end
    return ((h % 360) + 360) % 360
end

local function sideExists(name)
    return pcall(VP_GetSide, { Side = name })
end

local function ensureSide(name, color)
    if sideExists(name) then
        info("阵营 " .. name .. " 已存在")
        return true
    end
    local ok2 = pcall(ScenEdit_AddSide, { name = name, color = color })
    if ok2 then ok("阵营 " .. name .. " 创建成功") end
    return ok2
end

local function setHostile(from, to)
    pcall(ScenEdit_SetSidePosture, from, to, "H")
end

local function createOrReuse(side, name, props)
    local exist = findUnit(side, name)
    if exist then
        if CFG.overwrite_existing then
            pcall(ScenEdit_DeleteUnit, { guid = exist.guid })
            warn(side .. "/" .. name .. " 已存在，已删除重建")
        else
            info(side .. "/" .. name .. " 已存在，复用")
            return exist
        end
    end
    local u = safeAddUnit(props)
    if u then
        ok("[" .. side .. "] " .. name .. " (dbid=" .. props.dbid .. ")")
    end
    return u
end

-- ============================================================
-- 清空单位所有 mount 待发弹（把数量减到 0，但保留武器记录/格子）
-- 注意：不能用 remove_weapon 删记录——那会把格子也删掉，导致后续
--       AddReloadsToUnit 找不到兼容 mount，弹装不回去。
--       这里用 AddReloadsToUnit + remove=true 仅扣减数量，格子保留。
-- ============================================================
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("clearUnitWeapons: 找不到 " .. side .. "/" .. name)
        return false
    end

    -- 1) 快照所有 mount 中 cur>0 的武器（边减边遍历原表不安全）
    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs + 1] = {
                    dbid = w.wpn_dbid, num = cur, mountid = m.mount_guid,
                }
            end
        end
    end

    -- 2) 逐条把数量减到 0（保留记录）
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({
            guid = u.guid, wpn_dbid = j.dbid,
            mount_guid = j.mountid, number = j.num, remove = true,
        })
        if (_errnum_ or 0) == 0 then done = done + 1
        else fail = fail + 1 end
    end

    ok(("%s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
end

-- ============================================================
-- 环境预检
-- ============================================================
info("========================================")
info("CMO 3v3 红蓝对抗脚本 — 精简版")
info("========================================")

for _, name in ipairs({ "DDG 113", "052D NJ", "052D XY", "055 NC", "YJ-21", "YJ-18", "CG 59", "CVN 70" }) do
    local v = CFG["dbid_" .. name:gsub("%s+", ""):lower()]
    -- 简化校验
end

ensureSide(CFG.side_blue, "128,128,255")
ensureSide(CFG.side_red,  "255,64,64")
setHostile(CFG.side_red,  CFG.side_blue)
setHostile(CFG.side_blue, CFG.side_red)

for _, side in ipairs({ CFG.side_blue, CFG.side_red }) do
    pcall(ScenEdit_SetDoctrine, { side = side }, {
        weapon_control_status_air        = 0,
        weapon_control_status_surface    = 0,
        weapon_control_status_subsurface = 0,
    })
end
ok("Doctrine WCS = Free")

-- ============================================================
-- 创建蓝方单位
-- ============================================================
info("创建蓝方单位...")
createOrReuse(CFG.side_blue, "DDG 113", {
    side = CFG.side_blue, type = "Ship",
    name = "DDG 113", dbid = CFG.dbid_ddg113,
    latitude = 21.5419, longitude = 129.9125,
    heading = clampHeading(294.05), speed = 0,
    proficiency = "Veteran",
})
createOrReuse(CFG.side_blue, "Blue-DBID-2862", {
    side = CFG.side_blue, type = "Ship",
    name = "Blue-DBID-2862", dbid = CFG.dbid_cg59,
    latitude = 21.6100, longitude = 130.1791,
    heading = clampHeading(294.58), speed = 0,
    proficiency = "Veteran",
})
createOrReuse(CFG.side_blue, "Blue-DBID-3551", {
    side = CFG.side_blue, type = "Ship",
    name = "Blue-DBID-3551", dbid = CFG.dbid_cvn70,
    latitude = 21.4200, longitude = 130.1713,
    heading = clampHeading(293.16), speed = 0,
    proficiency = "Veteran",
})

-- ============================================================
-- 创建红方单位
-- ============================================================
info("创建红方单位...")
createOrReuse(CFG.side_red, "Red-052D-1", {
    side = CFG.side_red, type = "Ship",
    name = "Red-052D-1", dbid = CFG.dbid_052d_nj,
    latitude = 21.1437, longitude = 123.451,
    heading = clampHeading(115), speed = 20,
    proficiency = "Veteran",
})
createOrReuse(CFG.side_red, "Red-052D-2", {
    side = CFG.side_red, type = "Ship",
    name = "Red-052D-2", dbid = CFG.dbid_052d_xy,
    latitude = 18.2035, longitude = 123.988,
    heading = clampHeading(50), speed = 20,
    proficiency = "Veteran",
})
createOrReuse(CFG.side_red, "Red-055-1", {
    side = CFG.side_red, type = "Ship",
    name = "Red-055-1", dbid = CFG.dbid_055_nc,
    latitude = 24.8324, longitude = 128.583,
    heading = clampHeading(135), speed = 20,
    proficiency = "Veteran",
})

-- ============================================================
-- 设置红方 Radar=Active
-- ============================================================
info("设置红方 Radar=Active...")
for _, name in ipairs({ "Red-052D-1", "Red-052D-2", "Red-055-1" }) do
    local u = findUnit(CFG.side_red, name)
    if u and u.guid then
        pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active")
    end
end
ok("红方 Radar=Active")

-- ============================================================
-- 红方全知（God's Eye View）—— 跳过探测，直接获得全部敌方 contact
-- ============================================================
info("设置红方为全知(OMNI)...")
do
    _errnum_ = 0
    local a = ScenEdit_SetSideOptions({ side = CFG.side_red, awareness = "OMNI" })
    if (_errnum_ or 0) == 0 then
        ok("红方 awareness = " .. tostring(a and a.awareness or "OMNI"))
    else
        warn("设置全知失败: " .. tostring(_errmsg_))
    end
end

-- ============================================================
-- 清空红方待发弹（重装前归零）
-- ============================================================
info("清空红方待发弹...")
for _, name in ipairs({ "Red-052D-1", "Red-052D-2", "Red-055-1" }) do
    clearUnitWeapons(CFG.side_red, name)
end

-- ============================================================
-- 弹药补给
-- ============================================================
info("弹药补给...")

local AMMO = {
    { unitname = "Red-052D-1", wpn_dbid = CFG.dbid_yj21, number = 16 },
    { unitname = "Red-052D-2", wpn_dbid = CFG.dbid_yj18, number = 16 },
    { unitname = "Red-052D-2", wpn_dbid = CFG.dbid_yj21, number = 16 },
    { unitname = "Red-055-1",  wpn_dbid = CFG.dbid_yj18, number = 32 },
}

for _, a in ipairs(AMMO) do
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = CFG.side_red, unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, number = a.number,
    })
    if ok2 then
        ok("+ " .. a.number .. "x [" .. a.wpn_dbid .. "] → " .. a.unitname)
    else
        warn("弹药补给失败: " .. a.unitname .. " (dbid=" .. a.wpn_dbid .. ")")
    end
end

-- ============================================================
-- 自检：打印 Red-055-1 最终实际待发弹（应只剩 YJ-18(2868)=32）
-- ============================================================
info("自检 Red-055-1 待发弹...")
do
    local u = ScenEdit_GetUnit({ side = CFG.side_red, name = "Red-055-1" })
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
        ok("Red-055-1 待发弹合计 = " .. total)
    end
end

-- ============================================================
-- 攻击指令：手动发射指定弹种/数量打击蓝方目标
-- 注意：定义为【全局函数】，以便被定时触发器里的 LuaScript 调用
--       侧名从 CFG 注入（本场景为中文“红方/蓝方”），不可硬编码
-- 依赖红方全知(OMNI)以确保能取到目标 contact
-- ============================================================
_SIDE_RED  = CFG.side_red       -- 暴露为全局，供触发器脚本读取
_SIDE_BLUE = CFG.side_blue

function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({ side = _SIDE_RED,  name = attackerName })
    local tgt = ScenEdit_GetUnit({ side = _SIDE_BLUE, name = targetName })

    if not (atk and atk.guid) then
        print("[CMO] [ERROR] 攻击失败: 找不到攻击方 " .. attackerName); return false
    end
    if not (tgt and tgt.guid) then
        print("[CMO] [ERROR] 攻击失败: 找不到目标 " .. targetName); return false
    end

    -- 在红方 contact 列表里找指向该目标的 contact
    local contactGuid
    local pok, cs = pcall(ScenEdit_GetContacts, { side = _SIDE_RED })
    if pok and type(cs) == "table" then
        for _, c in ipairs(cs) do
            if c.actualunitid == tgt.guid then contactGuid = c.guid; break end
        end
    end

    local r
    if contactGuid then
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, contactGuid,
                { mode = "1", weapon = wpnDbid, qty = qty })
        print(("[CMO] [INFO] %s → contact 方式攻击 %s"):format(attackerName, targetName))
    else
        print(("[CMO] [WARNING] %s 未取到 %s 的 contact，改用 BOL 朝坐标发射"):format(attackerName, targetName))
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, "BOL",
                { latitude = tgt.latitude, longitude = tgt.longitude,
                  mode = 1, weapon = wpnDbid, qty = qty })
    end

    if r then
        print(("[CMO] [SUCCESS] %s 发射 %d 枚 [%d] → %s"):format(attackerName, qty, wpnDbid, targetName))
        return true
    else
        print(("[CMO] [ERROR] %s 攻击 %s 失败 (errmsg=%s)"):format(attackerName, targetName, tostring(_errmsg_)))
        return false
    end
end

-- ============================================================
-- 定时齐射调度（TOT 近似同时到达）
-- 每艘船【一枚一枚】发射：改 startDelay(首发延迟) 与 interval(枚间隔) 控制每枚时刻
-- 时间基准 = 你粘贴脚本执行时的当前仿真时间
-- 注意：延迟发射靠 Time 触发器，需游戏【推进时间】才会触发（暂停不行）
-- ============================================================

-- 把“当前仿真时间 + addSeconds”转成 CMO 事件可用的 DotNet ticks 字符串
local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    local offSet = 62135596801            -- 0001-01-01 到 1970-01-01 的秒数
    local newTime = (t + offSet + addSeconds) * 10000000
    return string.format("%.0f", newTime)
end

-- 齐射清单：{ 攻击方, 目标, 弹种dbid, 总枚数, 首发延迟(秒), 枚间隔(秒) }
-- 第 k 枚发射时刻 = 首发延迟 + (k-1) * 枚间隔；首发延迟=0 则第1枚立即发
local SALVO = {
    { "Red-052D-2", "Blue-DBID-3551", CFG.dbid_yj21, 6,  0,  5 },
    { "Red-055-1",  "Blue-DBID-2862", CFG.dbid_yj18, 7,  37, 5 },
    { "Red-052D-1", "DDG 113",        CFG.dbid_yj21, 4,  74, 5 },
}

info("调度逐枚定时发射...")
local nowT = ScenEdit_CurrentTime()
info("当前仿真时间(基准0) = " .. tostring(nowT))

-- 调度单枚发射：delay<=0 立即发 1 枚；否则建 Time 触发器到点发 1 枚
local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    if delay <= 0 then
        fireAt(atkName, tgtName, wpn, 1)
        return true
    end
    local evName = "Event " .. tag
    local trName = "Trig " .. tag
    local acName = "Act " .. tag
    local fireTime = totTicks(delay)
    local script =
        ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    _errnum_ = 0
    local okTr = pcall(ScenEdit_SetTrigger, { mode="add", type="Time", name=trName, Time=fireTime })
    local okAc = pcall(ScenEdit_SetAction,  { mode="add", type="LuaScript", name=acName, ScriptText=script })
    local okEv = pcall(ScenEdit_SetEvent, evName, { mode="add", IsActive=true, IsRepeatable=false })
    pcall(ScenEdit_SetEventTrigger, evName, { mode="add", name=trName })
    pcall(ScenEdit_SetEventAction,  evName, { mode="add", name=acName })
    return okTr and okAc and okEv
end

local sched, failc = 0, 0
for i, s in ipairs(SALVO) do
    local atkName, tgtName, wpn, qty, startDelay, interval = s[1], s[2], s[3], s[4], s[5], s[6]
    for k = 1, qty do
        local delay = startDelay + (k - 1) * interval
        local tag = "TOT_" .. i .. "_" .. k .. "_" .. tostring(nowT)
        if scheduleOne(atkName, tgtName, wpn, delay, tag) then
            sched = sched + 1
            ok(("调度 %s 第%d枚 @%ds -> %s"):format(atkName, k, delay, tgtName))
        else
            failc = failc + 1
            err(("调度失败 %s 第%d枚 @%ds (errmsg=%s)"):format(atkName, k, delay, tostring(_errmsg_)))
        end
    end
end
ok(("逐枚调度完成：成功 %d，失败 %d"):format(sched, failc))

ok("脚本执行完成。延迟的弹需游戏推进时间后才会逐枚发射。")
