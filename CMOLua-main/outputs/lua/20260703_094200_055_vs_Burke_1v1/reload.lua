-- ============================================================
-- reload.lua - 为055装填16枚YJ-18
-- 使用方式: 运行 clear.lua 后再运行本脚本
-- ============================================================

local LOG_PREFIX = "[CMO-RELOAD]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO", msg) end
local function ok(msg) log("SUCCESS", msg) end
local function warn(msg) log("WARNING", msg) end

-- ---------- 配置区 ----------
local SIDE_RED = "红方"
local NAME_055 = "055-Nanchang"  -- 必须与main.lua的name一致！
local DBID_YJ18 = 2868            -- YJ-18（用户提供）
local RELOAD_COUNT = 16           -- 装填16枚

-- ---------- 装弹后自检 ----------
local function dumpAmmo(side, name)
    local u = ScenEdit_GetUnit({side = side, name = name})
    if not u then return end
    local total = 0
    local lines = {}
    for i, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then
                table.insert(lines, ("  MOUNT %d dbid=%s cur=%d"):format(i, tostring(w.wpn_dbid), c))
                total = total + c
            end
        end
    end
    if #lines > 0 then
        print("")
        for _, line in ipairs(lines) do
            info(line)
        end
    end
    ok(name .. " 待发弹合计 = " .. total)
    return total
end

-- ---------- 执行装弹 ----------
print("")
print("=================================================")
print("  装填 YJ-18")
print("=================================================")
info("为 " .. SIDE_RED .. " / " .. NAME_055 .. " 装填 " .. RELOAD_COUNT .. " 枚 YJ-18 (DBID " .. DBID_YJ18 .. ")")
print("")

local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
    side = SIDE_RED,
    unitname = NAME_055,
    wpn_dbid = DBID_YJ18,
    number = RELOAD_COUNT,
})

if ok2 then
    ok("+ " .. RELOAD_COUNT .. "x [YJ-18:" .. DBID_YJ18 .. "] → " .. NAME_055)
else
    warn("弹药补给失败: " .. NAME_055 .. " (dbid=" .. DBID_YJ18 .. ")")
end

-- ---------- 装弹后自检 ----------
print("")
info("=== 装弹自检 ===")
local ammoCount = dumpAmmo(SIDE_RED, NAME_055)

print("")
if ammoCount >= RELOAD_COUNT then
    ok("装弹成功! 实际装填 " .. ammoCount .. " 枚")
else
    warn("装弹数量不足! 期望 " .. RELOAD_COUNT .. " 枚，实际 " .. ammoCount .. " 枚")
end
print("=================================================")
print("")
