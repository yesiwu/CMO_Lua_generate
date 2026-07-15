-- =============================================================================
-- A24场景.lua  — 有限反击训练场景 (A24)
-- 方案名称：有限反击训练场景 | 创建日期：2025-10-22 | 版本：1.0
-- 说明：从 json/A24场景.json 自动生成
-- =============================================================================
-- 【DBID 查询说明】
-- 以下装备类型在 CMO 数据库中未找到对应条目，按 SKILL 规范跳过：
--   SAT_JIANBING23   (卫星)           — 无匹配
--   GND_DF17_LAUNCHER (DF-17 发射车) — 无匹配
--   GND_DF26B_LAUNCHER (DF-26B 发射车)— 无匹配
--   EW_YUNLEIGAN9     (云雷干9)       — 无匹配
--   BOMBER_H6K       (H-6K 轰炸机)   — 无精确匹配
--   AWACS_KJ500      (KJ-500 预警机)  — 无精确匹配
--   UUV_RED          (潜艇/UUV)      — 无匹配
--   DDG_055          (055驱逐舰)      — 无匹配
--   CVN_LINCOLN      (航母)           — 无匹配
--   Ticonderoga       (巡洋舰)         — 无精确匹配
--   DDG_CHAFEE       (Burke 驱逐舰)   — 无精确匹配
--   AUX_KZ_SUPPLY   (补给舰)         — 无匹配
--   FFG_RICHMOND     (护卫舰)         — 无匹配
--   LHA_AMERICA      (两栖攻击舰)     — 无匹配
--   USV_OVERLORD    (无人水面艇)      — 无匹配
--   AGOS_VICTORIOUS (监视船)          — 无匹配
--   AC_F35C_LIGHTNING (F-35C)        — 无精确匹配
--   GND_HMS_LAUNCHER (远程火箭炮)    — 无匹配
--   GND_TYPHON_LAUNCHER (标准导弹发射车) — 无匹配

Tool_EmulateNoConsole(true)

-- =============================================================================
-- 1. 创建阵营 & 设置关系
-- =============================================================================

local ok, err = pcall(ScenEdit_AddSide, {name = '红方', color = '255,0,0'})
if not ok then print('[WARNING] 红方 side 可能已存在: ' .. tostring(err)) end

local ok2, err2 = pcall(ScenEdit_AddSide, {name = '蓝方', color = '0,0,255'})
if not ok2 then print('[WARNING] 蓝方 side 可能已存在: ' .. tostring(err2)) end

pcall(ScenEdit_SetSidePosture, '红方', '蓝方', 'H')

-- =============================================================================
-- 2. 红方单位（按 JSON Equipments 位置信息）
-- =============================================================================

-- === 02打击大队 (2x DF-17 发射车) → SKIP: DBID 未找到

-- === 03打击大队 (4x DF-26B 发射车) → SKIP

-- === 606打击大队 (2x DF-26B 发射车) → SKIP

-- === 北部卫星测控站 (50x 卫星 SAT_JIANBING23) → SKIP

-- === 电子战群01 (1x J-16D, 位置: lat=9.94, lon=115.50) ===
local ok, u = pcall(ScenEdit_AddUnit, {
    side        = '红方',
    type        = 'Aircraft',
    name        = '电子战群01_J16D',
    dbid        = 4632,
    LoadoutID   = 753,
    latitude    = 9.94,
    longitude   = 115.50,
    altitude    = 0,
    heading     = 0,
    speed       = 0,
    proficiency = 'Veteran'
})
if ok and u then ScenEdit_SetKeyValue('RED_EW01_J16D', u.guid)
else print('[ERROR] 电子战群01_J16D: ' .. tostring(u)) end

-- === 03电子干扰大队 (3x 翼龙2D, 位置: lat=9.95-9.97, lon=115.55-115.57) ===
for i = 1, 3 do
    local lat = 9.94 + i * 0.01
    local lon = 115.54 + i * 0.01
    local key = 'RED_EJ03_WL2D_' .. i
    local ok, u = pcall(ScenEdit_AddUnit, {
        side        = '红方',
        type        = 'Aircraft',
        name        = '03电子干扰大队_翼龙2D_' .. i,
        dbid        = 4725,
        LoadoutID   = 2179,
        latitude    = lat,
        longitude   = lon,
        altitude    = 0,
        heading     = 0,
        speed       = 0,
        proficiency = 'Veteran'
    })
    if ok and u then ScenEdit_SetKeyValue(key, u.guid)
    else print('[ERROR] ' .. key .. ': ' .. tostring(u)) end
end

