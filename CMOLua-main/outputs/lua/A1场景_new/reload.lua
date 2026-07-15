-- ============================================================
-- reload.lua — 红方5舰装弹脚本
-- 武器 DBID（MCP）：
--   YJ-20 → YJ-83  = 541
--   YJ-18           = 2868
-- 单位名与 main.lua 完全一致
-- ============================================================

Tool_EmulateNoConsole(true)

local LOG = "[CMO]"
local SIDE_RED = "红方"

local function info(msg) print(LOG .. " [INFO] " .. msg) end
local function warn(msg) print(LOG .. " [WARN] " .. msg) end
local function ok(msg)   print(LOG .. " [OK] "   .. msg) end

-- ============================================================
-- 武器 DBID（YJ-20 → YJ-83 替代）
-- ============================================================
local WPN_YJ83 = 541   -- YJ-83（替代 YJ-20）
local WPN_YJ18 = 2868  -- YJ-18

-- ============================================================
-- 装弹清单（unitname 与 main.lua 完全一致）
-- ============================================================
local AMMO = {
    -- Red 052D-1：YJ-83×12 + YJ-18×8
    { unitname = "Red-052D-1", wpn_dbid = WPN_YJ83, number = 12 },  -- 替代 YJ-20
    { unitname = "Red-052D-1", wpn_dbid = WPN_YJ18, number = 8  },
    -- Red 052D-2：YJ-83×16 + YJ-18×8
    { unitname = "Red-052D-2", wpn_dbid = WPN_YJ83, number = 16 },
    { unitname = "Red-052D-2", wpn_dbid = WPN_YJ18, number = 8  },
    -- Red 052D-3：YJ-83×8 + YJ-18×16
    { unitname = "Red-052D-3", wpn_dbid = WPN_YJ83, number = 8  },
    { unitname = "Red-052D-3", wpn_dbid = WPN_YJ18, number = 16 },
    -- Red 055-1：YJ-83×16 + YJ-18×24
    { unitname = "Red-055-1",  wpn_dbid = WPN_YJ83, number = 16 },
    { unitname = "Red-055-1",  wpn_dbid = WPN_YJ18, number = 24 },
    -- Red 055-2：YJ-83×8 + YJ-18×32
    { unitname = "Red-055-2",  wpn_dbid = WPN_YJ83, number = 8  },
    { unitname = "Red-055-2",  wpn_dbid = WPN_YJ18, number = 32 },
}

-- ============================================================
-- 执行装弹
-- ============================================================
ok("=== 装弹开始 ===")
local okCount, failCount = 0, 0
for _, a in ipairs(AMMO) do
    local u = ScenEdit_GetUnit({ side = SIDE_RED, name = a.unitname })
    if not u then
        warn("跳过（单位不存在）: " .. a.unitname)
    else
        local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
            side = SIDE_RED, unitname = a.unitname,
            wpn_dbid = a.wpn_dbid, number = a.number,
        })
        if ok2 then
            info(("+ %dx [%s] → %s"):format(a.number, a.wpn_dbid, a.unitname))
            okCount = okCount + 1
        else
            warn("弹药补给失败: " .. a.unitname .. " (dbid=" .. a.wpn_dbid .. ")")
            failCount = failCount + 1
        end
    end
end

ok(("装弹完毕: 成功 %d 条（失败 %d 条）"):format(okCount, failCount))
info("下一步: attack.lua")
