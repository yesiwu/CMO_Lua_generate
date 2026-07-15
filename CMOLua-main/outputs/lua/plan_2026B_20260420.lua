-- ============================================================
-- 方案: 2026B 联合打击
-- 来源: plan_a1_001_legacy.json
-- 生成时间: 2026-04-20
-- 说明:
--   - 蓝方: 5个敌方舰艇目标 (ticonderoga/DDG/LHA/T-AKE)
--   - 红方: 24个地面发射车 + 15架飞机 + 5艘UUV
--   - 卫星单位(wxjb/SAT_JIANBING23)已跳过
--   - DF-26B DBID 未查到，以 DF-26C(2879)/DF-26D(2880) 替代
--   - H-6K LoadoutID: 2322 不被 CMO 认可，改用 4100
-- 内容:
--   [第一部分] 单位生成 — 5x蓝方舰艇 + 49x红方单位
--   [第二部分] 作战规划 — 5个打击任务(ST-01-001~005) + 事件系统
-- ============================================================

-- === 添加蓝方 (Blue Side — 敌方目标) ========================

-- Tico Simoer (CG-47 Ticonderoga Baseline 0) @ 7.97N, 119.50E
local unit = ScenEdit_AddUnit({
    side       = 'Blue',
    type       = 'Ship',
    name       = 'tico_simoer',
    dbid       = 42,
    latitude   = 7.970356,
    longitude  = 119.503844,
    proficiency = 'Veteran',
    heading    = 0,
    speed      = 0,
})
if unit then ScenEdit_SetKeyValue('TICO_SIMOER_GUID', unit.guid) end

-- DDG Chafei (DDG-51 Arleigh Burke Flight I) @ 8.28N, 119.78E
unit = ScenEdit_AddUnit({
    side       = 'Blue',
    type       = 'Ship',
    name       = 'ddg_chafei',
    dbid       = 112,
    latitude   = 8.284662,
    longitude  = 119.783273,
    proficiency = 'Veteran',
    heading    = 0,
    speed      = 0,
})
if unit then ScenEdit_SetKeyValue('DDG_CHAFEI_GUID', unit.guid) end

-- LHA Meiguo (LHD-1 Wasp) @ 7.92N, 120.09E
unit = ScenEdit_AddUnit({
    side       = 'Blue',
    type       = 'Ship',
    name       = 'lha_meiguo',
    dbid       = 170,
    latitude   = 7.922858,
    longitude  = 120.093579,
    proficiency = 'Veteran',
    heading    = 0,
    speed      = 0,
})
if unit then ScenEdit_SetKeyValue('LHA_MEIGUO_GUID', unit.guid) end

-- Supply KZ (T-AKE 1 Lewis and Clark) @ 0.10S, 106.16E
unit = ScenEdit_AddUnit({
    side       = 'Blue',
    type       = 'Ship',
    name       = 'supply_kz',
    dbid       = 753,
    latitude   = -0.101186,
    longitude  = 106.164261,
    proficiency = 'Veteran',
    heading    = 0,
    speed      = 0,
})
if unit then ScenEdit_SetKeyValue('SUPPLY_KZ_GUID', unit.guid) end

-- DDG Mo Museng (DDG-51 Arleigh Burke Flight I) @ 7.10N, 116.28E
unit = ScenEdit_AddUnit({
    side       = 'Blue',
    type       = 'Ship',
    name       = 'ddg_momuseng',
    dbid       = 112,
    latitude   = 7.104,
    longitude  = 116.28,
    proficiency = 'Veteran',
    heading    = 0,
    speed      = 0,
})
if unit then ScenEdit_SetKeyValue('DDG_MOMUSENG_GUID', unit.guid) end

-- === 添加红方 (Red Side — 我方作战力量) ====================

-- ---- 02打击大队: DF-26B 发射车 (DBID=2879, SSM Bn DF-26C) --------
-- 注: MCP 仅查到 DF-26C(2879)/DF-26D(2880)，未查到 DF-26B，用 DF-26C 替代
local d26b_positions = {
    {lat=18.54, lon=110.00}, {lat=18.54, lon=110.01}, {lat=18.55, lon=110.00},
    {lat=18.55, lon=110.01}, {lat=18.55, lon=110.01}, {lat=18.54, lon=110.01},
    {lat=18.55, lon=110.01}, {lat=18.54, lon=110.02}, {lat=18.54, lon=110.03},
    {lat=18.54, lon=110.03}, {lat=18.54, lon=110.03}, {lat=18.53, lon=110.03},
}
for i, pos in ipairs(d26b_positions) do
    local name = string.format('dfb%03d', i)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Facility',
        name       = name,
        dbid       = 2879,
        latitude   = pos.lat,
        longitude  = pos.lon,
        proficiency = 'Veteran',
        heading    = 90,
        speed      = 0,
    })
    if u then ScenEdit_SetKeyValue(string.format('DFB%03d_GUID', i), u.guid) end
end

-- ---- 03打击大队: DF-26D 发射车 (DBID=2880, SSM Bn DF-26D) --------
local d26d_positions = {
    {lat=23.67, lon=113.00}, {lat=23.67, lon=112.99}, {lat=23.65, lon=112.99},
    {lat=23.66, lon=112.98}, {lat=23.65, lon=112.97}, {lat=23.65, lon=112.99},
    {lat=23.64, lon=112.97}, {lat=23.64, lon=112.99}, {lat=23.65, lon=112.99},
    {lat=23.65, lon=113.00}, {lat=23.65, lon=113.00}, {lat=23.64, lon=112.99},
}
for i, pos in ipairs(d26d_positions) do
    local name = string.format('dfd%03d', i)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Facility',
        name       = name,
        dbid       = 2880,
        latitude   = pos.lat,
        longitude  = pos.lon,
        proficiency = 'Veteran',
        heading    = 90,
        speed      = 0,
    })
    if u then ScenEdit_SetKeyValue(string.format('DFD%03d_GUID', i), u.guid) end
end

-- ---- 05干扰大队: J-16D 电子战飞机 (DBID=4632, LoadoutID=965) --------
local j16d_positions = {
    {lat=9.91,  lon=115.53},
    {lat=9.91,  lon=115.50},
    {lat=9.90,  lon=115.49},
    {lat=9.94,  lon=115.52},
}
for i, pos in ipairs(j16d_positions) do
    local name = string.format('jd%03d', i + 1)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Aircraft',
        name       = name,
        dbid       = 4632,
        LoadoutID  = 965,
        latitude   = pos.lat,
        longitude  = pos.lon,
        altitude   = 1500,
        proficiency = 'Veteran',
        heading    = 90,
        speed      = 400,
    })
    if u then ScenEdit_SetKeyValue(string.format('JD%03d_GUID', i + 1), u.guid) end
