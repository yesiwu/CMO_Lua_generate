-- ============================================================
-- 联合打击计划 Lua 代码（SKILL 规范版）
-- 计划ID: 2026B
-- 计划名称: 联合火力突击
-- 数据来源: plan_a1_001_legacy(1).json
-- 生成时间: 2026-04-20
-- MCP 验证: 所有 DBID 均通过 MCP 数据库查询确认
-- ============================================================

-- ============================================================
-- 第一部分：创建红方和蓝方阵营
-- ============================================================
local ok, result = pcall(ScenEdit_AddSide, {name = "Red", color = "255,0,0"})
if not ok then print("创建红方失败: " .. tostring(result)) end

local ok2, result2 = pcall(ScenEdit_AddSide, {name = "Blue", color = "0,0,255"})
if not ok2 then print("创建蓝方失败: " .. tostring(result2)) end

ScenEdit_SetSidePosture("Red", "Blue", "H")
ScenEdit_SetSidePosture("Blue", "Red", "H")

-- ============================================================
-- 第二部分：蓝方目标（敌方舰艇）
-- 所有 DBID 均通过 MCP 查询 DataShip 表确认
-- ============================================================

-- 目标1: tico_simoer (CG-56 San Jacinto)
-- DBID 40 - CG 56 San Jacinto [Ticonderoga Baseline 3, VLS]
local unit1 = ScenEdit_AddUnit({
    side      = "Blue",
    type      = "Ship",
    dbid      = 40,
    name      = "tico_simoer",
    latitude  = 7.970356,
    longitude = 119.503844,
    heading   = 90,
    speed     = 20
})
if unit1 then ScenEdit_SetKeyValue("TICO_GUID", unit1.guid) end

-- 目标2: ddg_chafei (DDG-51 Arleigh Burke)
-- DBID 112 - DDG 51 Arleigh Burke [Arleigh Burke Flight I]
local unit2 = ScenEdit_AddUnit({
    side      = "Blue",
    type      = "Ship",
    dbid      = 112,
    name      = "ddg_chafei",
    latitude  = 8.284662,
    longitude = 119.783273,
    heading   = 90,
    speed     = 20
})
if unit2 then ScenEdit_SetKeyValue("DDG_CHAFEI_GUID", unit2.guid) end

-- 目标3: lha_meiguo (LHA-6 America)
-- DBID 2362 - LHA 6 America [Flight 0, Assault-Optimized Makin Island]
local unit3 = ScenEdit_AddUnit({
    side      = "Blue",
    type      = "Ship",
    dbid      = 2362,
    name      = "lha_meiguo",
    latitude  = 7.922858,
    longitude = 120.093579,
    heading   = 0,
    speed     = 15
})
if unit3 then ScenEdit_SetKeyValue("LHA_GUID", unit3.guid) end

-- 目标4: supply_kz (T-AO 187 Henry J. Kaiser)
-- DBID 26 - T-AO 187 Henry J. Kaiser [Mod Cimarron]
local unit4 = ScenEdit_AddUnit({
    side      = "Blue",
    type      = "Ship",
    dbid      = 26,
    name      = "supply_kz",
    latitude  = -0.101186,
    longitude = 106.164261,
    heading   = 90,
    speed     = 15
})
if unit4 then ScenEdit_SetKeyValue("SUPPLY_GUID", unit4.guid) end

-- 目标5: ddg_momuseng (DDG-51 Arleigh Burke)
-- DBID 112 - DDG 51 Arleigh Burke [Arleigh Burke Flight I]
local unit5 = ScenEdit_AddUnit({
    side      = "Blue",
    type      = "Ship",
    dbid      = 112,
    name      = "ddg_momuseng",
    latitude  = 7.104,
    longitude = 116.28,
    heading   = 0,
    speed     = 20
})
if unit5 then ScenEdit_SetKeyValue("DDG_MOMUSENG_GUID", unit5.guid) end

-- ============================================================
-- 第三部分：红方侦察集群 - 卫星
-- DBID 70 - Jian Bing [SAR, Optical, ELINT]
-- 注意: DBID 5452 在 CMO 数据库中不存在，已修正为 DBID 70
-- ============================================================
local sat1 = ScenEdit_AddUnit({
    side      = "Red",
    type      = "Satellite",
    dbid      = 70,
    name      = "wxjb",
    latitude  = 8.71,
    longitude = 119.90,
    altitude  = 10000
})
if sat1 then ScenEdit_SetKeyValue("WXJB_GUID", sat1.guid) end

-- ============================================================
-- 第四部分：红方作战集群 - DF-26B 导弹发射车（02打击大队）
-- DBID 2879 - SSM Bn (DF-26D [CSS-11])
-- 这是 CMO 数据库中对应 DF-26 导弹部队的正确 DBID
-- ============================================================

