-- ============================================================
-- 055 vs Burke 1v1 场景 - 主脚本
-- 功能：创建红蓝双方单位，设置全知全能
-- DBID 来源：MCP 查询
--   - 055: DBID 2834 (Type 055 Renhai)
--   - Burke: DBID 112 (DDG-51 Arleigh Burke)
-- ============================================================

local LOG = "[MAIN]"

-- ---------- 先创建阵营 ----------
local ok_red, res_red = pcall(ScenEdit_AddSide, {name = "红方", color = "255,0,0"})
local ok_blue, res_blue = pcall(ScenEdit_AddSide, {name = "蓝方", color = "0,0,255"})
if ok_red then print(LOG .. " 红方阵营已创建") else print(LOG .. " [WARN] 红方阵营: " .. tostring(res_red)) end
if ok_blue then print(LOG .. " 蓝方阵营已创建") else print(LOG .. " [WARN] 蓝方阵营: " .. tostring(res_blue)) end

-- ---------- 红方：055 驱逐舰 ----------
local unit_055 = ScenEdit_AddUnit({
    side          = "红方",
    type          = "Ship",
    name          = "南昌舰",
    dbid          = 2834,
    latitude      = 15.5,      -- 南海北部
    longitude     = 113.5,
    heading       = 90,
    speed         = 18,
    autodetectable = true,
    proficiency   = "Veteran",
})
if unit_055 then
    ScenEdit_SetKeyValue("RED_055_GUID", unit_055.guid)
    print(LOG .. " 红方055已部署: " .. unit_055.guid)
else
    print(LOG .. " [ERROR] 红方055部署失败")
end

-- ---------- 蓝方：Burke 级驱逐舰 ----------
local unit_burke = ScenEdit_AddUnit({
    side          = "蓝方",
    type          = "Ship",
    name          = "DDG-51_Arleigh_Burke",
    dbid          = 112,
    latitude      = 14.0,      -- 南海南部，与055相距约100海里
    longitude     = 115.0,
    heading       = 270,
    speed         = 15,
    autodetectable = true,   -- 关键：必须设为true，红方才能稳定获得contact
    proficiency   = "Veteran",
})
if unit_burke then
    ScenEdit_SetKeyValue("BLUE_BURKE_GUID", unit_burke.guid)
    print(LOG .. " 蓝方Burke已部署: " .. unit_burke.guid)
    -- 创建后再次确认 autodetectable（双保险）
    pcall(ScenEdit_SetUnit, {guid = unit_burke.guid, autodetectable = true})
else
    print(LOG .. " [ERROR] 蓝方Burke部署失败")
end

-- ---------- 设置敌对关系 ----------
pcall(ScenEdit_SetSidePosture, "红方", "蓝方", "H")
pcall(ScenEdit_SetSidePosture, "蓝方", "红方", "H")

-- ---------- 红方全知全能 ----------
pcall(ScenEdit_SetSideOptions, {side = "红方", awareness = "OMNI"})
print(LOG .. " 红方已设为全知全能(OMNI)")

-- ---------- 输出部署摘要 ----------
print("")
print("========================================")
print(LOG .. " 部署完成")
print("========================================")
print("红方单位:")
print("  - 南昌舰 (055, DBID=2834)")
print("  - GUID: " .. (unit_055 and unit_055.guid or "N/A"))
print("蓝方单位:")
print("  - DDG-51_Arleigh_Burke (Burke, DBID=112)")
print("  - GUID: " .. (unit_burke and unit_burke.guid or "N/A"))
print("========================================")
print("下一步执行顺序:")
print("  1. clear.lua  - 清空待发弹")
print("  2. reload.lua - 装填YJ-18")
print("  3. attack.lua - 发射13枚导弹")
print("========================================")
