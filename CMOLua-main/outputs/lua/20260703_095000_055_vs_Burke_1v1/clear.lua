-- ============================================================
-- 清弹脚本：清空055待发弹
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 配置区 ----------
local SIDE_RED = "红方"
local CLEAR_LIST = { "055-南昌舰" }  -- 必须与main.lua中的name完全一致

-- ---------- 清弹函数 ----------
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("clearUnitWeapons: 找不到 " .. side .. "/" .. name)
        return false
    end
    -- 快照所有mount中cur>0的武器（边减边遍历原表不安全）
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
    -- 逐条把数量减到0（保留记录）
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
    ok(name .. ": 减载归零 " .. done .. " 条 (失败 " .. fail .. ")")
    return fail == 0
end

-- ---------- 装弹后自检 ----------
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
    if total == 0 then
        ok(name .. " 待发弹已清空 (合计 = 0)")
    else
        warn(name .. " 待发弹合计 = " .. total)
    end
end

-- ---------- 执行：先清空 ----------
info("=== 清空待发弹 ===")
for _, name in ipairs(CLEAR_LIST) do 
    clearUnitWeapons(SIDE_RED, name) 
end

-- ---------- 执行：清空后自检 ----------
info("=== 清空后自检 ===")
for _, name in ipairs(CLEAR_LIST) do dumpAmmo(SIDE_RED, name) end

info("=== 清弹完成 ===")