end

-- ---- 06轰炸机大队: H-6K 轰炸机 (DBID=1731, LoadoutID=4100) --------
local h6k_positions = {
    {lat=26.32, lon=112.79, alt=900},
    {lat=26.30, lon=112.91, alt=1000},
    {lat=26.45, lon=112.90, alt=1000},
    {lat=26.22, lon=112.68, alt=1000},
    {lat=26.20, lon=112.91, alt=1000},
    {lat=26.39, lon=112.98, alt=1000},
}
for i, pos in ipairs(h6k_positions) do
    local name = string.format('hk%03d', i + 2)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Aircraft',
        name       = name,
        dbid       = 1731,
        LoadoutID  = 4100,
        latitude   = pos.lat,
        longitude  = pos.lon,
        altitude   = pos.alt,
        proficiency = 'Veteran',
        heading    = 90,
        speed      = 500,
    })
    if u then ScenEdit_SetKeyValue(string.format('HK%03d_GUID', i + 2), u.guid) end
end

-- ---- 07预警大队: KJ-500A 预警机 (DBID=6004, LoadoutID=494) --------
unit = ScenEdit_AddUnit({
    side       = 'Red',
    type       = 'Aircraft',
    name       = 'kja001',
    dbid       = 6004,
    LoadoutID  = 494,
    latitude   = 26.32,
    longitude  = 112.63,
    altitude   = 1000,
    proficiency = 'Veteran',
    heading    = 90,
    speed      = 240,
})
if unit then ScenEdit_SetKeyValue('KJA001_GUID', unit.guid) end

-- ---- 08战斗机大队: J-20A 战斗机 (DBID=5012, LoadoutID=3589) --------
local j20a_positions = {
    {lat=18.50, lon=109.97},
    {lat=18.50, lon=109.98},
    {lat=18.49, lon=109.98},
    {lat=18.49, lon=109.99},
}
for i, pos in ipairs(j20a_positions) do
    local name = string.format('zds%03d', i)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Aircraft',
        name       = name,
        dbid       = 5012,
        LoadoutID  = 3589,
        latitude   = pos.lat,
        longitude  = pos.lon,
        altitude   = 1000,
        proficiency = 'Veteran',
        heading    = 90,
        speed      = 520,
    })
    if u then ScenEdit_SetKeyValue(string.format('ZDS%03d_GUID', i), u.guid) end
end

-- ---- 03无人潜航支队: Remus 600 UUV (DBID=490, Submarine) --------
local uuv_positions = {
    {lat=0.11, lon=105.82},
    {lat=0.20, lon=105.93},
    {lat=0.06, lon=105.65},
    {lat=0.12, lon=106.03},
    {lat=0.21, lon=106.16},
}
for i, pos in ipairs(uuv_positions) do
    local name = string.format('wruuv%03d', i)
    local u = ScenEdit_AddUnit({
        side       = 'Red',
        type       = 'Submarine',
        name       = name,
        dbid       = 490,
        latitude   = pos.lat,
        longitude  = pos.lon,
        proficiency = 'Veteran',
        heading    = 0,
        speed      = 0,
    })
    if u then ScenEdit_SetKeyValue(string.format('WRUUV%03d_GUID', i), u.guid) end
end

-- === 阵营敌对关系 ==========================================
ScenEdit_SetSidePosture('Red', 'Blue', 'H')
ScenEdit_SetSidePosture('Blue', 'Red', 'H')

-- === 场景完成 ==============================================
ScenEdit_SpecialMessage('Red', '方案 2026B 单位生成完毕 — 5个蓝方舰艇目标 + 24个发射车 + 15架飞机 + 5艘UUV')

-- ============================================================
-- 第二部分：作战规划（Kill Chain 打击链路）
-- 来源: plan_a1_001_legacy.json - task.killWebs.killChains
-- 时间基准 T0 = 2025-10-27 13:30:00
-- ============================================================

-- === 辅助函数 ==============================================

--- 从 KeyStore 获取单位 GUID，未找到时返回 nil
--- @param key string
--- @return string|nil
local function getGuid(key)
    local guid = ScenEdit_GetKeyValue(key)
    return (guid and guid ~= '') and guid or nil
end

--- 获取单位名称，未找到时返回 '(unknown)'
--- @param guid string
--- @return string
local function getUnitName(guid)
    if not guid then return '(unknown)' end
    local ok, u = pcall(ScenEdit_GetUnit, {guid = guid})
    return (ok and u and u.name) or '(unknown)'
end

--- 向红方发送特殊消息（带平台名标注）
--- @param msg string
local function redMsg(msg)
    ScenEdit_SpecialMessage('Red', msg)
end

-- === 获取各平台 GUID ========================================

-- 蓝方目标 GUID
local guid_tico     = getGuid('TICO_SIMOER_GUID')
local guid_chafei   = getGuid('DDG_CHAFEI_GUID')
local guid_lha      = getGuid('LHA_MEIGUO_GUID')
local guid_supply   = getGuid('SUPPLY_KZ_GUID')
local guid_momuseng = getGuid('DDG_MOMUSENG_GUID')

-- DF-26B/C 发射车 GUID (dfb001-dfb012)
local dfb_guids = {}
for i = 1, 12 do
    dfb_guids[i] = getGuid(string.format('DFB%03d_GUID', i))
end

-- DF-26D 发射车 GUID (dfd001-dfd012)
local dfd_guids = {}
for i = 1, 12 do
    dfd_guids[i] = getGuid(string.format('DFD%03d_GUID', i))
end

-- J-16D 电子战飞机 GUID (jd002-jd007)
local jd_guids = {}
for i = 2, 7 do
    jd_guids[i] = getGuid(string.format('JD%03d_GUID', i))
end

-- H-6K 轰炸机 GUID (hk003-hk008)
local hk_guids = {}
for i = 3, 8 do
    hk_guids[i] = getGuid(string.format('HK%03d_GUID', i))
end

-- KJ-500A 预警机 GUID
local guid_kja001 = getGuid('KJA001_GUID')

-- J-20A 战斗机 GUID (zds001-zds004)
local zds_guids = {}
for i = 1, 4 do
    zds_guids[i] = getGuid(string.format('ZDS%03d_GUID', i))
end

-- Remus 600 UUV GUID (wruuv001-wruuv005)
local uuv_guids = {}
for i = 1, 5 do
    uuv_guids[i] = getGuid(string.format('WRUUV%03d_GUID', i))
end

-- ============================================================
-- 打击任务 1: ST-01-001 — 打击 lha_meiguo
-- 目标: LHA Meiguo (guid_lha) @ 7.92N, 120.09E
-- 参与平台: dfb001/002/003/005/011/012, dfd001/002/003/005/011/012, kja001, zds001-004
-- 开始时间: T0 (立即)
-- ============================================================

