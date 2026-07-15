-- ============================================================
-- main.lua — 红方5V3（辽宁舰+J-15×2 vs CVN-70编队）
-- 执行顺序：main.lua → clear.lua → reload.lua → attack.lua
-- MCP验证：DBID 来自 MCP 查询 + 用户 JSON 优先（冲突以用户为准）
--
-- DBID（用户指定，优先）：
--   055  DBID=3883 | 052D-1 DBID=2296 | 052D-2 DBID=3586
--   辽宁舰 DBID=2007 | J-15 DBID=2496 | YJ-18 DBID=2868
--   CVN-70 DBID=3551 | CG-59 DBID=2862 | DDG-113 DBID=4299
--   YJ-83K DBID=2137 | J-15 反舰挂载 LoadoutID=9682
-- ============================================================

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

_MANIFEST_SHIPS = {
  {name="红方055南昌舰",   dbid=3883, lat=30.55, lon=122.40, heading=90, speed=18, prof="Veteran"},
  {name="红方052D-1昆明舰", dbid=2296, lat=30.52, lon=122.35, heading=90, speed=16, prof="Veteran"},
  {name="红方052D-2南京舰", dbid=3586, lat=30.58, lon=122.45, heading=90, speed=16, prof="Veteran"},
  {name="红方辽宁舰",       dbid=2007, lat=30.60, lon=122.30, heading=90, speed=18, prof="Veteran"},
}
_MANIFEST_AIRCRAFT = {
  {name="J-15-1", dbid=2496, base="红方辽宁舰", prof="Veteran", loadoutid=9682},
  {name="J-15-2", dbid=2496, base="红方辽宁舰", prof="Veteran", loadoutid=9682},
}
_MANIFEST_BLUE = {
  {name="蓝方CVN-70卡尔文森", dbid=3551, lat=30.40, lon=124.50, heading=270, speed=14, prof="Veteran"},
  {name="蓝方CG-59普林斯顿",   dbid=2862, lat=30.38, lon=124.20, heading=270, speed=14, prof="Veteran"},
  {name="蓝方DDG-113约翰芬恩", dbid=4299, lat=30.42, lon=124.80, heading=270, speed=14, prof="Veteran"},
}

print("[main] MANIFEST 加载完成")
print("  红方舰艇: " .. #_MANIFEST_SHIPS .. " 艘")
print("  红方舰载机: " .. #_MANIFEST_AIRCRAFT .. " 架")
print("  蓝方舰艇: " .. #_MANIFEST_BLUE .. " 艘")

local function getUnit(side, name)
  local ok, u = pcall(ScenEdit_GetUnit, {side=side, name=name})
  if ok and u and u.guid then return u end
  return nil
end

-- ============================================================
-- 建阵营
-- ============================================================
print("\n===== [main] 建阵营 =====")

pcall(ScenEdit_AddSide, {name=_SIDE_RED,  color="255,0,0"})
pcall(ScenEdit_AddSide, {name=_SIDE_BLUE, color="0,0,255"})

pcall(ScenEdit_SetSideOptions, {side=_SIDE_RED,  awareness="OMNI"})
pcall(ScenEdit_SetSideOptions, {side=_SIDE_BLUE, awareness="OMNI"})

pcall(ScenEdit_SetSidePosture, _SIDE_RED,  _SIDE_BLUE, "H")
pcall(ScenEdit_SetSidePosture, _SIDE_BLUE, _SIDE_RED,  "H")

for _, side in ipairs({_SIDE_RED, _SIDE_BLUE}) do
  pcall(ScenEdit_SetDoctrine, {side=side}, {
    weapon_control_status_air="0",
    weapon_control_status_surface="0",
    weapon_control_status_subsurface="0",
    weapon_control_status_land="0",
  })
end

local sR = pcall(VP_GetSide, {Side=_SIDE_RED})
local sB = pcall(VP_GetSide, {Side=_SIDE_BLUE})
print(("[main] 阵营: 红方=%s 蓝方=%s"):format(
  tostring(sR and true or false),
  tostring(sB and true or false)))

-- ============================================================
-- 建红方舰艇
-- ============================================================
print("[main] 建红方舰艇...")
for _, s in ipairs(_MANIFEST_SHIPS) do
  if not getUnit(_SIDE_RED, s.name) then
    _errnum_ = 0
    local ok, r = pcall(ScenEdit_AddUnit, {
      type="Ship", side=_SIDE_RED, name=s.name, dbid=s.dbid,
      latitude=s.lat, longitude=s.lon,
      heading=s.heading, speed=s.speed, proficiency=s.prof,
    })
    print("[main] " .. s.name .. " ok=" .. tostring(ok) .. " err=" .. tostring(_errmsg_))
  else
    print("[main] " .. s.name .. " 已存在")
  end
end

-- ============================================================
-- 建蓝方舰艇（autodetectable=true）
-- ============================================================
print("[main] 建蓝方舰艇...")
for _, s in ipairs(_MANIFEST_BLUE) do
  if not getUnit(_SIDE_BLUE, s.name) then
    _errnum_ = 0
    local ok, r = pcall(ScenEdit_AddUnit, {
      type="Ship", side=_SIDE_BLUE, name=s.name, dbid=s.dbid,
      latitude=s.lat, longitude=s.lon,
      heading=s.heading, speed=s.speed,
      autodetectable=true, proficiency=s.prof,
    })
    print("[main] " .. s.name .. " ok=" .. tostring(ok) .. " err=" .. tostring(_errmsg_))
  else
    local u = getUnit(_SIDE_BLUE, s.name)
    if u then pcall(ScenEdit_SetUnit, {guid=u.guid, autodetectable=true}) end
    print("[main] " .. s.name .. " 已存在（autodetectable 已刷新）")
  end
  pcall(ScenEdit_SetEMCON, "Unit", s.name, "Radar=Active")
end

-- ============================================================
-- 建红方舰载机（带 loadoutid=9682，含 YJ-83K）
-- ============================================================
print("[main] 建红方舰载机...")
for _, a in ipairs(_MANIFEST_AIRCRAFT) do
  if not getUnit(_SIDE_RED, a.name) then
    _errnum_ = 0
    local ok, r = pcall(ScenEdit_AddUnit, {
      type="Aircraft", side=_SIDE_RED, name=a.name, dbid=a.dbid,
      loadoutid=a.loadoutid,
      base=a.base, proficiency=a.prof,
    })
    print("[main] " .. a.name .. " ok=" .. tostring(ok) .. " err=" .. tostring(_errmsg_))
    if not ok then
      -- 后备：不带 loadoutid 重试
      _errnum_ = 0
      ok = pcall(ScenEdit_AddUnit, {
        type="Aircraft", side=_SIDE_RED, name=a.name, dbid=a.dbid,
        base=a.base, proficiency=a.prof,
      })
      print("[main] " .. a.name .. " [后备裸机] ok=" .. tostring(ok) .. " err=" .. tostring(_errmsg_))
    end
  else
    print("[main] " .. a.name .. " 已存在")
  end
  if getUnit(_SIDE_RED, a.name) then
    pcall(ScenEdit_SetUnit, {side=_SIDE_RED, unitname=a.name, timetoready_minutes=0})
    pcall(ScenEdit_SetUnit, {side=_SIDE_RED, unitname=a.name, launch=true})
    pcall(ScenEdit_SetEMCON, "Unit", a.name, "Radar=Active")
  end
end

print("\n[main] 完成。")
