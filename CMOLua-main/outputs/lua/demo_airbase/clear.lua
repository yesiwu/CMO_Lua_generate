-- clear.lua — 清空 demo 脚本创建的所有单位和阵营

Tool_EmulateNoConsole(true)

local LOG = "[CMO]"

-- =====================================================================
-- 工具函数
-- =====================================================================
local function log(level, msg) print(LOG .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function warn(msg) log("WARN",    msg) end
local function ok(msg)   log("OK",     msg) end

-- =====================================================================
-- 清空挂载武器：遍历 mounts，逐一 remove=true 扣到 0
-- 适用范围：Loadout 里的可挂载武器（导弹/炸弹）
-- 不适用：固定配套件（机炮/干扰弹/吊舱/油箱）Lua 无法操作
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
            done = done + 1
        else
            fail = fail + 1
        end
    end

    ok(name .. ": " .. done .. " 条挂载武器归零 (" .. fail .. " 条失败)")
    return fail == 0
end

-- =====================================================================
-- 单位列表（与 main.lua 完全对应）
-- =====================================================================
local SIDES = {
    { name = "红方", units = {
        "红方机场-跑道",
        "红方机场-大机库",
        "J16-001",
        "J16-002",
        "H6A-001",
        "SH60J-001",
    }},
    { name = "蓝方", units = {
        "蓝方机场-跑道",
        "蓝方机场-大机库",
        "F35C-001",
        "F35C-002",
        "FA18C-001",
        "FA18C-002",
        "E2C-001",
    }},
}

-- =====================================================================
-- 1. 清空所有飞机的挂载武器（先清弹）
-- =====================================================================
info("=== 步骤1: 清空挂载武器 ===")
for _, sideData in ipairs(SIDES) do
    for _, unit_name in ipairs(sideData.units) do
        clearUnitWeapons(sideData.name, unit_name)
    end
end

-- =====================================================================
-- 2. 删除所有单位
-- =====================================================================
info("=== 步骤2: 删除单位 ===")
local okUnit, failUnit = 0, 0
for _, sideData in ipairs(SIDES) do
    for _, unit_name in ipairs(sideData.units) do
        local ok2, err2 = pcall(ScenEdit_DeleteUnit, {
            side = sideData.name,
            name = unit_name,
        })
        if ok2 then
            ok("已删除 [" .. sideData.name .. "] " .. unit_name)
            okUnit = okUnit + 1
        else
            warn("不存在 [" .. sideData.name .. "] " .. unit_name)
            failUnit = failUnit + 1
        end
    end
end

-- =====================================================================
-- 3. 阵营随单位自动清空（CMO 不支持手动删除阵营）
-- =====================================================================
info("=== 步骤3: 完成 ===")
ok("删除单位: " .. okUnit .. " 成功，" .. failUnit .. " 不存在")
info("注: 固定配套件（机炮/干扰弹/吊舱/油箱）无法清空，随单位删除")
info("clear.lua 执行完毕（重建运行 main.lua）")
