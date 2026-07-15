-- clear_ammo.lua — 只清弹：把 demo_airbase 所有飞机的挂载武器弹量清到 0
--
-- 原理：遍历每个单位的 mounts，逐一 remove=true 扣到 0，格子保留
-- 适用范围：Loadout 里的可挂载武器（AIM-120、JDAM 等）
-- 不适用：固定配套件（30mm 机炮、干扰弹、副油箱）Lua 无法操作
-- =====================================================================

Tool_EmulateNoConsole(true)

local LOG       = "[CMO]"
local SIDE_RED  = "红方"
local SIDE_BLUE = "蓝方"

local function info(msg) print(LOG .. " [INFO] "    .. msg) end
local function warn(msg) print(LOG .. " [WARN] "    .. msg) end
local function ok(msg)   print(LOG .. " [SUCCESS] " .. msg) end

-- =====================================================================
-- 清空指定单位的挂载武器（remove=true 扣到 0，格子保留）
-- =====================================================================
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("找不到单位: " .. side .. "/" .. name)
        return false
    end

    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs + 1] = {
                    dbid    = w.wpn_dbid,
                    num     = cur,
                    mountid = m.mount_guid,
                }
            end
        end
    end

    if #jobs == 0 then
        ok(name .. ": 无待发弹，跳过")
        return true
    end

    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({
            guid       = u.guid,
            wpn_dbid   = j.dbid,
            mount_guid = j.mountid,
            number     = j.num,
            remove     = true,
        })
        if (_errnum_ or 0) == 0 then
            ok(string.format("  - [DBID=%d] ×%d → 归零", j.dbid, j.num))
            done = done + 1
        else
            warn(string.format("  - [DBID=%d] 失败 (_errnum_=%s)", j.dbid, tostring(_errnum_)))
            fail = fail + 1
        end
    end

    ok(name .. ": " .. done .. " 条归零 (" .. fail .. " 条失败)")
    return fail == 0
end

-- =====================================================================
-- 所有单位清单（与 main.lua 完全一致）
-- =====================================================================
local UNITS = {
    { side = SIDE_RED,  name = "J16-001"   },
    { side = SIDE_RED,  name = "J16-002"   },
    { side = SIDE_RED,  name = "H6A-001"   },
    { side = SIDE_RED,  name = "SH60J-001" },
    { side = SIDE_BLUE, name = "F35C-001"  },
    { side = SIDE_BLUE, name = "F35C-002"  },
    { side = SIDE_BLUE, name = "FA18C-001" },
    { side = SIDE_BLUE, name = "FA18C-002" },
    { side = SIDE_BLUE, name = "E2C-001"   },
}

-- =====================================================================
-- 执行
-- =====================================================================
info("=== 清弹开始: " .. #UNITS .. " 个单位 ===")
local okCount, failCount = 0, 0
for _, entry in ipairs(UNITS) do
    local ok2 = clearUnitWeapons(entry.side, entry.name)
    if ok2 then okCount = okCount + 1
    else failCount = failCount + 1 end
end

info("=== 清弹完毕: " .. okCount .. " 单位成功 (" .. failCount .. " 失败) ===")
info("注: 固定配套件（机炮/干扰弹/副油箱）不在 API 范围内，无法清空")
