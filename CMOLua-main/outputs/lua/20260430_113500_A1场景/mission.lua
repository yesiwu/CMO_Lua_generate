-- =============================================================================
-- mission.lua — 联合火力突击训练场景 任务规划
-- 场景时间: 2025/10/27 15:00:00
-- 作战时间线:
--   T+0H   : 全部平台进入部署与侦察状态
--   T+30M  : 联合火力突击开始
--   T+1H   : 第二波次打击
--   T+2H   : 战果评估
-- =============================================================================

Tool_EmulateNoConsole(true)

local NOW = ScenEdit_CurrentTime()

-- =============================================================================
-- 【第一部分】红方任务
-- =============================================================================

-- -------------------------------------------------------------------------
-- M01: DF-26 反舰弹道导弹打击任务（对蓝方航母编队）
-- 对应: 红方01打击大队 / GND_DF26B_LAUNCHER x15 + GND_DF26D_LAUNCHER
-- 目标: CVN林肯号 + 巡洋舰 + 驱逐舰群
-- -------------------------------------------------------------------------

local m01 = ScenEdit_AddMission('红方', 'M01_DF26打击', 'strike', {type='naval'})
if m01 then
    ScenEdit_SetMission('红方', 'M01_DF26打击', {
        description       = 'DF-26B/D 反舰弹道导弹对蓝方航母编队实施精确打击',
        targetside      = '蓝方',
        consumablestrike = 1,
        one_shot       = false,
    })
    print('[任务] M01_DF26打击 已创建')
else
    print('[INFO] M01_DF26打击 已存在')
end

ScenEdit_SetMission('红方', 'M01_DF26打击', {isactive = false})

-- 分配 DF-26 发射车到打击任务
local df26_list = {'dfb001','dfb002','dfb003','dfb004','dfb005',
                   'dfb006','dfb007','dfb008','dfb009','dfb010',
                   'dfd001','dfd002','dfd003','dfd004','dfd005'}
for _, name in ipairs(df26_list) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M01_DF26打击')
end

-- 分配打击目标
pcall(ScenEdit_AssignUnitAsTarget, {mission='M01_DF26打击', unitname='cvn_linkeng'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M01_DF26打击', unitname='tico_pulinsidun'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M01_DF26打击', unitname='ddg_momuseng'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M01_DF26打击', unitname='ddg_laolunsi'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M01_DF26打击', unitname='ddg_001'})

-- -------------------------------------------------------------------------
-- M02: H-6K 轰炸机对海打击任务
-- 对应: 红方01/02轰炸机大队 / BOMBER_H6K x6
-- 目标: 蓝方舰艇群
-- -------------------------------------------------------------------------

local m02 = ScenEdit_AddMission('红方', 'M02_H6K轰炸打击', 'strike', {type='naval'})
if m02 then
    ScenEdit_SetMission('红方', 'M02_H6K轰炸打击', {
        description       = 'H-6K 轰炸机群对蓝方舰艇实施反舰导弹攻击',
        targetside      = '蓝方',
        consumablestrike = 1,
        one_shot       = true,
    })
    print('[任务] M02_H6K轰炸打击 已创建')
else
    print('[INFO] M02_H6K轰炸打击 已存在')
end

ScenEdit_SetMission('红方', 'M02_H6K轰炸打击', {isactive = false})

local h6k_names = {'h6k001','h6k002','h6k003','h6k004','h6k005','h6k006'}
for _, name in ipairs(h6k_names) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M02_H6K轰炸打击')
end

pcall(ScenEdit_AssignUnitAsTarget, {mission='M02_H6K轰炸打击', unitname='cvn_linkeng'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M02_H6K轰炸打击', unitname='ddg_momuseng'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M02_H6K轰炸打击', unitname='lha_america_001'})

-- -------------------------------------------------------------------------
-- M03: J-16 多用途战机打击任务
-- 对应: 红方02战机编队 / AC_J16 x10
-- 目标: 蓝方前卫驱逐舰
-- -------------------------------------------------------------------------