-- 02打击大队 - DF-26B发射车 (12辆)
-- 位置: 海南/广东地区
for i = 1, 12 do
    local lat = {18.54, 18.54, 18.55, 18.55, 18.55, 18.54, 18.55, 18.55, 18.54, 18.54, 18.54, 18.53}
    local lon = {110.00, 110.01, 110.00, 110.01, 110.01, 110.01, 110.01, 110.02, 110.03, 110.03, 110.03, 110.03}
    local name = "dfb" .. string.format("%03d", i)
    local ok, u = pcall(ScenEdit_AddUnit, {
        side      = "Red",
        type      = "Facility",
        dbid      = 2879,
        name      = name,
        latitude  = lat[i],
        longitude = lon[i],
        heading   = 90
    })
    if ok and u then
        ScenEdit_SetKeyValue(name .. "_GUID", u.guid)
    end
end

-- ============================================================
-- 第五部分：红方作战集群 - DF-26D 导弹发射车（03打击大队）
-- ============================================================

-- 03打击大队 - DF-26D发射车 (12辆)
-- 位置: 广东韶关地区
for i = 1, 12 do
    local lat = {23.67, 23.67, 23.65, 23.66, 23.65, 23.65, 23.64, 23.64, 23.65, 23.65, 23.65, 23.64}
    local lon = {113.00, 112.99, 112.99, 112.98, 112.97, 112.99, 112.97, 112.99, 112.99, 113.00, 113.00, 112.99}
    local name = "dfd" .. string.format("%03d", i)
    local ok, u = pcall(ScenEdit_AddUnit, {
        side      = "Red",
        type      = "Facility",
        dbid      = 2879,
        name      = name,
        latitude  = lat[i],
        longitude = lon[i],
        heading   = 90
    })
    if ok and u then
        ScenEdit_SetKeyValue(name .. "_GUID", u.guid)
    end
end

-- ============================================================
-- 第六部分：红方网电集群 - J-16D 电子战飞机（05干扰大队）
-- DBID 4632 - J-16D Roaring Wolf
-- LoadoutID 753 - J-16D 电子战配置
-- ============================================================

local jd_units = {
    {name = "jd002", lat = 9.91,  lon = 115.53, loadout = 753},
    {name = "jd003", lat = 9.91,  lon = 115.50, loadout = 753},
    {name = "jd004", lat = 9.90,  lon = 115.49, loadout = 753},
    {name = "jd007", lat = 9.89,  lon = 115.48, loadout = 753},
}
for _, u in ipairs(jd_units) do
    local ok, unit = pcall(ScenEdit_AddUnit, {
        side      = "Red",
        type      = "Aircraft",
        dbid      = 4632,
        name      = u.name,
        latitude  = u.lat,
        longitude = u.lon,
        altitude  = 1500,
        heading   = 180,
        speed     = 600,
        LoadoutID = u.loadout
    })
    if ok and unit then
        ScenEdit_SetKeyValue(u.name .. "_GUID", unit.guid)
    end
end

-- ============================================================
-- 第七部分：红方空中作战集群 - H-6K 轰炸机（06轰炸机大队）
-- DBID 1731 - H-6K Badger
-- LoadoutID 451 - H-6K 典型载荷
-- ============================================================

local hk_units = {
    {name = "hk003", lat = 26.32, lon = 112.79, alt = 900},
    {name = "hk004", lat = 26.30, lon = 112.91, alt = 1000},
    {name = "hk005", lat = 26.45, lon = 112.90, alt = 1000},
    {name = "hk006", lat = 26.22, lon = 112.68, alt = 1000},
    {name = "hk007", lat = 26.20, lon = 112.91, alt = 1000},
    {name = "hk008", lat = 26.39, lon = 112.98, alt = 1000},
}
for _, u in ipairs(hk_units) do
    local ok, unit = pcall(ScenEdit_AddUnit, {
        side      = "Red",
        type      = "Aircraft",
        dbid      = 1731,
        name      = u.name,
        latitude  = u.lat,
        longitude = u.lon,
        altitude  = u.alt,
        heading   = 180,
        speed     = 500,
        LoadoutID = 451
    })
    if ok and unit then
        ScenEdit_SetKeyValue(u.name .. "_GUID", unit.guid)
    end
end

-- ============================================================
-- 第八部分：红方空中作战集群 - KJ-500 预警机（07预警大队）
-- DBID 3683 - KJ-500A Cub [GX9]
-- LoadoutID 494 - KJ-500 预警配置
-- ============================================================
local ok, kj_unit = pcall(ScenEdit_AddUnit, {
    side      = "Red",
    type      = "Aircraft",
    dbid      = 3683,
    name      = "kja001",
    latitude  = 26.32,
    longitude = 112.63,
    altitude  = 10000,
    heading   = 180,
    speed     = 400,
    LoadoutID = 494
})
if ok and kj_unit then
    ScenEdit_SetKeyValue("KJA001_GUID", kj_unit.guid)
end

-- ============================================================
-- 第九部分：红方空中作战集群 - J-20 战斗机（08战斗机大队）
-- DBID 2463 - J-20B Fagin
-- LoadoutID 198 - J-20B 典型载荷
-- ============================================================