local ok1, msn1 = pcall(ScenEdit_AddMission, 'Red', 'ST-01-001 打击lha_meiguo', 'strike', {type = 'sea'})
if ok1 and msn1 then
    ScenEdit_SetKeyValue('MSN_ST01_001_GUID', msn1.guid)
    -- 分配所有打击平台
    for _, idx in ipairs({1, 2, 3, 5, 11, 12}) do
        if dfb_guids[idx] then
            pcall(ScenEdit_AssignUnitToMission, dfb_guids[idx], msn1.guid)
        end
    end
    for _, idx in ipairs({1, 2, 3, 5, 11, 12}) do
        if dfd_guids[idx] then
            pcall(ScenEdit_AssignUnitToMission, dfd_guids[idx], msn1.guid)
        end
    end
    if guid_kja001 then pcall(ScenEdit_AssignUnitToMission, guid_kja001, msn1.guid) end
    for i = 1, 4 do
        if zds_guids[i] then pcall(ScenEdit_AssignUnitToMission, zds_guids[i], msn1.guid) end
    end
    -- 设置目标
    if guid_lha then
        pcall(ScenEdit_SetMission, 'Red', msn1.name, {target = guid_lha})
    end
    redMsg('[ST-01-001] 打击lha_meiguo任务已建立 — 参与: 12xDF-26 + 1xKJ-500A + 4xJ-20A')
else
    redMsg('[ST-01-001] 任务创建失败: ' .. tostring(msn1))
end

-- ============================================================
-- 打击任务 2: ST-01-002 — 打击 tico_simoer
-- 目标: Tico Simoer (guid_tico) @ 7.97N, 119.50E
-- 参与平台: dfb007/008, dfd004/006, jd003/004, hk005/006
-- 开始时间: T0 (立即)
-- ============================================================

local ok2, msn2 = pcall(ScenEdit_AddMission, 'Red', 'ST-01-002 打击tico_simoer', 'strike', {type = 'sea'})
if ok2 and msn2 then
    ScenEdit_SetKeyValue('MSN_ST01_002_GUID', msn2.guid)
    for _, idx in ipairs({7, 8}) do
        if dfb_guids[idx] then pcall(ScenEdit_AssignUnitToMission, dfb_guids[idx], msn2.guid) end
    end
    for _, idx in ipairs({4, 6}) do
        if dfd_guids[idx] then pcall(ScenEdit_AssignUnitToMission, dfd_guids[idx], msn2.guid) end
    end
    for _, idx in ipairs({3, 4}) do
        if jd_guids[idx] then pcall(ScenEdit_AssignUnitToMission, jd_guids[idx], msn2.guid) end
    end
    for _, idx in ipairs({5, 6}) do
        if hk_guids[idx] then pcall(ScenEdit_AssignUnitToMission, hk_guids[idx], msn2.guid) end
    end
    if guid_tico then
        pcall(ScenEdit_SetMission, 'Red', msn2.name, {target = guid_tico})
    end
    redMsg('[ST-01-002] 打击tico_simoer任务已建立 — 参与: 4xDF-26 + 2xJ-16D + 2xH-6K')
else
    redMsg('[ST-01-002] 任务创建失败: ' .. tostring(msn2))
end

-- ============================================================
-- 打击任务 3: ST-01-003 — 打击 ddg_chafei
-- 目标: DDG Chafei (guid_chafei) @ 8.28N, 119.78E
-- 参与平台: dfb004/006, dfd007/008, jd002/007, hk007/008
-- 开始时间: T0 (立即)
-- ============================================================

local ok3, msn3 = pcall(ScenEdit_AddMission, 'Red', 'ST-01-003 打击ddg_chafei', 'strike', {type = 'sea'})
if ok3 and msn3 then
    ScenEdit_SetKeyValue('MSN_ST01_003_GUID', msn3.guid)
    for _, idx in ipairs({4, 6}) do
        if dfb_guids[idx] then pcall(ScenEdit_AssignUnitToMission, dfb_guids[idx], msn3.guid) end
    end
    for _, idx in ipairs({7, 8}) do
        if dfd_guids[idx] then pcall(ScenEdit_AssignUnitToMission, dfd_guids[idx], msn3.guid) end
    end
    if jd_guids[2] then pcall(ScenEdit_AssignUnitToMission, jd_guids[2], msn3.guid) end
    if jd_guids[7] then pcall(ScenEdit_AssignUnitToMission, jd_guids[7], msn3.guid) end
    for _, idx in ipairs({7, 8}) do
        if hk_guids[idx] then pcall(ScenEdit_AssignUnitToMission, hk_guids[idx], msn3.guid) end
    end
    if guid_chafei then
        pcall(ScenEdit_SetMission, 'Red', msn3.name, {target = guid_chafei})
    end
    redMsg('[ST-01-003] 打击ddg_chafei任务已建立 — 参与: 4xDF-26 + 2xJ-16D + 2xH-6K')
else
    redMsg('[ST-01-003] 任务创建失败: ' .. tostring(msn3))
end

-- ============================================================
-- 打击任务 4: ST-01-004 — 打击 supply_kz
-- 目标: Supply KZ (guid_supply) @ 0.10S, 106.16E
-- 参与平台: wruuv005 (鱼雷攻击)
-- 开始时间: T0+2H2M (7320s)
-- ============================================================

-- 立即创建任务，待时机触发
local ok4, msn4 = pcall(ScenEdit_AddMission, 'Red', 'ST-01-004 打击supply_kz', 'strike', {type = 'sea'})
if ok4 and msn4 then
    ScenEdit_SetKeyValue('MSN_ST01_004_GUID', msn4.guid)
    if uuv_guids[5] then
        pcall(ScenEdit_AssignUnitToMission, uuv_guids[5], msn4.guid)
    end
    if guid_supply then
        pcall(ScenEdit_SetMission, 'Red', msn4.name, {target = guid_supply})
    end
    redMsg('[ST-01-004] 打击supply_kz任务已建立 — 参与: wruuv005 (鱼雷)')
else
    redMsg('[ST-01-004] 任务创建失败: ' .. tostring(msn4))
end

-- ============================================================
-- 打击任务 5: ST-01-005 — 打击 ddg_momuseng
-- 目标: DDG Mo Museng (guid_momuseng) @ 7.10N, 116.28E
-- 参与平台: dfb009/010, dfd009/010, hk003/004
-- 开始时间: T0 (立即)
-- ============================================================

