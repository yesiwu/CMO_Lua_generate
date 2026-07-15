-- ============================================================
-- clear.lua — 清弹（幂等）
-- API: ScenEdit_AddReloadsToUnit + remove=true（遍历 mounts 逐条清空）
-- 参考: SKILL.md §6 Weapon Reloads 章节
-- ============================================================

print("\n===== [clear] 清弹 =====")

local function warn(msg) print("[clear] [WARN] " .. msg) end
local function info(msg) print("[clear] " .. msg) end

local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("找不到 " .. side .. "/" .. name); return false
    end
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
        ScenEdit_AddReloadsToUnit({
            guid = u.guid, wpn_dbid = j.dbid,
            mount_guid = j.mountid, number = j.num, remove = true,
        })
        if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
    end
    info(("%s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
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
    info(name .. " 待发弹合计 = " .. total)
end

local SIDE_RED = "红方"
local CLEAR_LIST = {
    "红方055南昌舰",
    "红方052D-1昆明舰",
    "红方052D-2南京舰",
    "J-15-1",
    "J-15-2",
}

info("=== 清弹前 ===")
for _, name in ipairs(CLEAR_LIST) do dumpAmmo(SIDE_RED, name) end

info("=== 执行清弹 ===")
for _, name in ipairs(CLEAR_LIST) do clearUnitWeapons(SIDE_RED, name) end

info("=== 清弹后 ===")
for _, name in ipairs(CLEAR_LIST) do dumpAmmo(SIDE_RED, name) end

print("[clear] 完成。")
