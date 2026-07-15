-- ============================================================
-- 装弹脚本: 055装填16枚YJ-18
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR",   msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ---------- 配置区 ----------
local SIDE_RED   = "红方"
local NAME_055   = "055-Nanchang"   -- 必须与 main.lua 一致

-- YJ-18 DBID: 2868 (用户指定)
-- 装弹数量: 16枚
local YJ18_DBID  = 2868
local YJ18_COUNT = 16

-- ---------- 装弹 ----------
info("=== 装填 YJ-18 ===")

local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
    side     = SIDE_RED,
    unitname = NAME_055,
    wpn_dbid = YJ18_DBID,
    number   = YJ18_COUNT,
})

if ok2 then
    ok("+ " .. YJ18_COUNT .. "x [YJ-18 dbid=" .. YJ18_DBID .. "] → " .. NAME_055)
else
    warn("弹药补给失败: " .. NAME_055 .. " (dbid=" .. YJ18_DBID .. ")")
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

info("=== 装弹后自检 ===")
dumpAmmo(SIDE_RED, NAME_055)

ok("装弹完成! 下一步: 运行 attack.lua 发起打击")
