-- ============================================================================
-- 添加单位模板（通用）
-- ============================================================================
-- 变量说明：
--   {{SIDE}}        - 阵营名称（如 "红方"、"蓝方"）
--   {{UNIT_NAME}}   - 单位名称（所有脚本中必须保持一致）
--   {{DBID}}        - 装备 DBID（必须通过 MCP query_dbid 查询获得）
--   {{LATITUDE}}    - 纬度（十进制，如 35.6762）
--   {{LONGITUDE}}   - 经度（十进制，如 139.6503）
--   {{ALTITUDE}}    - 高度（飞机用，米；舰艇/潜艇填 0）
--
-- ⚠ Aircraft 专用变量：
--   {{LOADOUT_ID}}  - 挂载 ID（必须通过 MCP read_query 查询 DataAircraftLoadouts）
--                    SQL: SELECT ID FROM DataAircraftLoadouts WHERE ComponentID = {{DBID}}
--                    ⚠ 必须是数值类型（不能是字符串）！
--   {{BASE}}        - 基地名称（可选，不填则用经纬度定位）
-- ============================================================================

-- ============================================================
-- Aircraft（飞机）：必须提供 LoadoutID
-- ============================================================
-- 步骤：
--   1. MCP query_dbid("J-16") → 获取 DBID（如 2853）
--   2. MCP read_query("SELECT ID FROM DataAircraftLoadouts WHERE ComponentID=2853") → 获取 LoadoutID 列表
--   3. 选一个 LoadoutID（如 1821），填入下方
ScenEdit_AddUnit({
    side        = "{{SIDE}}",
    type        = "Aircraft",
    name        = "{{UNIT_NAME}}",
    dbid        = {{DBID}},          -- MCP 查询结果
    LoadoutID   = {{LOADOUT_ID}},   -- ★ 必须：MCP read_query DataAircraftLoadouts
    latitude    = "{{LATITUDE}}",
    longitude   = "{{LONGITUDE}}",
    altitude    = "{{ALTITUDE}}",   -- 米
    heading     = 90,
    speed       = 450,
    proficiency = "Regular",
})

-- ============================================================
-- Ship（舰艇）：不需要 LoadoutID
-- ============================================================
ScenEdit_AddUnit({
    side        = "{{SIDE}}",
    type        = "Ship",
    name        = "{{UNIT_NAME}}",
    dbid        = {{DBID}},          -- MCP 查询结果
    latitude    = "{{LATITUDE}}",
    longitude   = "{{LONGITUDE}}",
    heading     = 45,
    speed       = 20,
    proficiency = "Veteran",
})

-- ============================================================
-- Submarine（潜艇）：不需要 LoadoutID
-- ============================================================
ScenEdit_AddUnit({
    side        = "{{SIDE}}",
    type        = "Submarine",
    name        = "{{UNIT_NAME}}",
    dbid        = {{DBID}},          -- MCP 查询结果
    latitude    = "{{LATITUDE}}",
    longitude   = "{{LONGITUDE}}",
    altitude    = "{{ALTITUDE}}",   -- 深度（米，负值）
    heading     = 180,
    speed       = 5,
    proficiency = "Regular",
})

-- ============================================================
-- Facility（地面设施）：不需要 LoadoutID
-- ============================================================
ScenEdit_AddUnit({
    side        = "{{SIDE}}",
    type        = "Facility",
    name        = "{{UNIT_NAME}}",
    dbid        = {{DBID}},          -- MCP 查询结果
    latitude    = "{{LATITUDE}}",
    longitude   = "{{LONGITUDE}}",
})
