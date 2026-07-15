-- ============================================================
-- reload.lua  — 红方3舰：装填弹药 + 自检
-- 使用方式：在 CMO Lua 控制台执行 reload.lua（先执行 clear.lua）
--
-- 武器 DBID（MCP 查询）:
--   YJ-21 = 4058
--   YJ-18 = 2868
--
-- 装弹清单:
--   红方-052D-Alpha  : YJ-21 ×16
--   红方-052D-Beta   : YJ-18 ×16, YJ-21 ×16
--   红方-055-Alpha   : YJ-18 ×32
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- 工具函数
-- ============================================================
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ============================================================
-- 装弹后自检：打印某舰实际待发弹
-- ============================================================
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

-- ============================================================
-- 配置区
-- ============================================================
local SIDE_RED = "红方"

-- 装弹清单（unitname 必须与 main.lua 创建时完全一致）
local AMMO = {
    { unitname = "Red-052D-Alpha", wpn_dbid = 4058, number = 16 },  -- YJ-21
    { unitname = "Red-052D-Beta",  wpn_dbid = 2868, number = 16 },  -- YJ-18
    { unitname = "Red-052D-Beta",  wpn_dbid = 4058, number = 16 },  -- YJ-21
    { unitname = "Red-055-Alpha",  wpn_dbid = 2868, number = 32 },  -- YJ-18
}

-- ============================================================
-- 执行装弹
-- ============================================================
info("=== 装弹 ===")
for _, a in ipairs(AMMO) do
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = SIDE_RED, unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, number = a.number,
    })
    if ok2 then
        ok("+ " .. a.number .. "x [" .. a.wpn_dbid .. "] → " .. a.unitname)
    else
        warn("弹药补给失败: " .. a.unitname .. " (dbid=" .. a.wpn_dbid .. ")")
    end
end

-- ============================================================
-- 执行装弹后自检
-- ============================================================
info("=== 装弹自检 ===")
local verified = {}
for _, a in ipairs(AMMO) do
    if not verified[a.unitname] then
        dumpAmmo(SIDE_RED, a.unitname)
        verified[a.unitname] = true
    end
end

ok("reload.lua 执行完毕")
