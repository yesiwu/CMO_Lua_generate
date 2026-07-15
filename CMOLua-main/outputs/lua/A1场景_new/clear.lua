-- ============================================================
-- clear.lua — 清空红方5舰待发弹（归零）
-- 单位名与 main.lua 完全一致
-- ============================================================

Tool_EmulateNoConsole(true)

local LOG = "[CMO]"
local SIDE_RED = "红方"

local function info(msg) print(LOG .. " [INFO] " .. msg) end
local function warn(msg) print(LOG .. " [WARN] " .. msg) end
local function ok(msg)   print(LOG .. " [OK] "   .. msg) end

-- ============================================================
-- 诊断 dump
-- ============================================================
local function dumpAmmo(side, name, label)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u then warn("dump: 找不到 " .. name); return end
    info("=== " .. name .. " (" .. label .. ") ===")
    for i, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then
                info(("  MOUNT[%d] dbid=%s cur=%d"):format(i, tostring(w.wpn_dbid), c))
            end
        end
    end
end

-- ============================================================
-- 清空函数
-- ============================================================
local function clearUnit(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("clearUnit: 找不到 " .. side .. "/" .. name); return false end
    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs + 1] = { dbid = w.wpn_dbid, num = cur, mountid = m.mount_guid }
            end
        end
    end
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({ guid = u.guid, wpn_dbid = j.dbid,
            mount_guid = j.mountid, number = j.num, remove = true })
        if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
    end
    ok(("%s: 清空 %d 条（失败 %d）"):format(name, done, fail))
    return fail == 0
end

-- ============================================================
-- 配置区（单位名与 main.lua 完全一致）
-- ============================================================
local CLEAR_LIST = {
    "Red-052D-1",
    "Red-052D-2",
    "Red-052D-3",
    "Red-055-1",
    "Red-055-2",
}

-- ============================================================
-- 执行
-- ============================================================
ok("=== 清空待发弹 ===")
for _, name in ipairs(CLEAR_LIST) do
    dumpAmmo(SIDE_RED, name, "清空前")
    clearUnit(SIDE_RED, name)
    dumpAmmo(SIDE_RED, name, "清空后")
end
ok("clear.lua 完毕")
info("下一步: reload.lua")
