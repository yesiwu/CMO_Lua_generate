-- ============================================================
-- main.lua: 红蓝双方单位创建
-- 红方: Red-055-1 / Red-055-2 / Red-052D-1 / Red-052D-2 / 红方辽宁舰(J-15×2)
-- 蓝方: DDG 113-1 / Blue-DBID-2862(CG-59) / Blue-DBID-3551(CVN-70)
-- 辽宁舰+舰载机: J-15-RED-01/02 使用 loadoutId=9682(反舰挂载)
-- 蓝方单位: autodetectable=true / 红方传感器默认开启
-- 数据来源: JSON red_blue_5v3_liaoning1.json
-- ============================================================

-- ---------- 全局配置 ----------
_SIDE_RED   = "红方"
_SIDE_BLUE  = "蓝方"

-- ---------- 红方全知全能 ----------
ScenEdit_SetSideOptions({side=_SIDE_RED, awareness="OMNI"})

-- ---------- 蓝方单位 autodetectable=true ----------
local BLUE_UNITS = {
    {name="DDG 113-1",          dbid=4299, lat=21.5419, lon=129.9125, heading=294.05},
    {name="Blue-DBID-2862",      dbid=2862, lat=21.61,   lon=130.1791, heading=294.58},
    {name="Blue-DBID-3551",      dbid=3551, lat=21.42,   lon=130.1713, heading=293.16},
}

for _, u in ipairs(BLUE_UNITS) do
    ScenEdit_AddUnit({
        side    = _SIDE_BLUE,
        type    = "Ship",
        name    = u.name,
        dbid    = u.dbid,
        latitude  = u.lat,
        longitude = u.lon,
        heading   = u.heading,
        speed     = 0,
        autodetectable = true,
    })
end
print("[main] 蓝方单位创建完毕（autodetectable=true）")

-- ---------- 红方水面舰艇 ----------
-- 注：Red-055-2 / Red-052D-2 坐标为 null，仅创建有坐标的舰艇
local RED_SHIPS = {
    {name="Red-055-1",   dbid=3883, lat=24.8324, lon=128.5830, heading=135},
    {name="Red-052D-1",  dbid=2296, lat=21.1437, lon=123.4510, heading=115},
    {name="Red-052D-2",  dbid=3586, lat=18.2035, lon=123.9880, heading=50},
}

for _, s in ipairs(RED_SHIPS) do
    ScenEdit_AddUnit({
        side    = _SIDE_RED,
        type    = "Ship",
        name    = s.name,
        dbid    = s.dbid,
        latitude  = s.lat,
        longitude = s.lon,
        heading   = s.heading,
        speed     = 20,
        autodetectable = true,
    })
end
print("[main] 红方水面舰艇创建完毕")

-- ---------- 红方辽宁舰 ----------
local cv = ScenEdit_AddUnit({
    side    = _SIDE_RED,
    type    = "Ship",
    name    = "红方辽宁舰",
    dbid    = 2007,
    latitude  = 25.0,
    longitude = 130.0,
    heading   = 90,
    speed     = 20,
    autodetectable = true,
})
print("[main] 辽宁舰创建完毕（" .. (cv and cv.guid or "nil") .. "）")

-- ---------- 红方 J-15 舰载机（mode="0"，不触发武器清单变更） ----------
-- loadoutId=9682 对应 YJ-83K [C-802AK]（DB 中 J-15 反舰挂载）
-- opts={mode="0"} 表示"保留清单（不触发装弹/清弹）"
ScenEdit_AddUnit({
    side      = _SIDE_RED,
    type      = "Aircraft",
    name      = "J-15-RED-01",
    dbid      = 2496,
    loadoutId = 9682,
    base      = "红方辽宁舰",
    heading   = 90,
    speed     = 300,
    altitude  = 500,
    opts      = {mode="0"},
})
print("[main] J-15-RED-01 创建完毕（loadoutId=9682, opts={mode=0}）")

ScenEdit_AddUnit({
    side      = _SIDE_RED,
    type      = "Aircraft",
    name      = "J-15-RED-02",
    dbid      = 2496,
    loadoutId = 9682,
    base      = "红方辽宁舰",
    heading   = 90,
    speed     = 300,
    altitude  = 500,
    opts      = {mode="0"},
})
print("[main] J-15-RED-02 创建完毕（loadoutId=9682, opts={mode=0}）")

print("[main] ===== 所有单位创建完毕 =====")
