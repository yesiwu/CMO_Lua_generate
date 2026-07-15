-- ============================================================
-- 055 vs Burke 1v1 场景生成脚本
-- 红方055打击蓝方DDG-113
-- ============================================================

-- ---------- 配置区 ----------
local CFG_SIDE_RED   = "红方"
local CFG_SIDE_BLUE  = "蓝方"

-- 055 大驱 DBID: 3883 (用户指定)
local DBID_055       = 3883
local NAME_055       = "055-Nanchang"
local LAT_055        = 15.0
local LON_055        = 115.0

-- DDG-113 DBID: 4299
local DBID_DDG       = 4299
local NAME_DDG       = "DDG-113-JohnFinn"
local LAT_DDG        = 15.5
local LON_DDG        = 115.5

-- ---------- 场景初始化 ----------
print("[CMO] === 初始化场景 ===")

-- 创建红方
local ok, msg = pcall(ScenEdit_AddSide, {name = CFG_SIDE_RED, color = '255,0,0'})
if ok then print("[CMO] 创建红方成功") end

-- 创建蓝方
ok, msg = pcall(ScenEdit_AddSide, {name = CFG_SIDE_BLUE, color = '0,0,255'})
if ok then print("[CMO] 创建蓝方成功") end

-- 设置敌对关系
pcall(ScenEdit_SetSidePosture, CFG_SIDE_RED, CFG_SIDE_BLUE, 'H')
pcall(ScenEdit_SetSidePosture, CFG_SIDE_BLUE, CFG_SIDE_RED, 'H')

-- ---------- 红方全知全能 ----------
pcall(ScenEdit_SetSideOptions, {side = CFG_SIDE_RED, awareness = 'OMNI'})
print("[CMO] 红方已设为全知全能 (OMNI)")

-- ---------- 创建红方055大驱 ----------
local unit_055 = ScenEdit_AddUnit({
    side        = CFG_SIDE_RED,
    type        = 'Ship',
    name        = NAME_055,
    dbid        = DBID_055,
    latitude    = LAT_055,
    longitude   = LON_055,
    heading     = 90,
    speed       = 15,
    proficiency = 'Veteran',
})
if unit_055 then
    ScenEdit_SetKeyValue('RED_055_GUID', unit_055.guid)
    print("[CMO] 红方055创建成功: " .. NAME_055 .. " GUID=" .. unit_055.guid)
else
    print("[CMO] ERROR: 红方055创建失败!")
end

-- ---------- 创建蓝方DDG-113 ----------
local unit_ddg = ScenEdit_AddUnit({
    side              = CFG_SIDE_BLUE,
    type              = 'Ship',
    name              = NAME_DDG,
    dbid              = DBID_DDG,
    latitude          = LAT_DDG,
    longitude         = LON_DDG,
    heading           = 270,
    speed             = 12,
    proficiency       = 'Veteran',
    autodetectable    = true,   -- 关键：设为可探测，红方才能获得contact
})
if unit_ddg then
    ScenEdit_SetKeyValue('BLUE_DDG_GUID', unit_ddg.guid)
    print("[CMO] 蓝方DDG-113创建成功: " .. NAME_DDG .. " GUID=" .. unit_ddg.guid)
else
    print("[CMO] ERROR: 蓝方DDG-113创建失败!")
end

-- ---------- 创建后再次确保蓝方单位autodetectable ----------
if unit_ddg and unit_ddg.guid then
    pcall(ScenEdit_SetUnit, {guid = unit_ddg.guid, autodetectable = true})
    print("[CMO] 蓝方单位 autodetectable 已确认")
end

print("[CMO] === 场景初始化完成 ===")
print("[CMO] 下一步: 运行 clear.lua 清空弹药")
print("[CMO]       运行 reload.lua 装填YJ-18")
print("[CMO]       运行 attack.lua 发起打击")