local ok5, msn5 = pcall(ScenEdit_AddMission, 'Red', 'ST-01-005 打击ddg_momuseng', 'strike', {type = 'sea'})
if ok5 and msn5 then
    ScenEdit_SetKeyValue('MSN_ST01_005_GUID', msn5.guid)
    for _, idx in ipairs({9, 10}) do
        if dfb_guids[idx] then pcall(ScenEdit_AssignUnitToMission, dfb_guids[idx], msn5.guid) end
    end
    for _, idx in ipairs({9, 10}) do
        if dfd_guids[idx] then pcall(ScenEdit_AssignUnitToMission, dfd_guids[idx], msn5.guid) end
    end
    for _, idx in ipairs({3, 4}) do
        if hk_guids[idx] then pcall(ScenEdit_AssignUnitToMission, hk_guids[idx], msn5.guid) end
    end
    if guid_momuseng then
        pcall(ScenEdit_SetMission, 'Red', msn5.name, {target = guid_momuseng})
    end
    redMsg('[ST-01-005] 打击ddg_momuseng任务已建立 — 参与: 4xDF-26 + 2xH-6K')
else
    redMsg('[ST-01-005] 任务创建失败: ' .. tostring(msn5))
end

-- ============================================================
-- 作战阶段事件
-- 触发: 场景加载时执行，记录作战阶段开始
-- ============================================================

local evPhase = ScenEdit_SetEvent('作战阶段开始', {
    mode = 'add',
    IsRepeatable = false,
    IsActive = true,
})
if evPhase then
    ScenEdit_SetKeyValue('EV_PHASE_GUID', evPhase.guid)

    -- 触发器: 场景加载
    ScenEdit_SetTrigger({mode = 'add', type = 'ScenLoaded', name = 'OnLoad'})
    ScenEdit_SetEventTrigger(evPhase.guid, {mode = 'add', name = 'OnLoad'})

    -- 动作: 显示阶段信息
    ScenEdit_SetAction({
        mode = 'add',
        type = 'LuaScript',
        name = 'PhaseStart',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', '[阶段开始] 反舰作战实施阶段 | T0=2025-10-27 13:30:00 | " ..
            "目标: lha_meiguo/ddg_chafei/tico_simoer/supply_kz/ddg_momuseng | " ..
            "预期结束: T0+2H40M')"..
            "\r\nScenEdit_SpecialMessage('Red', '[作战集群] 02打击大队(DF-26B) | 03打击大队(DF-26D) | " ..
            "05干扰大队(J-16D) | 06轰炸机大队(H-6K) | 07预警大队(KJ-500A) | " ..
            "08战斗机大队(J-20A) | 03无人潜航支队(Remus-600)')"
        )
    })
    ScenEdit_SetEventAction(evPhase.guid, {mode = 'add', name = 'PhaseStart'})
end

-- ============================================================
-- 打击完成评估事件
-- 触发: 每当蓝方舰艇被摧毁时，评估是否满足终止条件
-- 终止条件: 海上目标毁伤率达到 50% (3/5 目标被摧毁)
-- ============================================================

local evEval = ScenEdit_SetEvent('打击效果评估', {
    mode = 'add',
    IsRepeatable = true,
    IsActive = true,
})
if evEval then
    ScenEdit_SetKeyValue('EV_EVAL_GUID', evEval.guid)

    -- 触发器: 任意单位被摧毁
    ScenEdit_SetTrigger({mode = 'add', type = 'UnitDamaged', name = 'UnitDamagedOrDestroyed'})
    ScenEdit_SetEventTrigger(evEval.guid, {mode = 'add', name = 'UnitDamagedOrDestroyed'})

    -- 动作: 评估摧毁数量
    local evalScript = [[
local function getGuid(key)
    local g = ScenEdit_GetKeyValue(key)
    return (g and g ~= '') and g or nil
end
local targets = {
    {key='TICO_SIMOER_GUID',  name='tico_simoer'},
    {key='DDG_CHAFEI_GUID',   name='ddg_chafei'},
    {key='LHA_MEIGUO_GUID',   name='lha_meiguo'},
    {key='SUPPLY_KZ_GUID',    name='supply_kz'},
    {key='DDG_MOMUSENG_GUID', name='ddg_momuseng'},
}
local destroyed = 0
for _, t in ipairs(targets) do
    local guid = getGuid(t.key)
    if guid then
        local ok, u = pcall(ScenEdit_GetUnit, {guid = guid})
        if ok and u and (u.damage >= 1.0 or u:isDestroyed()) then
            destroyed = destroyed + 1
        end
    end
end
local rate = destroyed / #targets
if rate >= 0.5 then
    ScenEdit_SetScore('Red', 100, '海上目标毁伤率 >= 50%, 任务完成')
    ScenEdit_SpecialMessage('Red', '[任务完成] 海上目标毁伤率: ' .. math.floor(rate * 100) .. '% ('
        .. destroyed .. '/5) — 满足终止条件')
    ScenEdit_EndScenario()
else
    ScenEdit_SpecialMessage('Red', '[毁评] 摧毁 ' .. destroyed .. '/5 目标 ('
        .. math.floor(rate * 100) .. '%), 继续执行')
end
]]
    ScenEdit_SetAction({mode = 'add', type = 'LuaScript', name = 'EvaluateStrike', ScriptText = evalScript})
    ScenEdit_SetEventAction(evEval.guid, {mode = 'add', name = 'EvaluateStrike'})
end

-- ============================================================
-- 第三部分：杀伤链时序事件（F2T2EA 平台间协同）
-- 来源: plan_a1_001_legacy.json - task.killWebs.killChains[*].LinkList
-- 时间基准 T0 = 2025-10-27 13:30:00
-- linkType 映射: find(发现) fix(定位) track(跟踪) aim(瞄准)
--                engage(打击) assessment(毁评)
-- ============================================================

-- === ISO 8601 Duration 解析辅助函数 ========================
-- 将 "PT1H52M" / "PT2H0M" 等格式转换为秒数
--- @param duration string ISO 8601 duration like "PT1H52M"
--- @return number seconds
local function parsePT(googleduration)
    if not googleduration or googleduration == '' then return 0 end
    local hours = tonumber(string.match(googleduration, '(%d+)H')) or 0
    local mins  = tonumber(string.match(googleduration, '(%d+)M')) or 0
    local secs  = tonumber(string.match(googleduration, '(%d+)S')) or 0
    return hours * 3600 + mins * 60 + secs
end

-- === 时间基准 T0 ==========================================
local T0 = ScenEdit_CurrentTime()  -- 2025-10-27 13:30:00

