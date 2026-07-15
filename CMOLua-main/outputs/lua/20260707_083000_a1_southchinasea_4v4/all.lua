-- ============================================================
-- all.lua — 南海 4V4 YJ-18 联合反舰打击（单文件四阶段执行）
-- 把 main.lua / clear.lua / reload.lua / attack.lua 合并为单脚本
-- 4V4：2×055 + 2×052D（红方） vs 2×DDG-113 + CVN-70 + CG-59（蓝方）
-- 在 CMO Console (Alt+F9) 一次执行即可完成全部流程
-- ============================================================

print("===== all.lua START =====")

-- ============================================================
-- PART 1: manifest 嵌入（v2.0 单一数据源）
-- ============================================================
print("\n===== PART 1: 加载 manifest =====")

SCENARIO = {
    title       = "南海 4V4 YJ-18 反舰饱和打击",
    location    = "南海",
    start_time  = "2026-07-07 08:30:00",
    duration    = "1小时",
    sides       = { "红方", "蓝方" },
    red_skill   = "OMNI",
    contact_settle_delay = 15,
}

WEAPONS = {
    { dbid=2868, name="YJ-18 [3M54E Klub Copy]", category="Anti-ship missile", default_quantity=8, loadout_verified=true },
}

UNITS = {
    ["Red-055-1"] = { side="红方", name="Red-055-1", type="Ship", dbid=3883,
        latitude=18.50, longitude=113.00, heading=180, speed=18, proficiency="Veteran",
        autodetectable=false, dbid_verified=true, role="055 主力突击 DDG-113 #1" },
    ["Red-055-2"] = { side="红方", name="Red-055-2", type="Ship", dbid=3883,
        latitude=18.60, longitude=113.10, heading=180, speed=18, proficiency="Veteran",
        autodetectable=false, dbid_verified=true, role="055 主力突击 DDG-113 #2" },
    ["Red-052D-1"] = { side="红方", name="Red-052D-1", type="Ship", dbid=2296,
        latitude=18.40, longitude=113.20, heading=180, speed=18, proficiency="Veteran",
        autodetectable=false, dbid_verified=true, role="052D-1 突击 CVN-70" },
    ["Red-052D-2"] = { side="红方", name="Red-052D-2", type="Ship", dbid=3586,
        latitude=18.70, longitude=113.20, heading=180, speed=18, proficiency="Veteran",
        autodetectable=false, dbid_verified=true, role="052D-2 突击 CG-59" },
    ["Blue-DDG113-1"] = { side="蓝方", name="Blue-DDG113-1", type="Ship", dbid=4299,
        latitude=-0.50, longitude=105.50, heading=0, speed=0, proficiency="Veteran",
        autodetectable=true, dbid_verified=true, role="伯克 IIA 驱逐舰 #1" },
    ["Blue-DDG113-2"] = { side="蓝方", name="Blue-DDG113-2", type="Ship", dbid=4299,
        latitude=-0.40, longitude=105.80, heading=0, speed=0, proficiency="Veteran",
        autodetectable=true, dbid_verified=true, role="伯克 IIA 驱逐舰 #2" },
    ["Blue-CVN70"] = { side="蓝方", name="Blue-CVN70", type="Ship", dbid=3551,
        latitude=-0.90, longitude=106.11, heading=0, speed=0, proficiency="Veteran",
        autodetectable=true, dbid_verified=true, role="航母（核心目标）" },
    ["Blue-CG59"] = { side="蓝方", name="Blue-CG59", type="Ship", dbid=2862,
        latitude=-0.66, longitude=105.95, heading=0, speed=0, proficiency="Veteran",
        autodetectable=true, dbid_verified=true, role="宙斯盾巡洋舰" },
}

CLEAR_LIST = { "Red-055-1", "Red-055-2", "Red-052D-1", "Red-052D-2" }

AMMO = {
    { unitname="Red-055-1",  wpn_dbid=2868, number=16 },
    { unitname="Red-055-2",  wpn_dbid=2868, number=16 },
    { unitname="Red-052D-1", wpn_dbid=2868, number=16 },
    { unitname="Red-052D-2", wpn_dbid=2868, number=10 },
}

STRIKE = {
    { attacker="Red-055-1",  target="Blue-DDG113-1", weapon_dbid=2868, quantity=13, startDelay=0, interval=1, intent="055-1 突击 DDG-113-1" },
    { attacker="Red-055-2",  target="Blue-DDG113-2", weapon_dbid=2868, quantity=13, startDelay=2, interval=1, intent="055-2 突击 DDG-113-2" },
    { attacker="Red-052D-1", target="Blue-CVN70",   weapon_dbid=2868, quantity=8,  startDelay=5, interval=1, intent="052D-1 突击 CVN-70" },
    { attacker="Red-052D-2", target="Blue-CG59",    weapon_dbid=2868, quantity=5,  startDelay=8, interval=1, intent="052D-2 突击 CG-59" },
}

