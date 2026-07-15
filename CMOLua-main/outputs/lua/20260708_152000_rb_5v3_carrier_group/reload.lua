-- ============================================================
-- reload.lua: 装弹
-- 数据来源: JSON red_blue_5v3_liaoning.json §platforms
--   055: 装弹16/发射13 YJ-18
--   052D-1: 装弹16/发射8 YJ-18
--   052D-2: 装弹10/发射5 YJ-18
--   J-15: 4×YJ-83K（loadoutid=9682 已含，reload 再补）
-- ============================================================

print("[CMO] [INFO] ============ reload.lua 开始 ============")

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. tostring(msg)) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function ok(msg)   log("SUCCESS", msg) end

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

local CFG = {
    dbid_yj18  = 2868,
    dbid_yj83k = 2137,
    side_red   = "红方",
}

local AMMO_LIST = {
    { unitname = "红方055南昌舰",    wpn_dbid = CFG.dbid_yj18, number = 16 },
    { unitname = "红方052D-1昆明舰", wpn_dbid = CFG.dbid_yj18, number = 16 },
    { unitname = "红方052D-2南京舰", wpn_dbid = CFG.dbid_yj18, number = 10 },
    { unitname = "J-15-1",          wpn_dbid = CFG.dbid_yj83k, number = 4  },
    { unitname = "J-15-2",          wpn_dbid = CFG.dbid_yj83k, number = 4  },
}

print("========================================")
print("       STEP 3/4: 装弹")
print("========================================")

for _, a in ipairs(AMMO_LIST) do
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = CFG.side_red, unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, number = a.number,
    })
    if ok2 then
        local wname = (a.wpn_dbid == CFG.dbid_yj18) and "YJ-18" or "YJ-83K"
        ok("+ " .. a.number .. "x [" .. wname .. " dbid=" .. a.wpn_dbid .. "] -> " .. a.unitname)
    else
        warn("补给失败: " .. a.unitname)
    end
end

print("=== 装弹自检 ===")
for _, name in ipairs({
    "红方055南昌舰", "红方052D-1昆明舰", "红方052D-2南京舰",
    "J-15-1", "J-15-2",
}) do
    dumpAmmo(CFG.side_red, name)
end
ok("STEP 3 完成: 弹药已就绪")
