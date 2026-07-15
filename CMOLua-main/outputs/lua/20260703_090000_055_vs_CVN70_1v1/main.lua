-- ============================================================
-- main.lua — 红蓝 1v1 对抗: 055 vs CVN-70
-- 地点: 南海
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- 配置
-- ============================================================
local CFG_SIDE_RED   = "红方"
local CFG_SIDE_BLUE  = "蓝方"

-- DBID
local DBID_055       = 3883    -- Type 055 Nanchang
local DBID_CVN70     = 3551    -- CVN 70 Carl Vinson

-- 位置 (南海)
local RED_055_LAT    = 18.5
local RED_055_LON    = 116.0
local BLUE_CVN70_LAT  = 16.0
local BLUE_CVN70_LON  = 118.0

-- ============================================================
-- 创建红方阵营
-- ============================================================
local ok, err = pcall(ScenEdit_AddSide, {name = CFG_SIDE_RED})
if not ok then print("[CMO] 红方阵营可能已存在: " .. tostring(err)) end

-- ============================================================
-- 创建蓝方阵营
-- ============================================================
local ok, err = pcall(ScenEdit_AddSide, {name = CFG_SIDE_BLUE})
if not ok then print("[CMO] 蓝方阵营可能已存在: " .. tostring(err)) end

-- ============================================================
-- 设置红方 OMNI (全知)
-- ============================================================
pcall(ScenEdit_SetSideOptions, {side = CFG_SIDE_RED, awareness = "OMNI"})

-- ============================================================
-- 创建 055 驱逐舰
-- ============================================================
print("[CMO] 创建红方 055-Nanchang...")
local ok055, err055 = pcall(ScenEdit_AddUnit, {
    side     = CFG_SIDE_RED,
    type     = "Ship",
    dbid     = DBID_055,
    name     = "055-Nanchang",
    latitude  = RED_055_LAT,
    longitude = RED_055_LON,
    heading  = 180,
    speed    = 15,
    autodetectable = true
})
if ok055 then
    print("[CMO] 055-Nanchang 创建成功")
else
    print("[CMO] 055-Nanchang 创建失败: " .. tostring(err055))
end

-- ============================================================
-- 创建 CVN-70 航母
-- ============================================================
print("[CMO] 创建蓝方 CVN-70...")
local okCVN, errCVN = pcall(ScenEdit_AddUnit, {
    side     = CFG_SIDE_BLUE,
    type     = "Ship",
    dbid     = DBID_CVN70,
    name     = "CVN-70",
    latitude  = BLUE_CVN70_LAT,
    longitude = BLUE_CVN70_LON,
    heading  = 0,
    speed    = 20,
    autodetectable = true
})
if okCVN then
    print("[CMO] CVN-70 创建成功")
else
    print("[CMO] CVN-70 创建失败: " .. tostring(errCVN))
end

-- ============================================================
-- 设置阵营态度
-- ============================================================
pcall(ScenEdit_SetSidePosture, CFG_SIDE_RED, CFG_SIDE_BLUE, "H")  -- 红方敌视蓝方
pcall(ScenEdit_SetSidePosture, CFG_SIDE_BLUE, CFG_SIDE_RED, "H")  -- 蓝方敌视红方

print("[CMO] === main.lua 执行完毕 ===")
print("[CMO] 下一步: 执行 reload.lua 装填导弹")