-- === 05电子干扰大队 (4x J-16D, 位置: lat=9.93-9.96, lon=115.49-115.52) ===
for i = 1, 4 do
    local lat = 9.92 + i * 0.01
    local lon = 115.48 + i * 0.01
    local key = 'RED_EJ05_J16D_' .. i
    local ok, u = pcall(ScenEdit_AddUnit, {
        side        = '红方',
        type        = 'Aircraft',
        name        = '05电子干扰大队_J16D_' .. i,
        dbid        = 4632,
        LoadoutID   = 753,
        latitude    = lat,
        longitude   = lon,
        altitude    = 0,
        heading     = 0,
        speed       = 0,
        proficiency = 'Veteran'
    })
    if ok and u then ScenEdit_SetKeyValue(key, u.guid)
    else print('[ERROR] ' .. key .. ': ' .. tostring(u)) end
end

-- === 电子战群02 (1x 云雷干9 EW_YUNLEIGAN9) → SKIP

-- === 06轰炸机大队 (9x H-6K) → SKIP: 无精确 DBID

-- === 07预警大队 (2x KJ-500) → SKIP: 无精确 DBID

-- === 08战斗机大队 (4x J-20A, 位置: lat=9.91-9.94, lon=115.47-115.50) ===
for i = 1, 4 do
    local lat = 9.90 + i * 0.01
    local lon = 115.46 + i * 0.01
    local key = 'RED_F08_J20_' .. i
    local ok, u = pcall(ScenEdit_AddUnit, {
        side        = '红方',
        type        = 'Aircraft',
        name        = '08战斗机大队_J20_' .. i,
        dbid        = 5012,
        LoadoutID   = 1191,
        latitude    = lat,
        longitude   = lon,
        altitude    = 0,
        heading     = 0,
        speed       = 0,
        proficiency = 'Veteran'
    })
    if ok and u then ScenEdit_SetKeyValue(key, u.guid)
    else print('[ERROR] ' .. key .. ': ' .. tostring(u)) end
end

-- === 空中打击群04 (4x J-16, 位置: lat=9.90-9.93, lon=115.46-115.49) ===
for i = 1, 4 do
    local lat = 9.89 + i * 0.01
    local lon = 115.45 + i * 0.01
    local key = 'RED_S04_J16_' .. i
    local ok, u = pcall(ScenEdit_AddUnit, {
        side        = '红方',
        type        = 'Aircraft',
        name        = '空中打击群04_J16_' .. i,
        dbid        = 2853,
        LoadoutID   = 1821,
        latitude    = lat,
        longitude   = lon,
        altitude    = 0,
        heading     = 0,
        speed       = 0,
        proficiency = 'Veteran'
    })
    if ok and u then ScenEdit_SetKeyValue(key, u.guid)
    else print('[ERROR] ' .. key .. ': ' .. tostring(u)) end
end

-- === 空中打击群03 (5x J-16, 位置: lat=9.85-9.89, lon=115.41-115.45) ===
for i = 1, 5 do
    local lat = 9.84 + i * 0.01
    local lon = 115.40 + i * 0.01
    local key = 'RED_S03_J16_' .. i
    local ok, u = pcall(ScenEdit_AddUnit, {
        side        = '红方',
        type        = 'Aircraft',
        name        = '空中打击群03_J16_' .. i,
        dbid        = 2853,
        LoadoutID   = 1821,
        latitude    = lat,
        longitude   = lon,
        altitude    = 0,
        heading     = 0,
        speed       = 0,
        proficiency = 'Veteran'
    })
    if ok and u then ScenEdit_SetKeyValue(key, u.guid)
    else print('[ERROR] ' .. key .. ': ' .. tostring(u)) end
end

-- === 06战斗机大队 (6x J-16, 位置: lat=9.84-9.89, lon=115.40-115.45) ===
for i = 1, 6 do
    local lat = 9.83 + i * 0.01
    local lon = 115.39 + i * 0.01
    local key = 'RED_F06_J16_' .. i
    local ok, u = pcall(ScenEdit_AddUnit, {
        side        = '红方',
        type        = 'Aircraft',
        name        = '06战斗机大队_J16_' .. i,
        dbid        = 2853,
        LoadoutID   = 1821,
        latitude    = lat,
        longitude   = lon,
        altitude    = 0,
        heading     = 0,
        speed       = 0,
        proficiency = 'Veteran'
    })
    if ok and u then ScenEdit_SetKeyValue(key, u.guid)
    else print('[ERROR] ' .. key .. ': ' .. tostring(u)) end
end