-- === 辅助函数：创建 Kill Chain 环节事件 ===================
--- @param chainLabel string  e.g. "ST-01-001"
--- @param linkName string   e.g. "发现lha_meiguo"
--- @param linkType string   e.g. "find"
--- @param platforms table   array of {name, role, description}
--- @param offsetSecs number 时间偏移秒数
--- @param durationSecs number 持续时长(秒)
--- @param message string 提示信息
--- @return string eventName
local function createKillChainEvent(chainLabel, linkName, linkType, platforms, offsetSecs, durationSecs, message)
    local evName = string.format('[%s] %s', chainLabel, linkName)
    local ev = ScenEdit_SetEvent(evName, {
        mode         = 'add',
        IsRepeatable = true,
        IsActive     = true,
    })
    if not ev then return nil end

    -- 时间触发器
    local triggerName = string.format('%s_%s_trigger', chainLabel, linkType)
    local triggerTime = T0 + offsetSecs
    ScenEdit_SetTrigger({
        mode = 'add',
        type = 'Time',
        name = triggerName,
        time = triggerTime,
    })
    ScenEdit_SetEventTrigger(ev.guid, {mode = 'add', name = triggerName})

    -- 构建脚本
    local platList = {}
    for _, p in ipairs(platforms) do
        table.insert(platList, string.format('%s(%s)', p.name, p.role))
    end
    local platStr = table.concat(platList, ' | ')

    local linkTypeCN = {
        find       = '发现',
        fix        = '定位',
        track      = '跟踪',
        aim        = '瞄准',
        engage     = '打击',
        assessment = '毁评',
    }
    local cnName = linkTypeCN[linkType] or linkType

    local scriptText = string.format(
        "ScenEdit_SpecialMessage('Red', '[%s] %s | 参与: %s | %s+%s | %s')",
        chainLabel,
        linkName,
        platStr,
        cnName,
        chainLabel,
        message
    )

    ScenEdit_SetAction({
        mode       = 'add',
        type       = 'LuaScript',
        name       = string.format('%s_%s_action', chainLabel, linkType),
        ScriptText = scriptText,
    })
    ScenEdit_SetEventAction(ev.guid, {
        mode = 'add',
        name = string.format('%s_%s_action', chainLabel, linkType),
    })

    return evName
end

-- ============================================================
-- ST-01-001 打击 lha_meiguo
-- 环节时序: find@T0+1H47M | fix@T0+1H48M | track@T0+1H49M
--           | aim@T0+1H50M  | engage@T0+0S  | assess@T0+2H10M
-- 侦察平台: wxjb (W051)
-- 打击平台: dfb001/002/003/005/011/012 | dfd001/002/003/005/011/012
--           | kja001 | zds001/002/003/004
-- ============================================================

-- Link: 30001 发现lha_meiguo @ T0+1H47M
createKillChainEvent('ST-01-001', '发现lha_meiguo', 'find',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H47M'),
    parsePT('PT3M'),
    '卫星侦察网确认目标方位')

-- Link: 30002 定位lha_meiguo @ T0+1H48M
createKillChainEvent('ST-01-001', '定位lha_meiguo', 'fix',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H48M'),
    parsePT('PT4M'),
    '精确锁定目标位置')

-- Link: 30003 跟踪lha_meiguo @ T0+1H49M
createKillChainEvent('ST-01-001', '跟踪lha_meiguo', 'track',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H49M'),
    parsePT('PT5M'),
    '持续跟踪目标运动轨迹')

-- Link: 30004 瞄准lha_meiguo @ T0+1H50M
createKillChainEvent('ST-01-001', '瞄准lha_meiguo', 'aim',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H50M'),
    parsePT('PT6M'),
    '瞄准系统锁定目标')

-- Link: 30005 打击lha_meiguo @ T0+0S
createKillChainEvent('ST-01-001', '打击lha_meiguo', 'engage',
    {
        {name='dfb001', role='DF-26B打击'},
        {name='dfb002', role='DF-26B打击'},
        {name='dfb003', role='DF-26B打击'},
        {name='dfb005', role='DF-26B打击'},
        {name='dfb011', role='DF-26B打击'},
        {name='dfb012', role='DF-26B打击'},
        {name='dfd001', role='DF-26D打击'},
        {name='dfd002', role='DF-26D打击'},
        {name='dfd003', role='DF-26D打击'},
        {name='dfd005', role='DF-26D打击'},
        {name='dfd011', role='DF-26D打击'},
        {name='dfd012', role='DF-26D打击'},
        {name='kja001', role='侦察支援'},
        {name='zds001', role='J-20A打击'},
        {name='zds002', role='J-20A打击'},
        {name='zds003', role='J-20A打击'},
        {name='zds004', role='J-20A打击'},
    },
    parsePT('PT0S'),
    parsePT('PT2H40M'),
    '弹群齐射，多平台饱和攻击')

-- Link: 30006 毁评lha_meiguo @ T0+2H10M
createKillChainEvent('ST-01-001', '毁评lha_meiguo', 'assessment',
    {{name='wxjb', role='保障'}},
    parsePT('PT2H10M'),
    parsePT('PT14M'),
    '卫星过顶核查毁伤效果')

-- ============================================================
-- ST-01-002 打击 tico_simoer
-- 环节时序: find@T0+1H52M | fix@T0+1H53M | track@T0+1H54M
--           | aim@T0+1H55M  | engage@T0+0S  | assess@T0+2H10M
-- 侦察平台: gf01 (W003)
-- 打击平台: dfb007/008 | dfd004/006 | jd003/004 | hk005/006
-- ============================================================

-- Link: 10001 发现simoer @ T0+1H52M
createKillChainEvent('ST-01-002', '发现simoer', 'find',
    {{name='gf01', role='保障'}},
    parsePT('PT1H52M'),
    parsePT('PT4M'),
    '卫星侦察网确认目标方位')

-- Link: 10002 定位simoer @ T0+1H53M
createKillChainEvent('ST-01-002', '定位simoer', 'fix',
    {{name='gf01', role='保障'}},
    parsePT('PT1H53M'),
    parsePT('PT4M'),
    '精确锁定目标位置')

-- Link: 10003 跟踪simoer号 @ T0+1H54M
createKillChainEvent('ST-01-002', '跟踪simoer号', 'track',
    {{name='gf01', role='保障'}},
    parsePT('PT1H54M'),
    parsePT('PT5M'),
    '持续跟踪目标运动轨迹')

-- Link: 10004 瞄准simoer @ T0+1H55M
createKillChainEvent('ST-01-002', '瞄准simoer', 'aim',
    {{name='gf01', role='保障'}},
    parsePT('PT1H55M'),
    parsePT('PT6M'),
    '瞄准系统锁定目标')

-- Link: 1005 打击simoer @ T0+0S
createKillChainEvent('ST-01-002', '打击simoer', 'engage',
    {
        {name='dfb007', role='DF-26B打击'},
        {name='dfb008', role='DF-26B打击'},
        {name='dfd004', role='DF-26D打击'},
        {name='dfd006', role='DF-26D打击'},
        {name='jd003',  role='电磁干扰'},
        {name='jd004',  role='电磁干扰'},
        {name='hk005',  role='H-6K对陆攻击'},
        {name='hk006',  role='H-6K对陆攻击'},
    },
    parsePT('PT0S'),
    parsePT('PT2H30M'),
    '电子干扰掩护+反舰导弹饱和攻击')

