-- ==========================================================================
-- reload.lua — STEP 3/4 — 消耗与诱歼作战方案
--   按 manifest.AMMO 列表给单位装弹
--   注意: 不指定 mount_guid — 让 CMO 自动选 mount (不同 Mount 支持不同武器)
--
-- 自审:
--   [x] 全部从 manifest.AMMO 引用 (单位名/wpn_dbid/number)
--   [x] pcall 包装
--   [x] 装弹前不清弹 (main.lua 之后调用, 没有默认武器可装)
-- ==========================================================================

print("[CMO] [INFO] ============ reload.lua 开始 ============")

dofile("manifest.lua")

local function log(level, msg) print("[CMO] [" .. level .. "] " .. tostring(msg)) end
local function info(msg)  log("INFO",    msg) end
local function warn(msg)  log("WARNING", msg) end
local function ok(msg)    log("SUCCESS", msg) end

local function reloadUnit(unitname, wpn_dbid, number)
    -- 查找 unit
    local side
    for _, u in pairs(UNITS) do
        if u.name == unitname then side = u.side; break end
    end
    if not side then
        warn("manifest 没找到单位: " .. unitname)
        return false
    end

    local u = ScenEdit_GetUnit({ side = side, name = unitname })
    if not (u and u.guid) then
        warn("ScenEdit_GetUnit 找不到 " .. side .. "/" .. unitname)
        return false
    end

    -- 检查现有 mount 武器中是否有 wpn_dbid, 累加 number
    -- 否则走全单位 AddReloadsToUnit (CMO 自动找合适 mount)
    local existing = 0
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            if tonumber(w.wpn_dbid) == tonumber(wpn_dbid) then
                existing = existing + (tonumber(w.wpn_current) or 0)
            end
        end
    end

    if existing > 0 then
        info(string.format("%s 已有 %d 枚 dbid=%d, 追加 %d",
            unitname, existing, wpn_dbid, number))
    end

    -- pcall 包装
    _errnum_ = 0
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side      = side,
        unitname  = unitname,
        wpn_dbid  = wpn_dbid,
        number    = number,
    })
    if ok2 and (_errnum_ or 0) == 0 then
        ok(string.format("+ %d x [dbid=%d] -> %s", number, wpn_dbid, unitname))
        return true
    else
        warn(string.format("装弹失败 %s (errmsg=%s)", unitname, tostring(_errmsg_)))
        return false
    end
end

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

-- ==========================================================================
-- 装弹: AMMO 列表
-- ==========================================================================
print()
print("[CMO] ---------- 装弹 " .. #AMMO .. " 个单位 ----------")

local reloaded = 0
for i, a in ipairs(AMMO) do
    if reloadUnit(a.unitname, a.wpn_dbid, a.number) then
        reloaded = reloaded + 1
    end
end

-- 自检
print()
print("[CMO] ---------- 装弹自检 ----------")
for _, a in ipairs(AMMO) do
    local u = UNITS[a.unitname]
    if u then dumpAmmo(u.side, u.name) end
end

if reloaded == #AMMO then
    ok(string.format("STEP 3 完成: %d/%d 单位装弹成功", reloaded, #AMMO))
    print("[CMO] [INFO] 下一步: 跑 attack.lua (真延时打击)")
else
    warn(string.format("STEP 3 部分完成: %d/%d 单位装弹", reloaded, #AMMO))
end