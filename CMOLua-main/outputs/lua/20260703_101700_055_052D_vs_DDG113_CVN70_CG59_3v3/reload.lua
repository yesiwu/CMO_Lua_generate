-- ============================================================
-- reload.lua: 装填红方舰艇弹药
-- 055: 16枚YJ-18, 052D-1: 16枚YJ-18, 052D-2: 10枚YJ-18
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 配置区 ----------
local SIDE_RED = "红方"
local YJ18_DBID = 2868

-- 装弹清单（unitname 必须与 main.lua 创建时完全一致）
local AMMO = {
    { unitname = "055-Nanchang",    wpn_dbid = YJ18_DBID, number = 16 },  -- YJ-18
    { unitname = "052D-1-Nanjing",  wpn_dbid = YJ18_DBID, number = 16 },  -- YJ-18
    { unitname = "052D-2-Fuzhou",   wpn_dbid = YJ18_DBID, number = 10 },  -- YJ-18
}

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
    ok(name .. " 待发弹合计 = " .. total)
end

-- ---------- 执行 ----------
print("")
print("========================================")
print("       装填弹药")
print("========================================")
print("")

-- 装弹
for _, a in ipairs(AMMO) do
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = SIDE_RED, unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, number = a.number,
    })
    if ok2 then
        ok("+ " .. a.number .. "x [" .. a.wpn_dbid .. "] -> " .. a.unitname)
    else
        warn("弹药补给失败: " .. a.unitname .. " (dbid=" .. a.wpn_dbid .. ")")
    end
end

-- 自检
print("")
info("=== 装弹自检 ===")
dumpAmmo(SIDE_RED, "055-Nanchang")
dumpAmmo(SIDE_RED, "052D-1-Nanjing")
dumpAmmo(SIDE_RED, "052D-2-Fuzhou")

print("")
ok("reload.lua 执行完毕")
