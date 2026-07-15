-- ============================================================
-- main.lua — 红蓝1v1对抗：055 vs CVN-70
-- 红方: Type 055 装载 YJ-18，发射13枚打击蓝方航母
-- 地点: 南海附近
--
-- 使用方式: CMO Lua 控制台依次执行
--   1. main.lua  (创建单位)
--   2. reload.lua (装填导弹)
--   3. attack.lua (发射打击)
--
-- MCP DBID 来源:
--   红方 055: DBID 2834
--   蓝方 CVN-70: DBID 246
--   武器 YJ-18: DBID 2868
-- ============================================================

Tool_EmulateNoConsole(true)

-- ============================================================
-- ① 创建双方阵营
-- ============================================================
local ok, err = pcall(ScenEdit_AddSide, {name = '蓝方'})
if not ok then print('[CMO] 蓝方阵营已存在或创建失败: ' .. tostring(err)) end

ok, err = pcall(ScenEdit_AddSide, {name = '红方'})
if not ok then print('[CMO] 红方阵营已存在或创建失败: ' .. tostring(err)) end

-- ============================================================
-- ② 敌对关系设定
-- ============================================================
ScenEdit_SetSidePosture('红方', '蓝方', 'H')
ScenEdit_SetSidePosture('蓝方', '红方', 'H')

-- ============================================================
-- ③ 红方全知全能（无限视野，所有蓝方目标自动发现）
-- ============================================================
ScenEdit_SetSideOptions({side = '红方', awareness = 'OMNI'})

-- 红方 doctrine：打击规则自由
ScenEdit_SetDoctrine({side = '红方'}, {
    weapon_control_status_air        = 0,  -- WCS: Free
    weapon_control_status_surface    = 0,  -- WCS: Free
    weapon_control_status_subsurface  = 0,  -- WCS: Free
    ignore_plotted_course           = 'no',
    use_nuclear_weapons             = 'no',
})

-- ============================================================
-- ④ 创建蓝方单位 — CVN-70 Carl Vinson
-- ============================================================
-- 位置: 南海中部（约北纬18度，东经117度）
local blue_cvn = ScenEdit_AddUnit({
    side       = '蓝方',
    type       = 'Ship',
    name       = 'CVN-70',
    dbid       = 246,        -- CVN 70 Carl Vinson
    latitude   = 18.0,
    longitude  = 117.0,
    heading    = 0,
    speed      = 20,         -- 巡航速度
    proficiency = 'Veteran',
    autodetectable = true,    -- 关键：允许红方探测到
})
if blue_cvn and blue_cvn.guid then
    ScenEdit_SetKeyValue('BLUE_CVN70_GUID', blue_cvn.guid)
    print('[CMO] 蓝方 CVN-70 创建完成, GUID=' .. blue_cvn.guid)
else
    print('[CMO] [ERROR] 蓝方 CVN-70 创建失败')
end

-- 创建后再次设置 autodetectable（双保险）
if blue_cvn and blue_cvn.guid then
    pcall(ScenEdit_SetUnit, {guid = blue_cvn.guid, autodetectable = true})
end

-- ============================================================
-- ⑤ 创建红方单位 — Type 055 南昌舰
-- ============================================================
-- 位置: 南海北部（约北纬20度，东经115度），面向CVN-70
local red_055 = ScenEdit_AddUnit({
    side       = '红方',
    type       = 'Ship',
    name       = '055-Nanchang',
    dbid       = 2834,       -- Type 055 Renhai [101 Nanchang]
    latitude   = 20.0,
    longitude  = 115.0,
    heading    = 135,        -- 面向东南方（指向CVN-70）
    speed      = 0,          -- 静止待命
    proficiency = 'Veteran',
})
if red_055 and red_055.guid then
    ScenEdit_SetKeyValue('RED_055_GUID', red_055.guid)
    print('[CMO] 红方 055-Nanchang 创建完成, GUID=' .. red_055.guid)
else
    print('[CMO] [ERROR] 红方 055-Nanchang 创建失败')
end

-- ============================================================
-- ⑥ 设置红方 EMCON（雷达主动模式支持全知作战）
-- ============================================================
ScenEdit_SetEMCON('Side', '红方', 'Radar=Active;Sonar=Passive;OECM=Active')

-- ============================================================
-- ⑦ 计算双方距离（用于评估）
-- ============================================================
if red_055 and blue_cvn then
    local range_nm = Tool_Range(
        {latitude = red_055.latitude, longitude = red_055.longitude},
        {latitude = blue_cvn.latitude, longitude = blue_cvn.longitude}
    )
    print('[CMO] 红方055 → 蓝方CVN-70 距离: ' .. string.format('%.1f', range_nm) .. ' 海里')
end

print('[CMO] === main.lua 执行完毕 ===')
print('[CMO] 下一步: 执行 reload.lua 装填 YJ-18 导弹')
print('[CMO] 再执行 attack.lua 发射 13 枚打击 CVN-70')