-- 弹药自检
local function checkAmmoBalance()
    local ammoByUnit, strikeByUnit = {}, {}
    for _, a in ipairs(AMMO) do ammoByUnit[a.unitname] = (ammoByUnit[a.unitname] or 0) + a.number end
    for _, s in ipairs(STRIKE) do strikeByUnit[s.attacker] = (strikeByUnit[s.attacker] or 0) + s.quantity end
    local all_ok = true
    for unit, totalStrike in pairs(strikeByUnit) do
        local totalAmmo = ammoByUnit[unit] or 0
        if totalAmmo < totalStrike then
            print(("[manifest] 弹药不足! %s 装弹 %d 但 STRIKE 需要 %d"):format(unit, totalAmmo, totalStrike))
            all_ok = false
        else
            print(("[manifest] %s 装弹=%d 打击=%d 余=%d"):format(unit, totalAmmo, totalStrike, totalAmmo - totalStrike))
        end
    end
    return all_ok
end

local function countKeys(t) local n=0 for _ in pairs(t) do n=n+1 end return n end

if not checkAmmoBalance() then error("[manifest] 弹药预算不通过") end
print(("[manifest] 校验通过: %d 单位, %d 装弹项, %d 打击项"):format(countKeys(UNITS), #AMMO, #STRIKE))

-- ============================================================
-- 全局配置（事件沙箱可见）
-- ============================================================
_SIDE_RED             = "红方"
_SIDE_BLUE            = "蓝方"
_WPN_YJ18             = 2868
_CONTACT_SETTLE_DELAY = 15
_LOG_PREFIX           = "[CMO]"

-- ============================================================
-- 工具函数
-- ============================================================
local function sameGuid(a, b) return a and b and tostring(a):lower() == tostring(b):lower() end
local function info(msg) print(_LOG_PREFIX .. " [INFO] "  .. msg) end
local function warn(msg) print(_LOG_PREFIX .. " [WARN] "  .. msg) end
local function ok(msg)   print(_LOG_PREFIX .. " [OK] "    .. msg) end
local function err(msg)  print(_LOG_PREFIX .. " [ERROR] " .. msg) end

local function addContact(dst, seen, c)
    if type(c) ~= "table" then return end
    local cg = c.guid or c.Guid
    if not cg then return end
    local key = tostring(cg)
    if seen[key] then return end
    seen[key] = true
    dst[#dst+1] = c
end
local function collectContactsFromTable(dst, seen, t, depth)
    if type(t) ~= "table" or depth > 5 then return end
    addContact(dst, seen, t)
    for _, v in pairs(t) do
        if type(v) == "table" then collectContactsFromTable(dst, seen, v, depth+1) end
    end
end
local function collectContacts(sideName)
    local out, seen = {}, {}
    local ok2, r = pcall(ScenEdit_GetContacts, { side = sideName })
    if ok2 and type(r) == "table" then collectContactsFromTable(out, seen, r, 0) end
    local ok3, s = pcall(VP_GetSide, { Side = sideName })
    if ok3 and s and type(s.contacts) == "table" then collectContactsFromTable(out, seen, s.contacts, 0) end
    return out
end
local function contactName(c) return tostring(c.name or c.Name or c.actualunitname or c.actualUnitName or "") end

local function findContactForTarget(sideName, tgt, tgtName)
    if not (tgt and tgt.guid) then return nil end
    pcall(ScenEdit_SetSideOptions, { side = sideName, awareness = "OMNI" })
    local cs = collectContacts(sideName)
    for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        if cg and (
            sameGuid(c.actualunitid, tgt.guid)
            or sameGuid(c.actualUnitID, tgt.guid)
            or sameGuid(c.actualunitguid, tgt.guid)
            or sameGuid(c.actualUnitGuid, tgt.guid)
            or sameGuid(c.actualunit, tgt.guid)
            or sameGuid(c.actualUnit, tgt.guid)
            or sameGuid(c.actual_guid, tgt.guid)
            or sameGuid(c.actualGuid, tgt.guid)
        ) then return cg end
    end
    for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        local nm = contactName(c)
        if cg and tgtName and (nm == tgtName or nm:find(tgtName, 1, true)) then return cg end
    end
    return nil
end

function fireAt(attackerName, targetName, wpnDbid, qty)
    local ok2, atk = pcall(ScenEdit_GetUnit, { side = _SIDE_RED, name = attackerName })
    local ok3, tgt = pcall(ScenEdit_GetUnit, { side = _SIDE_BLUE, name = targetName })
    if not ok2 or not atk or not atk.guid then err("找不到攻击方 "..attackerName) return false end
    if not ok3 or not tgt or not tgt.guid then err("找不到目标 "..targetName) return false end

    pcall(ScenEdit_SetUnit, { guid = tgt.guid, autodetectable = true })

    local contactGuid
    for attempt = 1, 3 do
        contactGuid = findContactForTarget(_SIDE_RED, tgt, targetName)
        if contactGuid then break end
        if attempt < 3 then warn(("Attempt %d/3: 无 contact，2 秒后重试"):format(attempt)) end
    end

    local r
    if contactGuid then
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, contactGuid, { mode="1", weapon=wpnDbid, qty=qty })
        info(("%s -> CONTACT 攻击 %s"):format(attackerName, targetName))
    else
        _errnum_ = 0
        r = ScenEdit_AttackContact(atk.guid, tgt.guid, { mode="1", weapon=wpnDbid, qty=qty })
        warn(("%s -> UNIT-GUID 攻击 %s (OMNI 降级)"):format(attackerName, targetName))
    end

    if r then
        ok(("%s 发射 %d × [%d] -> %s"):format(attackerName, qty, wpnDbid, targetName))
        return true
    else
        err(("%s 攻击 %s 失败: %s"):format(attackerName, targetName, tostring(_errmsg_)))
        return false
    end
end

local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    local offSet = 62135596801
    return string.format("%.0f", (t + offSet + addSeconds) * 1e7)
end

local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    delay = delay + _CONTACT_SETTLE_DELAY
    local stamp = tostring(ScenEdit_CurrentTime())
    tag = tag .. "_" .. stamp
    local evName = "Event " .. tag
    local trName = "Trig "  .. tag
    local acName = "Act "   .. tag
    local fireTime = totTicks(delay)
    local script =
        ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    pcall(ScenEdit_SetTrigger, { mode="add", type="Time", name=trName, Time=fireTime })
    pcall(ScenEdit_SetAction,  { mode="add", type="LuaScript", name=acName, ScriptText=script })
    pcall(ScenEdit_SetEvent,   evName, { mode="add", IsActive=true, IsRepeatable=false })
    pcall(ScenEdit_SetEventTrigger, evName, { mode="add", name=trName })
    pcall(ScenEdit_SetEventAction,  evName, { mode="add", name=acName })
    return true
end

-- ============================================================
-- 工具：单位已存在 / 添加 / 清弹 / dump
-- ============================================================
local function unitExists(side, name)
    local ok2, u = pcall(ScenEdit_GetUnit, { side = side, name = name })
    return ok2 and u and u.guid
end

local function safeAddUnit(spec)
    if unitExists(spec.side, spec.name) then
        warn(("单位已存在，跳过: %s/%s"):format(spec.side, spec.name))
        return ScenEdit_GetUnit({ side = spec.side, name = spec.name })
    end
    local args = {
        side=spec.side, type=spec.type, name=spec.name, dbid=spec.dbid,
        latitude=spec.latitude, longitude=spec.longitude,
        heading=spec.heading, speed=spec.speed, proficiency=spec.proficiency,
        autodetectable=spec.autodetectable,
    }
    _errnum_ = 0
    local ok2, u = pcall(ScenEdit_AddUnit, args)
    if not ok2 or not u or not u.guid then
        err(("AddUnit 失败: %s/%s dbid=%s err=%s"):format(
            spec.side, spec.name, tostring(spec.dbid), tostring(_errmsg_)))
        return nil
    end
    pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = spec.autodetectable })
    ok(("创建: %s/%s dbid=%s"):format(spec.side, spec.name, tostring(spec.dbid)))
    return u
