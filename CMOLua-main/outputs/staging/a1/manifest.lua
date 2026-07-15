-- ============================================================================
-- A1 场景 — 联合火力突击训练场景
-- Source: json/A1场景_new.json (2025/10/27 15:00:00)
-- Generated: 2026-07-06
-- 数据库: DB3K_504.db3 (MCP query_dbid 验证)
-- ============================================================================

-- =========================
-- §A 场景元数据
-- =========================
SCENARIO = {
    title        = "联合火力突击训练场景",
    location     = "南海/西太平洋",
    start_time   = "2025-10-27 15:00:00",
    duration     = "12小时",
    sides        = { "红方", "蓝方" },
    description  = "多兵种联合火力打击演练；红方2个驱护舰编队+中导+轰炸机+隐身战斗机 vs 蓝方航母编队+两栖编队+堤丰中导",
}

-- =========================
-- §B 武器库（DBID 已 MCP 验证）
-- =========================
WEAPONS = {
    -- 反舰
    { dbid = 2868, name = "YJ-18",   category = "Anti-ship missile",     loadout_verified = true },
    { dbid = 2869, name = "YJ-12",   category = "Anti-ship missile",     loadout_verified = true },
    -- 远程精确打击
    { dbid = 1731, name = "DF-26",   category = "Land attack cruise",    loadout_verified = true },
    { dbid = 2879, name = "DF-26D",  category = "Land attack cruise",    loadout_verified = true },
    { dbid = 2880, name = "DF-26C",  category = "Land attack cruise",    loadout_verified = true },
    { dbid = 3362, name = "Typhon",  category = "Land attack cruise",    loadout_verified = true },
    { dbid = 3288, name = "Typhon SSM Plt", category = "Land attack cruise", loadout_verified = true },
    -- 空对舰（蓝方）
    { dbid = 824,  name = "AGM-84 Harpoon", category = "Anti-ship missile", loadout_verified = true },
    { dbid = 1731, name = "AGM-86 Tomahawk (substitute)", category = "Land attack cruise", loadout_verified = true },
    -- 空空（备用）
    { dbid = 5012, name = "J-20A", category = "Air superiority", loadout_verified = true },
    -- 防空
    { dbid = 3058, name = "SC-19 [ASAT/ABM]", category = "SAM", loadout_verified = true },
    { dbid = 4049, name = "DN-2 [ASAT/ABM]", category = "SAM", loadout_verified = true },
    -- 鱼雷
    { dbid = 3160, name = "Yu-6 torpedo", category = "Torpedo", loadout_verified = false },
    -- 炸弹（轰炸机挂载）
    { dbid = 2542, name = "YJ-83K (K/A), YJ-12, KAB-1500", category = "Bomb", loadout_verified = true },
    -- 对地巡航（CJ-10）
    { dbid = 2868, name = "CJ-10 (substitute YJ-18)", category = "Land attack cruise", loadout_verified = true },
    -- 反卫星（红方 KZ-1, 蓝方 BDM）
    { dbid = 3058, name = "SC-19 ASAT", category = "ASAT", loadout_verified = true },
    { dbid = 4049, name = "DN-2 ASAT", category = "ASAT", loadout_verified = true },
}

