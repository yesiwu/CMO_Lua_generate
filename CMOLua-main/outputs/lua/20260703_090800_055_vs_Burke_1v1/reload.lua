-- ============================================================
-- 装弹脚本：055装16枚YJ-18
-- 场景：南海1v1，055 vs Burke
-- ============================================================

-- ---------- 日志工具 ----------
local LOG_PREFIX = "[CMO-RELOAD]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO", msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg) log("ERROR", msg) end
local function ok(msg) log("SUCCESS", msg) end

-- ---------- 清空函数 ----------
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({side = side, name = name})
    if not u or not u.guid then
        warn("clearUnitWeapons: 找不到 " .. side .. "/" .. name)
        return false
    end
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

-- ---------- 配置区 ----------
local SIDE_RED = "红方"
local UNIT_055 = "055-Nanchang"  -- 必须与 main.lua 一致
local YJ18_DBID = 2867  -- YJ-18 侵彻弹头版

-- 要清空的舰
local CLEAR_LIST = { UNIT_055 }

-- 装弹清单
local AMMO = {
    { unitname = UNIT_055, wpn_dbid = YJ18_DBID, number = 16 },  -- 16枚YJ-18
}

-- ---------- 执行：先清空 ----------
info("=== 清空待发弹 ===")
for _, name in ipairs(CLEAR_LIST) do clearUnitWeapons(SIDE_RED, name) end

-- ---------- 执行：装弹 ----------
info("=== 装弹 ===")
for _, a in ipairs(AMMO) do
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = SIDE_RED, unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, number = a.number,
    })
    if ok2 then
        ok("+ " .. a.number .. "x [" .. a.wpn_dbid .. "] YJ-18 → " .. a.unitname)
    else
        warn("弹药补给失败: " .. a.unitname)
    end
end

-- ---------- 执行：装弹后自检 ----------
info("=== 装弹自检 ===")
for _, name in ipairs(CLEAR_LIST) do dumpAmmo(SIDE_RED, name) end
