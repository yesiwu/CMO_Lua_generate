-- ============================================================
-- clear.lua: 清空 055-Nanchang 原有的待发弹
-- 必须在 reload.lua 之前运行
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 配置区 ----------
local SIDE_RED = "红方"

-- 需要清弹的单位（必须与 main.lua 创建时完全一致）
local CLEAR_LIST = {
    "055-Nanchang",
}

-- ---------- 清弹函数 ----------
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
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
                    dbid = w.wpn_dbid,
                    num = cur,
                    mountid = m.mount_guid,
                }
            end
        end
    end

    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({
            guid = u.guid,
            wpn_dbid = j.dbid,
            mount_guid = j.mountid,
            number = j.num,
            remove = true,
        })
        if (_errnum_ or 0) == 0 then
            done = done + 1
        else
            fail = fail + 1
        end
    end

    ok(("%s 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
end

-- ---------- 执行：清空 ----------
info("========================================")
info("清空待发弹")
info("========================================")

for _, name in ipairs(CLEAR_LIST) do
    clearUnitWeapons(SIDE_RED, name)
end

ok("clear.lua 执行完毕")
