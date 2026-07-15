-- ==========================================================================
-- main.lua  红蓝 7V4 辽宁舰协同反舰 — 建阵营 + 建单位
-- 数据来源: json/red_blue_5v3_liaoning1.json（052D DBID 以用户指定为准）
-- MCP 已验证: 055=3883 052D-1=2296 052D-2=3586 辽宁舰=2007 DDG113=4299
--             CG59=2862 CVN70=3551 J-15=2496 loadout=9682 YJ18=2868 YJ83K=2137
-- 红线 #20: 所有 ScenEdit_* 调用用 pcall(function() ... end) 包裹
-- ==========================================================================

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

local function getUnit(side, name)
  local ok, u = pcall(function() return ScenEdit_GetUnit({side=side, name=name}) end)
  if ok and u and u.guid then return u end
  return nil
end

local function ensureUnit(spec)
  local exist = getUnit(spec.side, spec.name)
  if exist then
    print(("[main] 已存在: %s"):format(spec.name)); return exist
  end
  local ok, r = pcall(ScenEdit_AddUnit, spec)
  if not ok then
    print(("[main] [ERROR] 创建 %s 失败: %s"):format(spec.name, tostring(r)))
    return nil
  end
  local u = getUnit(spec.side, spec.name)
  print(("[main] 创建 %s ok=%s"):format(spec.name, tostring(u ~= nil)))
  return u
end

-- ---------- 阵营（红线 #18: 必须传 table）----------
pcall(function() ScenEdit_AddSide({name=_SIDE_RED,  color="255,0,0"}) end)
pcall(function() ScenEdit_AddSide({name=_SIDE_BLUE, color="0,0,255"}) end)
pcall(function() VP_GetSide({Side=_SIDE_RED}) end)
pcall(function() VP_GetSide({Side=_SIDE_BLUE}) end)

-- ---------- 红方全知全能（红线 #6）----------
pcall(function() ScenEdit_SetSideOptions({side=_SIDE_RED, awareness="OMNI"}) end)

-- ---------- 敌对关系 ----------
pcall(function() ScenEdit_SetSidePosture(_SIDE_RED,  _SIDE_BLUE, "H") end)
pcall(function() ScenEdit_SetSidePosture(_SIDE_BLUE, _SIDE_RED,  "H") end)

-- ---------- 双方 WCS = Free(0)（红线 #12）----------
pcall(function() ScenEdit_SetDoctrine({side=_SIDE_RED}, {
  weapon_control_status_air="0", weapon_control_status_surface="0",
  weapon_control_status_subsurface="0", weapon_control_status_land="0"}) end)
pcall(function() ScenEdit_SetDoctrine({side=_SIDE_BLUE}, {
  weapon_control_status_air="0", weapon_control_status_surface="0",
  weapon_control_status_subsurface="0", weapon_control_status_land="0"}) end)
print("[main] 阵营/敌对/WCS 设置完毕")

-- ---------- 红方水面舰艇（DBID 用户指定优先）----------
ensureUnit({type="Ship", side=_SIDE_RED, name="Red-055-1",  dbid=3883,
  latitude=24.8324, longitude=128.5830, heading=135, speed=20, proficiency="Veteran"})
ensureUnit({type="Ship", side=_SIDE_RED, name="Red-055-2",  dbid=3883,
  latitude=26.0,    longitude=130.0,    heading=135, speed=20, proficiency="Veteran"})
ensureUnit({type="Ship", side=_SIDE_RED, name="Red-052D-1", dbid=2296,
  latitude=21.1437, longitude=123.4510, heading=115, speed=20, proficiency="Veteran"})
ensureUnit({type="Ship", side=_SIDE_RED, name="Red-052D-2", dbid=3586,
  latitude=18.2035, longitude=123.9880, heading=50,  speed=20, proficiency="Veteran"})

-- ---------- 红方辽宁舰（母舰，不装反舰弹）----------
local CARRIER_NAME = "红方辽宁舰"
ensureUnit({type="Ship", side=_SIDE_RED, name=CARRIER_NAME, dbid=2007,
  latitude=25.0, longitude=130.0, heading=90, speed=20, proficiency="Veteran"})

-- ---------- 红方 J-15 舰载机（loadoutid=9682，opts={mode="0"} 不触发清弹/装弹）----------
local function ensureJ15(nm)
  if getUnit(_SIDE_RED, nm) then
    print(("[main] J-15 %s 已存在"):format(nm)); return
  end
  pcall(function() ScenEdit_AddUnit({
    type="Aircraft", side=_SIDE_RED, name=nm,
    dbid=2496, loadoutid=9682,
    base=CARRIER_NAME, proficiency="Veteran",
    opts={mode="0"}}) end)
  print(("[main] J-15 %s 创建 ok=%s"):format(nm, tostring(getUnit(_SIDE_RED, nm) ~= nil)))
end
ensureJ15("J-15-RED-01")
ensureJ15("J-15-RED-02")

-- ---------- 蓝方水面目标（红线 #8: autodetectable=true + 传感器开启）----------
local BLUE_UNITS = {
  {name="DDG 113-1",      dbid=4299, lat=21.5419, lon=129.9125, hdg=294.05},
  {name="DDG 113-2",      dbid=4299, lat=22.0,    lon=131.0,    hdg=294.05},
  {name="Blue-DBID-2862", dbid=2862, lat=21.61,   lon=130.1791, hdg=294.58},
  {name="Blue-DBID-3551", dbid=3551, lat=21.42,   lon=130.1713, hdg=293.16},
}
for _, b in ipairs(BLUE_UNITS) do
  local u = ensureUnit({type="Ship", side=_SIDE_BLUE, name=b.name, dbid=b.dbid,
    latitude=b.lat, longitude=b.lon, heading=b.hdg, speed=0, proficiency="Veteran"})
  if u and u.guid then
    pcall(function() ScenEdit_SetUnit({guid=u.guid, autodetectable=true}) end)
    pcall(function() ScenEdit_SetEMCON("Unit", b.name, "Radar=Active;Sonar=Active") end)
  end
end

print("[main] ===== 所有单位创建完毕 =====")