-- Link: 10006 毁评simoer @ T0+2H10M
createKillChainEvent('ST-01-002', '毁评simoer', 'assessment',
    {{name='gf01', role='保障'}},
    parsePT('PT2H10M'),
    parsePT('PT14M'),
    '卫星过顶核查毁伤效果')

-- ============================================================
-- ST-01-003 打击 ddg_chafei
-- 环节时序: find@T0+1H46M | fix@T0+1H47M | track@T0+1H48M
--           | aim@T0+1H49M  | engage@T0+0S  | assess@T0+2H10M
-- 侦察平台: wxjb (W051)
-- 打击平台: dfb004/006 | dfd007/008 | jd002/007 | hk007/008
-- ============================================================

-- Link: 20001 侦察发现chafei @ T0+1H46M
createKillChainEvent('ST-01-003', '侦察发现chafei', 'find',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H46M'),
    parsePT('PT3M'),
    '卫星侦察网确认目标方位')

-- Link: 20002 定位chafei @ T0+1H47M
createKillChainEvent('ST-01-003', '定位chafei', 'fix',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H47M'),
    parsePT('PT4M'),
    '精确锁定目标位置')

-- Link: 20003 跟踪chafei @ T0+1H48M
createKillChainEvent('ST-01-003', '跟踪chafei', 'track',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H48M'),
    parsePT('PT5M'),
    '持续跟踪目标运动轨迹')

-- Link: 20004 瞄准chafei @ T0+1H49M
createKillChainEvent('ST-01-003', '瞄准chafei', 'aim',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H49M'),
    parsePT('PT6M'),
    '瞄准系统锁定目标')

-- Link: 20005 打击chafei @ T0+0S
createKillChainEvent('ST-01-003', '打击chafei', 'engage',
    {
        {name='dfb004', role='DF-26B打击'},
        {name='dfb006', role='DF-26B打击'},
        {name='dfd007', role='DF-26D打击'},
        {name='dfd008', role='DF-26D打击'},
        {name='jd002',  role='电磁干扰'},
        {name='jd007',  role='电磁干扰'},
        {name='hk007',  role='H-6K对陆攻击'},
        {name='hk008',  role='H-6K对陆攻击'},
    },
    parsePT('PT0S'),
    parsePT('PT2H30M'),
    '电子干扰掩护+反舰导弹饱和攻击')

-- Link: 20006 毁评chafei @ T0+2H10M
createKillChainEvent('ST-01-003', '毁评chafei', 'assessment',
    {{name='wxjb', role='保障'}},
    parsePT('PT2H10M'),
    parsePT('PT14M'),
    '卫星过顶核查毁伤效果')

-- ============================================================
-- ST-01-004 打击 supply_kz
-- 环节时序: find@T0+1H53M | fix@T0+1H54M | track@T0+1H55M
--           | aim@T0+1H56M  | engage@T0+2H2M | assess@T0+2H18M
-- 侦察平台: gf01 (W003)
-- 打击平台: wruuv005 (UUV 鱼雷攻击)
-- ============================================================

-- Link: 40001 侦察发现supply_kz @ T0+1H53M
createKillChainEvent('ST-01-004', '侦察发现supply_kz', 'find',
    {{name='gf01', role='保障'}},
    parsePT('PT1H53M'),
    parsePT('PT3M'),
    '卫星侦察网确认补给舰位置')

-- Link: 40002 定位supply_kz @ T0+1H54M
createKillChainEvent('ST-01-004', '定位supply_kz', 'fix',
    {{name='gf01', role='保障'}},
    parsePT('PT1H54M'),
    parsePT('PT4M'),
    '精确锁定目标位置')

-- Link: 40003 跟踪supply_kz @ T0+1H55M
createKillChainEvent('ST-01-004', '跟踪supply_kz', 'track',
    {{name='gf01', role='保障'}},
    parsePT('PT1H55M'),
    parsePT('PT5M'),
    '持续跟踪目标运动轨迹')

-- Link: 40004 瞄准supply_kz @ T0+1H56M
createKillChainEvent('ST-01-004', '瞄准supply_kz', 'aim',
    {{name='gf01', role='保障'}},
    parsePT('PT1H56M'),
    parsePT('PT6M'),
    '瞄准系统锁定目标')

-- Link: 40005 打击supply_kz @ T0+2H2M
createKillChainEvent('ST-01-004', '打击supply_kz', 'engage',
    {{name='wruuv005', role='鱼雷攻击(UUV)'}},
    parsePT('PT2H2M'),
    parsePT('PT16M'),
    'UUV抵近发射鱼雷')

-- Link: 40006 毁评supply_kz @ T0+2H18M
createKillChainEvent('ST-01-004', '毁评supply_kz', 'assessment',
    {{name='gf01', role='保障'}},
    parsePT('PT2H18M'),
    parsePT('PT12M'),
    '卫星过顶核查毁伤效果')

-- ============================================================
-- ST-01-005 打击 ddg_momuseng
-- 环节时序: find@T0+1H52M | fix@T0+1H53M | track@T0+1H54M
--           | aim@T0+1H55M  | engage@T0+0S  | assess@T0+2H10M
-- 侦察平台: wxjb (W051)
-- 打击平台: dfb009/010 | dfd009/010 | hk003/004
-- ============================================================

-- Link: 50001 发现ddg_momuseng @ T0+1H52M
createKillChainEvent('ST-01-005', '发现ddg_momuseng', 'find',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H52M'),
    parsePT('PT4M'),
    '卫星侦察网确认目标方位')

-- Link: 50002 定位ddg_momuseng @ T0+1H53M
createKillChainEvent('ST-01-005', '定位ddg_momuseng', 'fix',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H53M'),
    parsePT('PT4M'),
    '精确锁定目标位置')

-- Link: 50003 跟踪ddg_momuseng @ T0+1H54M
createKillChainEvent('ST-01-005', '跟踪ddg_momuseng', 'track',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H54M'),
    parsePT('PT5M'),
    '持续跟踪目标运动轨迹')

-- Link: 50004 瞄准ddg_momuseng @ T0+1H55M
createKillChainEvent('ST-01-005', '瞄准ddg_momuseng', 'aim',
    {{name='wxjb', role='保障'}},
    parsePT('PT1H55M'),
    parsePT('PT6M'),
    '瞄准系统锁定目标')

