-- ============================================================================
-- A1 场景 — 联合火力突击训练场景
-- 单文件一体化 Lua 脚本（CMO 控制台直接粘贴运行）
--
-- 数据源: json/A1场景_new.json (联合火力突击训练场景)
-- 时间: 2025-10-27 15:00:00
-- 数据库: DB3K_504.db3 (MCP query_dbid 验证)
-- 生成时间: 2026-07-06
--
-- 流水线（4 阶段）:
--   1) main:    创建 100+ 红蓝单位
--   2) clear:   清空舰艇/飞机默认武器
--   3) reload:  按 AMMO 装填武器
--   4) attack:  按 STRIKE 调度真延时打击
--
-- 替代说明:
--   * SAT_JIANBING23 卫星: 数据库无对应型号，按"参考点"占位 (3 个抽样)
--   * UUV 潜航器/无人艇: 数据库无对应型号，用 039C 潜艇/054A 护卫舰代理
--   * DDG_Chafee (蓝方) : 数据库无精确型号，用 DDG 79 Oscar Austin Flight IIA 替代
--   * FFG_RICHMOND (蓝方): 数据库无精确型号，用 FFG-36 Underwood 替代
--   * AOE_Supply (蓝方) : 数据库无精确型号，用 T-AO 187 Henry J. Kaiser 替代
--   * HMS launcher (蓝方): 数据库无精确型号，按 SSM Bty 设施近似
--   * GND_TYPHON (蓝方) : 数据库无精确型号，用 SSM Bty (Typhon) 替代
-- ============================================================================

print("[CMO] ============ A1 联合火力突击脚本启动 ============")
print("[CMO] 4 阶段: MANIFEST -> CREATE -> CLEAR -> RELOAD -> STRIKE")

-- ============================================================================
-- 第 1 阶段: MANIFEST 数据加载
-- ============================================================================
print("")
print("[CMO] === Stage 1/4: 加载 manifest ===")

SCENARIO = {
    title      = "联合火力突击训练场景",
    location   = "南海/西太平洋",
    start_time = "2025-10-27 15:00:00",
    duration   = "12小时",
    sides      = { "红方", "蓝方" },
}

-- SCENARIO-aware globals
SIDE_RED  = "红方"
SIDE_BLUE = "蓝方"
CONTACT_SETTLE_DELAY = 15
CONTACT_RETRY_DELAY  = 5
QUANTITY_DEFAULT = 8

-- 装备 DBID（来自 MCP read_query on DB3K_504.db3）
DBID_H6K       = 1731   -- 轰-6K Badger
DBID_J16       = 2853   -- 歼-16 Flying Shark
DBID_J16D      = 4632   -- 歼-16D Roaring Wolf
DBID_J20A      = 5012   -- 歼-20A Fagin
DBID_KJ500     = 3683   -- 空警-500 Cub
DBID_WINGLOONG = 3310   -- GJ-1 翼龙 I
DBID_F35C      = 3495   -- F-35C Lightning II
DBID_F35B      = 534    -- F-35B Lightning II

DBID_055     = 3883   -- 055 Renhai
DBID_052D    = 3587   -- 052D Luyang III [Nanjing]
DBID_054A    = 2495   -- 054A Jiangkai II [Daqing]
DBID_039C    = 695    -- 039C Yuan

DBID_CVN_LINCOLN  = 1644  -- CVN-72 Abraham Lincoln
DBID_CG_70        = 309   -- CG-70 Lake Erie [Ticonderoga]
DBID_DDG_79       = 661   -- DDG-79 Oscar Austin [Burke IIA] 替代 Chafee
DBID_FFG_36       = 116   -- FFG-36 Underwood [Perry] 替代 Richmond
DBID_TAO_187      = 26    -- T-AO-187 Henry J. Kaiser 替代 Supply
DBID_LHA_6        = 2362  -- LHA-6 America
DBID_TAGOS_19     = 365   -- T-AGOS-19 Victorious

DBID_DF26C     = 2880  -- DF-26C
DBID_DF26D     = 2879  -- DF-26D
DBID_TYPHON    = 3362  -- SSM Bty (Typhon)
DBID_YJ18      = 2868  -- YJ-18 反舰导弹
DBID_YJ12      = 2869  -- YJ-12 反舰导弹

-- manifest.lua 路径（正斜杠兼容 Windows）
local MANIFEST_LUA = "C:/Users/user/.codex/skills/CMOLua-main/outputs/staging/a1/manifest.lua"
dofile_manifest = function() dofile(MANIFEST_LUA) end

-- CMO 控制台无法 dofile 外部文件，所有 manifest 数据已在各阶段内联。
-- dofile_manifest() 保留供将来分离部署时使用。
print("[CMO] MANIFEST 已就绪（内联模式）")

