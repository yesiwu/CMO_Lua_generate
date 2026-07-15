-- ============================================================
-- 清弹脚本: 055清空现有弹药
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 配置区 ----------
local SIDE_RED  = "红方"
local NAME_055  = "055-Nanchang"   -- 必须与 main.lua 一致

-- ---------- 清空函数 ----------
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({side = side, name = name})
    if not u or not u.guid then
        warn("clearUnitWeapons: 找不到 " .. side .. "/" .. name)
        return false
    end
    -- 快照所有 mount 中 cur>0 的武器
    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs + 1] = {
                    dbid   = w.wpn_dbid,
                    num    = cur,
                    mountid = m.mount_guid,
                }
            end
        end
    end
    -- 逐条把数量减到 0（保留记录）
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({
            guid       = u.guid,
            wpn_dbid   = j.dbid,
            mount_guid = j.mountid,
            number     = j.num,
            remove     = true,
        })
        if (_errnum_ or 0) == 0 then done = done + 1
        else fail = fail + 1 end
    end
    ok(("%s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
end

-- ---------- 装弹后自检 ----------
local function dumpAmmo(side, name)
    local u = ScenEdit_GetUnit({side = side, name = name})
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

-- ---------- 执行清空 ----------
info("=== 清空 055 待发弹 ===")
clearUnitWeapons(SIDE_RED, NAME_055)

-- ---------- 清空后自检 ----------
info("=== 清空后自检 ===")
dumpAmmo(SIDE_RED, NAME_055)

ok("清弹完成! 下一步: 运行 reload.lua 装填YJ-18")
