-- reload.lua — 演示：红方 J-16 / H-6A 完整装弹流程
--
-- 武器 DBID（MCP 查询）：
--   PL-15    DBID=4049   空空导弹（预警机/战斗机用）
--   YJ-83K   DBID=2869   空对面导弹
--   KD-88    DBID=2081   空对地导弹
--
-- 流程：清空待发弹 → 重新装弹 → 装弹后自检
-- 依赖：main.lua 已创建红方飞机
-- =====================================================================

Tool_EmulateNoConsole(true)

-- =====================================================================
-- 日志工具函数
-- =====================================================================
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARNING", msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- =====================================================================
-- 武器 DBID（MCP 查询，禁止硬编码）
-- =====================================================================
local WPN_PL15   = 4049   -- PL-15（超视距空空）
local WPN_YJ83K  = 2869   -- YJ-83K（空对面）
local WPN_KD88   = 2081   -- KD-88（空对地）

-- =====================================================================
-- 清空：遍历 mounts，批量 remove=true
-- 原理：传入当前数量 + remove=true，等价于清空该弹种，格子保留
-- =====================================================================
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
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

-- =====================================================================
-- 装弹后自检
-- =====================================================================
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

-- =====================================================================
-- 配置区
-- =====================================================================
local SIDE_RED  = "红方"
local SIDE_BLUE = "蓝方"

-- 1) 要清空的飞机清单（与 main.lua 完全一致）
--    机场（跑道/机库）没有挂载武器，不需要清弹
local CLEAR_LIST = {
    -- 红方飞机
    { side = SIDE_RED,  name = "J16-001"   },
    { side = SIDE_RED,  name = "J16-002"   },
    { side = SIDE_RED,  name = "H6A-001"   },
    { side = SIDE_RED,  name = "SH60J-001" },
    -- 蓝方飞机
    { side = SIDE_BLUE, name = "F35C-001"  },
    { side = SIDE_BLUE, name = "F35C-002"  },
    { side = SIDE_BLUE, name = "FA18C-001" },
    { side = SIDE_BLUE, name = "FA18C-002" },
    { side = SIDE_BLUE, name = "E2C-001"   },
}

-- 2) 装弹清单
local AMMO = {
    -- J16-001：PL-15 ×4（空空）+ YJ-83K ×2（对面）
    { side = SIDE_RED,  unitname = "J16-001", wpn_dbid = WPN_PL15,  number = 4 },
    { side = SIDE_RED,  unitname = "J16-001", wpn_dbid = WPN_YJ83K, number = 2 },
    -- J16-002：PL-15 ×2 + YJ-83K ×4
    { side = SIDE_RED,  unitname = "J16-002", wpn_dbid = WPN_PL15,  number = 2 },
    { side = SIDE_RED,  unitname = "J16-002", wpn_dbid = WPN_YJ83K, number = 4 },
    -- H6A-001：KD-88 ×6（对地）
    { side = SIDE_RED,  unitname = "H6A-001", wpn_dbid = WPN_KD88,  number = 6 },
    -- FA18C-001：SLAM-ER ×4 + Harpoon ×2（已在 main.lua 定义）
    { side = SIDE_BLUE, unitname = "FA18C-001", wpn_dbid = 2869, number = 4 },
    { side = SIDE_BLUE, unitname = "FA18C-001", wpn_dbid = 45,   number = 2 },
    -- FA18C-002：SLAM-ER ×2 + Harpoon ×4
    { side = SIDE_BLUE, unitname = "FA18C-002", wpn_dbid = 2869, number = 2 },
    { side = SIDE_BLUE, unitname = "FA18C-002", wpn_dbid = 45,   number = 4 },
}

-- =====================================================================
-- 步骤 1：清空待发弹
-- =====================================================================
info("=== 步骤1: 清空待发弹 ===")
for _, entry in ipairs(CLEAR_LIST) do
    clearUnitWeapons(entry.side, entry.name)
end

-- =====================================================================
-- 步骤 2：重新装弹
-- =====================================================================
info("=== 步骤2: 重新装弹 ===")
local okCount, failCount = 0, 0
for _, a in ipairs(AMMO) do
    local ok2, err2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = a.side, unitname = a.unitname,
        wpn_dbid = a.wpn_dbid, number = a.number,
    })
    if ok2 then
        ok(string.format("+ %dx [DBID=%d] → %s", a.number, a.wpn_dbid, a.unitname))
        okCount = okCount + 1
    else
        warn("弹药补给失败: " .. a.unitname .. " (dbid=" .. a.wpn_dbid .. ") " .. tostring(err2))
        failCount = failCount + 1
    end
end

ok(string.format("装弹完毕: 成功 %d 条（失败 %d 条）", okCount, failCount))

-- =====================================================================
-- 步骤 3：装弹后自检
-- =====================================================================
info("=== 步骤3: 装弹自检 ===")
for _, entry in ipairs(CLEAR_LIST) do dumpAmmo(entry.side, entry.name) end

ok("reload.lua 执行完毕")
info("下一步: attack.lua")