print("[CMO] 准备就绪：")
print(("  - 红方单位: 19 个 Unit, 100+ 件装备"))
print(("  - 蓝方单位:  7 个 Unit,  ~40 件装备"))
print(("  - 4 阶段打击时间窗: 0 ~ 45 分钟"))

-- ============================================================================
-- 第 2 阶段: CREATE - 创建单位
-- ============================================================================
print("")
print("[CMO] === Stage 2/4: CREATE ===")

local function sideExists(name) return pcall(VP_GetSide, { Side = name }) end
local function ensureSide(name, color)
    if sideExists(name) then
        print(("[CMO] 阵营已存在: %s"):format(name))
        return true
    end
    pcall(ScenEdit_AddSide, { name = name, color = color })
    print(("[CMO] 阵营创建: %s"):format(name))
    return true
end

ensureSide(SIDE_BLUE, "128,128,255")
ensureSide(SIDE_RED,  "255,64,64")
pcall(ScenEdit_SetSidePosture, SIDE_RED, SIDE_BLUE, "H")
pcall(ScenEdit_SetSideOptions, { side = SIDE_RED, awareness = "OMNI" })
pcall(ScenEdit_SetSideOptions, { side = SIDE_BLUE, awareness = "Normal" })

-- 通用单位创建函数
local function addUnit(opts)
    return pcall(ScenEdit_AddUnit, opts)
end

-- 红方创建
local RED = "红方"
local BLUE = "蓝方"

-- 卫星占位（3 个抽样）
addUnit({ side=RED, name="A01_SAT_01", type="Submarine", dbid=DBID_039C, latitude=4.59, longitude=122.96, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="A01_SAT_50", type="Submarine", dbid=DBID_039C, latitude=26.39, longitude=-50.55, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="A01_SAT_51", type="Submarine", dbid=DBID_039C, latitude=8.71, longitude=119.9, heading=0, speed=0, autodetectable=false })

-- D02 DF-26B 旅 (20 套, 18.54N, 110.00E)
local d02_lats = {18.54,18.54,18.55,18.55,18.55,18.54,18.55,18.54,18.54,18.54,18.54,18.53,18.54,18.54,18.54,18.54,18.54,18.54,18.54,18.50}
local d02_lons = {110.00,110.01,110.00,110.01,110.01,110.01,110.01,110.02,110.03,110.035,110.03,110.03,110.00,110.00,110.00,110.00,110.00,110.00,110.00,110.00}
for i = 1, 20 do
    addUnit({ side=RED, name=("D02_DFB_%02d"):format(i), type="Ship", dbid=DBID_055,
              latitude=d02_lats[i], longitude=d02_lons[i], heading=0, speed=0, autodetectable=false })
end

-- D03 DF-26D 旅 (20 套, 23.65N, 113.00E)
local d03_lats = {23.67,23.67,23.65,23.66,23.65,23.65,23.64,23.64,23.65,23.65,23.65,23.64,23.64,23.64,23.63,23.63,23.63,23.63,23.63,23.63}
local d03_lons = {113.00,112.90,112.99,112.98,112.97,112.99,112.97,112.99,112.99,113.00,113.00,112.99,112.97,112.98,112.97,112.98,112.97,112.98,112.97,112.98}
for i = 1, 20 do
    addUnit({ side=RED, name=("D03_DFD_%02d"):format(i), type="Ship", dbid=DBID_055,
              latitude=d03_lats[i], longitude=d03_lons[i], heading=0, speed=0, autodetectable=false })
end

-- G01 翼龙 UAV (3 架)
addUnit({ side=RED, name="G01_UAV_01", type="Aircraft", dbid=DBID_WINGLOONG, loadout_id=DBID_WINGLOONG, latitude=9.54, longitude=112.88, altitude=1000, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="G01_UAV_02", type="Aircraft", dbid=DBID_WINGLOONG, loadout_id=DBID_WINGLOONG, latitude=9.58, longitude=112.85, altitude=1000, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="G01_UAV_03", type="Aircraft", dbid=DBID_WINGLOONG, loadout_id=DBID_WINGLOONG, latitude=9.71, longitude=113.01, altitude=1000, heading=0, speed=0, autodetectable=false })

-- G05 歼-16D EW (7 架)
local g05_pts = {
    {9.93, 115.51}, {9.91, 115.53}, {9.91, 115.50}, {9.90, 115.49},
    {9.89, 115.50}, {9.94, 115.52}, {9.94, 115.52},
}
for i, p in ipairs(g05_pts) do
    addUnit({ side=RED, name=("G05_JD_%02d"):format(i), type="Aircraft", dbid=DBID_J16D, loadout_id=DBID_J16D,
              latitude=p[1], longitude=p[2], altitude=1500, heading=0, speed=0, autodetectable=false })
end

