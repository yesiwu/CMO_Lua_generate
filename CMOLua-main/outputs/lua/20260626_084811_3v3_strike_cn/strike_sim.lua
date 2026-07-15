-- ============================================================
-- CMO Lua 打击仿真脚本
-- 场景：红方 3 舰 vs 蓝方 3 舰
-- 红方全知，contact 优先打击 → BOL 兜底
-- ============================================================

-- ============================================================
-- 【配置区】
-- ============================================================
local CFG_SIDE_RED  = "红方"
local CFG_SIDE_BLUE = "蓝方"

-- 蓝方单位清单（名称 / DBID / 经度 / 纬度 / 朝向）
local BLUE_UNITS = {
    { name = "蓝方-DDG113", dbid = 2866, lon = 129.9125, lat = 21.5419, heading = 294.05 },
    { name = "蓝方-CG59",   dbid = 2862, lon = 130.1791, lat = 21.6100, heading = 294.58 },
    { name = "蓝方-CV70",   dbid = 3551, lon = 130.1713, lat = 21.4200, heading = 293.16 },
}

-- 红方装弹清单（启动时装填，完成后剩余库存）
-- { 单元名, 武器DBID, 数量 }
local AMMO = {
    -- 052D-1：YJ-21 x16
    { "红方-052D-1", 4058, 16, "YJ-21" },
    -- 052D-2：YJ-18 x16 + YJ-21 x16
    { "红方-052D-2", 2868, 16, "YJ-18" },
    { "红方-052D-2", 4058, 16, "YJ-21" },
    -- 055：YJ-18 x32
    { "红方-055-1",  2868, 32, "YJ-18" },
}

-- 打击清单：{ 攻击方, 目标名, 武器DBID, 数量 }
local STRIKE = {
    { "红方-052D-1", "蓝方-DDG113", 4058, 4 },   -- 052D-1 → DDG113   4x YJ-21
    { "红方-052D-2", "蓝方-CV70",   4058, 6 },   -- 052D-2 → CVN70    6x YJ-21
    { "红方-055-1",  "蓝方-CG59",   2868, 7 },   -- 055     → CG59    7x YJ-18
}

-- ============================================================
-- 【通用函数】
-- ============================================================
local LOG = "[CMO]"

-- ---- 装弹（不清空，用于初始化或补充装填）----
local function reloadWeapon(side, name, dbid, qty)
    _errnum_ = 0
    ScenEdit_AddReloadsToUnit({ side = side, unitname = name, wpn_dbid = dbid, number = qty })
    if (_errnum_ or 0) == 0 then
        print(LOG .. " [OK] +" .. qty .. "x [" .. dbid .. "] → " .. name)
    else
        print(LOG .. " [ERROR] 装弹失败 " .. name .. " (dbid=" .. dbid .. ")")
    end
end

-- ---- 清空指定单元全部待发弹 ----
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then print(LOG .. " [WARNING] 清空: 找不到 " .. name); return end
    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs+1] = { dbid = w.wpn_dbid, num = cur, mountid = m.mount_guid }
            end
        end
    end
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({ guid = u.guid, wpn_dbid = j.dbid, mount_guid = j.mountid, number = j.num, remove = true })
        if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
    end
    print(LOG .. " [OK] " .. name .. " 清空 " .. done .. " 条 (失败 " .. fail .. ")")
end