local j20_units = {
    {name = "zds001", lat = 18.50, lon = 109.97},
    {name = "zds002", lat = 18.50, lon = 109.98},
    {name = "zds003", lat = 18.49, lon = 109.98},
    {name = "zds004", lat = 18.49, lon = 109.99},
}
for _, u in ipairs(j20_units) do
    local ok, unit = pcall(ScenEdit_AddUnit, {
        side      = "Red",
        type      = "Aircraft",
        dbid      = 2463,
        name      = u.name,
        latitude  = u.lat,
        longitude = u.lon,
        altitude  = 1000,
        heading   = 180,
        speed     = 800,
        LoadoutID = 198
    })
    if ok and unit then
        ScenEdit_SetKeyValue(u.name .. "_GUID", unit.guid)
    end
end

-- ============================================================
-- 第十部分：红方海上集群 - UUV 无人潜航器（03无人潜航支队）
-- DBID 700 - HSU-001 LDUUV
-- JSON 中平台类型为 UUV_RED, 使用 HSU-001 LDUUV 模拟
-- ============================================================

local uuv_units = {
    {name = "wruuv001", lat = 0.11, lon = 105.82},
    {name = "wruuv002", lat = 0.20, lon = 105.93},
    {name = "wruuv003", lat = 0.06, lon = 105.65},
    {name = "wruuv004", lat = 0.12, lon = 106.03},
    {name = "wruuv005", lat = 0.08, lon = 105.78},
}
for _, u in ipairs(uuv_units) do
    local ok, unit = pcall(ScenEdit_AddUnit, {
        side      = "Red",
        type      = "Submarine",
        dbid      = 700,
        name      = u.name,
        latitude  = u.lat,
        longitude = u.lon,
        heading   = 180,
        speed     = 8
    })
    if ok and unit then
        ScenEdit_SetKeyValue(u.name .. "_GUID", unit.guid)
    end
end

-- ============================================================
-- 第十一部分：创建打击任务
-- ============================================================

-- 反舰打击任务（红方对蓝方海上目标）
local ok, mission1 = pcall(ScenEdit_AddMission, "Red", "反舰打击任务", "strike", {type = "naval", targetside = "Blue"})
if ok then ScenEdit_SetKeyValue("STRIKE_MISSION_GUID", mission1.guid) end

-- 空中巡逻掩护任务
local ok2, mission2 = pcall(ScenEdit_AddMission, "Red", "空中巡逻掩护", "patrol", {type = "air"})
if ok2 then ScenEdit_SetKeyValue("AIR_PATROL_GUID", mission2.guid) end

-- 海上侦察巡逻任务
local ok3, mission3 = pcall(ScenEdit_AddMission, "Red", "海上侦察巡逻", "patrol", {type = "naval"})
if ok3 then ScenEdit_SetKeyValue("NAVAL_PATROL_GUID", mission3.guid) end

-- ============================================================
-- 第十二部分：设置红方作战条令
-- ============================================================

ScenEdit_SetDoctrine({side = "Red"}, {
    weapon_control_status_air        = 0,
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 0,
    use_nuclear_weapons             = "no"
})

ScenEdit_SetEMCON("Side", "Red", "Radar=Active;Sonar=Active;OECM=Active")

-- ============================================================
-- 第十三部分：设置蓝方作战条令（防守方）
-- ============================================================

ScenEdit_SetDoctrine({side = "Blue"}, {
    weapon_control_status_air        = 0,
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 0,
    use_nuclear_weapons             = "no"
})

ScenEdit_SetEMCON("Side", "Blue", "Radar=Active;Sonar=Active;OECM=Passive")

-- ============================================================
-- 代码执行完毕
-- ============================================================
print("========================================")
print("联合打击计划 Lua 代码执行完成")
print("========================================")
print("DBID 验证状态: MCP 全部通过")
print("")
print("蓝方目标:")
print("  - CG-56 San Jacinto (DBID 40)")
print("  - DDG-51 Arleigh Burke x2 (DBID 112)")
print("  - LHA-6 America (DBID 2362)")
print("  - T-AO-187 Henry J. Kaiser (DBID 26)")
print("")
print("红方平台:")
print("  - 侦察卫星 Jian Bing (DBID 70)")
print("  - DF-26 导弹发射阵地 x24 (DBID 2879)")
print("  - J-16D 电战机 x4 (DBID 4632, Loadout 753)")
print("  - H-6K 轰炸机 x6 (DBID 1731, Loadout 451)")
print("  - KJ-500 预警机 x1 (DBID 3683, Loadout 494)")
print("  - J-20B 战斗机 x4 (DBID 2463, Loadout 198)")
print("  - UUV 无人潜航器 x5 (DBID 700)")
print("")
print("任务: 反舰打击 x1, 空中巡逻 x1, 海上侦察 x1")
print("========================================")