end

local function clearUnitWeapons(side, name)
    local ok2, u = pcall(ScenEdit_GetUnit, { side = side, name = name })
    if not ok2 or not u or not u.guid then warn("找不到单位 "..side.."/"..name) return false end
    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then jobs[#jobs+1] = { dbid=w.wpn_dbid, num=cur, mountid=m.mount_guid } end
        end
    end
    if #jobs == 0 then return true end
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        local ok3 = pcall(ScenEdit_AddReloadsToUnit, {
            guid=u.guid, wpn_dbid=j.dbid, mount_guid=j.mountid, number=j.num, remove=true,
        })
        if ok3 and (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
    end
    ok(("%s: 减载归零 %d (失败 %d)"):format(name, done, fail))
    return fail == 0
end

local function dumpAmmo(side, name)
    local ok2, u = pcall(ScenEdit_GetUnit, { side = side, name = name })
    if not ok2 or not u then return 0 end
    local total = 0
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then total = total + c end
        end
    end
    info(("%s 待发弹合计 = %d"):format(name, total))
    return total
end

-- ============================================================
-- PART 2: 创建红蓝方单位
-- ============================================================
print("\n===== PART 2: 创建单位 =====")

pcall(ScenEdit_AddSide, { name = "红方", color = "255,0,0" })
pcall(ScenEdit_AddSide, { name = "蓝方", color = "0,0,255" })
ok("阵营已就绪")

pcall(ScenEdit_SetSideOptions, { side = "红方", awareness = "OMNI" })
ok("红方 awareness = OMNI")

pcall(ScenEdit_SetDoctrine, { side = "蓝方" }, {
    weapon_control_status_air=2, weapon_control_status_surface=2, weapon_control_status_subsurface=2,
})
pcall(ScenEdit_SetDoctrine, { side = "红方" }, {
    weapon_control_status_air=0, weapon_control_status_surface=0, weapon_control_status_subsurface=0,
})
ok("Doctrine 已设置（红方 Free，蓝方 Hold）")

pcall(ScenEdit_SetSidePosture, "红方", "蓝方", "H")
pcall(ScenEdit_SetSidePosture, "蓝方", "红方", "H")
ok("红蓝敌对 (H)")

local createCount = 0
for _, spec in pairs(UNITS) do
    if safeAddUnit(spec) then createCount = createCount + 1 end
end
ok("创建 " .. createCount .. " / " .. countKeys(UNITS) .. " 单位")

-- 蓝方 autodetectable 二次确认 + EMCON 默认开启
for _, spec in pairs(UNITS) do
    if spec.side == "蓝方" then
        local ok2, u = pcall(ScenEdit_GetUnit, { side = spec.side, name = spec.name })
        if ok2 and u and u.guid then
            pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
            pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active;Sonar=Active;OECM=Passive")
        end
    end
end
ok("蓝方 autodetectable=true + EMCON 默认开启")

-- ============================================================
-- PART 3: 清弹
-- ============================================================
print("\n===== PART 3: 清弹 =====")
for _, name in ipairs(CLEAR_LIST) do clearUnitWeapons("红方", name) end
for _, name in ipairs(CLEAR_LIST) do dumpAmmo("红方", name) end

-- ============================================================
-- PART 4: 装弹 (YJ-18)
-- ============================================================
print("\n===== PART 4: 装弹 (YJ-18) =====")
local reloaded = 0
for _, a in ipairs(AMMO) do
    if a.wpn_dbid ~= _WPN_YJ18 then
        warn(("⚠ %s 装填 dbid=%d 非 YJ-18"):format(a.unitname, a.wpn_dbid))
    else
        _errnum_ = 0
        local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
            side="红方", unitname=a.unitname, wpn_dbid=a.wpn_dbid, number=a.number,
        })
        if ok2 and (_errnum_ or 0) == 0 then
            ok(("+ %d × [YJ-18] → %s"):format(a.number, a.unitname))
            reloaded = reloaded + 1
        else
            warn(("× %s 装填失败: %s"):format(a.unitname, tostring(_errmsg_)))
        end
    end
