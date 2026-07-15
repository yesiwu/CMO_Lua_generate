-- 添加飞机模板
-- ============================================================================
-- ⚠ Aircraft 必须有 LoadoutID（MCP read_query DataAircraftLoadouts 查询）
-- 变量说明：
--   {{SIDE}}        - 阵营名称
--   {{UNIT_NAME}}   - 单位名称
--   {{DBID}}        - 装备 DBID（通过 MCP query_dbid 查询获得）
--   {{LOADOUT_ID}}  - 挂载 ID（通过 MCP read_query DataAircraftLoadouts 查询，必须为数值）
--   {{BASE}}        - 基地名称（可选，不填则用经纬度定位）
--   {{LATITUDE}}    - 纬度
--   {{LONGITUDE}}   - 经度
--   {{ALTITUDE}}    - 高度（米，不加 FT 后缀）
-- ============================================================================

-- 方式1：指定基地
ScenEdit_AddUnit({
    side      = "{{SIDE}}",
    type      = "Aircraft",
    name      = "{{UNIT_NAME}}",
    dbid      = {{DBID}},
    LoadoutID = {{LOADOUT_ID}},   -- ★ 必须（数值）
    base      = "{{BASE}}"         -- 可选
})

-- 方式2：指定经纬度+高度（从基地外挂载到指定位置）
ScenEdit_AddUnit({
    side      = "{{SIDE}}",
    type      = "Aircraft",
    name      = "{{UNIT_NAME}}",
    dbid      = {{DBID}},
    LoadoutID = {{LOADOUT_ID}},   -- ★ 必须（数值）
    latitude  = "{{LATITUDE}}",
    longitude = "{{LONGITUDE}}",
    altitude  = {{ALTITUDE}},    -- 米（数值类型，不加引号）
    heading   = 90,
    speed     = 450,
})

-- 示例：添加 F-16 到 Blue 阵营（指定基地）
-- ScenEdit_AddUnit({
--     side      = "Blue",
--     type      = "Aircraft",
--     name      = "F-16 #1",
--     dbid      = 322,           -- MCP query_dbid("F-16C Blk 52")
--     LoadoutID = 122,           -- MCP read_query("DataAircraftLoadouts WHERE ComponentID=322")
--     base      = "Osan AFB"
-- })

-- 示例：添加 F-16 到指定位置（外挂载）
-- ScenEdit_AddUnit({
--     side      = "Blue",
--     type      = "Aircraft",
--     name      = "F-16 #2",
--     dbid      = 322,
--     LoadoutID = 122,
--     latitude  = "35.0",
--     longitude = "129.1",
--     altitude  = 5000,          -- 米（数值，不是 "5000"）
--     heading   = 90,
--     speed     = 450,
-- })

-- 示例：添加 EA-18G 电子战机（无硬点挂载 YJ-83 的 Loadout）
-- ScenEdit_AddUnit({
--     side      = "红方",
--     type      = "Aircraft",
--     name      = "EA-18G #1",
--     dbid      = 343,           -- MCP query_dbid("EA-18G Growler")
--     LoadoutID = 102,           -- MCP read_query("DataAircraftLoadouts WHERE ComponentID=343")
--     latitude  = "28.5",
--     longitude = "124.0",
--     altitude  = 9144,
--     heading   = 90,
--     speed     = 250,
-- })
