-- ============================================================
-- main.lua - 055 vs Burke 1v1 场景生成
-- 场景: 南海对抗，红方055攻击蓝方Burke
-- ============================================================

local LOG_PREFIX = "[CMO-MAIN]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO", msg) end
local function ok(msg) log("SUCCESS", msg) end

-- ---------- 配置区 ----------
-- 单位 DBID（MCP查询 + 用户指定）
local DBID_055 = 3883        -- Type 055 Renhai [101 Nanchang] (YJ-21版)
local DBID_BURKE = 112      -- DDG-51 Arleigh Burke [Arleigh Burke Flight I]
local DBID_YJ18 = 2868       -- YJ-18 (用户提供)

-- 坐标（南海）
local LAT_055 = 15.0         -- N15.00.00
local LON_055 = 115.0       -- E115.00.00
local LAT_BURKE = 16.0      -- N16.00.00
local LON_BURKE = 118.0     -- E118.00.00

-- 单位名称（所有脚本必须保持一致！）
local NAME_055 = "055-Nanchang"
local NAME_BURKE = "DDG-51-Burke"

-- ---------- 创建阵营 ----------
info("=== 创建红蓝双方 ===")

ScenEdit_AddSide({name = "红方", color = "255,0,0"})
ok("红方 创建完成")

ScenEdit_AddSide({name = "蓝方", color = "0,0,255"})
ok("蓝方 创建完成")

-- ---------- 设置敌对关系 ----------
info("=== 设置敌对关系 ===")
ScenEdit_SetSidePosture("红方", "蓝方", "H")  -- 红方视蓝方为敌对
ScenEdit_SetSidePosture("蓝方", "红方", "H")  -- 蓝方视红方为敌对
ok("敌对关系设置完成")

-- ---------- 红方全知全能 ----------
info("=== 设置红方全知全能 ===")
ScenEdit_SetSideOptions({side = "红方", awareness = "OMNI"})
ok("红方 已设置为全知全能 (OMNI)")

-- ---------- 创建红方055 ----------
info("=== 创建红方单位 ===")
local unit_055 = ScenEdit_AddUnit({
    side        = "红方",
    type        = "Ship",
    name        = NAME_055,
    dbid        = DBID_055,
    latitude    = LAT_055,
    longitude   = LON_055,
    heading     = 45,
    speed       = 15,
    autodetectable = true,
    proficiency = "Veteran"
})

if unit_055 and unit_055.guid then
    ScenEdit_SetKeyValue("055_GUID", unit_055.guid)
    ok("055-Nanchang 创建完成 (GUID: " .. unit_055.guid .. ")")
else
    print(LOG_PREFIX .. " [ERROR] 055创建失败")
end

-- ---------- 创建蓝方Burke（目标） ----------
info("=== 创建蓝方单位 ===")
local unit_burke = ScenEdit_AddUnit({
    side        = "蓝方",
    type        = "Ship",
    name        = NAME_BURKE,
    dbid        = DBID_BURKE,
    latitude    = LAT_BURKE,
    longitude   = LON_BURKE,
    heading     = 180,
    speed       = 12,
    autodetectable = true,  -- 关键：必须设置，红方才能稳定拿到contact
    proficiency = "Veteran"
})

if unit_burke and unit_burke.guid then
    ScenEdit_SetKeyValue("BURKE_GUID", unit_burke.guid)
    ok("DDG-51-Burke 创建完成 (GUID: " .. unit_burke.guid .. ")")
else
    print(LOG_PREFIX .. " [ERROR] Burke创建失败")
end

-- ---------- 创建后再次设置autodetectable（双保险） ----------
info("=== 二次设置蓝方autodetectable ===")
if unit_burke and unit_burke.guid then
    pcall(ScenEdit_SetUnit, {guid = unit_burke.guid, autodetectable = true})
    ok("Burke autodetectable 已确认")
end

-- ---------- 输出场景信息 ----------
print("")
print("=================================================")
print("  055 vs Burke 1v1 场景生成完毕")
print("=================================================")
print("  红方: 055-Nanchang (DBID " .. DBID_055 .. ")")
print("        位置: N" .. LAT_055 .. ".00.00, E" .. LON_055 .. ".00.00")
print("")
print("  蓝方: DDG-51-Burke (DBID " .. DBID_BURKE .. ")")
print("        位置: N" .. LAT_BURKE .. ".00.00, E" .. LON_BURKE .. ".00.00")
print("")
print("  下一步: 运行 clear.lua → reload.lua → attack.lua")
print("=================================================")
print("")