local m03 = ScenEdit_AddMission('红方', 'M03_J16空中打击', 'strike', {type='naval'})
if m03 then
    ScenEdit_SetMission('红方', 'M03_J16空中打击', {
        description       = 'J-16 机群对蓝方前卫驱逐舰实施协同打击',
        targetside      = '蓝方',
        consumablestrike = 1,
        one_shot       = true,
        flightsize     = 4,
        minaircraftreq = 4,
    })
    print('[任务] M03_J16空中打击 已创建')
else
    print('[INFO] M03_J16空中打击 已存在')
end

ScenEdit_SetMission('红方', 'M03_J16空中打击', {isactive = false})

local j16_names = {'j16001','j16002','j16003','j16004','j16005','j16006','j16007','j16008','j16009','j16010'}
for _, name in ipairs(j16_names) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M03_J16空中打击')
end

pcall(ScenEdit_AssignUnitAsTarget, {mission='M03_J16空中打击', unitname='ddg_momuseng'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M03_J16空中打击', unitname='ddg_laolunsi'})

-- -------------------------------------------------------------------------
-- M04: J-16D 电子战支援任务
-- 对应: 红方01电子战编队 / AC_J16D x7
-- 角色: 电磁压制 + 目标照射支援
-- -------------------------------------------------------------------------

local m04 = ScenEdit_AddMission('红方', 'M04_J16D电子战', 'patrol', {type='SEAD'})
if m04 then
    ScenEdit_SetMission('红方', 'M04_J16D电子战', {
        description      = 'J-16D 实施广域电子压制，掩护空中打击编队',
        targetside     = '蓝方',
        flightsize     = 2,
        minaircraftreq = 2,
    })
    print('[任务] M04_J16D电子战 已创建')
else
    print('[INFO] M04_J16D电子战 已存在')
end

-- 巡逻区域（覆盖蓝方舰艇上空）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-电子战区-1', latitude=3.0,  longitude=108.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-电子战区-2', latitude=3.0,  longitude=112.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-电子战区-3', latitude=-1.0, longitude=112.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-电子战区-4', latitude=-1.0, longitude=108.0, highlighted=false, type='generic'})

ScenEdit_SetMission('红方', 'M04_J16D电子战', {
    patrolzone   = {'RP-电子战区-1','RP-电子战区-2','RP-电子战区-3','RP-电子战区-4'},
    patrolType   = 'FighterCAP',
    onethirdrule = false,
})

local j16d_names = {'jd001','jd002','jd003','jd004','jd005','jd006','jd007'}
for _, name in ipairs(j16d_names) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M04_J16D电子战')
end

-- -------------------------------------------------------------------------
-- M05: J-20 隐身战斗机空中优势任务
-- 对应: 红方01隐身战机编队 / AC_J20 x8
-- -------------------------------------------------------------------------

local m05 = ScenEdit_AddMission('红方', 'M05_J20空中优势', 'patrol', {type='air'})
if m05 then
    ScenEdit_SetMission('红方', 'M05_J20空中优势', {
        description      = 'J-20 隐身战机在作战区域夺取制空权',
        targetside     = '蓝方',
        flightsize     = 4,
        minaircraftreq = 2,
    })
    print('[任务] M05_J20空中优势 已创建')
else
    print('[INFO] M05_J20空中优势 已存在')
end

pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J20巡逻-1', latitude=5.0,  longitude=108.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J20巡逻-2', latitude=5.0,  longitude=115.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J20巡逻-3', latitude=-1.0, longitude=115.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-J20巡逻-4', latitude=-1.0, longitude=108.0, highlighted=false, type='generic'})

ScenEdit_SetMission('红方', 'M05_J20空中优势', {
    patrolzone   = {'RP-J20巡逻-1','RP-J20巡逻-2','RP-J20巡逻-3','RP-J20巡逻-4'},
    patrolType   = 'FighterCAP',
    onethirdrule = false,
})

