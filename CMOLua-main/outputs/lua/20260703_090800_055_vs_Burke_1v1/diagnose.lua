-- ============================================================
-- 诊断脚本：检查场景状态
-- 场景：南海1v1，055 vs Burke
-- ============================================================

local LOG = "[CMO-DIAGNOSE]"

local function info(msg) print(LOG .. " [INFO] " .. msg) end
local function ok(msg) print(LOG .. " [OK] " .. msg) end
local function warn(msg) print(LOG .. " [WARN] " .. msg) end
local function err(msg) print(LOG .. " [ERROR] " .. msg) end

info("=== 场景诊断 ===")

-- 检查阵营
local sides = {"红方", "蓝方"}
for _, side in ipairs(sides) do
    local ok2, s = pcall(VP_GetSide, {Side = side})
    if ok2 and s then
        ok("阵营 " .. side .. " 存在，单位数: " .. #(s.units or {}))
    else
        warn("阵营 " .. side .. " 不存在或无法访问")
    end
end

-- 检查055
local unit_055 = ScenEdit_GetUnit({side = "红方", name = "055-Nanchang"})
if unit_055 and unit_055.guid then
    ok("055-Nanchang 存在")
    info("  GUID: " .. unit_055.guid)
    info("  位置: " .. string.format("%.4f, %.4f", unit_055.latitude, unit_055.longitude))
    info("  航向: " .. unit_055.heading .. "°")
    info("  航速: " .. unit_055.speed .. "节")
    -- 检查弹药
    local total = 0
    for i, m in ipairs(unit_055.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then
                info("  " .. m.mount_guid .. " : " .. c .. "x dbid=" .. w.wpn_dbid)
                total = total + c
            end
        end
    end
    ok("055 待发弹合计: " .. total)
else
    err("055-Nanchang 未找到!")
end

-- 检查Burke
local unit_burke = ScenEdit_GetUnit({side = "蓝方", name = "DDG-51-Burke"})
if unit_burke and unit_burke.guid then
    ok("DDG-51-Burke 存在")
    info("  GUID: " .. unit_burke.guid)
    info("  位置: " .. string.format("%.4f, %.4f", unit_burke.latitude, unit_burke.longitude))
    info("  航向: " .. unit_burke.heading .. "°")
    info("  航速: " .. unit_burke.speed .. "节")
    info("  autodetectable: " .. tostring(unit_burke.autodetectable))
else
    err("DDG-51-Burke 未找到!")
end

-- 计算距离
if unit_055 and unit_burke then
    local range = Tool_Range(
        {latitude = unit_055.latitude, longitude = unit_055.longitude},
        {latitude = unit_burke.latitude, longitude = unit_burke.longitude}
    )
    ok("055 → Burke 距离: " .. string.format("%.1f 海里", range))
end

-- 检查contact
info("检查红方contact列表...")
local ok2, contacts = pcall(ScenEdit_GetContacts, {Side = "红方"})
if ok2 and contacts then
    info("contact数量: " .. #contacts)
    for i, c in ipairs(contacts) do
        info("  [" .. i .. "] " .. (c.name or "unnamed") 
            .. " guid=" .. (c.guid or "nil")
            .. " type=" .. (c.type or "nil")
            .. " actualunitid=" .. (c.actualunitid or "nil"))
    end
else
    warn("无法获取contact列表")
end

info("=== 诊断完毕 ===")
