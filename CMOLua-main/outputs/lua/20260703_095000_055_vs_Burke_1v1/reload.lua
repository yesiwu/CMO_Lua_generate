-- ============================================================
-- 装弹脚本：为055装填16枚YJ-18
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 配置区 ----------
local SIDE_RED = "红方"

-- 装弹清单（unitname必须与main.lua创建时完全一致）
-- YJ-18 DBID: 2868 (用户指定)
local AMMO = {
    { unitname = "055-南昌舰", wpn_dbid = 2868, number = 16 },  -- YJ-18
}

-- ---------- 装弹 ----------
info("=== 装弹 ===")
local total_success = 0
local total_fail = 0

for _, a in ipairs(AMMO) do
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = SIDE_RED, 
        unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, 
        number = a.number,
    })
    if ok2 then
        ok("+ " .. a.number .. "x [YJ-18 dbid=" .. a.wpn_dbid .. "] → " .. a.unitname)
        total_success = total_success + 1
    else
        warn("弹药补给失败: " .. a.unitname .. " (dbid=" .. a.wpn_dbid .. ")")
        total_fail = total_fail + 1
    end
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
    ok(name .. " 待发弹合计 = " .. total)
end

info("=== 装弹自检 ===")
for _, a in ipairs(AMMO) do 
    dumpAmmo(SIDE_RED, a.unitname) 
end

info("=== 装弹完成 (成功=" .. total_success .. " 失败=" .. total_fail .. ") ===")