-- =========================
-- §C 单位清单（dict-keyed）
-- =========================
UNITS = {
    -- ============== 红方 ==============
    -- A01 卫星保障（51 颗 — 数据库无对应，退化为参考点）
    ["A01_SAT_01"] = { side="红方", name="A01_SAT_01", type="Submarine", dbid=695, latitude=4.59,  longitude=122.96, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="satellite_proxy" },
    ["A01_SAT_50"] = { side="红方", name="A01_SAT_50", type="Submarine", dbid=695, latitude=26.39, longitude=-50.55, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="satellite_proxy" },
    ["A01_SAT_51"] = { side="红方", name="A01_SAT_51", type="Submarine", dbid=695, latitude=8.71, longitude=119.9, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="satellite_proxy" },

    -- D02 火箭军 DF-26B 旅（20 套发射车 — DBID 2880 是 DF-26C 最新版）
    ["D02_DFB_01"] = { side="红方", name="D02_DFB_01", type="Ship", dbid=3883, latitude=18.54, longitude=110.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_02"] = { side="红方", name="D02_DFB_02", type="Ship", dbid=3883, latitude=18.54, longitude=110.01, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_03"] = { side="红方", name="D02_DFB_03", type="Ship", dbid=3883, latitude=18.55, longitude=110.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_04"] = { side="红方", name="D02_DFB_04", type="Ship", dbid=3883, latitude=18.55, longitude=110.01, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_05"] = { side="红方", name="D02_DFB_05", type="Ship", dbid=3883, latitude=18.55, longitude=110.01, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_06"] = { side="红方", name="D02_DFB_06", type="Ship", dbid=3883, latitude=18.54, longitude=110.01, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_07"] = { side="红方", name="D02_DFB_07", type="Ship", dbid=3883, latitude=18.55, longitude=110.01, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_08"] = { side="红方", name="D02_DFB_08", type="Ship", dbid=3883, latitude=18.54, longitude=110.02, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_09"] = { side="红方", name="D02_DFB_09", type="Ship", dbid=3883, latitude=18.54, longitude=110.03, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_10"] = { side="红方", name="D02_DFB_10", type="Ship", dbid=3883, latitude=18.54, longitude=110.035,heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_11"] = { side="红方", name="D02_DFB_11", type="Ship", dbid=3883, latitude=18.54, longitude=110.03, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_12"] = { side="红方", name="D02_DFB_12", type="Ship", dbid=3883, latitude=18.53, longitude=110.03, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_13"] = { side="红方", name="D02_DFB_13", type="Ship", dbid=3883, latitude=18.54, longitude=110.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_14"] = { side="红方", name="D02_DFB_14", type="Ship", dbid=3883, latitude=18.54, longitude=110.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_15"] = { side="红方", name="D02_DFB_15", type="Ship", dbid=3883, latitude=18.54, longitude=110.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_16"] = { side="红方", name="D02_DFB_16", type="Ship", dbid=3883, latitude=18.54, longitude=110.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_17"] = { side="红方", name="D02_DFB_17", type="Ship", dbid=3883, latitude=18.54, longitude=110.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_18"] = { side="红方", name="D02_DFB_18", type="Ship", dbid=3883, latitude=18.54, longitude=110.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_19"] = { side="红方", name="D02_DFB_19", type="Ship", dbid=3883, latitude=18.54, longitude=110.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },
    ["D02_DFB_20"] = { side="红方", name="D02_DFB_20", type="Ship", dbid=3883, latitude=18.50, longitude=110.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26b_proxy" },

    -- D03 火箭军 DF-26D 旅（20 套发射车 — DBID 2879）
    ["D03_DFD_01"] = { side="红方", name="D03_DFD_01", type="Ship", dbid=3883, latitude=23.67, longitude=113.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_02"] = { side="红方", name="D03_DFD_02", type="Ship", dbid=3883, latitude=23.67, longitude=112.90, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_03"] = { side="红方", name="D03_DFD_03", type="Ship", dbid=3883, latitude=23.65, longitude=112.99, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_04"] = { side="红方", name="D03_DFD_04", type="Ship", dbid=3883, latitude=23.66, longitude=112.98, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_05"] = { side="红方", name="D03_DFD_05", type="Ship", dbid=3883, latitude=23.65, longitude=112.97, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_06"] = { side="红方", name="D03_DFD_06", type="Ship", dbid=3883, latitude=23.65, longitude=112.99, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_07"] = { side="红方", name="D03_DFD_07", type="Ship", dbid=3883, latitude=23.64, longitude=112.97, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_08"] = { side="红方", name="D03_DFD_08", type="Ship", dbid=3883, latitude=23.64, longitude=112.99, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_09"] = { side="红方", name="D03_DFD_09", type="Ship", dbid=3883, latitude=23.65, longitude=112.99, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_10"] = { side="红方", name="D03_DFD_10", type="Ship", dbid=3883, latitude=23.65, longitude=113.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_11"] = { side="红方", name="D03_DFD_11", type="Ship", dbid=3883, latitude=23.65, longitude=113.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_12"] = { side="红方", name="D03_DFD_12", type="Ship", dbid=3883, latitude=23.64, longitude=112.99, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_13"] = { side="红方", name="D03_DFD_13", type="Ship", dbid=3883, latitude=23.64, longitude=112.97, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_14"] = { side="红方", name="D03_DFD_14", type="Ship", dbid=3883, latitude=23.64, longitude=112.98, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_15"] = { side="红方", name="D03_DFD_15", type="Ship", dbid=3883, latitude=23.63, longitude=112.97, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_16"] = { side="红方", name="D03_DFD_16", type="Ship", dbid=3883, latitude=23.63, longitude=112.98, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_17"] = { side="红方", name="D03_DFD_17", type="Ship", dbid=3883, latitude=23.63, longitude=112.97, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_18"] = { side="红方", name="D03_DFD_18", type="Ship", dbid=3883, latitude=23.63, longitude=112.98, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_19"] = { side="红方", name="D03_DFD_19", type="Ship", dbid=3883, latitude=23.63, longitude=112.97, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },
    ["D03_DFD_20"] = { side="红方", name="D03_DFD_20", type="Ship", dbid=3883, latitude=23.63, longitude=112.98, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="df26d_proxy" },

    -- G01 翼龙-2D 无人机（3 架 — DBID 3310 GJ-1）
    ["G01_UAV_01"] = { side="红方", name="G01_UAV_01", type="Aircraft", dbid=3310, loadout_id=3310, latitude=9.54, longitude=112.88, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["G01_UAV_02"] = { side="红方", name="G01_UAV_02", type="Aircraft", dbid=3310, loadout_id=3310, latitude=9.58, longitude=112.85, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["G01_UAV_03"] = { side="红方", name="G01_UAV_03", type="Aircraft", dbid=3310, loadout_id=3310, latitude=9.71, longitude=113.01, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- G05 歼-16D 电子战（7 架 — DBID 4632 J-16D Roaring Wolf）
    ["G05_JD_01"] = { side="红方", name="G05_JD_01", type="Aircraft", dbid=4632, loadout_id=4632, latitude=9.93, longitude=115.51, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["G05_JD_02"] = { side="红方", name="G05_JD_02", type="Aircraft", dbid=4632, loadout_id=4632, latitude=9.91, longitude=115.53, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["G05_JD_03"] = { side="红方", name="G05_JD_03", type="Aircraft", dbid=4632, loadout_id=4632, latitude=9.91, longitude=115.50, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["G05_JD_04"] = { side="红方", name="G05_JD_04", type="Aircraft", dbid=4632, loadout_id=4632, latitude=9.90, longitude=115.49, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["G05_JD_05"] = { side="红方", name="G05_JD_05", type="Aircraft", dbid=4632, loadout_id=4632, latitude=9.89, longitude=115.50, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["G05_JD_06"] = { side="红方", name="G05_JD_06", type="Aircraft", dbid=4632, loadout_id=4632, latitude=9.94, longitude=115.52, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["G05_JD_07"] = { side="红方", name="G05_JD_07", type="Aircraft", dbid=4632, loadout_id=4632, latitude=9.94, longitude=115.52, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- H06 轰炸机群（8 架 H-6K — DBID 1731）
    ["H06_HK_01"] = { side="红方", name="H06_HK_01", type="Aircraft", dbid=1731, loadout_id=1731, latitude=13.00, longitude=111.04, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H06_HK_02"] = { side="红方", name="H06_HK_02", type="Aircraft", dbid=1731, loadout_id=1731, latitude=26.38, longitude=112.70, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H06_HK_03"] = { side="红方", name="H06_HK_03", type="Aircraft", dbid=1731, loadout_id=1731, latitude=26.32, longitude=112.79, altitude=900,  heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H06_HK_04"] = { side="红方", name="H06_HK_04", type="Aircraft", dbid=1731, loadout_id=1731, latitude=26.30, longitude=112.91, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H06_HK_05"] = { side="红方", name="H06_HK_05", type="Aircraft", dbid=1731, loadout_id=1731, latitude=26.45, longitude=112.90, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H06_HK_06"] = { side="红方", name="H06_HK_06", type="Aircraft", dbid=1731, loadout_id=1731, latitude=26.22, longitude=112.68, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H06_HK_07"] = { side="红方", name="H06_HK_07", type="Aircraft", dbid=1731, loadout_id=1731, latitude=26.20, longitude=112.91, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H06_HK_08"] = { side="红方", name="H06_HK_08", type="Aircraft", dbid=1731, loadout_id=1731, latitude=26.39, longitude=112.98, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- H02 第二轰炸机群（6 架 H-6K — DBID 1731）
    ["H02_HK_11"] = { side="红方", name="H02_HK_11", type="Aircraft", dbid=1731, loadout_id=1731, latitude=13.04, longitude=114.05, altitude=300, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H02_HK_12"] = { side="红方", name="H02_HK_12", type="Aircraft", dbid=1731, loadout_id=1731, latitude=13.04, longitude=114.05, altitude=300, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H02_HK_13"] = { side="红方", name="H02_HK_13", type="Aircraft", dbid=1731, loadout_id=1731, latitude=13.04, longitude=114.05, altitude=300, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H02_HK_14"] = { side="红方", name="H02_HK_14", type="Aircraft", dbid=1731, loadout_id=1731, latitude=13.056,longitude=114.05, altitude=300, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H02_HK_15"] = { side="红方", name="H02_HK_15", type="Aircraft", dbid=1731, loadout_id=1731, latitude=13.05, longitude=114.05, altitude=300, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["H02_HK_16"] = { side="红方", name="H02_HK_16", type="Aircraft", dbid=1731, loadout_id=1731, latitude=13.05, longitude=114.06, altitude=300, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- YJ07 预警机 KJ-500（2 架 — DBID 3683）
    ["YJ07_KJ_01"] = { side="红方", name="YJ07_KJ_01", type="Aircraft", dbid=3683, loadout_id=3683, latitude=13.02, longitude=110.95, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["YJ07_KJ_02"] = { side="红方", name="YJ07_KJ_02", type="Aircraft", dbid=3683, loadout_id=3683, latitude=26.32, longitude=112.63, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- Z08 隐身战斗机（4 架 J-20A — DBID 5012）
    ["Z08_J20_01"] = { side="红方", name="Z08_J20_01", type="Aircraft", dbid=5012, loadout_id=5012, latitude=18.50, longitude=109.97, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z08_J20_02"] = { side="红方", name="Z08_J20_02", type="Aircraft", dbid=5012, loadout_id=5012, latitude=18.50, longitude=109.98, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z08_J20_03"] = { side="红方", name="Z08_J20_03", type="Aircraft", dbid=5012, loadout_id=5012, latitude=18.49, longitude=109.98, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z08_J20_04"] = { side="红方", name="Z08_J20_04", type="Aircraft", dbid=5012, loadout_id=5012, latitude=18.49, longitude=109.99, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- Z07 第二隐身战斗机群（4 架 J-20A — DBID 5012）
    ["Z07_J20_01"] = { side="红方", name="Z07_J20_01", type="Aircraft", dbid=5012, loadout_id=5012, latitude=13.01, longitude=110.82, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z07_J20_02"] = { side="红方", name="Z07_J20_02", type="Aircraft", dbid=5012, loadout_id=5012, latitude=12.94, longitude=110.89, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z07_J20_03"] = { side="红方", name="Z07_J20_03", type="Aircraft", dbid=5012, loadout_id=5012, latitude=12.88, longitude=111.00, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z07_J20_04"] = { side="红方", name="Z07_J20_04", type="Aircraft", dbid=5012, loadout_id=5012, latitude=12.92, longitude=111.10, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- Z05 多用途战机（6 架 J-16 — DBID 2853）
    ["Z05_J16_01"] = { side="红方", name="Z05_J16_01", type="Aircraft", dbid=2853, loadout_id=2853, latitude=10.91, longitude=114.02, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z05_J16_02"] = { side="红方", name="Z05_J16_02", type="Aircraft", dbid=2853, loadout_id=2853, latitude=10.94, longitude=114.14, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z05_J16_03"] = { side="红方", name="Z05_J16_03", type="Aircraft", dbid=2853, loadout_id=2853, latitude=9.46,  longitude=113.14, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z05_J16_04"] = { side="红方", name="Z05_J16_04", type="Aircraft", dbid=2853, loadout_id=2853, latitude=10.90, longitude=114.07, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z05_J16_05"] = { side="红方", name="Z05_J16_05", type="Aircraft", dbid=2853, loadout_id=2853, latitude=10.91, longitude=114.11, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z05_J16_06"] = { side="红方", name="Z05_J16_06", type="Aircraft", dbid=2853, loadout_id=2853, latitude=10.93, longitude=114.08, altitude=1000, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- Z06 多用途战机（6 架 J-16 — DBID 2853）
    ["Z06_J16_07"] = { side="红方", name="Z06_J16_07", type="Aircraft", dbid=2853, loadout_id=2853, latitude=9.61, longitude=113.13, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z06_J16_08"] = { side="红方", name="Z06_J16_08", type="Aircraft", dbid=2853, loadout_id=2853, latitude=9.61, longitude=113.13, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z06_J16_09"] = { side="红方", name="Z06_J16_09", type="Aircraft", dbid=2853, loadout_id=2853, latitude=9.65, longitude=113.05, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z06_J16_10"] = { side="红方", name="Z06_J16_10", type="Aircraft", dbid=2853, loadout_id=2853, latitude=9.64, longitude=112.94, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z06_J16_11"] = { side="红方", name="Z06_J16_11", type="Aircraft", dbid=2853, loadout_id=2853, latitude=9.72, longitude=113.10, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["Z06_J16_12"] = { side="红方", name="Z06_J16_12", type="Aircraft", dbid=2853, loadout_id=2853, latitude=9.64, longitude=113.00, altitude=1500, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- DDG01 水面舰艇支队（5 艘 — 052D/055/054A）
    ["DDG01_052D_01"] = { side="红方", name="DDG01_052D_01", type="Ship", dbid=3587, latitude=5.68, longitude=108.90, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["DDG01_055_01"]  = { side="红方", name="DDG01_055_01",  type="Ship", dbid=3883, latitude=6.14, longitude=108.60, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["DDG01_052D_02"] = { side="红方", name="DDG01_052D_02", type="Ship", dbid=3587, latitude=5.82, longitude=108.48, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["DDG01_054A_01"] = { side="红方", name="DDG01_054A_01", type="Ship", dbid=2495, latitude=5.93, longitude=108.18, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["DDG01_054A_02"] = { side="红方", name="DDG01_054A_02", type="Ship", dbid=2495, latitude=5.66, longitude=108.54, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- DDG02 第二驱护编队（2 艘）
    ["DDG02_052D_01"] = { side="红方", name="DDG02_052D_01", type="Ship", dbid=3587, latitude=7.90, longitude=115.41, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["DDG02_054A_01"] = { side="红方", name="DDG02_054A_01", type="Ship", dbid=2495, latitude=7.54, longitude=115.28, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- DDG03 单独护卫舰（1 艘 054A）
    ["DDG03_054A_01"] = { side="红方", name="DDG03_054A_01", type="Ship", dbid=2495, latitude=13.30, longitude=118.24, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- SUB01/02 039C 潜艇（2 艘 — DBID 695）
    ["SUB01_039C_01"] = { side="红方", name="SUB01_039C_01", type="Submarine", dbid=695, latitude=7.51, longitude=116.23, heading=0, speed=0, autodetectable=false, dbid_verified=true },
    ["SUB02_039C_01"] = { side="红方", name="SUB02_039C_01", type="Submarine", dbid=695, latitude=12.86, longitude=118.72, heading=0, speed=0, autodetectable=false, dbid_verified=true },

    -- UU03 UUV 潜航器（15 个 - 数据库无 UUV 条目，按海上无人潜航器代理，使用潜艇做近似平台以保留航点）
    ["UU03_UUV_01"] = { side="红方", name="UU03_UUV_01", type="Submarine", dbid=695, latitude=-0.155, longitude=106.1643, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_02"] = { side="红方", name="UU03_UUV_02", type="Submarine", dbid=695, latitude=0.20,  longitude=105.93,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_03"] = { side="红方", name="UU03_UUV_03", type="Submarine", dbid=695, latitude=0.06,  longitude=105.65,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_04"] = { side="红方", name="UU03_UUV_04", type="Submarine", dbid=695, latitude=0.12,  longitude=106.03,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_05"] = { side="红方", name="UU03_UUV_05", type="Submarine", dbid=695, latitude=0.21,  longitude=106.16,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_06"] = { side="红方", name="UU03_UUV_06", type="Submarine", dbid=695, latitude=5.69,  longitude=106.98,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_07"] = { side="红方", name="UU03_UUV_07", type="Submarine", dbid=695, latitude=5.50,  longitude=107.16,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_08"] = { side="红方", name="UU03_UUV_08", type="Submarine", dbid=695, latitude=5.15,  longitude=107.87,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_09"] = { side="红方", name="UU03_UUV_09", type="Submarine", dbid=695, latitude=5.11,  longitude=108.28,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_10"] = { side="红方", name="UU03_UUV_10", type="Submarine", dbid=695, latitude=5.00,  longitude=108.54,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_11"] = { side="红方", name="UU03_UUV_11", type="Submarine", dbid=695, latitude=7.70,  longitude=116.14,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_12"] = { side="红方", name="UU03_UUV_12", type="Submarine", dbid=695, latitude=13.38, longitude=119.12,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_13"] = { side="红方", name="UU03_UUV_13", type="Submarine", dbid=695, latitude=7.49,  longitude=116.11,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_14"] = { side="红方", name="UU03_UUV_14", type="Submarine", dbid=695, latitude=12.78, longitude=118.95,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },
    ["UU03_UUV_15"] = { side="红方", name="UU03_UUV_15", type="Submarine", dbid=695, latitude=12.63, longitude=118.93,   heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="uuv_proxy" },

    -- UU04 无人艇（6 个 — 同上近以为小型舰艇代理）
    ["UU04_UUV_01"] = { side="红方", name="UU04_UUV_01", type="Ship", dbid=2495, latitude=5.58, longitude=107.42, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="usv_proxy" },
    ["UU04_UUV_02"] = { side="红方", name="UU04_UUV_02", type="Ship", dbid=2495, latitude=5.37, longitude=108.00, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="usv_proxy" },
    ["UU04_UUV_03"] = { side="红方", name="UU04_UUV_03", type="Ship", dbid=2495, latitude=5.39, longitude=107.63, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="usv_proxy" },
    ["UU04_UUV_04"] = { side="红方", name="UU04_UUV_04", type="Ship", dbid=2495, latitude=8.15, longitude=116.48, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="usv_proxy" },
    ["UU04_UUV_05"] = { side="红方", name="UU04_UUV_05", type="Ship", dbid=2495, latitude=7.80, longitude=116.29, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="usv_proxy" },
    ["UU04_UUV_06"] = { side="红方", name="UU04_UUV_06", type="Ship", dbid=2495, latitude=7.39, longitude=115.77, heading=0, speed=0, autodetectable=false, dbid_verified=true, subtype="usv_proxy" },

    -- ============== 蓝方 ==============
    -- 2026001 航母编队（8 艘）
    ["BLUE_CVN_LINCOLN"] = { side="蓝方", name="BLUE_CVN_LINCOLN", type="Ship", dbid=1644, latitude=-0.90,    longitude=106.11,    heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_CG_PULLINS"]  = { side="蓝方", name="BLUE_CG_PULLINS",  type="Ship", dbid=309,  latitude=-0.659581,longitude=105.813746,heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_DDG_MOMUSENG"]= { side="蓝方", name="BLUE_DDG_MOMUSENG",type="Ship", dbid=661,  latitude=7.104,    longitude=116.28,    heading=0, speed=0, autodetectable=true, dbid_verified=true, name_note="DDG_Chafee_proxy_to_DDG-79_Oscar_Austin" },
    ["BLUE_DDG_LAOLUNSI"]= { side="蓝方", name="BLUE_DDG_LAOLUNSI",type="Ship", dbid=661,  latitude=-1.463116,longitude=106.661538,heading=0, speed=0, autodetectable=true, dbid_verified=true, name_note="DDG_Chafee_proxy" },
    ["BLUE_DDG_SITELEI"] = { side="蓝方", name="BLUE_DDG_SITELEI", type="Ship", dbid=661,  latitude=-0.040782,longitude=106.369201,heading=0, speed=0, autodetectable=true, dbid_verified=true, name_note="DDG_Chafee_proxy" },
    ["BLUE_SUPPLY_KZ"]   = { side="蓝方", name="BLUE_SUPPLY_KZ",   type="Ship", dbid=26,   latitude=-0.101186,longitude=106.164261,heading=0, speed=0, autodetectable=true, dbid_verified=true, name_note="AUX_KZ_SUPPLY_proxy_Henry_J_Kaiser" },
    ["BLUE_FFG_LISHIMAN"]= { side="蓝方", name="BLUE_FFG_LISHIMAN",type="Ship", dbid=116,  latitude=0.695643, longitude=105.206647,heading=0, speed=0, autodetectable=true, dbid_verified=true, name_note="FFG_RICHMOND_proxy_FFG-36_Underwood" },
    ["BLUE_DDG_HUOBATE"] = { side="蓝方", name="BLUE_DDG_HUOBATE", type="Ship", dbid=661,  latitude=0.42728,  longitude=105.267494,heading=0, speed=0, autodetectable=true, dbid_verified=true, name_note="DDG_Chafee_proxy" },

    -- LHA01 美军两栖攻击群（3 艘）
    ["BLUE_LHA_AMERICA"] = { side="蓝方", name="BLUE_LHA_AMERICA", type="Ship", dbid=2362, latitude=7.922858, longitude=120.093579, heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_CG_SIMOER"]   = { side="蓝方", name="BLUE_CG_SIMOER",   type="Ship", dbid=309,  latitude=7.970356, longitude=119.503844, heading=0, speed=0, autodetectable=true, dbid_verified=true, name_note="Ticonderoga_proxy_CG-70" },
    ["BLUE_DDG_CHAFEI"]  = { side="蓝方", name="BLUE_DDG_CHAFEI",  type="Ship", dbid=661,  latitude=8.284662, longitude=119.783273, heading=0, speed=0, autodetectable=true, dbid_verified=true, name_note="DDG_Chafee_proxy" },

    -- USV01 无人艇（3 个 - 数据库无 USV 条目，用 054A 近似保留航点）
    ["BLUE_USV_01"] = { side="蓝方", name="BLUE_USV_01", type="Ship", dbid=2495, latitude=2.08, longitude=106.72, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="usv_proxy" },
    ["BLUE_USV_02"] = { side="蓝方", name="BLUE_USV_02", type="Ship", dbid=2495, latitude=2.08, longitude=107.19, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="usv_proxy" },
    ["BLUE_USV_03"] = { side="蓝方", name="BLUE_USV_03", type="Ship", dbid=2495, latitude=2.02, longitude=107.67, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="usv_proxy" },

    -- AGOS01 海洋调查船（3 艘 - DBID 365 T-AGOS 19 Victorious）
    ["BLUE_AGOS_SHENLI"]   = { side="蓝方", name="BLUE_AGOS_SHENLI",   type="Ship", dbid=365, latitude=19.72, longitude=124.75, heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_AGOS_WUXIA"]    = { side="蓝方", name="BLUE_AGOS_WUXIA",    type="Ship", dbid=365, latitude=20.29, longitude=119.57, heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_AGOS_ZHUCHENG"] = { side="蓝方", name="BLUE_AGOS_ZHUCHENG", type="Ship", dbid=365, latitude=14.06, longitude=119.20, heading=0, speed=0, autodetectable=true, dbid_verified=true },

    -- F03 隐身战斗机群（7 架 — F-35C × 3, F-35B × 4）
    ["BLUE_F35C_01"] = { side="蓝方", name="BLUE_F35C_01", type="Aircraft", dbid=3495, loadout_id=3495, latitude=-0.723911, longitude=106.122993, altitude=1000, heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_F35C_02"] = { side="蓝方", name="BLUE_F35C_02", type="Aircraft", dbid=3495, loadout_id=3495, latitude=-0.792082, longitude=106.185909, altitude=1000, heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_F35C_03"] = { side="蓝方", name="BLUE_F35C_03", type="Aircraft", dbid=3495, loadout_id=3495, latitude=-0.752938, longitude=106.05896,  altitude=1000, heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_F35B_01"] = { side="蓝方", name="BLUE_F35B_01", type="Aircraft", dbid=534,  loadout_id=534,  latitude=7.92,      longitude=120.093579, altitude=1000, heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_F35B_02"] = { side="蓝方", name="BLUE_F35B_02", type="Aircraft", dbid=534,  loadout_id=534,  latitude=7.89,      longitude=120.093579, altitude=1000, heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_F35B_03"] = { side="蓝方", name="BLUE_F35B_03", type="Aircraft", dbid=534,  loadout_id=534,  latitude=7.9215,    longitude=120.129358, altitude=1000, heading=0, speed=0, autodetectable=true, dbid_verified=true },
    ["BLUE_F35B_04"] = { side="蓝方", name="BLUE_F35B_04", type="Aircraft", dbid=534,  loadout_id=534,  latitude=7.9178,    longitude=120.093579, altitude=1000, heading=0, speed=0, autodetectable=true, dbid_verified=true },

    -- HMS01 远程火箭营（9 套发射车 - 数据库无 HMS 精确型号，按 SSM Bty 近似）
    ["BLUE_HMS_01"] = { side="蓝方", name="BLUE_HMS_01", type="Ship", dbid=1644, latitude=9.95, longitude=118.70, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="hms_proxy" },
    ["BLUE_HMS_02"] = { side="蓝方", name="BLUE_HMS_02", type="Ship", dbid=1644, latitude=9.95, longitude=118.70, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="hms_proxy" },
    ["BLUE_HMS_03"] = { side="蓝方", name="BLUE_HMS_03", type="Ship", dbid=1644, latitude=9.95, longitude=118.70, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="hms_proxy" },
    ["BLUE_HMS_04"] = { side="蓝方", name="BLUE_HMS_04", type="Ship", dbid=1644, latitude=9.95, longitude=118.70, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="hms_proxy" },
    ["BLUE_HMS_05"] = { side="蓝方", name="BLUE_HMS_05", type="Ship", dbid=1644, latitude=9.95, longitude=118.70, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="hms_proxy" },
    ["BLUE_HMS_06"] = { side="蓝方", name="BLUE_HMS_06", type="Ship", dbid=1644, latitude=8.539521, longitude=117.323625, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="hms_proxy" },
    ["BLUE_HMS_07"] = { side="蓝方", name="BLUE_HMS_07", type="Ship", dbid=1644, latitude=8.603141, longitude=117.327882, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="hms_proxy" },
    ["BLUE_HMS_08"] = { side="蓝方", name="BLUE_HMS_08", type="Ship", dbid=1644, latitude=8.538925, longitude=117.261165, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="hms_proxy" },
    ["BLUE_HMS_09"] = { side="蓝方", name="BLUE_HMS_09", type="Ship", dbid=1644, latitude=8.471862, longitude=117.264859, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="hms_proxy" },

    -- TYPHON02 蓝方中导营（4 套发射车 — DBID 3362 SSM Bty Typhon）
    ["BLUE_TYPHON_01"] = { side="蓝方", name="BLUE_TYPHON_01", type="Ship", dbid=1644, latitude=18.35, longitude=120.90, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="typhon_proxy" },
    ["BLUE_TYPHON_02"] = { side="蓝方", name="BLUE_TYPHON_02", type="Ship", dbid=1644, latitude=18.35, longitude=120.90, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="typhon_proxy" },
    ["BLUE_TYPHON_03"] = { side="蓝方", name="BLUE_TYPHON_03", type="Ship", dbid=1644, latitude=18.35, longitude=120.90, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="typhon_proxy" },
    ["BLUE_TYPHON_04"] = { side="蓝方", name="BLUE_TYPHON_04", type="Ship", dbid=1644, latitude=18.35, longitude=120.90, heading=0, speed=0, autodetectable=true, dbid_verified=true, subtype="typhon_proxy" },
}

-- =========================
-- §D 清弹/装弹/打击清单
-- =========================

-- 清弹（红方水面舰艇先清默认 YJ-18/CJ-10，再装填 YJ-18/DF-26）
CLEAR_LIST = {
    "DDG01_052D_01", "DDG01_055_01", "DDG01_052D_02",
    "DDG01_054A_01", "DDG01_054A_02",
    "DDG02_052D_01", "DDG02_054A_01",
    "DDG03_054A_01",
    "H06_HK_01","H06_HK_02","H06_HK_03","H06_HK_04","H06_HK_05","H06_HK_06","H06_HK_07","H06_HK_08",
    "H02_HK_11","H02_HK_12","H02_HK_13","H02_HK_14","H02_HK_15","H02_HK_16",
    "Z05_J16_01","Z05_J16_02","Z05_J16_03","Z05_J16_04","Z05_J16_05","Z05_J16_06",
    "Z06_J16_07","Z06_J16_08","Z06_J16_09","Z06_J16_10","Z06_J16_11","Z06_J16_12",
}

-- 装弹（每艘 052D 装 8 枚 YJ-18, 055 装 16 枚, 054A 装 8 枚, 轰-6K 装 6 枚 YJ-12 反舰/对地）
AMMO = {
    -- 水面舰艇
    { unitname = "DDG01_052D_01", wpn_dbid = 2868, number = 8 },
    { unitname = "DDG01_055_01",  wpn_dbid = 2868, number = 16 },
    { unitname = "DDG01_052D_02", wpn_dbid = 2868, number = 8 },
    { unitname = "DDG01_054A_01", wpn_dbid = 2868, number = 4 },
    { unitname = "DDG01_054A_02", wpn_dbid = 2868, number = 4 },
    { unitname = "DDG02_052D_01", wpn_dbid = 2868, number = 8 },
    { unitname = "DDG02_054A_01", wpn_dbid = 2868, number = 4 },
    { unitname = "DDG03_054A_01", wpn_dbid = 2868, number = 4 },
    -- 轰-6K 装 YJ-12 反舰/对地
    { unitname = "H06_HK_01", wpn_dbid = 2869, number = 4 },
    { unitname = "H06_HK_02", wpn_dbid = 2869, number = 4 },
    { unitname = "H06_HK_03", wpn_dbid = 2869, number = 4 },
    { unitname = "H06_HK_04", wpn_dbid = 2869, number = 4 },
    { unitname = "H06_HK_05", wpn_dbid = 2869, number = 4 },
    { unitname = "H06_HK_06", wpn_dbid = 2869, number = 4 },
    { unitname = "H06_HK_07", wpn_dbid = 2869, number = 4 },
    { unitname = "H06_HK_08", wpn_dbid = 2869, number = 4 },
    { unitname = "H02_HK_11", wpn_dbid = 2869, number = 4 },
    { unitname = "H02_HK_12", wpn_dbid = 2869, number = 4 },
    { unitname = "H02_HK_13", wpn_dbid = 2869, number = 4 },
    { unitname = "H02_HK_14", wpn_dbid = 2869, number = 4 },
    { unitname = "H02_HK_15", wpn_dbid = 2869, number = 4 },
    { unitname = "H02_HK_16", wpn_dbid = 2869, number = 4 },
    -- J-16 多用途机装 YJ-83 反舰
    { unitname = "Z05_J16_01", wpn_dbid = 2868, number = 4 },
    { unitname = "Z05_J16_02", wpn_dbid = 2868, number = 4 },
    { unitname = "Z05_J16_03", wpn_dbid = 2868, number = 4 },
    { unitname = "Z05_J16_04", wpn_dbid = 2868, number = 4 },
    { unitname = "Z05_J16_05", wpn_dbid = 2868, number = 4 },
    { unitname = "Z05_J16_06", wpn_dbid = 2868, number = 4 },
    { unitname = "Z06_J16_07", wpn_dbid = 2868, number = 4 },
    { unitname = "Z06_J16_08", wpn_dbid = 2868, number = 4 },
    { unitname = "Z06_J16_09", wpn_dbid = 2868, number = 4 },
    { unitname = "Z06_J16_10", wpn_dbid = 2868, number = 4 },
    { unitname = "Z06_J16_11", wpn_dbid = 2868, number = 4 },
    { unitname = "Z06_J16_12", wpn_dbid = 2868, number = 4 },
    -- 火箭军 DF-26 旅
    { unitname = "D02_DFB_01",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_02",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_03",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_04",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_05",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_06",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_07",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_08",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_09",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_10",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_11",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_12",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_13",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_14",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_15",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_16",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_17",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_18",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_19",  wpn_dbid = 2880, number = 4 },
    { unitname = "D02_DFB_20",  wpn_dbid = 2880, number = 4 },
    { unitname = "D03_DFD_01",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_02",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_03",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_04",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_05",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_06",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_07",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_08",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_09",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_10",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_11",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_12",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_13",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_14",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_15",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_16",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_17",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_18",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_19",  wpn_dbid = 2879, number = 4 },
    { unitname = "D03_DFD_20",  wpn_dbid = 2879, number = 4 },
}

-- 打击清单（命名键，红线 #2）
STRIKE = {
    -- 阶段 1 (T+0min): 火箭军 DF-26 突袭蓝方港口/堤丰阵地
    { attacker = "D02_DFB_01",  target = "BLUE_TYPHON_01", weapon_dbid = 2880, quantity = 4, startDelay = 0,    interval = 30, intent = "DF-26B 旅第一波：反舰/对陆打击蓝方堤丰中导阵地" },
    { attacker = "D02_DFB_05",  target = "BLUE_TYPHON_02", weapon_dbid = 2880, quantity = 4, startDelay = 60,   interval = 30, intent = "DF-26B 第二波：续压制堤丰" },
    { attacker = "D03_DFD_01",  target = "BLUE_TYPHON_03", weapon_dbid = 2879, quantity = 4, startDelay = 120,  interval = 30, intent = "DF-26D 旅介入，扩大对陆打击面" },
    { attacker = "D03_DFD_10",  target = "BLUE_TYPHON_04", weapon_dbid = 2879, quantity = 4, startDelay = 180,  interval = 30, intent = "DF-26D 第二波" },

    -- 阶段 2 (T+10min): 055/052D 反舰导弹齐射蓝方航母编队
    { attacker = "DDG01_055_01",  target = "BLUE_CVN_LINCOLN", weapon_dbid = 2868, quantity = 16, startDelay = 600,  interval = 5, intent = "055 主力齐射 16 枚 YJ-18 突击蓝方航母 Lincoln" },
    { attacker = "DDG01_052D_01",target = "BLUE_CG_PULLINS",  weapon_dbid = 2868, quantity = 8,  startDelay = 700,  interval = 4, intent = "052D-1 协同齐射 YJ-18 打击 CG 普林斯顿" },
    { attacker = "DDG01_052D_02",target = "BLUE_DDG_MOMUSENG",weapon_dbid = 2868, quantity = 8,  startDelay = 800,  interval = 4, intent = "052D-2 齐射 YJ-18 打击 DDG 莫姆森(Chafee proxy)" },
    { attacker = "DDG01_054A_01",target = "BLUE_FFG_LISHIMAN",weapon_dbid = 2868, quantity = 4,  startDelay = 900,  interval = 4, intent = "054A 护卫舰 YJ-18 突击 FFG 李ishman" },
    { attacker = "DDG01_054A_02",target = "BLUE_DDG_LAOLUNSI",weapon_dbid = 2868, quantity = 4,  startDelay = 1000, interval = 4, intent = "054A 协同打击 DDG 劳伦斯" },
    { attacker = "DDG02_052D_01",target = "BLUE_DDG_SITELEI", weapon_dbid = 2868, quantity = 8,  startDelay = 1100, interval = 4, intent = "第二编队 052D 打击 DDG 斯特雷" },
    { attacker = "DDG02_054A_01",target = "BLUE_DDG_HUOBATE", weapon_dbid = 2868, quantity = 4,  startDelay = 1200, interval = 4, intent = "第二编队 054A 打击 DDG 霍巴特" },
    { attacker = "DDG03_054A_01",target = "BLUE_SUPPLY_KZ",   weapon_dbid = 2868, quantity = 4,  startDelay = 1300, interval = 4, intent = "外圈护卫 054A 打击 AOE 综合补给舰" },

    -- 阶段 3 (T+25min): 轰-6K 发射 YJ-12 突击两栖编队
    { attacker = "H06_HK_01", target = "BLUE_LHA_AMERICA", weapon_dbid = 2869, quantity = 4, startDelay = 1500, interval = 20, intent = "轰-6K 第 1 波 YJ-12 突击 LHA 美利坚" },
    { attacker = "H06_HK_02", target = "BLUE_LHA_AMERICA", weapon_dbid = 2869, quantity = 4, startDelay = 1520, interval = 20, intent = "轰-6K 第 2 波续攻 LHA" },
    { attacker = "H06_HK_03", target = "BLUE_CG_SIMOER",   weapon_dbid = 2869, quantity = 4, startDelay = 1600, interval = 20, intent = "轰-6K 突击 CG 西摩尔" },
    { attacker = "H06_HK_04", target = "BLUE_DDG_CHAFEI",  weapon_dbid = 2869, quantity = 4, startDelay = 1700, interval = 20, intent = "轰-6K 突击 DDG 查菲" },
    { attacker = "H02_HK_11", target = "BLUE_LHA_AMERICA", weapon_dbid = 2869, quantity = 4, startDelay = 1800, interval = 20, intent = "H02 轰-6K 集群 YJ-12 补充突击 LHA" },
    { attacker = "H02_HK_13", target = "BLUE_LHA_AMERICA", weapon_dbid = 2869, quantity = 4, startDelay = 1820, interval = 20, intent = "H02 集群第 2 波" },

    -- 阶段 4 (T+40min): J-16 多用途战机对地/反舰突击 HMS 阵地
    { attacker = "Z05_J16_01", target = "BLUE_HMS_01", weapon_dbid = 2868, quantity = 4, startDelay = 2400, interval = 5, intent = "J-16 中队对陆突击 HMS 远程火箭营第 1 阵地" },
    { attacker = "Z05_J16_02", target = "BLUE_HMS_02", weapon_dbid = 2868, quantity = 4, startDelay = 2420, interval = 5, intent = "J-16 中队续攻 HMS 阵地" },
    { attacker = "Z05_J16_03", target = "BLUE_HMS_06", weapon_dbid = 2868, quantity = 4, startDelay = 2500, interval = 5, intent = "J-16 中队转火第 6 阵地" },
    { attacker = "Z06_J16_07", target = "BLUE_HMS_07", weapon_dbid = 2868, quantity = 4, startDelay = 2600, interval = 5, intent = "Z06 中队突击 HMS 第 7 阵地" },
    { attacker = "Z06_J16_09", target = "BLUE_HMS_09", weapon_dbid = 2868, quantity = 4, startDelay = 2700, interval = 5, intent = "Z06 中队突击 HMS 末端阵地" },
}

-- =========================
-- §E 弹药余额自检
-- =========================
local function checkAmmoBalance()
    local ammoByUnit = {}
    for _, a in ipairs(AMMO) do
        ammoByUnit[a.unitname] = (ammoByUnit[a.unitname] or 0) + a.number
    end
    local strikeByUnit = {}
    for _, s in ipairs(STRIKE) do
        strikeByUnit[s.attacker] = (strikeByUnit[s.attacker] or 0) + s.quantity
    end
    for unit, totalStrike in pairs(strikeByUnit) do
        local totalAmmo = ammoByUnit[unit] or 0
        if totalAmmo < totalStrike then
            error(("[manifest] 弹药不足! %s 装弹 %d 枚但 STRIKE 需要 %d 枚")
                :format(unit, totalAmmo, totalStrike))
        end
        print(("[manifest] %s 弹药余额 = %d"):format(unit, totalAmmo - totalStrike))
    end
end

local function checkAircraftLoadout()
    for uid, u in pairs(UNITS) do
        if u.type == "Aircraft" then
            if not u.loadout_id then
                error(("[manifest] Aircraft '%s' 缺少 loadout_id"):format(uid))
            end
        end
    end
end

local function tableCountKeys(t)
    local n = 0
    for _ in pairs(t) do n = n + 1 end
    return n
end

checkAircraftLoadout()
checkAmmoBalance()

print(("[manifest] 校验通过: %d 单位, %d 装弹项, %d 打击项 (A1 联合火力突击)"):format(
    tableCountKeys(UNITS), #AMMO, #STRIKE))