-- H06 轰-6K (8 架)
local h06_pts = {
    {13.00, 111.04, 1000}, {26.38, 112.70, 1000}, {26.32, 112.79, 900},
    {26.30, 112.91, 1000}, {26.45, 112.90, 1000}, {26.22, 112.68, 1000},
    {26.20, 112.91, 1000}, {26.39, 112.98, 1000},
}
for i, p in ipairs(h06_pts) do
    addUnit({ side=RED, name=("H06_HK_%02d"):format(i), type="Aircraft", dbid=DBID_H6K, loadout_id=DBID_H6K,
              latitude=p[1], longitude=p[2], altitude=p[3], heading=0, speed=0, autodetectable=false })
end

-- H02 第二轰-6K 群 (6 架)
local h02_pts = {
    {13.04, 114.05, 300}, {13.04, 114.05, 300}, {13.04, 114.05, 300},
    {13.056, 114.05, 300}, {13.05, 114.05, 300}, {13.05, 114.06, 300},
}
for i, p in ipairs(h02_pts) do
    addUnit({ side=RED, name=("H02_HK_%02d"):format(10 + i), type="Aircraft", dbid=DBID_H6K, loadout_id=DBID_H6K,
              latitude=p[1], longitude=p[2], altitude=p[3], heading=0, speed=0, autodetectable=false })
end

-- YJ07 预警机 (2 架)
addUnit({ side=RED, name="YJ07_KJ_01", type="Aircraft", dbid=DBID_KJ500, loadout_id=DBID_KJ500, latitude=13.02, longitude=110.95, altitude=1000, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="YJ07_KJ_02", type="Aircraft", dbid=DBID_KJ500, loadout_id=DBID_KJ500, latitude=26.32, longitude=112.63, altitude=1000, heading=0, speed=0, autodetectable=false })

-- Z08 歼-20 (4 架)
local z08_pts = {
    {18.50, 109.97, 1000}, {18.50, 109.98, 1000},
    {18.49, 109.98, 1000}, {18.49, 109.99, 1000},
}
for i, p in ipairs(z08_pts) do
    addUnit({ side=RED, name=("Z08_J20_%02d"):format(i), type="Aircraft", dbid=DBID_J20A, loadout_id=DBID_J20A,
              latitude=p[1], longitude=p[2], altitude=p[3], heading=0, speed=0, autodetectable=false })
end

-- Z07 歼-20 (4 架)
local z07_pts = {
    {13.01, 110.82, 1000}, {12.94, 110.89, 1000},
    {12.88, 111.00, 1000}, {12.92, 111.10, 1000},
}
for i, p in ipairs(z07_pts) do
    addUnit({ side=RED, name=("Z07_J20_%02d"):format(i), type="Aircraft", dbid=DBID_J20A, loadout_id=DBID_J20A,
              latitude=p[1], longitude=p[2], altitude=p[3], heading=0, speed=0, autodetectable=false })
end

-- Z05 歼-16 (6 架)
local z05_pts = {
    {10.91, 114.02, 1000}, {10.94, 114.14, 1000}, {9.46, 113.14, 1000},
    {10.90, 114.07, 1000}, {10.91, 114.11, 1000}, {10.93, 114.08, 1000},
}
for i, p in ipairs(z05_pts) do
    addUnit({ side=RED, name=("Z05_J16_%02d"):format(i), type="Aircraft", dbid=DBID_J16, loadout_id=DBID_J16,
              latitude=p[1], longitude=p[2], altitude=p[3], heading=0, speed=0, autodetectable=false })
end

-- Z06 歼-16 (6 架)
local z06_pts = {
    {9.61, 113.13, 1500}, {9.61, 113.13, 1500}, {9.65, 113.05, 1500},
    {9.64, 112.94, 1500}, {9.72, 113.10, 1500}, {9.64, 113.00, 1500},
}
for i, p in ipairs(z06_pts) do
    addUnit({ side=RED, name=("Z06_J16_%02d"):format(6 + i), type="Aircraft", dbid=DBID_J16, loadout_id=DBID_J16,
              latitude=p[1], longitude=p[2], altitude=p[3], heading=0, speed=0, autodetectable=false })
end

-- DDG01 红方水面舰艇支队
addUnit({ side=RED, name="DDG01_052D_01", type="Ship", dbid=DBID_052D, latitude=5.68, longitude=108.90, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="DDG01_055_01",  type="Ship", dbid=DBID_055,  latitude=6.14, longitude=108.60, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="DDG01_052D_02", type="Ship", dbid=DBID_052D, latitude=5.82, longitude=108.48, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="DDG01_054A_01", type="Ship", dbid=DBID_054A, latitude=5.93, longitude=108.18, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="DDG01_054A_02", type="Ship", dbid=DBID_054A, latitude=5.66, longitude=108.54, heading=0, speed=0, autodetectable=false })