-- === 07战斗机大队 (4x J-20A, 位置: lat=9.88-9.91, lon=115.44-115.47) ===
for i = 1, 4 do
    local lat = 9.87 + i * 0.01
    local lon = 115.43 + i * 0.01
    local key = 'RED_F07_J20_' .. i
    local ok, u = pcall(ScenEdit_AddUnit, {
        side        = '红方',
        type        = 'Aircraft',
        name        = '07战斗机大队_J20_' .. i,
        dbid        = 5012,
        LoadoutID   = 1191,
        latitude    = lat,
        longitude   = lon,
        altitude    = 0,
        heading     = 0,
        speed       = 0,
        proficiency = 'Veteran'
    })
    if ok and u then ScenEdit_SetKeyValue(key, u.guid)
    else print('[ERROR] ' .. key .. ': ' .. tostring(u)) end
end

-- === 01僚机大队 (10x MQ-4C Triton, 位置: lat=9.80-9.98, lon=115.35-115.53) ===
for i = 1, 10 do
    local lat = 9.79 + i * 0.02
    local lon = 115.34 + i * 0.02
    local key = 'RED_U01_MQ4C_' .. i
    local ok, u = pcall(ScenEdit_AddUnit, {
        side        = '红方',
        type        = 'Aircraft',
        name        = '01僚机大队_MQ4C_' .. i,
        dbid        = 4939,
        LoadoutID   = 1204,
        latitude    = lat,
        longitude   = lon,
        altitude    = 0,
        heading     = 0,
        speed       = 0,
        proficiency = 'Veteran'
    })
    if ok and u then ScenEdit_SetKeyValue(key, u.guid)
    else print('[ERROR] ' .. key .. ': ' .. tostring(u)) end
end

-- === 水下特遣队01 (30x UUV_RED) → SKIP

-- === 04特遣大队 (7x UUV_RED) → SKIP

-- === 05驱逐舰大队 (1x DDG_055) → SKIP

-- === 06护卫舰支队 (4x DDG_055) → SKIP

-- === 07驱逐舰支队 (2x DDG_055) → SKIP

-- === 09潜艇大队 (2x UUV_RED) → SKIP

-- =============================================================================
-- 3. 蓝方单位（按 JSON Equipments 位置信息）
-- =============================================================================

-- === 10号编队 (CVN_LINCOLN/Ticonderoga/DDG_CHAFEE/AUX_KZ_SUPPLY/FFG_RICHMOND) → SKIP

-- === 11号两栖编队 (LHA_AMERICA/Ticonderoga/DDG_CHAFEE) → SKIP

-- === 12无人舰艇编队 (6x USV_OVERLORD) → SKIP

-- === 13监视船编队 (3x AGOS_VICTORIOUS) → SKIP

-- === 14闪电战斗机编队 ===
-- F-35C (4x, 位置: lat=-1.85~-4.41, lon=107.80~108.13)
for i = 1, 4 do
    local key = 'BLUE_F14_F35C_' .. i
    local ok, u = pcall(ScenEdit_AddUnit, {
        side        = '蓝方',
        type        = 'Aircraft',
        name        = '14闪电战斗机编队_F35C_' .. i,
        dbid        = 824,
        LoadoutID   = 689,
        latitude    = -1.84 - (i - 1) * 0.01,
        longitude   = 107.81 - (i - 1) * 0.01,
        altitude    = 1000,
        heading     = 0,
        speed       = 0,
        proficiency = 'Veteran'
    })
    if ok and u then ScenEdit_SetKeyValue(key, u.guid)
    else print('[ERROR] ' .. key .. ': ' .. tostring(u)) end
end

-- F-35B (2x, 位置: lat=-1.85~-1.86, lon=107.80~107.81)
for i = 1, 2 do
    local key = 'BLUE_F14_F35B_' .. i
    local ok, u = pcall(ScenEdit_AddUnit, {
        side        = '蓝方',
        type        = 'Aircraft',
        name        = '14闪电战斗机编队_F35B_' .. i,
        dbid        = 3870,
        LoadoutID   = 1621,
        latitude    = -1.84 - i * 0.01,
        longitude   = 107.80 - i * 0.01,
        altitude    = 1000,
        heading     = 0,
        speed       = 0,
        proficiency = 'Veteran'
    })
    if ok and u then ScenEdit_SetKeyValue(key, u.guid)
    else print('[ERROR] ' .. key .. ': ' .. tostring(u)) end
end

-- === 15远程火力营 (10x GND_HMS_LAUNCHER) → SKIP

-- === 16导弹连 (4x GND_TYPHON_LAUNCHER) → SKIP

-- =============================================================================
-- 4. 场景初始化消息
-- =============================================================================
pcall(ScenEdit_SpecialMessage, '红方', 'A24场景单位已部署完成。')
pcall(ScenEdit_SpecialMessage, '蓝方', 'A24场景单位已部署完成。')
print('[A24场景] Lua 脚本执行完毕。')