local j20_names = {'j20001','j20002','j20003','j20004','j20005','j20006','j20007','j20008'}
for _, name in ipairs(j20_names) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M05_J20空中优势')
end

-- -------------------------------------------------------------------------
-- M06: KJ-500 预警与侦察巡逻
-- 对应: 红方预警机编队 / AWACS_KJ500 x2
-- -------------------------------------------------------------------------

local m06 = ScenEdit_AddMission('红方', 'M06_KJ500预警', 'patrol', {type='air'})
if m06 then
    ScenEdit_SetMission('红方', 'M06_KJ500预警', {
        description      = 'KJ-500 预警机执行大范围侦察与指挥引导',
        flightsize     = 1,
        minaircraftreq = 1,
    })
    print('[任务] M06_KJ500预警 已创建')
else
    print('[INFO] M06_KJ500预警 已存在')
end

pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-KJ500-1', latitude=5.0,  longitude=106.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-KJ500-2', latitude=5.0,  longitude=116.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-KJ500-3', latitude=-1.0, longitude=116.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-KJ500-4', latitude=-1.0, longitude=106.0, highlighted=false, type='generic'})

ScenEdit_SetMission('红方', 'M06_KJ500预警', {
    patrolzone   = {'RP-KJ500-1','RP-KJ500-2','RP-KJ500-3','RP-KJ500-4'},
    patrolType   = 'AWACS',
    onethirdrule = false,
})

for _, name in ipairs({'kj500001','kj500002'}) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M06_KJ500预警')
end

-- -------------------------------------------------------------------------
-- M07: 水面舰艇反舰打击任务
-- 对应: 红方01/02水面舰艇支队 / 052D x3 + 055 x1 + 054A x4
-- -------------------------------------------------------------------------

local m07 = ScenEdit_AddMission('红方', 'M07_水面舰打击', 'strike', {type='naval'})
if m07 then
    ScenEdit_SetMission('红方', 'M07_水面舰打击', {
        description       = '052D/055/054A 对蓝方舰艇实施协同反舰打击',
        targetside      = '蓝方',
        consumablestrike = 1,
        one_shot       = false,
    })
    print('[任务] M07_水面舰打击 已创建')
else
    print('[INFO] M07_水面舰打击 已存在')
end

ScenEdit_SetMission('红方', 'M07_水面舰打击', {isactive = false})

local red_ships = {'ddg_01073','ddg_09006','ddg_01072','ddg_01005','ffg_05005','ffg_05006','ffg_05007','ffg_05008'}
for _, name in ipairs(red_ships) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M07_水面舰打击')
end

pcall(ScenEdit_AssignUnitAsTarget, {mission='M07_水面舰打击', unitname='cvn_linkeng'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M07_水面舰打击', unitname='ddg_momuseng'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M07_水面舰打击', unitname='lha_america_001'})

-- -------------------------------------------------------------------------
-- M08: 潜艇/UUV 反舰巡逻与打击任务
-- 对应: 红方常规潜艇大队 + 无人潜艇大队
-- -------------------------------------------------------------------------

local m08 = ScenEdit_AddMission('红方', 'M08_潜艇UUV巡逻', 'patrol', {type='sub'})
if m08 then
    ScenEdit_SetMission('红方', 'M08_潜艇UUV巡逻', {
        description      = '039C 潜艇 + UUV 无人潜航器对蓝方水下区域实施侦察与伏击',
        targetside     = '蓝方',
        flightsize     = 4,
        minaircraftreq = 4,
    })
    print('[任务] M08_潜艇UUV巡逻 已创建')
else
    print('[INFO] M08_潜艇UUV巡逻 已存在')
end

-- 巡逻区域（水下伏击区）
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-潜艇伏击-1', latitude=0.0,  longitude=105.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-潜艇伏击-2', latitude=0.0,  longitude=107.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-潜艇伏击-3', latitude=6.0,  longitude=107.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='红方', name='RP-潜艇伏击-4', latitude=6.0,  longitude=105.0, highlighted=false, type='generic'})