-- Link: 50005 打击ddg_momuseng @ T0+0S
createKillChainEvent('ST-01-005', '打击ddg_momuseng', 'engage',
    {
        {name='dfb009', role='DF-26B打击'},
        {name='dfb010', role='DF-26B打击'},
        {name='dfd009', role='DF-26D打击'},
        {name='dfd010', role='DF-26D打击'},
        {name='hk003',  role='H-6K对陆攻击'},
        {name='hk004',  role='H-6K对陆攻击'},
    },
    parsePT('PT0S'),
    parsePT('PT2H30M'),
    '反舰导弹+巡航导弹饱和攻击')

-- Link: 50006 毁评ddg_momuseng @ T0+2H10M
createKillChainEvent('ST-01-005', '毁评ddg_momuseng', 'assessment',
    {{name='wxjb', role='保障'}},
    parsePT('PT2H10M'),
    parsePT('PT14M'),
    '卫星过顶核查毁伤效果')

-- ============================================================
-- 第四部分：跨平台协同事件
-- 描述: 非 F2T2EA 环节的额外协同动作
--       包含电子战协调、预警机侦察支援、干扰结束通知等
-- ============================================================

-- === J-16D 电子战协同 (ST-01-002, ST-01-003) ==============
-- 电子干扰开始 @ T0+0S
local evJDStart = ScenEdit_SetEvent('[协同] J-16D电子干扰开始', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evJDStart then
    ScenEdit_SetTrigger({mode='add', type='Time', name='JDStart_trigger',
        time = T0 + parsePT('PT0S')})
    ScenEdit_SetEventTrigger(evJDStart.guid, {mode='add', name='JDStart_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='JDStart_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[电子战] J-16D电子干扰开始 | jd002/003/004/007投入 | " ..
            "覆盖ST-01-002(ST-01-003)打击区域 | 干扰敌方防空雷达')"
        )})
    ScenEdit_SetEventAction(evJDStart.guid, {mode='add', name='JDStart_action'})
end

-- 电子干扰结束 @ T0+2H30M
local evJDEnd = ScenEdit_SetEvent('[协同] J-16D电子干扰结束', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evJDEnd then
    ScenEdit_SetTrigger({mode='add', type='Time', name='JDEnd_trigger',
        time = T0 + parsePT('PT2H30M')})
    ScenEdit_SetEventTrigger(evJDEnd.guid, {mode='add', name='JDEnd_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='JDEnd_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[电子战] J-16D电子干扰结束 | jd002/003/004/007撤出 | " ..
            "ST-01-002/003打击完成 | 效果待卫星评估')"
        )})
    ScenEdit_SetEventAction(evJDEnd.guid, {mode='add', name='JDEnd_action'})
end

-- === 预警机侦察支援 (ST-01-001) ============================
-- 预警机侦察开始 @ T0+0S
local evKJAStart = ScenEdit_SetEvent('[协同] KJ-500A预警机侦察开始', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evKJAStart then
    ScenEdit_SetTrigger({mode='add', type='Time', name='KJAStart_trigger',
        time = T0 + parsePT('PT0S')})
    ScenEdit_SetEventTrigger(evKJAStart.guid, {mode='add', name='KJAStart_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='KJAStart_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[预警] KJ-500A预警机侦察开始 | kja001建立区域警戒 | " ..
            "探测蓝方舰载雷达信号 | ST-01-001打击支援')"
        )})
    ScenEdit_SetEventAction(evKJAStart.guid, {mode='add', name='KJAStart_action'})
end

-- 预警机侦察结束 @ T0+2H40M
local evKJAEnd = ScenEdit_SetEvent('[协同] KJ-500A预警机侦察结束', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evKJAEnd then
    ScenEdit_SetTrigger({mode='add', type='Time', name='KJAEnd_trigger',
        time = T0 + parsePT('PT2H40M')})
    ScenEdit_SetEventTrigger(evKJAEnd.guid, {mode='add', name='KJAEnd_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='KJAEnd_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[预警] KJ-500A预警机侦察结束 | ST-01-001打击完成 | " ..
            "目标区态势报告已上传')"
        )})
    ScenEdit_SetEventAction(evKJAEnd.guid, {mode='add', name='KJAEnd_action'})
end

-- === H-6K 轰炸机协同 (ST-01-002, ST-01-003, ST-01-005) ====
-- H-6K 编队出发 @ T0+0S
local evHKStart = ScenEdit_SetEvent('[协同] H-6K轰炸机编队出发', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evHKStart then
    ScenEdit_SetTrigger({mode='add', type='Time', name='HKStart_trigger',
        time = T0 + parsePT('PT0S')})
    ScenEdit_SetEventTrigger(evHKStart.guid, {mode='add', name='HKStart_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='HKStart_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[空中] H-6K轰炸机编队出发 | hk003/004/005/006/007/008投入 | " ..
            "携载巡航导弹 | 支援ST-01-002/003/005打击')"
        )})
    ScenEdit_SetEventAction(evHKStart.guid, {mode='add', name='HKStart_action'})
end

-- H-6K 打击完成报告 @ T0+2H30M
local evHKEnd = ScenEdit_SetEvent('[协同] H-6K轰炸机打击完成', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evHKEnd then
    ScenEdit_SetTrigger({mode='add', type='Time', name='HKEnd_trigger',
        time = T0 + parsePT('PT2H30M')})
    ScenEdit_SetEventTrigger(evHKEnd.guid, {mode='add', name='HKEnd_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='HKEnd_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[空中] H-6K轰炸机打击完成 | hk003~hk008撤出 | " ..
            "导弹命中待评估 | 返航准备')"
        )})
    ScenEdit_SetEventAction(evHKEnd.guid, {mode='add', name='HKEnd_action'})
end

-- === DF-26 打击集群协同 ================================
-- DF-26B 打击旅就位 @ T0+0S
local evDF26BStart = ScenEdit_SetEvent('[协同] DF-26B打击旅就位', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evDF26BStart then
    ScenEdit_SetTrigger({mode='add', type='Time', name='DF26BStart_trigger',
        time = T0 + parsePT('PT0S')})
    ScenEdit_SetEventTrigger(evDF26BStart.guid, {mode='add', name='DF26BStart_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='DF26BStart_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[火箭军] DF-26B打击旅就位 | dfb001~dfb012展开 | " ..
            "各目标分配就绪 | ST-01-001/002/003/005联合打击开始')"
        )})
    ScenEdit_SetEventAction(evDF26BStart.guid, {mode='add', name='DF26BStart_action'})
end

