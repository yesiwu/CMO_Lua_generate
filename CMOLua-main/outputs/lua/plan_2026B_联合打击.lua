-- ============================================================
-- 联合打击计划 Lua 代码
-- 计划ID: 2026B
-- 计划名称: 联合火力突击
-- 生成时间: 2026-04-20
-- 数据来源: plan_a1_001_legacy(1).json
-- ============================================================

-- ============================================================
-- 第一部分：创建红方和蓝方阵营（如不存在）
-- ============================================================
ScenEdit_AddSide({name = "Red", color = "255,0,0"})
ScenEdit_AddSide({name = "Blue", color = "0,0,255"})

-- 设置阵营关系
ScenEdit_SetSidePosture("Red", "Blue", "H")
ScenEdit_SetSidePosture("Blue", "Red", "H")

-- ============================================================
-- 第二部分：蓝方目标（敌方舰艇）
-- ============================================================

-- 目标1: tico_simoer (提康德罗加级巡洋舰)
ScenEdit_AddUnit({
    side     = "Blue",
    type     = "Ship",
    dbid     = 40,
    name     = "tico_simoer",
    latitude = 7.970356,
    longitude = 119.503844,
    heading  = 90,
    speed    = 20
})

-- 目标2: ddg_chafei (阿里伯克级驱逐舰)
ScenEdit_AddUnit({
    side     = "Blue",
    type     = "Ship",
    dbid     = 112,
    name     = "ddg_chafei",
    latitude = 8.284662,
    longitude = 119.783273,
    heading  = 90,
    speed    = 20
})

-- 目标3: lha_meiguo (美国级两栖攻击舰)
ScenEdit_AddUnit({
    side     = "Blue",
    type     = "Ship",
    dbid     = 2362,
    name     = "lha_meiguo",
    latitude = 7.922858,
    longitude = 120.093579,
    heading  = 0,
    speed    = 15
})

-- 目标4: supply_kz (亨利J. Kaiser级补给舰)
ScenEdit_AddUnit({
    side     = "Blue",
    type     = "Ship",
    dbid     = 26,
    name     = "supply_kz",
    latitude = 8.8,
    longitude = 119.0,
    heading  = 90,
    speed    = 15
})

-- 目标5: ddg_momuseng (阿里伯克级驱逐舰)
ScenEdit_AddUnit({
    side     = "Blue",
    type     = "Ship",
    dbid     = 112,
    name     = "ddg_momuseng",
    latitude = 7.104,
    longitude = 116.28,
    heading  = 0,
    speed    = 20
})

-- ============================================================
-- 第三部分：红方打击平台 - DF-26B 导弹发射车（02打击大队）
-- ============================================================

-- 02打击大队 - DF-26B发射车 (12辆)
ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb001",
    latitude = 18.54,
    longitude = 110.00,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb002",
    latitude = 18.54,
    longitude = 110.01,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb003",
    latitude = 18.55,
    longitude = 110.00,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb004",
    latitude = 18.55,
    longitude = 110.01,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb005",
    latitude = 18.55,
    longitude = 110.01,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb006",
    latitude = 18.54,
    longitude = 110.01,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb007",
    latitude = 18.55,
    longitude = 110.01,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb008",
    latitude = 18.55,
    longitude = 110.02,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb009",
    latitude = 18.54,
    longitude = 110.03,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb010",
    latitude = 18.54,
    longitude = 110.04,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb011",
    latitude = 18.53,
    longitude = 110.05,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfb012",
    latitude = 18.53,
    longitude = 110.06,
    heading  = 90
})

-- ============================================================
-- 第四部分：红方打击平台 - DF-26D 导弹发射车（03打击大队）
-- ============================================================

-- 03打击大队 - DF-26D发射车 (12辆)
ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd001",
    latitude = 25.0,
    longitude = 115.0,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd002",
    latitude = 25.0,
    longitude = 115.01,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd003",
    latitude = 25.01,
    longitude = 115.0,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd004",
    latitude = 25.01,
    longitude = 115.01,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd005",
    latitude = 25.02,
    longitude = 115.0,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd006",
    latitude = 25.02,
    longitude = 115.01,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd007",
    latitude = 25.03,
    longitude = 115.02,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd008",
    latitude = 25.03,
    longitude = 115.03,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd009",
    latitude = 25.04,
    longitude = 115.04,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd010",
    latitude = 25.04,
    longitude = 115.05,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd011",
    latitude = 25.05,
    longitude = 115.05,
    heading  = 90
})

ScenEdit_AddUnit({
    side     = "Red",
    type     = "Facility",
    dbid     = 2879,
    name     = "dfd012",
    latitude = 25.05,
    longitude = 115.06,
    heading  = 90
})

