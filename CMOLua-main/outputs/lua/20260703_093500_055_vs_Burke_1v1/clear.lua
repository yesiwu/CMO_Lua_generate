-- ============================================================
-- 055 vs Burke 1v1 场景 - 清弹脚本
-- 功能：清空055舰上所有待发弹
-- 原理：用 AddReloadsToUnit + remove=true 减少数量到0，保留挂载格子
-- ============================================================

local LOG = "[CLEAR]"
local SIDE_RED = "红方"
local UNIT_NAME = "南昌舰"

-- ---------- 日志工具函数 ----------
local function log(level, msg) print(LOG .. " [" .. level .. "] " .. msg) end

-- ---------- 清空待发弹函数 ----------
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({side = side, name = name})
    if not u or not u.guid then
        log("WARN", "clearUnitWeapons: 找不到 " .. side .. "/" .. name)
        return false
    end

    -- 快照所有 mount 中 cur>0 的武器
    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs + 1] = {
                    dbid = w.wpn_dbid, num = cur, mountid = m.mount_guid,
                }
                log("INFO", string.format("  发现: dbid=%s, cur=%d, mount=%s",
                    tostring(w.wpn_dbid), cur, m.mount_guid or "nil"))
            end
        end
    end

    -- 逐条把数量减到 0
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({
            guid = u.guid, wpn_dbid = j.dbid,
            mount_guid = j.mountid, number = j.num, remove = true,
        })
        if (_errnum_ or 0) == 0 then
            done = done + 1
        else
            fail = fail + 1
        end
    end

    log("OK", string.format("%s: 减载归零 %d 条 (失败 %d)", name, done, fail))
    return fail == 0
end

-- ---------- 装弹后自检函数 ----------
local function dumpAmmo(side, name)
    local u = ScenEdit_GetUnit({side = side, name = name})
    if not u then return end
    local total = 0
    for i, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then
                log("INFO", string.format("  MOUNT %d dbid=%s cur=%d", i, tostring(w.wpn_dbid), c))
                total = total + c
            end
        end
    end
    log("OK", name .. " 待发弹合计 = " .. total)
end

-- ---------- 执行：清空待发弹 ----------
print("")
print("========================================")
log("INFO", "开始清空待发弹")
print("========================================")

clearUnitWeapons(SIDE_RED, UNIT_NAME)

print("")
log("INFO", "清弹后状态:")
dumpAmmo(SIDE_RED, UNIT_NAME)

print("")
print("========================================")
log("OK", "清弹完成")
print("========================================")
