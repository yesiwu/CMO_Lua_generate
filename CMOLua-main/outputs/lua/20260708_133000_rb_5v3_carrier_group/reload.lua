-- ============================================================
-- reload.lua — 装弹
-- 舰艇：YJ-18（DBID=2868）各 8 枚
-- 舰载机：J-15 YJ-83K（DBID=2137）各 4 枚
-- API: ScenEdit_AddReloadsToUnit({side, unitname, wpn_dbid, number})
-- ============================================================

print("\n===== [reload] 装弹 =====")

local function getUnit(side, name)
  local ok, u = pcall(ScenEdit_GetUnit, {side=side, name=name})
  if ok and u and u.guid then return u end
  return nil
end

-- ============================================================
-- 舰艇装弹：YJ-18（DBID=2868）直接 AddReloadsToUnit
-- ============================================================
local SHIPS_RELOAD = {
  {name="红方055南昌舰",   qty=8,  wpn=2868},
  {name="红方052D-1昆明舰", qty=8,  wpn=2868},
  {name="红方052D-2南京舰", qty=8,  wpn=2868},
}

print("[reload] === 舰艇装弹（YJ-18 DBID=2868）===")
for _, s in ipairs(SHIPS_RELOAD) do
  _errnum_ = 0
  local ok, r = pcall(ScenEdit_AddReloadsToUnit, {
    side     = "红方",
    unitname = s.name,
    wpn_dbid = s.wpn,
    number   = s.qty,
  })
  print(("[reload] %s 装%d枚 YJ-18 ok=%s err=%s"):format(
    s.name, s.qty, tostring(ok), tostring(_errmsg_)))
end

-- ============================================================
-- 舰载机装弹：J-15 YJ-83K（DBID=2137）
-- J-15 默认 Loadout 无 YJ-83K，用 AddReloadsToUnit 挂载
-- ============================================================
local AIRCRAFT_RELOAD = {
  {name="J-15-1", qty=4, wpn=2137},
  {name="J-15-2", qty=4, wpn=2137},
}

print("\n[reload] === 舰载机装弹（J-15 YJ-83K DBID=2137）===")
for _, a in ipairs(AIRCRAFT_RELOAD) do
  _errnum_ = 0
  local ok, r = pcall(ScenEdit_AddReloadsToUnit, {
    side     = "红方",
    unitname = a.name,
    wpn_dbid = a.wpn,
    number   = a.qty,
  })
  print(("[reload] %s 装%d枚 YJ-83K ok=%s err=%s"):format(
    a.name, a.qty, tostring(ok), tostring(_errmsg_)))
end

-- 装弹后自检
print("\n[reload] === 装弹后检查 ===")
local ALL_UNITS = {
  {side="红方", name="红方055南昌舰"},
  {side="红方", name="红方052D-1昆明舰"},
  {side="红方", name="红方052D-2南京舰"},
  {side="红方", name="J-15-1"},
  {side="红方", name="J-15-2"},
}
for _, item in ipairs(ALL_UNITS) do
  local ok, u = pcall(ScenEdit_GetUnit, {side=item.side, name=item.name})
  if ok and u then
    print(("[reload] %s magazine=%s"):format(item.name, tostring(u.magazine)))
  end
end

print("\n[reload] 完成。")
