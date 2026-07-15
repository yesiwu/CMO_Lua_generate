-- ============================================================
-- clear.lua - 清空055待发弹
-- 使用方式: 直接在CMO Lua控制台运行
-- ============================================================

local LOG_PREFIX = "[CMO-CLEAR]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO", msg) end
local function ok(msg) log("SUCCESS", msg) end
local function warn(msg) log("WARNING", msg) end

-- ---------- 配置区 ----------
local SIDE_RED = "红方"
local NAME_055 = "055-Nanchang"  -- 必须与main.lua的name一致！

-- ---------- 清弹函数 ----------
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({side = side, name = name})
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
        if (_errnum_ or 0) == 0 then
            done = done + 1
        else
            fail = fail + 1
        end
    end
    ok(("%s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
end

-- ---------- 执行清弹 ----------
print("")
print("=================================================")
print("  清空待发弹")
print("=================================================")
info("清空 " .. SIDE_RED .. " / " .. NAME_055 .. " 的待发弹...")
print("")

clearUnitWeapons(SIDE_RED, NAME_055)

print("")
ok("清弹完成")
print("=================================================")
print("")