ScenEdit_SetMission('红方', 'M08_潜艇UUV巡逻', {
    patrolzone   = {'RP-潜艇伏击-1','RP-潜艇伏击-2','RP-潜艇伏击-3','RP-潜艇伏击-4'},
    patrolType   = 'SubHunter',
    onethirdrule = false,
})

-- 分配潜艇
pcall(ScenEdit_AssignUnitToMission, 'sub039c001', 'M08_潜艇UUV巡逻')
pcall(ScenEdit_AssignUnitToMission, 'sub039c002', 'M08_潜艇UUV巡逻')

-- 分配 UUV（UUV 数量多，轮流分配）
local uuv_names = {'wruuv001','wruuv002','wruuv003','wruuv004','wruuv005',
                   'wruuv006','wruuv007','wruuv008','wruuv009','wruuv010'}
for _, name in ipairs(uuv_names) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M08_潜艇UUV巡逻')
end

pcall(ScenEdit_AssignUnitAsTarget, {mission='M08_潜艇UUV巡逻', unitname='cvn_linkeng'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M08_潜艇UUV巡逻', unitname='ffg_richmond_001'})

-- =============================================================================
-- 【第二部分】蓝方任务
-- =============================================================================

-- -------------------------------------------------------------------------
-- M11: F-35C/B 战斗空中巡逻（CAP）
-- 对应: 蓝方03闪电战斗机编队 / F-35C x3 + F-35B x4
-- -------------------------------------------------------------------------

local m11 = ScenEdit_AddMission('蓝方', 'M11_F35_CAP', 'patrol', {type='air'})
if m11 then
    ScenEdit_SetMission('蓝方', 'M11_F35_CAP', {
        description      = 'F-35C/B 在航母编队上空执行战斗空中巡逻',
        flightsize     = 4,
        minaircraftreq = 3,
    })
    print('[任务] M11_F35_CAP 已创建')
else
    print('[INFO] M11_F35_CAP 已存在')
end

pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-F35CAP-1', latitude=2.0,  longitude=104.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-F35CAP-2', latitude=2.0,  longitude=108.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-F35CAP-3', latitude=-2.0, longitude=108.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-F35CAP-4', latitude=-2.0, longitude=104.0, highlighted=false, type='generic'})

ScenEdit_SetMission('蓝方', 'M11_F35_CAP', {
    patrolzone   = {'B-RP-F35CAP-1','B-RP-F35CAP-2','B-RP-F35CAP-3','B-RP-F35CAP-4'},
    patrolType   = 'FighterCAP',
    onethirdrule = false,
})

local f35_names = {'f35c_001','f35c_002','f35c_003','f35b_001','f35b_002','f35b_003','f35b_004'}
for _, name in ipairs(f35_names) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M11_F35_CAP')
end

-- -------------------------------------------------------------------------
-- M12: 蓝方 H-6K 对陆/对海打击任务
-- 对应: 蓝方02轰炸机编队 / H-6K x6
-- -------------------------------------------------------------------------

local m12 = ScenEdit_AddMission('蓝方', 'M12_蓝方轰炸', 'strike', {type='naval'})
if m12 then
    ScenEdit_SetMission('蓝方', 'M12_蓝方轰炸', {
        description       = '蓝方 H-6K 轰炸机对红方舰艇实施反舰打击',
        targetside      = '红方',
        consumablestrike = 1,
        one_shot       = true,
        flightsize     = 3,
        minaircraftreq = 3,
    })
    print('[任务] M12_蓝方轰炸 已创建')
else
    print('[INFO] M12_蓝方轰炸 已存在')
end

ScenEdit_SetMission('蓝方', 'M12_蓝方轰炸', {isactive = false})

local h6k_blue_names = {'h6k_b001','h6k_b002','h6k_b003','h6k_b004','h6k_b005','h6k_b006'}
for _, name in ipairs(h6k_blue_names) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M12_蓝方轰炸')
end

pcall(ScenEdit_AssignUnitAsTarget, {mission='M12_蓝方轰炸', unitname='ddg_01005'})
pcall(ScenEdit_AssignUnitAsTarget, {mission='M12_蓝方轰炸', unitname='ddg_01073'})