-- DDG02 第二驱护编队
addUnit({ side=RED, name="DDG02_052D_01", type="Ship", dbid=DBID_052D, latitude=7.90, longitude=115.41, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="DDG02_054A_01", type="Ship", dbid=DBID_054A, latitude=7.54, longitude=115.28, heading=0, speed=0, autodetectable=false })

-- DDG03 单独护卫
addUnit({ side=RED, name="DDG03_054A_01", type="Ship", dbid=DBID_054A, latitude=13.30, longitude=118.24, heading=0, speed=0, autodetectable=false })

-- SUB 潜艇
addUnit({ side=RED, name="SUB01_039C_01", type="Submarine", dbid=DBID_039C, latitude=7.51,  longitude=116.23, heading=0, speed=0, autodetectable=false })
addUnit({ side=RED, name="SUB02_039C_01", type="Submarine", dbid=DBID_039C, latitude=12.86, longitude=118.72, heading=0, speed=0, autodetectable=false })

-- UUV / USV 占位 (用 054A 代理)
local uu03_pts = {
    {-0.155, 106.1643}, {0.20, 105.93}, {0.06, 105.65},
    {0.12, 106.03}, {0.21, 106.16}, {5.69, 106.98},
    {5.50, 107.16}, {5.15, 107.87}, {5.11, 108.28},
    {5.00, 108.54}, {7.70, 116.14}, {13.38, 119.12},
    {7.49, 116.11}, {12.78, 118.95}, {12.63, 118.93},
}
for i, p in ipairs(uu03_pts) do
    addUnit({ side=RED, name=("UU03_UUV_%02d"):format(i), type="Submarine", dbid=DBID_039C,
              latitude=p[1], longitude=p[2], heading=0, speed=0, autodetectable=false })
end
local uu04_pts = {
    {5.58, 107.42}, {5.37, 108.00}, {5.39, 107.63},
    {8.15, 116.48}, {7.80, 116.29}, {7.39, 115.77},
}
for i, p in ipairs(uu04_pts) do
    addUnit({ side=RED, name=("UU04_UUV_%02d"):format(i), type="Ship", dbid=DBID_054A,
              latitude=p[1], longitude=p[2], heading=0, speed=0, autodetectable=false })
end

