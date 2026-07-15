-- ============================================================
-- main.lua — 红方5舰 vs 蓝方5舰 反舰导弹饱和打击仿真
-- 场景：联合火力突击（替代方案 B）
-- 使用方式：CMO Lua 控制台依次执行 main.lua → clear.lua → reload.lua → attack.lua
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- ① 创建双方阵营
-- ============================================================
local ok, err = pcall(ScenEdit_AddSide, { name = "蓝方" })
if not ok then print("[CMO] 蓝方可能已存在: " .. tostring(err)) end

ok, err = pcall(ScenEdit_AddSide, { name = "红方" })
if not ok then print("[CMO] 红方可能已存在: " .. tostring(err)) end

-- ============================================================
-- ② 敌对关系
-- ============================================================
ScenEdit_SetSidePosture("红方", "蓝方", "H")
ScenEdit_SetSidePosture("蓝方", "红方", "H")

-- ============================================================
-- ③ 红方全知全能（OMNI）
-- ============================================================
ScenEdit_SetSideOptions({ side = "红方", awareness = "OMNI" })
ScenEdit_SetEMCON("Side", "红方", "Radar=Active;Sonar=Passive;OECM=Active")

-- ============================================================
-- ④ 红方单位
-- ============================================================

-- Red 052D-1
ScenEdit_AddUnit({
    side     = "红方", type = "Ship",
    name     = "Red-052D-1",
    dbid     = 2296,   -- Type 052D Luyang III
    latitude  = 20.9500, longitude = 123.6000,
    heading   = 105.00, speed = 0,
    proficiency = "Veteran",
})

-- Red 052D-2
ScenEdit_AddUnit({
    side     = "红方", type = "Ship",
    name     = "Red-052D-2",
    dbid     = 2296,
    latitude  = 18.6000, longitude = 124.0500,
    heading   = 45.00, speed = 0,
    proficiency = "Veteran",
})

-- Red 052D-3
ScenEdit_AddUnit({
    side     = "红方", type = "Ship",
    name     = "Red-052D-3",
    dbid     = 2296,
    latitude  = 22.2000, longitude = 124.8000,
    heading   = 95.00, speed = 0,
    proficiency = "Veteran",
})

-- Red 055-1
ScenEdit_AddUnit({
    side     = "红方", type = "Ship",
    name     = "Red-055-1",
    dbid     = 2834,   -- Type 055 Renhai
    latitude  = 24.7000, longitude = 128.3000,
    heading   = 140.00, speed = 0,
    proficiency = "Veteran",
})

-- Red 055-2
ScenEdit_AddUnit({
    side     = "红方", type = "Ship",
    name     = "Red-055-2",
    dbid     = 2834,
    latitude  = 23.5000, longitude = 127.2000,
    heading   = 125.00, speed = 0,
    proficiency = "Veteran",
})

-- ============================================================
-- ⑤ 蓝方单位
-- ============================================================

-- Blue DDG-1（阿利·伯克 Flight I）
ScenEdit_AddUnit({
    side     = "蓝方", type = "Ship",
    name     = "Blue-DDG-1",
    dbid     = 112,    -- DDG 51 Arleigh Burke
    latitude  = 21.6200, longitude = 130.0500,
    heading   = 292.00, speed = 0,
    proficiency = "Veteran",
})

-- Blue DDG-2（提康德罗加 Baseline 3，DM 用户指定 DBID=2862）
ScenEdit_AddUnit({
    side     = "蓝方", type = "Ship",
    name     = "Blue-DDG-2",
    dbid     = 2862,   -- CG 59 Princeton
    latitude  = 21.4800, longitude = 130.2400,
    heading   = 291.50, speed = 0,
    proficiency = "Veteran",
})

-- Blue FFG-1（DM 用户指定 DBID=3551，即 CVN 70）
ScenEdit_AddUnit({
    side     = "蓝方", type = "Ship",
    name     = "Blue-FFG-1",
    dbid     = 3551,   -- CVN 70 Carl Vinson（用户指定）
    latitude  = 21.3600, longitude = 129.8500,
    heading   = 293.00, speed = 0,
    proficiency = "Veteran",
})

-- Blue AOR-1（综合补给舰）
ScenEdit_AddUnit({
    side     = "蓝方", type = "Ship",
    name     = "Blue-AOR-1",
    dbid     = 490,    -- AOE 6 Supply
    latitude  = 21.5600, longitude = 130.4100,
    heading   = 290.00, speed = 0,
    proficiency = "Veteran",
})

-- Blue LPD-1（黄蜂级两栖攻击舰）
ScenEdit_AddUnit({
    side     = "蓝方", type = "Ship",
    name     = "Blue-LPD-1",
    dbid     = 428,    -- LHD 2 Essex
    latitude  = 21.2500, longitude = 130.1200,
    heading   = 292.50, speed = 0,
    proficiency = "Veteran",
})

print("[CMO] main.lua 执行完毕 — 5红5蓝已创建")
print("[CMO] 红方全知模式: OMNI")
print("[CMO] 下一步: clear.lua")
