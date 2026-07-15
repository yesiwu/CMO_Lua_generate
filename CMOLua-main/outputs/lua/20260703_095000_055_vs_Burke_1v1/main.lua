-- ============================================================
-- 场景初始化脚本
-- 红方055 vs 蓝方DDG-113 1v1场景
-- 南海区域
-- ============================================================

local LOG_PREFIX = "[CMO]"
local function log(level, msg) print(LOG_PREFIX .. " [" .. level .. "] " .. msg) end
local function info(msg) log("INFO",    msg) end
local function ok(msg)   log("SUCCESS", msg) end

info("=== 初始化场景 ===")

-- ---------- 创建红方 ----------
info("创建红方...")
ScenEdit_AddSide({name = "红方", color = "255,0,0"})

-- ---------- 创建蓝方 ----------
info("创建蓝方...")
ScenEdit_AddSide({name = "蓝方", color = "0,0,255"})

-- ---------- 设置红蓝敌对关系 ----------
info("设置红蓝敌对关系...")
ScenEdit_SetSidePosture("红方", "蓝方", "H")  -- 红方视蓝方为敌对
ScenEdit_SetSidePosture("蓝方", "红方", "H")  -- 蓝方视红方为敌对

-- ---------- 红方全知全能 ----------
info("设置红方全知全能...")
ScenEdit_SetSideOptions({side = "红方", awareness = "OMNI"})

-- ---------- 部署红方055 ----------
-- 位置：南海某处 (约北纬15度，东经115度附近)
local red_unit = ScenEdit_AddUnit({
    side        = "红方",
    type        = "Ship",
    name        = "055-南昌舰",
    dbid        = 3883,
    latitude    = 15.0,
    longitude   = 115.0,
    heading     = 90,
    speed       = 15,
    proficiency = "Veteran",
})
if red_unit and red_unit.guid then
    ScenEdit_SetKeyValue("RED_055_GUID", red_unit.guid)
    ok("红方055已部署: " .. red_unit.guid)
else
    print(LOG_PREFIX .. " [ERROR] 红方055部署失败")
end

-- ---------- 部署蓝方DDG-113 ----------
-- 位置：南海某处，与055相距约100海里
local blue_unit = ScenEdit_AddUnit({
    side            = "蓝方",
    type            = "Ship",
    name            = "DDG-113",
    dbid            = 4299,
    latitude        = 13.5,
    longitude       = 117.0,
    heading         = 270,
    speed           = 12,
    proficiency     = "Veteran",
    autodetectable  = true,  -- 关键：蓝方目标必须可被探测
})
if blue_unit and blue_unit.guid then
    ScenEdit_SetKeyValue("BLUE_DDG_GUID", blue_unit.guid)
    ok("蓝方DDG-113已部署: " .. blue_unit.guid)
    -- 双保险：再次设置autodetectable
    pcall(ScenEdit_SetUnit, {guid = blue_unit.guid, autodetectable = true})
else
    print(LOG_PREFIX .. " [ERROR] 蓝方DDG-113部署失败")
end

info("=== 场景初始化完成 ===")
print("")
print("=== 下一步操作 ===")
print("1. 运行 clear.lua 清空055待发弹")
print("2. 运行 reload.lua 装填16枚YJ-18")
print("3. 运行 attack.lua 发射13枚YJ-18攻击DDG-113")