-- DF-26D 打击旅就位 @ T0+0S
local evDF26DStart = ScenEdit_SetEvent('[协同] DF-26D打击旅就位', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evDF26DStart then
    ScenEdit_SetTrigger({mode='add', type='Time', name='DF26DStart_trigger',
        time = T0 + parsePT('PT0S')})
    ScenEdit_SetEventTrigger(evDF26DStart.guid, {mode='add', name='DF26DStart_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='DF26DStart_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[火箭军] DF-26D打击旅就位 | dfd001~dfd012展开 | " ..
            "各目标分配就绪 | 支援ST-01-001/002/003/005联合打击')"
        )})
    ScenEdit_SetEventAction(evDF26DStart.guid, {mode='add', name='DF26DStart_action'})
end

-- DF-26 联合打击结束 @ T0+2H40M
local evDF26End = ScenEdit_SetEvent('[协同] DF-26联合打击结束', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evDF26End then
    ScenEdit_SetTrigger({mode='add', type='Time', name='DF26End_trigger',
        time = T0 + parsePT('PT2H40M')})
    ScenEdit_SetEventTrigger(evDF26End.guid, {mode='add', name='DF26End_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='DF26End_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[火箭军] DF-26联合打击结束 | dfb001~dfb012/dfd001~dfd012 | " ..
            "导弹齐射完毕 | ST-01-001/002/003/005全部打击完成 | 等待卫星毁评')"
        )})
    ScenEdit_SetEventAction(evDF26End.guid, {mode='add', name='DF26End_action'})
end

-- === UUV 打击协同 (ST-01-004) ==============================
-- UUV 前出 @ T0+2H2M (与 engage 环节同时)
local evUUVStart = ScenEdit_SetEvent('[协同] Remus-600 UUV前出打击', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evUUVStart then
    ScenEdit_SetTrigger({mode='add', type='Time', name='UUVStart_trigger',
        time = T0 + parsePT('PT2H2M')})
    ScenEdit_SetEventTrigger(evUUVStart.guid, {mode='add', name='UUVStart_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='UUVStart_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[水下] Remus-600 UUV前出 | wruuv005抵近supply_kz | " ..
            "鱼雷瞄准 | ST-01-004打击开始 | 水下接敌')"
        )})
    ScenEdit_SetEventAction(evUUVStart.guid, {mode='add', name='UUVStart_action'})
end

-- UUV 打击完成 @ T0+2H18M
local evUUVEnd = ScenEdit_SetEvent('[协同] Remus-600 UUV打击完成', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evUUVEnd then
    ScenEdit_SetTrigger({mode='add', type='Time', name='UUVEnd_trigger',
        time = T0 + parsePT('PT2H18M')})
    ScenEdit_SetEventTrigger(evUUVEnd.guid, {mode='add', name='UUVEnd_trigger'})
    ScenEdit_SetAction({mode='add', type='LuaScript', name='UUVEnd_action',
        ScriptText = (
            "ScenEdit_SpecialMessage('Red', " ..
            "'[水下] Remus-600 UUV打击完成 | wruuv005命中supply_kz | " ..
            "鱼雷攻击命中 | ST-01-004打击完毕 | 待毁评确认')"
        )})
    ScenEdit_SetEventAction(evUUVEnd.guid, {mode='add', name='UUVEnd_action'})
end

-- ============================================================
-- 第五部分：全阶段结束评估
-- 触发: T0+2H40M (阶段结束时间)
-- ============================================================

local evPhaseEnd = ScenEdit_SetEvent('[阶段] 反舰作战实施阶段结束', {
    mode = 'add', IsRepeatable = false, IsActive = true,
})
if evPhaseEnd then
    ScenEdit_SetTrigger({mode='add', type='Time', name='PhaseEnd_trigger',
        time = T0 + parsePT('PT2H40M')})
    ScenEdit_SetEventTrigger(evPhaseEnd.guid, {mode='add', name='PhaseEnd_trigger'})

    local endScript = [[
local function getGuid(key)
    local g = ScenEdit_GetKeyValue(key)
    return (g and g ~= '') and g or nil
end
local targets = {
    {key='TICO_SIMOER_GUID',  name='tico_simoer'},
    {key='DDG_CHAFEI_GUID',   name='ddg_chafei'},
    {key='LHA_MEIGUO_GUID',   name='lha_meiguo'},
    {key='SUPPLY_KZ_GUID',    name='supply_kz'},
    {key='DDG_MOMUSENG_GUID', name='ddg_momuseng'},
}
local destroyed = 0
for _, t in ipairs(targets) do
    local guid = getGuid(t.key)
    if guid then
        local ok, u = pcall(ScenEdit_GetUnit, {guid = guid})
        if ok and u then
            local dmg = tonumber(tostring(u.damage):match('([%d%.]+)')) or 0
            if dmg >= 1.0 or u:isDestroyed() then
                destroyed = destroyed + 1
            end
        end
    end
end
local rate = destroyed / #targets
ScenEdit_SpecialMessage('Red', '[阶段结束] 反舰作战实施阶段结束 | '
    .. destroyed .. '/5 目标摧毁 (' .. math.floor(rate * 100) .. '%)')
if rate >= 0.5 then
    ScenEdit_SetScore('Red', 100, '海上目标毁伤率 >= 50%, 任务完成')
    ScenEdit_SpecialMessage('Red', '[任务完成] 满足终止条件 — 海上目标毁伤率 >= 50%')
    ScenEdit_EndScenario()
else
    ScenEdit_SpecialMessage('Red', '[任务未达] 毁伤率 ' .. math.floor(rate * 100)
        .. '% < 50% | 建议继续补充打击')
end
]]
    ScenEdit_SetAction({mode='add', type='LuaScript', name='PhaseEnd_action',
        ScriptText = endScript})
    ScenEdit_SetEventAction(evPhaseEnd.guid, {mode='add', name='PhaseEnd_action'})
end

-- ============================================================
-- 第三~五部分加载完毕
-- ============================================================
redMsg('[完成] 第三~五部分加载完毕 — 杀伤链事件(5链×6环节) + 跨平台协同(9组) + 阶段结束评估')
print('========================================')
print('杀伤链时序事件加载完成')
print('  ST-01-001 lha_meiguo: 6环节 @ T0~T0+2H40M')
print('  ST-01-002 tico_simoer: 6环节 @ T0~T0+2H30M')
print('  ST-01-003 ddg_chafei: 6环节 @ T0~T0+2H30M')
print('  ST-01-004 supply_kz:  6环节 @ T0~T0+2H30M')
print('  ST-01-005 ddg_momuseng:6环节 @ T0~T0+2H30M')
print('跨平台协同事件:')
print('  J-16D电子干扰开始/结束')
print('  KJ-500A预警机侦察开始/结束')
print('  H-6K轰炸机编队出发/打击完成')
print('  DF-26B/D打击旅就位/联合打击结束')
print('  Remus-600 UUV前出/打击完成')
print('阶段结束评估: T0+2H40M')
print('========================================')