-- -------------------------------------------------------------------------
-- M13: 蓝方舰艇区域防空巡逻
-- 对应: DDG + Ticonderoga + FFG
-- -------------------------------------------------------------------------

local m13 = ScenEdit_AddMission('蓝方', 'M13_蓝方防空', 'patrol', {type='naval'})
if m13 then
    ScenEdit_SetMission('蓝方', 'M13_蓝方防空', {
        description      = 'DDG/Ticonderoga/FFG 在编队周围执行区域防空巡逻',
        flightsize     = 4,
        minaircraftreq = 4,
    })
    print('[任务] M13_蓝方防空 已创建')
else
    print('[INFO] M13_蓝方防空 已存在')
end

pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-防空区-1', latitude=2.0, longitude=104.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-防空区-2', latitude=2.0, longitude=108.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-防空区-3', latitude=-2.0, longitude=108.0, highlighted=false, type='generic'})
pcall(ScenEdit_AddReferencePoint, {side='蓝方', name='B-RP-防空区-4', latitude=-2.0, longitude=104.0, highlighted=false, type='generic'})

ScenEdit_SetMission('蓝方', 'M13_蓝方防空', {
    patrolzone   = {'B-RP-防空区-1','B-RP-防空区-2','B-RP-防空区-3','B-RP-防空区-4'},
    patrolType   = 'AreaCAP',
    onethirdrule = false,
})

local blue_ships = {'ddg_momuseng','ddg_laolunsi','ddg_001','ddg_002','ddg_003',
                    'tico_pulinsidun','ffg_richmond_001'}
for _, name in ipairs(blue_ships) do
    pcall(ScenEdit_AssignUnitToMission, name, 'M13_蓝方防空')
end

-- =============================================================================
-- 【第三部分】时间事件链（TCA）
-- 对应 JSON 中的作战阶段与时间节点
-- 场景开始时间: 2025/10/27 15:00:00
-- =============================================================================

-- -------------------------------------------------------------------------
-- EV_A: 作战开始（T+0，场景加载时触发）
-- 进入侦察与巡逻阶段
-- -------------------------------------------------------------------------

local evA = ScenEdit_SetEvent('EV_A_作战开始', {mode='add', IsRepeatable=false, IsActive=true})
ScenEdit_SetTrigger({mode='add', type='ScenLoaded', name='场景加载触发'})
ScenEdit_SetEventTrigger(evA.guid, {mode='add', name='场景加载触发'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='A_开始通知',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【Phase 1 — 侦察与部署】全部平台进入侦察与巡逻状态，密切关注蓝方动向")\r\n'..
                 'ScenEdit_SpecialMessage("蓝方", "【警戒】编队保持高度戒备，密切关注电磁活动")'})
ScenEdit_SetEventAction(evA.guid, {mode='add', name='A_开始通知'})

-- -------------------------------------------------------------------------
-- EV_T30: T+30min — 联合火力突击开始
-- 对应 JSON 作战决心中的"空中打击"阶段
-- -------------------------------------------------------------------------

local evT30 = ScenEdit_SetEvent('EV_T30_联合打击', {mode='add', IsRepeatable=false, IsActive=true})
ScenEdit_SetTrigger({mode='add', type='Time', name='T30触发',
    time = NOW + 1800})  -- 1800 秒 = 30 分钟
ScenEdit_SetEventTrigger(evT30.guid, {mode='add', name='T30触发'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='T30_DF26激活',
    ScriptText = 'local ok = pcall(ScenEdit_SetMission, "红方", "M01_DF26打击", {isactive=true})\r\n'..
                 'ScenEdit_SpecialMessage("红方", "【Phase 2 — DF-26 打击开始】反舰弹道导弹对蓝方航母编队发起第一波次攻击！")'})
