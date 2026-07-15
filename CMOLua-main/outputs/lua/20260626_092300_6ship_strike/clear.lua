-- ============================================================
-- clear.lua  — 红方3舰：清空所有待发弹（归0）+ 自检对比
-- 使用方式：在 CMO Lua 控制台执行 clear.lua
-- 注意：仅清空不清空特定弹种，遍历所有 cur>0 的弹全部归0
--       用 AddReloadsToUnit + remove=true 扣减数量，保留挂载格子
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- 工具函数
-- ============================================================
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ============================================================
-- 诊断 dump：打印某舰所有挂位及待发弹（清空前后都用）
-- ============================================================
local function dumpAllAmmo(side, name, label)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u then
        warn("dumpAllAmmo: 找不到 " .. side .. "/" .. name); return
    end
    info("=== " .. name .. " 待发弹 (" .. label .. ") ===")
    local total = 0
    local count = 0
    for i, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            info(("  MOUNT[%d] mount_guid=%s dbid=%s cur=%d"):format(
                i, tostring(m.mount_guid), tostring(w.wpn_dbid), c))
            total = total + c
            if c > 0 then count = count + 1 end
        end
    end
    ok(("%s [%s] 挂位总数=%d 待发>0 的条目=%d 合计=%d"):format(name, label, #(u.mounts or {}), count, total))
end

-- ============================================================
-- 清空函数：遍历所有挂位，将 cur>0 的弹减至 0，保留格子
-- 注意：不能用 remove_weapon 删记录——那会把格子也删掉，
--       导致后续 AddReloadsToUnit 找不到兼容 mount，弹装不回去。
--       这里用 AddReloadsToUnit + remove=true 仅扣减数量，格子保留。
-- ============================================================
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("clearUnitWeapons: 找不到 " .. side .. "/" .. name)
        return false
    end
    -- 快照所有 mount 中 cur>0 的武器（边减边遍历原表不安全）
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

    info("发现 " .. #jobs .. " 条待清空的弹")
    -- 逐条把数量减到 0（保留记录）
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({
            guid = u.guid, wpn_dbid = j.dbid,
            mount_guid = j.mountid, number = j.num, remove = true,
        })
        local ok2 = (_errnum_ or 0) == 0
        info(("  remove dbid=%s num=%d mount=%s => %s"):format(
            tostring(j.dbid), j.num, tostring(j.mountid), ok2 and "OK" or "FAIL"))
        if ok2 then done = done + 1
        else fail = fail + 1 end
    end
    ok(("%s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
end

-- ============================================================
-- 配置区（单位名必须与 main.lua 创建时完全一致）
-- ============================================================
local SIDE_RED = "红方"
local CLEAR_LIST = {
    "Red-052D-Alpha",
    "Red-052D-Beta",
    "Red-055-Alpha",
}

-- ============================================================
-- 执行：先自检清空前状态 → 清空 → 自检清空后状态
-- ============================================================
for _, name in ipairs(CLEAR_LIST) do
    dumpAllAmmo(SIDE_RED, name, "清空前")
    clearUnitWeapons(SIDE_RED, name)
    dumpAllAmmo(SIDE_RED, name, "清空后")
end

ok("clear.lua 执行完毕")
info("下一步：执行 reload.lua 进行装弹")
