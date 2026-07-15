-- ============================================================
-- reload.lua: 装填红方所有单位的弹药
-- 055-1:   16 枚 YJ-18
-- 055-2:   16 枚 YJ-18
-- 052D-1:  16 枚 YJ-18
-- 052D-2:  10 枚 YJ-18
-- 只装方案指定弹种，其它弹种不补
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

local SIDE_RED = "红方"
local YJ18_DBID = 2868

local AMMO = {
    { unitname = "055-1",  wpn_dbid = YJ18_DBID, number = 16 },  -- YJ-18 x16
    { unitname = "055-2",  wpn_dbid = YJ18_DBID, number = 16 },  -- YJ-18 x16
    { unitname = "052D-1", wpn_dbid = YJ18_DBID, number = 16 },  -- YJ-18 x16
    { unitname = "052D-2", wpn_dbid = YJ18_DBID, number = 10 },  -- YJ-18 x10
}

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

print("")
print("========================================")
print("       装填弹药 (YJ-18)")
print("========================================")
print("")

for _, a in ipairs(AMMO) do
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = SIDE_RED, unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, number = a.number,
    })
    if ok2 then
        ok("+ " .. a.number .. "x [YJ-18 dbid=" .. a.wpn_dbid .. "] -> " .. a.unitname)
    else
        warn("补给失败: " .. a.unitname)
    end
end

print("")
info("=== 装弹自检 ===")
for _, name in ipairs({ "055-1", "055-2", "052D-1", "052D-2" }) do
    dumpAmmo(SIDE_RED, name)
end

print("")
ok("reload.lua 执行完毕")