ScenEdit_SetEventAction(evT30.guid, {mode='add', name='T30_DF26激活'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='T30_J16D激活',
    ScriptText = 'pcall(ScenEdit_SetEMCON, "Side", "红方", "Radar=Active;Sonar=Active;OECM=Active")\r\n'..
                 'ScenEdit_SpecialMessage("红方", "【Phase 2 — 电磁压制】J-16D 全面开启电子战模式，蓝方雷达效能受限")'})
ScenEdit_SetEventAction(evT30.guid, {mode='add', name='T30_J16D激活'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='T30_蓝方警报',
    ScriptText = 'ScenEdit_SpecialMessage("蓝方", "【警报】探测到弹道导弹来袭！编队立即启动反导拦截！")\r\n'..
                 'pcall(ScenEdit_SetMission, "蓝方", "M11_F35_CAP", {isactive=true})'})
ScenEdit_SetEventAction(evT30.guid, {mode='add', name='T30_蓝方警报'})

-- -------------------------------------------------------------------------
-- EV_T40: T+40min — 空中打击编队前出
-- -------------------------------------------------------------------------

local evT40 = ScenEdit_SetEvent('EV_T40_空中前出', {mode='add', IsRepeatable=false, IsActive=true})
ScenEdit_SetTrigger({mode='add', type='Time', name='T40触发',
    time = NOW + 2400})  -- 40 分钟
ScenEdit_SetEventTrigger(evT40.guid, {mode='add', name='T40触发'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='T40_H6K激活',
    ScriptText = 'pcall(ScenEdit_SetMission, "红方", "M02_H6K轰炸打击", {isactive=true})\r\n'..
                 'pcall(ScenEdit_SetMission, "红方", "M03_J16空中打击", {isactive=true})\r\n'..
                 'ScenEdit_SpecialMessage("红方", "【Phase 2续 — 空中突击】H-6K + J-16 机群前出，对蓝方舰艇发起导弹攻击！")'})
ScenEdit_SetEventAction(evT40.guid, {mode='add', name='T40_H6K激活'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='T40_蓝方应对',
    ScriptText = 'ScenEdit_SpecialMessage("蓝方", "【拦截】F-35 机群起飞拦截来袭导弹！防空系统全力运转！")'})
ScenEdit_SetEventAction(evT40.guid, {mode='add', name='T40_蓝方应对'})

-- -------------------------------------------------------------------------
-- EV_T60: T+60min — 第二波次打击
-- -------------------------------------------------------------------------

local evT60 = ScenEdit_SetEvent('EV_T60_第二波次', {mode='add', IsRepeatable=false, IsActive=true})
ScenEdit_SetTrigger({mode='add', type='Time', name='T60触发',
    time = NOW + 3600})  -- 60 分钟
ScenEdit_SetEventTrigger(evT60.guid, {mode='add', name='T60触发'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='T60_水面打击激活',
    ScriptText = 'pcall(ScenEdit_SetMission, "红方", "M07_水面舰打击", {isactive=true})\r\n'..
                 'ScenEdit_SpecialMessage("红方", "【Phase 3 — 联合打击】052D/055/054A 驱逐舰编队发起协同反舰导弹攻击！")'})
ScenEdit_SetEventAction(evT60.guid, {mode='add', name='T60_水面打击激活'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='T60_蓝方反击',
    ScriptText = 'pcall(ScenEdit_SetMission, "蓝方", "M12_蓝方轰炸", {isactive=true})\r\n'..
                 'ScenEdit_SpecialMessage("蓝方", "【反击】H-6K 轰炸机起飞，对红方舰艇实施对向打击！")'})
ScenEdit_SetEventAction(evT60.guid, {mode='add', name='T60_蓝方反击'})

-- -------------------------------------------------------------------------
-- EV_T120: T+120min — 战果评估
-- -------------------------------------------------------------------------

local evT120 = ScenEdit_SetEvent('EV_T120_战果评估', {mode='add', IsRepeatable=false, IsActive=true})
ScenEdit_SetTrigger({mode='add', type='Time', name='T120触发',
    time = NOW + 7200})  -- 120 分钟