end
ok(("装填成功 %d / %d 项"):format(reloaded, #AMMO))
for _, name in ipairs(CLEAR_LIST) do dumpAmmo("红方", name) end

-- ============================================================
-- PART 5: 真延时 TOT 调度
-- ============================================================
print("\n===== PART 5: 真延时 TOT 调度 =====")

local totalRounds = 0
local totalMissiles = 0
for i, s in ipairs(STRIKE) do
    if s.weapon_dbid ~= _WPN_YJ18 then
        warn(("STRIKE[%d] 武器非 YJ-18 跳过: %s"):format(i, s.intent or ""))
        goto continue
    end
    local ok2 = pcall(ScenEdit_GetUnit, { side = _SIDE_RED, name = s.attacker })
    local ok3 = pcall(ScenEdit_GetUnit, { side = _SIDE_BLUE, name = s.target })
    if not ok2 or not ok3 then
        warn(("STRIKE[%d] 单位不存在: %s -> %s"):format(i, s.attacker, s.target))
        goto continue
    end
    info(("调度 STRIKE[%d] %s -> %s × %d (delay=%ds intent=%s)"):format(
        i, s.attacker, s.target, s.quantity, s.startDelay, s.intent or ""))
    for k = 1, s.quantity do
        local delay = (s.startDelay or 0) + (k - 1) * (s.interval or 1)
        local tag = ("TOT_%d_%d_%s"):format(i, k, (s.intent or ""):gsub("%s+", "_"):sub(1, 30))
        scheduleOne(s.attacker, s.target, s.weapon_dbid, delay, tag)
        totalMissiles = totalMissiles + 1
    end
    totalRounds = totalRounds + 1
    ::continue::
end

ok(("%d 任务 / %d 枚 YJ-18 已调度（+ %d 秒 contact 稳定期）"):format(
    totalRounds, totalMissiles, _CONTACT_SETTLE_DELAY))

print("\n===== all.lua COMPLETE =====")
print("下一步：推进仿真时间（T+0 时第一枚自动开火）")