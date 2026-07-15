-- ============================================================
-- main.lua  — 6舰对抗仿真主脚本（蓝方3舰 vs 红方3舰）
-- 使用方式：在 CMO Lua 控制台依次执行 main.lua → reload.lua → attack.lua
-- MCP DBID 来源：
--   蓝方: DDG-113=112(CG59), DBID2862=2869, DBID3551=3551
--   红方: 052D=2296, 055=2834
--   武器: YJ-21=4058, YJ-18=2868
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- ① 创建双方阵营
-- ============================================================
local ok, err = pcall(ScenEdit_AddSide, {name = '蓝方'})
if not ok then print('[CMO] 蓝方阵营可能已存在: ' .. tostring(err)) end

ok, err = pcall(ScenEdit_AddSide, {name = '红方'})
if not ok then print('[CMO] 红方阵营可能已存在: ' .. tostring(err)) end

-- ============================================================
-- ② 敌对关系设定
-- ============================================================
ScenEdit_SetSidePosture('红方', '蓝方', 'H')
ScenEdit_SetSidePosture('蓝方', '红方', 'H')

-- 红方：全知全能模式（无限视野，所有目标自动发现）
ScenEdit_SetSideOptions({side = '红方', awareness = 'OMNI'})

-- 红方 doctrine：打击规则自由
ScenEdit_SetDoctrine({side = '红方'}, {
    weapon_control_status_air     = 0,
    weapon_control_status_surface = 0,
    weapon_control_status_subsurface = 0,
    ignore_plotted_course        = 'no',
    use_nuclear_weapons          = 'no',
})

-- ============================================================
-- ③ 创建蓝方单位（3艘）
-- ============================================================

-- 蓝方-1: DDG-113 (Arleigh Burke) — 用户指定 DBID 不可查，用 CG59 替代
local u1 = ScenEdit_AddUnit({
    side     = '蓝方',
    type     = 'Ship',
    name     = 'DDG-113',
    dbid     = 112,       -- DDG 51 Arleigh Burke (替代 DDG 113)
    latitude  = 21.5419,
    longitude = 129.9125,
    heading   = 294.05,
    speed     = 0,
    proficiency = 'Veteran',
})
if u1 and u1.guid then
    ScenEdit_SetKeyValue('BLUE_DDG113_GUID', u1.guid)
    print('[CMO] 蓝方 DDG-113 创建完成, GUID=' .. u1.guid)
else
    print('[CMO] [ERROR] 蓝方 DDG-113 创建失败')
end

-- 蓝方-2: 用户指定 DBID 2862 → CG 59 Princeton
local u2 = ScenEdit_AddUnit({
    side     = '蓝方',
    type     = 'Ship',
    name     = 'Blue-CG59',
    dbid     = 2869,      -- CG 59 Princeton (用户指定 DBID 2862 对应)
    latitude  = 21.6100,
    longitude = 130.1791,
    heading   = 294.58,
    speed     = 0,
    proficiency = 'Veteran',
})
if u2 and u2.guid then
    ScenEdit_SetKeyValue('BLUE_CG59_GUID', u2.guid)
    print('[CMO] 蓝方 CG-59 创建完成, GUID=' .. u2.guid)
else
    print('[CMO] [ERROR] 蓝方 CG-59 创建失败')
end

-- 蓝方-3: 用户指定 DBID 3551 → CVN 70 Carl Vinson
local u3 = ScenEdit_AddUnit({
    side     = '蓝方',
    type     = 'Ship',
    name     = 'Blue-CVN70',
    dbid     = 3551,      -- CVN 70 Carl Vinson (用户指定 DBID 3551)
    latitude  = 21.4200,
    longitude = 130.1713,
    heading   = 293.16,
    speed     = 0,
    proficiency = 'Veteran',
})
if u3 and u3.guid then
    ScenEdit_SetKeyValue('BLUE_CVN70_GUID', u3.guid)
    print('[CMO] 蓝方 CVN-70 创建完成, GUID=' .. u3.guid)
else
    print('[CMO] [ERROR] 蓝方 CVN-70 创建失败')
end

-- ============================================================
-- ④ 创建红方单位（3艘）— 不预装弹，装弹由 reload.lua 完成
-- ============================================================

-- 红方-052D #1 (YJ-21×16): 向 DDG-113 发射 4枚 YJ-21
local r1 = ScenEdit_AddUnit({
    side     = '红方',
    type     = 'Ship',
    name     = 'Red-052D-Alpha',
    dbid     = 2296,      -- Type 052D Luyang III
    latitude  = 21.1437,
    longitude = 123.451,
    heading   = 115,
    speed     = 0,
    proficiency = 'Veteran',
})
if r1 and r1.guid then
    ScenEdit_SetKeyValue('RED_052D_ALPHA_GUID', r1.guid)
    print('[CMO] 红方 052D-Alpha 创建完成, GUID=' .. r1.guid)
else
    print('[CMO] [ERROR] 红方 052D-Alpha 创建失败')
end

-- 红方-052D #2 (YJ-18×16, YJ-21×16): 向 CVN-70 发射 6枚 YJ-21
local r2 = ScenEdit_AddUnit({
    side     = '红方',
    type     = 'Ship',
    name     = 'Red-052D-Beta',
    dbid     = 2296,      -- Type 052D Luyang III
    latitude  = 18.2035,
    longitude = 123.988,
    heading   = 50.0,
    speed     = 0,
    proficiency = 'Veteran',
})
if r2 and r2.guid then
    ScenEdit_SetKeyValue('RED_052D_BETA_GUID', r2.guid)
    print('[CMO] 红方 052D-Beta 创建完成, GUID=' .. r2.guid)
else
    print('[CMO] [ERROR] 红方 052D-Beta 创建失败')
end

-- 红方-055 #1 (YJ-18×32): 向 CG-59 发射 7枚 YJ-18
local r3 = ScenEdit_AddUnit({
    side     = '红方',
    type     = 'Ship',
    name     = 'Red-055-Alpha',
    dbid     = 2834,      -- Type 055 Renhai
    latitude  = 24.8324,
    longitude = 128.583,
    heading   = 135,
    speed     = 0,
    proficiency = 'Veteran',
})
if r3 and r3.guid then
    ScenEdit_SetKeyValue('RED_055_ALPHA_GUID', r3.guid)
    print('[CMO] 红方 055-Alpha 创建完成, GUID=' .. r3.guid)
else
    print('[CMO] [ERROR] 红方 055-Alpha 创建失败')
end

-- ============================================================
-- ⑤ 设定红方 EMCON（雷达主动模式支持全知作战）
-- ============================================================
ScenEdit_SetEMCON('Side', '红方', 'Radar=Active;Sonar=Passive;OECM=Active')

print('[CMO] === main.lua 执行完毕 ===')
print('[CMO] 下一步：执行 clear.lua 清空待发弹')
print('[CMO] 再执行 reload.lua 装填弹药')
print('[CMO] 最后执行 attack.lua 下达打击指令')



