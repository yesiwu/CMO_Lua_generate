-- ============================================================
-- 1v1 对决：红方055 vs 蓝方Burke
-- 场景：南海，055装16枚YJ-18，发射12枚攻击Burke
-- 生成时间：2026-07-03 09:08
-- ============================================================

-- ---------- 日志工具 ----------
local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO", msg) end
local function warn(msg) log("WARNING", msg) end
local function err(msg) log("ERROR", msg) end
local function ok(msg) log("SUCCESS", msg) end

info("=== 1v1 场景：055 vs Burke ===")

-- ---------- 配置区 ----------
local CFG_SIDE_RED = "红方"
local CFG_SIDE_BLUE = "蓝方"

-- 055驱逐舰 (DBID 3883 - Type 055 Renhai with YJ-21)
local UNIT_055 = {
    name = "055-Nanchang",
    dbid = 3883,
    latitude = 14.5,      -- 南海中部
    longitude = 113.5,
    heading = 0,
    speed = 15,
    proficiency = "Veteran"
}

-- Burke驱逐舰 (DBID 2868 - DDG 51 Arleigh Burke Flight I)
local UNIT_BURKE = {
    name = "DDG-51-Burke",
    dbid = 2868,
    latitude = 15.2,      -- 055北方约40海里
    longitude = 113.8,
    heading = 180,
    speed = 12,
    proficiency = "Veteran"
}

-- ---------- 创建阵营 ----------
info("创建阵营...")
local sides_created = {}
for _, side in ipairs({CFG_SIDE_RED, CFG_SIDE_BLUE}) do
    local ok_result = pcall(ScenEdit_AddSide, {name = side})
    if ok_result then
        info("  阵营 " .. side .. " 就绪")
        sides_created[side] = true
    end
end

-- ---------- 设置敌对关系 ----------
info("设置敌对关系...")
ScenEdit_SetSidePosture(CFG_SIDE_RED, CFG_SIDE_BLUE, "H")   -- 红方视蓝方为敌对
ScenEdit_SetSidePosture(CFG_SIDE_BLUE, CFG_SIDE_RED, "H")   -- 蓝方视红方为敌对

-- ---------- 红方全知全能 ----------
info("红方设置全知全能...")
pcall(ScenEdit_SetSideOptions, {side = CFG_SIDE_RED, awareness = "OMNI"})

-- ---------- 创建055驱逐舰 ----------
info("创建红方055驱逐舰...")
local result_055 = ScenEdit_AddUnit({
    side = CFG_SIDE_RED,
    type = "Ship",
    name = UNIT_055.name,
    dbid = UNIT_055.dbid,
    latitude = UNIT_055.latitude,
    longitude = UNIT_055.longitude,
    heading = UNIT_055.heading,
    speed = UNIT_055.speed,
    proficiency = UNIT_055.proficiency,
    autodetectable = true  -- 让蓝方也能发现红方（对称设置）
})

if result_055 and result_055.guid then
    ScenEdit_SetKeyValue("055_GUID", result_055.guid)
    ok("055创建成功: " .. result_055.guid)
else
    err("055创建失败!")
end

-- ---------- 创建Burke驱逐舰 ----------
info("创建蓝方Burke驱逐舰...")
local result_burke = ScenEdit_AddUnit({
    side = CFG_SIDE_BLUE,
    type = "Ship",
    name = UNIT_BURKE.name,
    dbid = UNIT_BURKE.dbid,
    latitude = UNIT_BURKE.latitude,
    longitude = UNIT_BURKE.longitude,
    heading = UNIT_BURKE.heading,
    speed = UNIT_BURKE.speed,
    proficiency = UNIT_BURKE.proficiency,
    autodetectable = true  -- 关键！红方全知但目标必须有此标记才能生成contact
})

if result_burke and result_burke.guid then
    ScenEdit_SetKeyValue("BURKE_GUID", result_burke.guid)
    ok("Burke创建成功: " .. result_burke.guid)
else
    err("Burke创建失败!")
end

-- ---------- 装弹16枚YJ-18 ----------
-- YJ-18 DBID: 2867 (侵彻弹头版) 或 2868 (标准版)
local YJ18_DBID = 2867
info("装弹16枚YJ-18 (DBID=" .. YJ18_DBID .. ")...")

pcall(ScenEdit_AddReloadsToUnit, {
    side = CFG_SIDE_RED,
    unitname = UNIT_055.name,
    wpn_dbid = YJ18_DBID,
    number = 16
})

-- ---------- 输出目标坐标信息 ----------
local tgt = ScenEdit_GetUnit({side = CFG_SIDE_BLUE, name = UNIT_BURKE.name})
if tgt then
    info("目标坐标: " .. string.format("%.4f, %.4f", tgt.latitude, tgt.longitude))
    info("目标航向: " .. tgt.heading .. "°, 航速: " .. tgt.speed .. "节")
end

ok("=== 主脚本执行完毕 ===")
ok("下一步: 运行 reload.lua 装弹，然后 attack.lua 发射")