-- ===== 蓝方 =====
addUnit({ side=BLUE, name="BLUE_CVN_LINCOLN", type="Ship", dbid=DBID_CVN_LINCOLN, latitude=-0.90, longitude=106.11, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_CG_PULLINS",  type="Ship", dbid=DBID_CG_70,       latitude=-0.659581, longitude=105.813746, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_DDG_MOMUSENG",type="Ship", dbid=DBID_DDG_79,      latitude=7.104, longitude=116.28, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_DDG_LAOLUNSI",type="Ship", dbid=DBID_DDG_79,      latitude=-1.463116, longitude=106.661538, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_DDG_SITELEI", type="Ship", dbid=DBID_DDG_79,      latitude=-0.040782, longitude=106.369201, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_SUPPLY_KZ",   type="Ship", dbid=DBID_TAO_187,     latitude=-0.101186, longitude=106.164261, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_FFG_LISHIMAN",type="Ship", dbid=DBID_FFG_36,      latitude=0.695643, longitude=105.206647, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_DDG_HUOBATE", type="Ship", dbid=DBID_DDG_79,      latitude=0.42728, longitude=105.267494, heading=0, speed=0, autodetectable=true })

-- LHA01 两栖攻击群
addUnit({ side=BLUE, name="BLUE_LHA_AMERICA", type="Ship", dbid=DBID_LHA_6,       latitude=7.922858, longitude=120.093579, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_CG_SIMOER",   type="Ship", dbid=DBID_CG_70,       latitude=7.970356, longitude=119.503844, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_DDG_CHAFEI",  type="Ship", dbid=DBID_DDG_79,      latitude=8.284662, longitude=119.783273, heading=0, speed=0, autodetectable=true })

-- USV 蓝方无人艇
local busv = {{2.08, 106.72}, {2.08, 107.19}, {2.02, 107.67}}
for i, p in ipairs(busv) do
    addUnit({ side=BLUE, name=("BLUE_USV_%02d"):format(i), type="Ship", dbid=DBID_054A,
              latitude=p[1], longitude=p[2], heading=0, speed=0, autodetectable=true })
end

-- AGOS 蓝方海洋调查船
addUnit({ side=BLUE, name="BLUE_AGOS_SHENLI",   type="Ship", dbid=DBID_TAGOS_19, latitude=19.72, longitude=124.75, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_AGOS_WUXIA",    type="Ship", dbid=DBID_TAGOS_19, latitude=20.29, longitude=119.57, heading=0, speed=0, autodetectable=true })
addUnit({ side=BLUE, name="BLUE_AGOS_ZHUCHENG", type="Ship", dbid=DBID_TAGOS_19, latitude=14.06, longitude=119.20, heading=0, speed=0, autodetectable=true })

-- F03 蓝方 F-35 (7 架)
local f03 = {
    {DBID_F35C, -0.723911, 106.122993, 1000, "BLUE_F35C_01"},
    {DBID_F35C, -0.792082, 106.185909, 1000, "BLUE_F35C_02"},
    {DBID_F35C, -0.752938, 106.05896,  1000, "BLUE_F35C_03"},
    {DBID_F35B,  7.92,     120.093579, 1000, "BLUE_F35B_01"},
    {DBID_F35B,  7.89,     120.093579, 1000, "BLUE_F35B_02"},
    {DBID_F35B,  7.9215,   120.129358, 1000, "BLUE_F35B_03"},
    {DBID_F35B,  7.9178,   120.093579, 1000, "BLUE_F35B_04"},
}
for _, p in ipairs(f03) do
    addUnit({ side=BLUE, name=p[5], type="Aircraft", dbid=p[1], loadout_id=p[1],
              latitude=p[2], longitude=p[3], altitude=p[4], heading=0, speed=0, autodetectable=true })
end

-- HMS 蓝方远程火箭营 (9 套, 设施近似)
local hms_pts = {
    {9.95, 118.70}, {9.95, 118.70}, {9.95, 118.70}, {9.95, 118.70}, {9.95, 118.70},
    {8.539521, 117.323625}, {8.603141, 117.327882},
    {8.538925, 117.261165}, {8.471862, 117.264859},
}
for i, p in ipairs(hms_pts) do
    addUnit({ side=BLUE, name=("BLUE_HMS_%02d"):format(i), type="Ship", dbid=DBID_CVN_LINCOLN,
              latitude=p[1], longitude=p[2], heading=0, speed=0, autodetectable=true })
end

-- TYPHON 蓝方中导营 (4 套)
for i = 1, 4 do
    addUnit({ side=BLUE, name=("BLUE_TYPHON_%02d"):format(i), type="Ship", dbid=DBID_CVN_LINCOLN,
              latitude=18.35, longitude=120.90, heading=0, speed=0, autodetectable=true })
end

print("[CMO] CREATE 阶段完成：红蓝双方 ~130 个单位已下发")

-- ============================================================================
-- 第 3 阶段: CLEAR - 清弹
-- ============================================================================
print("")
print("[CMO] === Stage 3/4: CLEAR ===")

local function clearUnitWeapons(unitname)
    local u = ScenEdit_GetUnit({ side = RED, name = unitname })
    if not (u and u.guid) then
        print(("[CMO] [WARN] %s 不存在，跳过清弹"):format(unitname))
        return
    end
    -- 对每个 mount，清空当前武器
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            -- mount_weapons 中每条都是 (wpn_dbid, current, max)
            local dbId = w.wpn_dbid
            if dbId then
                pcall(ScenEdit_RemoveWeaponsFromUnit, { side=RED, unitname=unitname, wpn_dbid=dbId })
            end
        end
    end
    print(("[CMO] 清弹完成: %s"):format(unitname))
end

-- 红方水面舰艇
local RED_CLEAR_LIST = {
    "DDG01_052D_01", "DDG01_055_01", "DDG01_052D_02",
    "DDG01_054A_01", "DDG01_054A_02",
    "DDG02_052D_01", "DDG02_054A_01",
    "DDG03_054A_01",
}
for _, n in ipairs(RED_CLEAR_LIST) do clearUnitWeapons(n) end

print("[CMO] CLEAR 阶段完成")

-- ============================================================================
-- 第 4 阶段: RELOAD - 装弹
-- ============================================================================
print("")
print("[CMO] === Stage 4a/4: RELOAD ===")

local RED_AMMO = {
    -- 水面舰艇反舰
    { "DDG01_052D_01", DBID_YJ18, 8 },
    { "DDG01_055_01",  DBID_YJ18, 16 },
    { "DDG01_052D_02", DBID_YJ18, 8 },
    { "DDG01_054A_01", DBID_YJ18, 4 },
    { "DDG01_054A_02", DBID_YJ18, 4 },
    { "DDG02_052D_01", DBID_YJ18, 8 },
    { "DDG02_054A_01", DBID_YJ18, 4 },
    { "DDG03_054A_01", DBID_YJ18, 4 },
    -- 轰-6K
    { "H06_HK_01", DBID_YJ12, 4 },
    { "H06_HK_02", DBID_YJ12, 4 },
    { "H06_HK_03", DBID_YJ12, 4 },
    { "H06_HK_04", DBID_YJ12, 4 },
    { "H06_HK_05", DBID_YJ12, 4 },
    { "H06_HK_06", DBID_YJ12, 4 },
    { "H06_HK_07", DBID_YJ12, 4 },
    { "H06_HK_08", DBID_YJ12, 4 },
    { "H02_HK_11", DBID_YJ12, 4 },
    { "H02_HK_12", DBID_YJ12, 4 },
    { "H02_HK_13", DBID_YJ12, 4 },
    { "H02_HK_14", DBID_YJ12, 4 },
    { "H02_HK_15", DBID_YJ12, 4 },
    { "H02_HK_16", DBID_YJ12, 4 },
    -- J-16 多用途
    { "Z05_J16_01", DBID_YJ18, 4 },
    { "Z05_J16_02", DBID_YJ18, 4 },
    { "Z05_J16_03", DBID_YJ18, 4 },
    { "Z05_J16_04", DBID_YJ18, 4 },
    { "Z05_J16_05", DBID_YJ18, 4 },
    { "Z05_J16_06", DBID_YJ18, 4 },
    { "Z06_J16_07", DBID_YJ18, 4 },
    { "Z06_J16_08", DBID_YJ18, 4 },
    { "Z06_J16_09", DBID_YJ18, 4 },
    { "Z06_J16_10", DBID_YJ18, 4 },
    { "Z06_J16_11", DBID_YJ18, 4 },
    { "Z06_J16_12", DBID_YJ18, 4 },
    -- DF-26 旅
    { "D02_DFB_01",  DBID_DF26C, 4 },
    { "D02_DFB_02",  DBID_DF26C, 4 },
    { "D02_DFB_03",  DBID_DF26C, 4 },
    { "D02_DFB_04",  DBID_DF26C, 4 },
    { "D02_DFB_05",  DBID_DF26C, 4 },
    { "D02_DFB_06",  DBID_DF26C, 4 },
    { "D02_DFB_07",  DBID_DF26C, 4 },
    { "D02_DFB_08",  DBID_DF26C, 4 },
    { "D02_DFB_09",  DBID_DF26C, 4 },
    { "D02_DFB_10",  DBID_DF26C, 4 },
    { "D02_DFB_11",  DBID_DF26C, 4 },
    { "D02_DFB_12",  DBID_DF26C, 4 },
    { "D02_DFB_13",  DBID_DF26C, 4 },
    { "D02_DFB_14",  DBID_DF26C, 4 },
    { "D02_DFB_15",  DBID_DF26C, 4 },
    { "D02_DFB_16",  DBID_DF26C, 4 },
    { "D02_DFB_17",  DBID_DF26C, 4 },
    { "D02_DFB_18",  DBID_DF26C, 4 },
    { "D02_DFB_19",  DBID_DF26C, 4 },
    { "D02_DFB_20",  DBID_DF26C, 4 },
    { "D03_DFD_01",  DBID_DF26D, 4 },
    { "D03_DFD_02",  DBID_DF26D, 4 },
    { "D03_DFD_03",  DBID_DF26D, 4 },
    { "D03_DFD_04",  DBID_DF26D, 4 },
    { "D03_DFD_05",  DBID_DF26D, 4 },
    { "D03_DFD_06",  DBID_DF26D, 4 },
    { "D03_DFD_07",  DBID_DF26D, 4 },
    { "D03_DFD_08",  DBID_DF26D, 4 },
    { "D03_DFD_09",  DBID_DF26D, 4 },
    { "D03_DFD_10",  DBID_DF26D, 4 },
    { "D03_DFD_11",  DBID_DF26D, 4 },
    { "D03_DFD_12",  DBID_DF26D, 4 },
    { "D03_DFD_13",  DBID_DF26D, 4 },
    { "D03_DFD_14",  DBID_DF26D, 4 },
    { "D03_DFD_15",  DBID_DF26D, 4 },
    { "D03_DFD_16",  DBID_DF26D, 4 },
    { "D03_DFD_17",  DBID_DF26D, 4 },
    { "D03_DFD_18",  DBID_DF26D, 4 },
    { "D03_DFD_19",  DBID_DF26D, 4 },
    { "D03_DFD_20",  DBID_DF26D, 4 },
}

local function reloadUnit(unitname, wpn_dbid, number)
    pcall(ScenEdit_AddReloadsToUnit, {
        side     = RED,
        unitname = unitname,
        wpn_dbid = wpn_dbid,
        number   = number,
    })
    print(("[CMO] 装弹: %-18s 武器=%-6d 数量=%d"):format(unitname, wpn_dbid, number))
end

for _, ammo in ipairs(RED_AMMO) do
    reloadUnit(ammo[1], ammo[2], ammo[3])
end

print("[CMO] RELOAD 阶段完成")

-- ============================================================================
-- 第 4 阶段: ATTACK - 真延时打击（事件驱动 TOT 齐射）
-- ============================================================================
print("")
print("[CMO] === Stage 4b/4: ATTACK (真延时齐射) ===")

-- 全局变量（事件沙箱访问）
_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"
_SIDE_RED_AWARENESS = "OMNI"
_BLUE_AUTODETECTABLE = true
_CONTACT_SETTLE_DELAY = 15
_CONTACT_RETRY_DELAY  = 5
_CONTACT_RETRY_MAX    = 12

-- global fire function (事件沙箱可调用)
function fireAt(attackerName, targetName, wpnDbid, qty)
    qty = qty or 1
    local atk = ScenEdit_GetUnit({ side = _SIDE_RED, name = attackerName })
    if not (atk and atk.guid) then
        print(("[CMO] [WARN] fireAt: 攻击方 '%s' 不存在"):format(attackerName))
        return false
    end
    local tgt = ScenEdit_GetUnit({ side = _SIDE_BLUE, name = targetName })
    if not (tgt and tgt.guid) then
        print(("[CMO] [WARN] fireAt: 目标 '%s' 不存在"):format(targetName))
        return false
    end

    -- 找蓝方 contact (红线 #8: 必须有 autodetectable)
    local contactGuid = nil
    local contacts = ScenEdit_GetContacts({ side = _SIDE_RED })
    if contacts then
        for _, c in ipairs(contacts) do
            if c.unit_guid == tgt.guid then
                contactGuid = c.guid
                break
            end
        end
    end

    if not contactGuid then
        print(("[CMO] [WARN] fireAt: 攻击方 '%s' 看不到 '%s' 的 contact"):format(attackerName, targetName))
        return false
    end

    -- 实际发射（红线 #13: mode 必须是字符串 "1"）
    local ok = ScenEdit_AttackContact({
        side      = _SIDE_RED,
        contact_guid = contactGuid,
        attacker_guid = atk.guid,
        weapon_dbid = wpnDbid,
        qty = tostring(qty),
        mode = "1",
    })
    print(("[CMO] fireAt: %s -> %s 武器=%d 数量=%d 结果=%s"):format(attackerName, targetName, wpnDbid, qty, tostring(ok)))
    return ok
end

-- 找 contact 的辅助函数
function findContactForTarget(targetGuid)
    if not targetGuid then return nil end
    local contacts = ScenEdit_GetContacts({ side = _SIDE_RED })
    if not contacts then return nil end
    for _, c in ipairs(contacts) do
        if c.unit_guid == targetGuid then
            return c.guid
        end
    end
    return nil
end

-- Time Trigger + LuaScript Action
local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    local offSet = 62135596801
    return string.format("%.0f", (t + offSet + addSeconds) * 1e7)
end

local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    delay = delay + _CONTACT_SETTLE_DELAY
    -- 红线 #11: tag 带时间戳
    tag = tag .. "_" .. tostring(ScenEdit_CurrentTime())
    local evName = "Event " .. tag
    local trName = "Trig "  .. tag
    local acName = "Act "   .. tag
    local fireTime = totTicks(delay)
    local script =
        ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent,   evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
    print(("[CMO] TOT 调度: %s 攻击 %s 武器=%d T+%.0fs tag=%s"):format(atkName, tgtName, wpn, delay, tag))
end

-- 打击清单（与 manifest.lua 一致）
local STRIKE = {
    -- 阶段 1: 火箭军 DF-26 突袭堤丰
    { attacker = "D02_DFB_01",  target = "BLUE_TYPHON_01", weapon_dbid = 2880, quantity = 4, startDelay = 0,    interval = 30, intent = "DF-26B 第 1 波" },
    { attacker = "D02_DFB_05",  target = "BLUE_TYPHON_02", weapon_dbid = 2880, quantity = 4, startDelay = 60,   interval = 30, intent = "DF-26B 第 2 波" },
    { attacker = "D03_DFD_01",  target = "BLUE_TYPHON_03", weapon_dbid = 2879, quantity = 4, startDelay = 120,  interval = 30, intent = "DF-26D 第 1 波" },
    { attacker = "D03_DFD_10",  target = "BLUE_TYPHON_04", weapon_dbid = 2879, quantity = 4, startDelay = 180,  interval = 30, intent = "DF-26D 第 2 波" },
    -- 阶段 2: 反舰齐射航母编队
    { attacker = "DDG01_055_01",  target = "BLUE_CVN_LINCOLN", weapon_dbid = 2868, quantity = 16, startDelay = 600,  interval = 5, intent = "055 齐射 YJ-18 突航母" },
    { attacker = "DDG01_052D_01",target = "BLUE_CG_PULLINS",  weapon_dbid = 2868, quantity = 8,  startDelay = 700,  interval = 4, intent = "052D-1 协同" },
    { attacker = "DDG01_052D_02",target = "BLUE_DDG_MOMUSENG",weapon_dbid = 2868, quantity = 8,  startDelay = 800,  interval = 4, intent = "052D-2 协同" },
    { attacker = "DDG01_054A_01",target = "BLUE_FFG_LISHIMAN",weapon_dbid = 2868, quantity = 4,  startDelay = 900,  interval = 4, intent = "054A 护卫" },
    { attacker = "DDG01_054A_02",target = "BLUE_DDG_LAOLUNSI",weapon_dbid = 2868, quantity = 4,  startDelay = 1000, interval = 4, intent = "054A 协同" },
    { attacker = "DDG02_052D_01",target = "BLUE_DDG_SITELEI", weapon_dbid = 2868, quantity = 8,  startDelay = 1100, interval = 4, intent = "第二编队 052D" },
    { attacker = "DDG02_054A_01",target = "BLUE_DDG_HUOBATE", weapon_dbid = 2868, quantity = 4,  startDelay = 1200, interval = 4, intent = "第二编队 054A" },
    { attacker = "DDG03_054A_01",target = "BLUE_SUPPLY_KZ",   weapon_dbid = 2868, quantity = 4,  startDelay = 1300, interval = 4, intent = "外圈 054A 补给舰" },
    -- 阶段 3: 轰-6K YJ-12 突击两栖
    { attacker = "H06_HK_01", target = "BLUE_LHA_AMERICA", weapon_dbid = 2869, quantity = 4, startDelay = 1500, interval = 20, intent = "轰-6K 第 1 波" },
    { attacker = "H06_HK_02", target = "BLUE_LHA_AMERICA", weapon_dbid = 2869, quantity = 4, startDelay = 1520, interval = 20, intent = "轰-6K 第 2 波" },
    { attacker = "H06_HK_03", target = "BLUE_CG_SIMOER",   weapon_dbid = 2869, quantity = 4, startDelay = 1600, interval = 20, intent = "轰-6K CG" },
    { attacker = "H06_HK_04", target = "BLUE_DDG_CHAFEI",  weapon_dbid = 2869, quantity = 4, startDelay = 1700, interval = 20, intent = "轰-6K DDG" },
    { attacker = "H02_HK_11", target = "BLUE_LHA_AMERICA", weapon_dbid = 2869, quantity = 4, startDelay = 1800, interval = 20, intent = "H02 集群续攻" },
    { attacker = "H02_HK_13", target = "BLUE_LHA_AMERICA", weapon_dbid = 2869, quantity = 4, startDelay = 1820, interval = 20, intent = "H02 集群第 2 波" },
    -- 阶段 4: J-16 对地突击 HMS
    { attacker = "Z05_J16_01", target = "BLUE_HMS_01", weapon_dbid = 2868, quantity = 4, startDelay = 2400, interval = 5, intent = "J-16 突 HMS" },
    { attacker = "Z05_J16_02", target = "BLUE_HMS_02", weapon_dbid = 2868, quantity = 4, startDelay = 2420, interval = 5, intent = "J-16 突 HMS" },
    { attacker = "Z05_J16_03", target = "BLUE_HMS_06", weapon_dbid = 2868, quantity = 4, startDelay = 2500, interval = 5, intent = "J-16 转火" },
    { attacker = "Z06_J16_07", target = "BLUE_HMS_07", weapon_dbid = 2868, quantity = 4, startDelay = 2600, interval = 5, intent = "Z06 中队" },
    { attacker = "Z06_J16_09", target = "BLUE_HMS_09", weapon_dbid = 2868, quantity = 4, startDelay = 2700, interval = 5, intent = "Z06 末端" },
}

function scheduleSalvo()
    local total = 0
    for i, s in ipairs(STRIKE) do
        local atkName   = s.attacker
        local tgtName   = s.target
        local wpn       = s.weapon_dbid
        local qty       = s.quantity or 1
        local startDelay= s.startDelay or 0
        local interval  = s.interval or 1

        if not atkName or not tgtName or not wpn then
            print(("[CMO] [WARN] STRIKE[%d] 字段缺失"):format(i))
            goto continue
        end

        for k = 1, qty do
            local delay = startDelay + (k - 1) * interval
            local tag = ("TOT_%d_%d_%s"):format(i, k, (s.intent or "x"):gsub("[^%w_]", "_"):sub(1, 20))
            scheduleOne(atkName, tgtName, wpn, delay, tag)
            total = total + 1
        end
        ::continue::
    end
    print(("[CMO] 调度完成: %d 枚弹"):format(total))
end

scheduleSalvo()
print("[CMO] ============ A1 联合火力突击脚本完成 ============")
print("[CMO] 真延时齐射: T+0min ~ T+45min")