-- ============================================================
-- 第五部分：红方打击平台 - H-6K 轰炸机（06轰炸机大队）
-- ============================================================

-- H-6K 轰炸机 (6架)
ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,
    name      = "hk003",
    latitude  = 26.32,
    longitude = 112.79,
    altitude  = 900,
    heading   = 180,
    speed     = 500,
    LoadoutID = 451
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,
    name      = "hk004",
    latitude  = 26.30,
    longitude = 112.91,
    altitude  = 1000,
    heading   = 180,
    speed     = 500,
    LoadoutID = 451
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,
    name      = "hk005",
    latitude  = 26.45,
    longitude = 112.90,
    altitude  = 1000,
    heading   = 180,
    speed     = 500,
    LoadoutID = 451
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,
    name      = "hk006",
    latitude  = 26.22,
    longitude = 112.68,
    altitude  = 1000,
    heading   = 180,
    speed     = 500,
    LoadoutID = 451
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,
    name      = "hk007",
    latitude  = 26.20,
    longitude = 112.91,
    altitude  = 1000,
    heading   = 180,
    speed     = 500,
    LoadoutID = 451
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,
    name      = "hk008",
    latitude  = 26.39,
    longitude = 112.98,
    altitude  = 1000,
    heading   = 180,
    speed     = 500,
    LoadoutID = 451
})

-- ============================================================
-- 第六部分：红方打击平台 - J-16D 电子战飞机（05干扰大队）
-- ============================================================

-- J-16D 电子战飞机 (4架)
ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 4632,
    name      = "jd002",
    latitude  = 26.0,
    longitude = 112.0,
    altitude  = 8000,
    heading   = 180,
    speed     = 600,
    LoadoutID = 753
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 4632,
    name      = "jd003",
    latitude  = 26.01,
    longitude = 112.01,
    altitude  = 8000,
    heading   = 180,
    speed     = 600,
    LoadoutID = 753
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 4632,
    name      = "jd004",
    latitude  = 26.02,
    longitude = 112.02,
    altitude  = 8000,
    heading   = 180,
    speed     = 600,
    LoadoutID = 753
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 4632,
    name      = "jd007",
    latitude  = 26.03,
    longitude = 112.03,
    altitude  = 8000,
    heading   = 180,
    speed     = 600,
    LoadoutID = 753
})

-- ============================================================
-- 第七部分：红方支援平台
-- ============================================================

-- KJ-500 预警机
ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,  -- 需要查询实际DBID
    name      = "kja001",
    latitude  = 26.32,
    longitude = 112.63,
    altitude  = 10000,
    heading   = 180,
    speed     = 400,
    LoadoutID = 451
})

-- J-20 隐身战斗机 (4架)
ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,  -- 需要查询实际DBID
    name      = "zds001",
    latitude  = 18.50,
    longitude = 109.97,
    altitude  = 1000,
    heading   = 180,
    speed     = 800,
    LoadoutID = 451
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,
    name      = "zds002",
    latitude  = 18.50,
    longitude = 109.98,
    altitude  = 1000,
    heading   = 180,
    speed     = 800,
    LoadoutID = 451
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,
    name      = "zds003",
    latitude  = 18.49,
    longitude = 109.98,
    altitude  = 1000,
    heading   = 180,
    speed     = 800,
    LoadoutID = 451
})

ScenEdit_AddUnit({
    side      = "Red",
    type      = "Aircraft",
    dbid      = 1731,
    name      = "zds004",
    latitude  = 18.49,
    longitude = 109.99,
    altitude  = 1000,
    heading   = 180,
    speed     = 800,
    LoadoutID = 451
})

-- ============================================================
-- 第八部分：创建打击任务
-- ============================================================

-- 反舰打击任务
ScenEdit_AddMission({
    side     = "Red",
    name     = "反舰打击任务",
    type     = "Strike",
    targetside = "Blue"
})

-- 巡逻任务（预警/电子掩护）
ScenEdit_AddMission({
    side  = "Red",
    name  = "电子掩护巡逻",
    type  = "Patrol",
    qty   = 4,
    patroltype = "Area"
})

-- ============================================================
-- 代码生成完毕
-- ============================================================
print("联合打击计划 Lua 代码执行完成")
print("共计创建:")
print("  - 蓝方目标: 5艘舰艇")
print("  - 红方DF-26导弹发射车: 24辆")
print("  - 红方H-6K轰炸机: 6架")
print("  - 红方J-16D电战机: 4架")
print("  - 红方支援飞机: 5架")
