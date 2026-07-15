-- ============================================================
-- 055 vs Burke 1v1 场景
-- 红方055打击蓝方伯克利
-- 055装弹16枚YJ-18，发射12枚
-- 地点：南海
-- ============================================================

local LOG_PREFIX = "[CMO]"

local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO", msg) end
local function ok(msg)  log("OK",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end

-- ============================================================
-- 配置区
-- ============================================================

-- 南海坐标
local RED_LAT  = 15.5    -- 055纬度
local RED_LON  = 115.0   -- 055经度
local BLUE_LAT = 15.3    -- 伯克利纬度
local BLUE_LON = 115.3   -- 伯克利经度

-- 055配置
local DBID_055    = 2834
local NAME_055    = "055-Nanchang"
local YJ18_LOAD   = 16    -- 装弹数量
local YJ18_FIRE   = 12    -- 发射数量
local DBID_YJ18   = 2867  -- YJ-18 DBID

-- 伯克利配置
local DBID_BURKE  = 112
local NAME_BURKE  = "DDG-51-Burke"

-- ============================================================
-- 清空待发弹函数
-- ============================================================
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("clearUnitWeapons: 找不到 " .. side .. "/" .. name)
        return false
    end
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
-- 装弹后自检
-- ============================================================
local function dumpAmmo(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u then return end
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
    ok(name .. " 待发弹合计 = " .. total)
end

-- ============================================================
-- 强制蓝方autodetectable（contact攻击前提）
-- ============================================================
local function forceBlueAutodetectable(name)
    local u = ScenEdit_GetUnit({ side = "蓝方", name = name })
    if not (u and u.guid) then return false end
    return pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
end

-- ============================================================
-- 获取contact
-- ============================================================
local function collectContacts(sideName)
    local out, seen = {}, {}
    local calls = {
        function() return ScenEdit_GetContacts({ side = sideName }) end,
        function() return VP_GetSide({ Side = sideName }) end,
    }
    for _, fn in ipairs(calls) do
        local ok2, r = pcall(fn)
        if ok2 and r then
            local cs = r.contacts or r
            if type(cs) == "table" then
                for _, c in ipairs(cs) do
                    local cg = c.guid or c.Guid
                    if cg and not seen[cg] then
                        seen[cg] = true
                        out[#out + 1] = c
                    end
                end
            end
        end
    end
    return out
end

local function findContactForTarget(sideName, tgt, tgtName)
    if not (tgt and tgt.guid) then return nil end
    pcall(ScenEdit_SetSideOptions, { side = sideName, awareness = "OMNI" })
    local cs = collectContacts(sideName)
    for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        if not cg then goto continue end
        local function sameGuid(a, b)
            return a and b and tostring(a):lower() == tostring(b):lower()
        end
        if sameGuid(c.actualunitid, tgt.guid)
            or sameGuid(c.actualUnitID, tgt.guid)
            or sameGuid(c.actualunitguid, tgt.guid)
            or sameGuid(c.actualUnitGuid, tgt.guid)
            or sameGuid(c.actualunit, tgt.guid)
            or sameGuid(c.actualUnit, tgt.guid) then
            info("matched contact for " .. tgtName .. " by GUID: " .. cg)
            return cg
        end
        if (c.name or c.Name or "") == tgtName then
            info("matched contact for " .. tgtName .. " by name: " .. cg)
            return cg
        end
        ::continue::
    end
    return nil
end

-- ============================================================
-- 发射函数
-- ============================================================
local function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({ side = "红方", name = attackerName })
    local tgt = ScenEdit_GetUnit({ side = "蓝方", name = targetName })

    if not (atk and atk.guid) then
        err("找不到攻击方 " .. attackerName); return false end
    if not (tgt and tgt.guid) then
        err("找不到目标 " .. targetName); return false end

    forceBlueAutodetectable(targetName)

    local contactGuid = findContactForTarget("红方", tgt, targetName)

    _errnum_ = 0
    local r
    if contactGuid then
        r = ScenEdit_AttackContact(atk.guid, contactGuid,
            { mode = 1, weapon = wpnDbid, qty = qty })
        info(attackerName .. " → contact 攻击 " .. targetName)
    else
        warn(attackerName .. " 无 contact，降级 BOL 朝坐标发射")
        r = ScenEdit_AttackContact(atk.guid, "BOL", {
            latitude = tgt.latitude, longitude = tgt.longitude,
            mode = 1, weapon = wpnDbid, qty = qty,
        })
    end

    if r and (_errnum_ or 0) == 0 then
        ok(attackerName .. " 发射 " .. qty .. "x [" .. wpnDbid .. "] → " .. targetName)
        return true
    else
        err(attackerName .. " 攻击 " .. targetName .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ============================================================
-- 主流程
-- ============================================================

-- 创建阵营
info("=== 创建阵营 ===")
ScenEdit_AddSide({ name = "红方", color = "255,0,0" })
ScenEdit_AddSide({ name = "蓝方", color = "0,0,255" })
ok("红方/蓝方 创建完成")

-- 设置敌对关系
ScenEdit_SetSidePosture("红方", "蓝方", "H")
ScenEdit_SetSidePosture("蓝方", "红方", "H")

-- 红方全知全能
ScenEdit_SetSideOptions({ side = "红方", awareness = "OMNI" })
ok("红方设为全知全能")

-- 创建055
info("=== 创建红方055 ===")
local u055 = ScenEdit_AddUnit({
    side        = "红方",
    type        = "Ship",
    name        = NAME_055,
    dbid        = DBID_055,
    latitude    = RED_LAT,
    longitude   = RED_LON,
    heading     = 90,
    speed       = 15,
    proficiency = "Veteran",
})
if u055 and u055.guid then
    ScenEdit_SetKeyValue("055_GUID", u055.guid)
    ok("055 创建完成: " .. u055.guid)
else
    err("055 创建失败")
end

-- 创建伯克利
info("=== 创建蓝方伯克利 ===")
local uBurke = ScenEdit_AddUnit({
    side             = "蓝方",
    type             = "Ship",
    name             = NAME_BURKE,
    dbid             = DBID_BURKE,
    latitude         = BLUE_LAT,
    longitude        = BLUE_LON,
    heading          = 270,
    speed            = 12,
    proficiency      = "Veteran",
    autodetectable   = true,  -- 关键：蓝方目标必须可探测
})
if uBurke and uBurke.guid then
    ScenEdit_SetKeyValue("BURKE_GUID", uBurke.guid)
    ok("伯克利创建完成: " .. uBurke.guid)
else
    err("伯克利创建失败")
end

-- 创建后强制设autodetectable（双保险）
info("=== 强制设置伯克利autodetectable ===")
if uBurke and uBurke.guid then
    pcall(ScenEdit_SetUnit, { guid = uBurke.guid, autodetectable = true })
    ok("伯克利autodetectable强制设置完成")
end

-- 清空055待发弹
info("=== 清空055待发弹 ===")
clearUnitWeapons("红方", NAME_055)

-- 装弹16枚YJ-18
info("=== 装弹 ===")
pcall(ScenEdit_AddReloadsToUnit, {
    side     = "红方",
    unitname = NAME_055,
    wpn_dbid = DBID_YJ18,
    number   = YJ18_LOAD,
})
ok("055 装弹 " .. YJ18_LOAD .. "x YJ-18 [" .. DBID_YJ18 .. "]")

-- 装弹自检
info("=== 装弹自检 ===")
dumpAmmo("红方", NAME_055)

-- 发射12枚YJ-18
info("=== 发射打击 ===")
fireAt(NAME_055, NAME_BURKE, DBID_YJ18, YJ18_FIRE)

-- 再次自检
info("=== 发射后自检 ===")
dumpAmmo("红方", NAME_055)

ok("=== 场景初始化完成 ===")
