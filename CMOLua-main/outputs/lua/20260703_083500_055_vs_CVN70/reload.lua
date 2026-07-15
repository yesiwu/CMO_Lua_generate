-- ============================================================
-- reload.lua — 装填 YJ-18 导弹
-- 红方 055 装载 16 枚 YJ-18，发射 13 枚
--
-- 使用方式: main.lua 执行后，在 CMO Lua 控制台执行本脚本
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- 配置区
-- ============================================================
local SIDE_RED = "红方"
local SIDE_BLUE = "蓝方"
local YJ18_DBID = 2868    -- YJ-18 导弹 DBID

-- 要清空的舰艇列表
local CLEAR_LIST = {"055-Nanchang"}

-- 装弹清单
local AMMO = {
    {unitname = "055-Nanchang", wpn_dbid = YJ18_DBID, number = 16},  -- YJ-18 x16
}

-- ============================================================
-- 日志工具函数
-- ============================================================
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO", msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg)  log("ERROR", msg) end
local function ok(msg)   log("SUCCESS", msg) end

-- ============================================================
-- 清空单元现有待发弹
-- ============================================================
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({side = side, name = name})
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
                    dbid = w.wpn_dbid,
                    num = cur,
                    mountid = m.mount_guid,
                }
            end
        end
    end
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({
            guid = u.guid,
            wpn_dbid = j.dbid,
            mount_guid = j.mountid,
            number = j.num,
            remove = true,
        })
        if (_errnum_ or 0) == 0 then
            done = done + 1
        else
            fail = fail + 1
        end
    end
    ok(("%s: 清弹 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
end

-- ============================================================
-- 装弹后自检
-- ============================================================
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

-- ============================================================
-- 执行: 先清空
-- ============================================================
info("=== 清空现有待发弹 ===")
for _, name in ipairs(CLEAR_LIST) do
    clearUnitWeapons(SIDE_RED, name)
end

-- ============================================================
-- 执行: 装弹
-- ============================================================
info("=== 装填 YJ-18 ===")
for _, a in ipairs(AMMO) do
    local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
        side = SIDE_RED,
        unitname = a.unitname,
        wpn_dbid = a.wpn_dbid,
        number = a.number,
    })
    if ok2 then
        ok("+ " .. a.number .. "x [YJ-18 DBID=" .. a.wpn_dbid .. "] → " .. a.unitname)
    else
        warn("弹药补给失败: " .. a.unitname .. " (dbid=" .. a.wpn_dbid .. ")")
    end
end

-- ============================================================
-- 执行: 装弹后自检
-- ============================================================
info("=== 装弹自检 ===")
for _, name in ipairs(CLEAR_LIST) do
    dumpAmmo(SIDE_RED, name)
end

print('[CMO] === reload.lua 执行完毕 ===')
print('[CMO] 下一步: 执行 attack.lua 发射 13 枚 YJ-18 打击 CVN-70')