-- ---- 自检：打印某舰待发弹 ----
local function dumpAmmo(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u then print(LOG .. " [WARNING] 自检: 找不到 " .. name); return end
    local total = 0
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then
                print(LOG .. " [INFO]   " .. name .. " dbid=" .. tostring(w.wpn_dbid) .. " 数量=" .. c)
                total = total + c
            end
        end
    end
    print(LOG .. " [INFO] " .. name .. " 合计=" .. total)
end

-- ---- 打击：contact 优先 → BOL 兜底 ----
local function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({ side = CFG_SIDE_RED, name = attackerName })
    local tgt = ScenEdit_GetUnit({ side = CFG_SIDE_BLUE, name = targetName })

    if not (atk and atk.guid) then
        print(LOG .. " [ERROR] 找不到攻击方 " .. attackerName); return false end
    if not (tgt and tgt.guid) then
        print(LOG .. " [ERROR] 找不到目标 " .. targetName); return false end

    -- 优先：从 contact 列表中找目标
    local contactGuid
    local pok, cs = pcall(ScenEdit_GetContacts, { side = CFG_SIDE_RED })
    if pok and type(cs) == "table" then
        for _, c in ipairs(cs) do
            if c.actualunitid == tgt.guid then contactGuid = c.guid; break end
        end
    end

    _errnum_ = 0
    local r
    if contactGuid then
        r = ScenEdit_AttackContact(atk.guid, contactGuid, { mode = 1, weapon = wpnDbid, qty = qty })
        print(LOG .. " [INFO] " .. attackerName .. " → contact 攻击 " .. targetName)
    else
        print(LOG .. " [WARNING] " .. attackerName .. " 未探测到 " .. targetName .. "，改用 BOL 朝坐标发射")
        r = ScenEdit_AttackContact(atk.guid, "BOL", {
                latitude  = tgt.latitude,
                longitude = tgt.longitude,
                mode      = 1,
                weapon    = wpnDbid,
                qty       = qty,
            })
    end

    if r and (_errnum_ or 0) == 0 then
        print(LOG .. " [OK] " .. attackerName .. " 发射 " .. qty .. "x ["
            .. wpnDbid .. "] → " .. targetName)
        return true
    else
        print(LOG .. " [ERROR] " .. attackerName .. " 攻击 " .. targetName
            .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ============================================================
-- 【部署阶段】：创建蓝方单位 + 红方单位
-- ============================================================

print(LOG .. " === 部署蓝方单位 ===")
for _, u in ipairs(BLUE_UNITS) do
    _errnum_ = 0
    ScenEdit_AddUnit({
        side = CFG_SIDE_BLUE, type = "Ship", name = u.name,
        dbid = u.dbid, latitude = u.lat, longitude = u.lon, heading = u.heading,
        headingtype = 1,
    })
    if (_errnum_ or 0) == 0 then
        print(LOG .. " [OK] " .. u.name .. " (DBID=" .. u.dbid .. ") @ ("
            .. u.lon .. ", " .. u.lat .. ") H=" .. u.heading)
    else
        print(LOG .. " [ERROR] 创建蓝方 " .. u.name .. " 失败")
    end
end

print(LOG .. " === 部署红方单位 ===")
local RED_UNITS = {
    { name = "红方-052D-1", dbid = 2296, lon = 123.451,  lat = 21.1437, heading = 115.0 },
    { name = "红方-052D-2", dbid = 2296, lon = 123.988,  lat = 18.2035, heading = 50.0  },
    { name = "红方-055-1",  dbid = 2834, lon = 128.583,  lat = 24.8324, heading = 135.0 },
}
for _, u in ipairs(RED_UNITS) do
    _errnum_ = 0
    ScenEdit_AddUnit({
        side = CFG_SIDE_RED, type = "Ship", name = u.name,
        dbid = u.dbid, latitude = u.lat, longitude = u.lon, heading = u.heading,
        headingtype = 1,
    })
    if (_errnum_ or 0) == 0 then
        print(LOG .. " [OK] " .. u.name .. " (DBID=" .. u.dbid .. ") @ ("
            .. u.lon .. ", " .. u.lat .. ") H=" .. u.heading)
    else
        print(LOG .. " [ERROR] 创建红方 " .. u.name .. " 失败")
    end
end

-- ============================================================
-- 【装弹阶段】：装填红方弹药
-- ============================================================
print(LOG .. " === 装填红方弹药 ===")
for _, a in ipairs(AMMO) do
    reloadWeapon(CFG_SIDE_RED, a[1], a[2], a[3])
end

-- ============================================================
-- 【打击前自检】
-- ============================================================
print(LOG .. " === 打击前自检 ===")
local redNames = {}
for _, a in ipairs(AMMO) do redNames[a[1]] = true end
for name, _ in pairs(redNames) do dumpAmmo(CFG_SIDE_RED, name) end

-- ============================================================
-- 【打击阶段】：contact 优先 → BOL 兜底
-- ============================================================
print(LOG .. " === 下达打击指令 ===")
for _, s in ipairs(STRIKE) do
    fireAt(s[1], s[2], s[3], s[4])
end
print(LOG .. " === 打击指令下达完毕 ===")

-- ============================================================
-- 【打击后自检】：检查剩余待发弹
-- ============================================================
print(LOG .. " === 打击后自检 ===")
for name, _ in pairs(redNames) do dumpAmmo(CFG_SIDE_RED, name) end
print(LOG .. " === 仿真结束 ===")