ScenEdit_SetEventTrigger(evT120.guid, {mode='add', name='T120触发'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='T120_评估通知',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【战果评估】联合火力突击效果评估中，请检查各目标毁伤状态")\r\n'..
                 'ScenEdit_SpecialMessage("蓝方", "【战损报告】编队遭受攻击，损失情况统计中")'})
ScenEdit_SetEventAction(evT120.guid, {mode='add', name='T120_评估通知'})

-- =============================================================================
-- 【第四部分】胜利条件判定事件
-- =============================================================================

-- 红方胜利: CVN 林肯号 70% 毁伤
local evWinCVN = ScenEdit_SetEvent('EV_红方胜利_CVN', {mode='add', IsRepeatable=false, IsActive=true})
ScenEdit_SetTrigger({mode='add', type='UnitDamaged', name='CVN受损',
    side='蓝方', unitname='cvn_linkeng', damaged_threshold=70})
ScenEdit_SetEventTrigger(evWinCVN.guid, {mode='add', name='CVN受损'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='WinCVN',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【任务完成】蓝方CVN达成70%毁伤，联合火力打击任务成功！")\r\n'..
                 'ScenEdit_SpecialMessage("蓝方", "【任务失败】航母丧失作战能力")\r\n'..
                 'ScenEdit_SetScore("红方", 100, "CVN击毁")\r\n'..
                 'ScenEdit_SetScore("蓝方", -100, "CVN损失")'})
ScenEdit_SetEventAction(evWinCVN.guid, {mode='add', name='WinCVN'})

-- 红方胜利: 蓝方舰艇损失过半（任意3艘舰艇50%毁伤）
local evWinShips = ScenEdit_SetEvent('EV_红方胜利_舰艇', {mode='add', IsRepeatable=true, IsActive=true})
ScenEdit_SetTrigger({mode='add', type='UnitDamaged', name='DDG受损',
    side='蓝方', unitname='ddg_momuseng', damaged_threshold=50})
ScenEdit_SetEventTrigger(evWinShips.guid, {mode='add', name='DDG受损'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='WinDDG',
    ScriptText = 'ScenEdit_SpecialMessage("红方", "【战果确认】蓝方前卫驱逐舰被重创，区域拒止目标达成")\r\n'..
                 'ScenEdit_SetScore("红方", 50, "驱逐舰击伤")'})
ScenEdit_SetEventAction(evWinShips.guid, {mode='add', name='WinDDG'})

-- 蓝方胜利: 红方 055 驱逐舰 60% 毁伤
local evWin055 = ScenEdit_SetEvent('EV_蓝方胜利_055', {mode='add', IsRepeatable=false, IsActive=true})
ScenEdit_SetTrigger({mode='add', type='UnitDamaged', name='055受损',
    side='红方', unitname='ddg_01005', damaged_threshold=60})
ScenEdit_SetEventTrigger(evWin055.guid, {mode='add', name='055受损'})

ScenEdit_SetAction({mode='add', type='LuaScript', name='Win055',
    ScriptText = 'ScenEdit_SpecialMessage("蓝方", "【任务完成】红方055驱逐舰被重创，防线成功守住！")\r\n'..
                 'ScenEdit_SpecialMessage("红方", "【任务失败】055驱逐舰丧失战斗力，联合打击受阻")\r\n'..
                 'ScenEdit_SetScore("蓝方", 100, "055击伤")\r\n'..
                 'ScenEdit_SetScore("红方", -50, "055损失")'})
ScenEdit_SetEventAction(evWin055.guid, {mode='add', name='Win055'})

print('========================================')
print('任务规划加载完成 — mission.lua')
print('红方任务: M01~M08')
print('蓝方任务: M11~M13')
print('事件链: EV_A(开始) -> EV_T30(联合打击) -> EV_T40(空中前出) -> EV_T60(第二波次) -> EV_T120(评估)')
print('胜利条件: CVN70%毁伤 / DDG50%毁伤 / 055达60%毁伤')
print('========================================')
