-- main.lua — 演示：红/蓝双方机场部件 + 飞机创建
-- MCP 查询结果（DB3K_504）：
--
-- 【红方】
--   J-16 Flying Shark (多用途)    DBID=2853  LoadoutID=1821  Type=2001
--   H-6A Badger (轰炸机)          DBID=140   LoadoutID=87    Type=3101
--   SH-60J Seahawk (直升机)       DBID=56    Loadoutid=3     Type=6001
--   Runway (3200m)                DBID=35    Type=1001
--   A/C Hangar (4x Large)         DBID=9     Type=1001
--
-- 【蓝方】
--   F-35C Lightning II           DBID=824   LoadoutID=689   Type=2001
--   F/A-18C Hornet                DBID=8     LoadoutID=38    Type=2001
--   E-2C Hawkeye (预警机)         DBID=13    LoadoutID=42    Type=2001
--   Runway (3200m)                DBID=35    Type=1001
--   A/C Hangar (4x Large)         DBID=9     Type=1001

-- =====================================================================
-- 1. 创建阵营（pcall 防止重复运行时报错）
-- =====================================================================
pcall(ScenEdit_AddSide, { name = "红方", color = "255,0,0" })
pcall(ScenEdit_AddSide, { name = "蓝方", color = "0,0,255" })

-- 敌对关系
ScenEdit_SetSidePosture("红方", "蓝方", "H")
ScenEdit_SetSidePosture("蓝方", "红方", "H")

-- =====================================================================
-- 2. 红方机场：跑道 + 机库
-- =====================================================================
ScenEdit_AddUnit({
  side   = "红方",
  type   = "Facility",
  dbid   = 35,
  name   = "红方机场-跑道",
  latitude  = 21.0,
  longitude = 110.0,
})

ScenEdit_AddUnit({
  side   = "红方",
  type   = "Facility",
  dbid   = 9,
  name   = "红方机场-大机库",
  latitude  = 21.001,
  longitude = 110.001,
})

-- =====================================================================
-- 3. 红方飞机
-- =====================================================================

-- 3.1 J-16 多用途战斗机 x2
ScenEdit_AddUnit({
  side      = "红方",
  type      = "Aircraft",
  dbid      = 2853,
  loadoutid = 1821,
  name      = "J16-001",
  latitude  = 21.0,
  longitude = 110.0,
  heading   = 90,
  altitude  = 0,
})

ScenEdit_AddUnit({
  side      = "红方",
  type      = "Aircraft",
  dbid      = 2853,
  loadoutid = 1821,
  name      = "J16-002",
  latitude  = 21.0,
  longitude = 110.0,
  heading   = 90,
  altitude  = 0,
})

-- 3.2 H-6A 轰炸机 x1
ScenEdit_AddUnit({
  side      = "红方",
  type      = "Aircraft",
  dbid      = 140,
  loadoutid = 87,
  name      = "H6A-001",
  latitude  = 21.0,
  longitude = 110.0,
  heading   = 90,
  altitude  = 0,
})

-- 3.3 SH-60J 直升机 x1
ScenEdit_AddUnit({
  side      = "红方",
  type      = "Aircraft",
  dbid      = 56,
  loadoutid = 3,
  name      = "SH60J-001",
  latitude  = 21.0,
  longitude = 110.0,
  heading   = 90,
  altitude  = 0,
})

-- =====================================================================
-- 4. 蓝方机场：跑道 + 机库
-- =====================================================================
ScenEdit_AddUnit({
  side   = "蓝方",
  type   = "Facility",
  dbid   = 35,
  name   = "蓝方机场-跑道",
  latitude  = 15.0,
  longitude = 120.0,
})

ScenEdit_AddUnit({
  side   = "蓝方",
  type   = "Facility",
  dbid   = 9,
  name   = "蓝方机场-大机库",
  latitude  = 15.001,
  longitude = 120.001,
})

-- =====================================================================
-- 5. 蓝方飞机
-- =====================================================================

-- 5.1 F-35C 隐身战斗机 x2
ScenEdit_AddUnit({
  side      = "蓝方",
  type      = "Aircraft",
  dbid      = 824,
  loadoutid = 689,
  name      = "F35C-001",
  latitude  = 15.0,
  longitude = 120.0,
  heading   = 90,
  altitude  = 0,
})

ScenEdit_AddUnit({
  side      = "蓝方",
  type      = "Aircraft",
  dbid      = 824,
  loadoutid = 689,
  name      = "F35C-002",
  latitude  = 15.0,
  longitude = 120.0,
  heading   = 90,
  altitude  = 0,
})

-- 5.2 F/A-18C 攻击机 x2
ScenEdit_AddUnit({
  side      = "蓝方",
  type      = "Aircraft",
  dbid      = 8,
  loadoutid = 38,
  name      = "FA18C-001",
  latitude  = 15.0,
  longitude = 120.0,
  heading   = 90,
  altitude  = 0,
})

ScenEdit_AddUnit({
  side      = "蓝方",
  type      = "Aircraft",
  dbid      = 8,
  loadoutid = 38,
  name      = "FA18C-002",
  latitude  = 15.0,
  longitude = 120.0,
  heading   = 90,
  altitude  = 0,
})

-- 5.3 E-2C 预警机 x1
ScenEdit_AddUnit({
  side      = "蓝方",
  type      = "Aircraft",
  dbid      = 13,
  loadoutid = 42,
  name      = "E2C-001",
  latitude  = 15.0,
  longitude = 120.0,
  heading   = 90,
  altitude  = 0,
})

-- =====================================================================
-- 6. 演示动作：让红方 J16-001 起飞升空
-- =====================================================================
ScenEdit_SetUnit({
  side         = "红方",
  name         = "J16-001",
  currentstate = "OnStation",
  latitude     = 22.0,
  longitude    = 112.0,
  altitude     = 8000,
  heading      = 90,
})

print("[main] demo 创建完成：红蓝双方机场 + 飞机")
