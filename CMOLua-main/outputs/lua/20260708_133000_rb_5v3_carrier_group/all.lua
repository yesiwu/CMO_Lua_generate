-- ============================================================
-- all.lua — 红方5V3（辽宁舰+J-15×2 vs CVN-70编队）
-- 方案：055/052D×2 水面饱和 YJ-18 主攻 CVN-70；J-15×2 YJ-83K 分别打 CG-59/DDG-113
-- 执行顺序：main → clear → reload → attack
-- MCP验证：DBID全部来自 DB3K_504.db3 查询（冲突以用户JSON为准）
-- ============================================================

print("\n========================================")
print("[all] 红方5V3 自动化脚本")
print("[all] 冲突解决：JSON DBID 优先于 MCP 推测")
print("========================================")

-- ============================================================
-- ★★★ MANIFEST（全文件唯一数据源，4段共享）★★★
-- ============================================================
_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

_MANIFEST_SHIPS = {
  {name="红方055南昌舰",   dbid=3883, lat=30.55, lon=122.40, heading=90, speed=18, prof="Veteran"},
  {name="红方052D-1昆明舰", dbid=2296, lat=30.52, lon=122.35, heading=90, speed=16, prof="Veteran"},
  {name="红方052D-2南京舰", dbid=3587, lat=30.58, lon=122.45, heading=90, speed=16, prof="Veteran"},
  {name="红方辽宁舰",       dbid=2007, lat=30.60, lon=122.30, heading=90, speed=18, prof="Veteran"},
}
_MANIFEST_AIRCRAFT = {
  {name="J-15-1", dbid=2496, base="红方辽宁舰", prof="Veteran"},
  {name="J-15-2", dbid=2496, base="红方辽宁舰", prof="Veteran"},
}
_MANIFEST_BLUE = {
  {name="蓝方CVN-70卡尔文森", dbid=3551, lat=30.40, lon=124.50, heading=270, speed=14, prof="Veteran"},
  {name="蓝方CG-59普林斯顿",   dbid=2862, lat=30.38, lon=124.20, heading=270, speed=14, prof="Veteran"},
  {name="蓝方DDG-113约翰芬恩", dbid=4299, lat=30.42, lon=124.80, heading=270, speed=14, prof="Veteran"},
}

-- 武器：水面 YJ-18(2868) / 航空 YJ-83K(2137)
_WPN_YJ18  = 2868
_WPN_YJ83K = 2137

-- TOT配置
_TOT_OFFSET = 621355968000000000
_CONTACT_SETTLE = 15  -- 秒（用户指定）

-- ============================================================
-- 工具函数（local，供各段调用）
-- ============================================================
local function getUnit(side, name)
  local ok, u = pcall(ScenEdit_GetUnit, {side=side, name=name})
  if ok and u and u.guid then return u end
  return nil
end

-- ============================================================
-- ★★★ 第1段：main.lua（建阵营 + 建单位）★★★
-- ============================================================
do
  print("\n===== [main] 建阵营 + 建单位 =====")

  -- 建阵营（红线#18：必须 table）
  pcall(ScenEdit_AddSide, {name=_SIDE_RED,  color="255,0,0"})
  pcall(ScenEdit_AddSide, {name=_SIDE_BLUE, color="0,0,255"})

  -- 红方全知全能（红线#6）
  pcall(ScenEdit_SetSideOptions, {side=_SIDE_RED,  awareness="OMNI"})
  pcall(ScenEdit_SetSideOptions, {side=_SIDE_BLUE, awareness="OMNI"})

  -- 互为敌对
  pcall(ScenEdit_SetSidePosture, _SIDE_RED,  _SIDE_BLUE, "H")
  pcall(ScenEdit_SetSidePosture, _SIDE_BLUE, _SIDE_RED,  "H")

  -- 红蓝双方 wcs=0（红线#12）
  for _, side in ipairs({_SIDE_RED, _SIDE_BLUE}) do
    pcall(ScenEdit_SetDoctrine, {side=side}, {
      weapon_control_status_air="0",
      weapon_control_status_surface="0",
      weapon_control_status_subsurface="0",
      weapon_control_status_land="0",
    })
  end

  -- 阵营诊断（红线#18 验证）
  local sR = pcall(VP_GetSide, {Side=_SIDE_RED})
  local sB = pcall(VP_GetSide, {Side=_SIDE_BLUE})
  print(("[main] 阵营: 红方=%s 蓝方=%s"):format(
    tostring(sR and true or false),
    tostring(sB and true or false)))

  -- 建红方舰艇
  print("[main] 建红方舰艇...")
  for _, s in ipairs(_MANIFEST_SHIPS) do
    if not getUnit(_SIDE_RED, s.name) then
      local ok = pcall(ScenEdit_AddUnit, {
        type="Ship", side=_SIDE_RED, name=s.name, dbid=s.dbid,
        latitude=s.lat, longitude=s.lon,
        heading=s.heading, speed=s.speed, proficiency=s.prof,
      })
      print("[main] " .. s.name .. " ok=" .. tostring(ok))
    else
      print("[main] " .. s.name .. " 已存在")
    end
  end

  -- 建蓝方舰艇（红线#8：autodetectable=true）
  print("[main] 建蓝方舰艇...")
  for _, s in ipairs(_MANIFEST_BLUE) do
    if not getUnit(_SIDE_BLUE, s.name) then
      local ok = pcall(ScenEdit_AddUnit, {
        type="Ship", side=_SIDE_BLUE, name=s.name, dbid=s.dbid,
        latitude=s.lat, longitude=s.lon,
        heading=s.heading, speed=s.speed,
        autodetectable=true, proficiency=s.prof,
      })
      print("[main] " .. s.name .. " ok=" .. tostring(ok))
    else
      -- 已存在也强制 autodetectable
      local u = getUnit(_SIDE_BLUE, s.name)
      if u then pcall(ScenEdit_SetUnit, {guid=u.guid, autodetectable=true}) end
      print("[main] " .. s.name .. " 已存在")
    end
    -- 蓝方传感器默认开启
    pcall(ScenEdit_SetEMCON, "Unit", s.name, "Radar=Active")
  end

  -- 建红方舰载机
  print("[main] 建红方舰载机...")
  for _, a in ipairs(_MANIFEST_AIRCRAFT) do
    if not getUnit(_SIDE_RED, a.name) then
      local ok = pcall(ScenEdit_AddUnit, {
        type="Aircraft", side=_SIDE_RED, name=a.name, dbid=a.dbid,
        base=a.base, proficiency=a.prof,
      })
      print("[main] " .. a.name .. " ok=" .. tostring(ok))
    else
      print("[main] " .. a.name .. " 已存在")
    end
    -- 准备时间归零 + 起飞 + 雷达
    pcall(ScenEdit_SetUnit, {side=_SIDE_RED, unitname=a.name, timetoready_minutes=0})
    pcall(ScenEdit_SetUnit, {side=_SIDE_RED, unitname=a.name, launch=true})
    pcall(ScenEdit_SetEMCON, "Unit", a.name, "Radar=Active")
  end

  print("[main] 完成。")
end

-- ============================================================
-- ★★★ 第2段：clear.lua（清弹）★★★
-- ============================================================
do
  print("\n===== [clear] 清弹 =====")

  local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
      print("[clear] [WARN] 找不到 " .. side .. "/" .. name); return false
    end
    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
      for _, w in ipairs(m.mount_weapons or {}) do
        local cur = tonumber(w.wpn_current) or 0
        if cur > 0 then
          jobs[#jobs + 1] = { dbid = w.wpn_dbid, num = cur, mountid = m.mount_guid }
        end
      end
    end
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
      _errnum_ = 0
      ScenEdit_AddReloadsToUnit({
        guid = u.guid, wpn_dbid = j.dbid,
        mount_guid = j.mountid, number = j.num, remove = true,
      })
      if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
    end
    print(("[clear] %s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
  end

  local CLEAR_LIST = {
    "红方055南昌舰", "红方052D-1昆明舰", "红方052D-2南京舰",
    "J-15-1", "J-15-2",
  }

  for _, name in ipairs(CLEAR_LIST) do clearUnitWeapons(_SIDE_RED, name) end
  print("[clear] 完成。")
end

-- ============================================================
-- ★★★ 第3段：reload.lua（装弹）★★★
-- ============================================================
do
  print("\n===== [reload] 装弹 =====")

  -- 舰艇：YJ-18 各 8 枚
  local SHIPS_RELOAD = {
    {name="红方055南昌舰",   qty=8, wpn=_WPN_YJ18},
    {name="红方052D-1昆明舰", qty=8, wpn=_WPN_YJ18},
    {name="红方052D-2南京舰", qty=8, wpn=_WPN_YJ18},
  }
  print("[reload] 舰艇装弹（YJ-18 DBID=" .. _WPN_YJ18 .. "）")
  for _, s in ipairs(SHIPS_RELOAD) do
    _errnum_ = 0
    local ok = pcall(ScenEdit_AddReloadsToUnit, {
      side=_SIDE_RED, unitname=s.name, wpn_dbid=s.wpn, number=s.qty,
    })
    print(("[reload] %s ×%d ok=%s err=%s"):format(s.name, s.qty, tostring(ok), tostring(_errmsg_)))
  end

  -- 舰载机：YJ-83K 各 4 枚
  local AIRCRAFT_RELOAD = {
    {name="J-15-1", qty=4, wpn=_WPN_YJ83K},
    {name="J-15-2", qty=4, wpn=_WPN_YJ83K},
  }
  print("[reload] 舰载机装弹（YJ-83K DBID=" .. _WPN_YJ83K .. "）")
  for _, a in ipairs(AIRCRAFT_RELOAD) do
    _errnum_ = 0
    local ok = pcall(ScenEdit_AddReloadsToUnit, {
      side=_SIDE_RED, unitname=a.name, wpn_dbid=a.wpn, number=a.qty,
    })
    print(("[reload] %s ×%d ok=%s err=%s"):format(a.name, a.qty, tostring(ok), tostring(_errmsg_)))
  end

  print("[reload] 完成。")
end

-- ============================================================
-- ★★★ 第4段：attack.lua（TOT 真延时打击 + RTB）★★★
-- ============================================================
do
  print("\n===== [attack] 真延时齐射 =====")

  -- ============================================================
  -- TOT 工具函数（必须是全局，红线#15）
  -- ============================================================

  function totTicks(unixSec)
    return string.format("%.0f", unixSec * 1e7 + _TOT_OFFSET)
  end

  function scheduleOne(atkName, tgtName, wpnDbid, qty, delay, tag)
    local fireUnix = ScenEdit_CurrentTime() + delay
    local fireTime = totTicks(fireUnix)
    local ts = tostring(fireUnix)
    local evName = "Ev_" .. tag .. "_" .. ts
    local trName = "Tr_" .. tag .. "_" .. ts
    local acName = "Ac_" .. tag .. "_" .. ts

    local script = table.concat({
      ("fireAt(%q,%q,%d,%d)\n"):format(atkName, tgtName, wpnDbid, qty),
      ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName),
      ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName),
      ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName),
    })

    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent,   evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})

    print(("[attack] [TOT] %s@T+%ds → %s weapon=%d qty=%d"):format(
      atkName, delay, tgtName, wpnDbid, qty))
  end

  -- ============================================================
  -- fireAt（全局，红线#15）
  -- ============================================================
  function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side=_SIDE_RED,  name=attackerName})
    local tgt = ScenEdit_GetUnit({side=_SIDE_BLUE, name=targetName})
    if not (atk and atk.guid) then
      print(("[CMO] [ERROR] fireAt: 找不到攻击方 %s"):format(attackerName)); return false end
    if not (tgt and tgt.guid) then
      print(("[CMO] [ERROR] fireAt: 找不到目标 %s"):format(targetName)); return false end

    -- 强制 autodetectable（红线#8：三重保险）
    pcall(ScenEdit_SetUnit, {guid=tgt.guid, autodetectable=true})

    local function sameGuid(a, b)
      if not (a and b) then return false end
      return string.lower(tostring(a)) == string.lower(tostring(b))
    end
    local function collectContacts(sn)
      local ok, r = pcall(ScenEdit_GetContacts, {side=sn})
      return (ok and r) and r or {}
    end
    local function findContact()
      local cs = collectContacts(_SIDE_RED)
      for _, c in ipairs(cs) do
        for _, f in ipairs({"actualunitid","actualUnitID","actualunitguid","actualUnitGuid","actualguid","actualGuid"}) do
          if sameGuid(c[f], tgt.guid) then return c.guid or c.Guid end
        end
      end
      for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        local nm = c.name or c.Name or c.contact_name or ""
        if cg and nm and (nm == targetName or nm:find(targetName, 1, true)) then return cg end
      end
      return nil
    end

    local contactGuid = findContact()
    _errnum_ = 0
    local r
    if contactGuid then
      r = ScenEdit_AttackContact(atk.guid, contactGuid, {mode="1", weapon=wpnDbid, qty=qty})
    else
      r = ScenEdit_AttackContact(atk.guid, tgt.guid, {mode="1", weapon=wpnDbid, qty=qty})
    end
    if not r then
      r = ScenEdit_AttackContact(atk.guid, tgt.guid, {mode="1", weapon=wpnDbid, qty=qty})
    end
    print(("[CMO] [FIRE] %s → %s weapon=%d qty=%d result=%s"):format(
      attackerName, targetName, wpnDbid, qty, tostring(r ~= nil)))
    return r ~= nil
  end

  -- ============================================================
  -- TOT 调度配置
  -- ============================================================
  -- 水面：055/052D×2 各 8×YJ-18 → CVN-70（ripple 5s）
  local WATER_TOT = {
    {atk="红方055南昌舰",   tgt="蓝方CVN-70卡尔文森", wpn=_WPN_YJ18,  qty=8, delay=135},
    {atk="红方052D-1昆明舰", tgt="蓝方CVN-70卡尔文森", wpn=_WPN_YJ18,  qty=8, delay=140},
    {atk="红方052D-2南京舰", tgt="蓝方CVN-70卡尔文森", wpn=_WPN_YJ18,  qty=8, delay=145},
  }
  -- 航空：J-15×2 各 4×YJ-83K → CG-59/DDG-113（ripple 5s）
  local AIR_TOT = {
    {atk="J-15-1", tgt="蓝方CG-59普林斯顿",   wpn=_WPN_YJ83K, qty=4, delay=155},
    {atk="J-15-2", tgt="蓝方DDG-113约翰芬恩", wpn=_WPN_YJ83K, qty=4, delay=160},
  }

  -- ============================================================
  -- 执行水面通道 TOT（delay 已含 +_CONTACT_SETTLE）
  -- ============================================================
  print("\n[attack] 水面通道 TOT（YJ-18 → CVN-70）")
  for i, t in ipairs(WATER_TOT) do
    scheduleOne(t.atk, t.tgt, t.wpn, t.qty, t.delay + _CONTACT_SETTLE, "WATER_" .. i)
  end

  -- ============================================================
  -- 执行航空通道 TOT
  -- ============================================================
  print("\n[attack] 航空通道 TOT（J-15 YJ-83K）")
  for i, t in ipairs(AIR_TOT) do
    scheduleOne(t.atk, t.tgt, t.wpn, t.qty, t.delay + _CONTACT_SETTLE, "AIR_" .. i)
  end

  -- ============================================================
  -- J-15 RTB 调度（红线#19：base + homebase 双重）
  -- ============================================================
  print("\n[attack] J-15 RTB 调度")

  local RTB_DELAY   = 175 + 60  -- 攻击完+60s缓冲
  local RTB_TS     = tostring(ScenEdit_CurrentTime())
  local RTB_TR_NAME = "Tr_RTB_" .. RTB_TS
  local RTB_AC_NAME = "Ac_RTB_" .. RTB_TS
  local RTB_EV_NAME = "Ev_RTB_" .. RTB_TS
  local RTB_FIRE    = totTicks(ScenEdit_CurrentTime() + RTB_DELAY)

  local RTB_SCRIPT = table.concat({
    -- J-15-1 RTB（三重保险：course + homebase + base）
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,course={{latitude=30.60,longitude=122.30}},altitude=8000,throttle='Cruise',speed=300})\n"):format(_SIDE_RED,"J-15-1"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,homebase=%q})\n"):format(_SIDE_RED,"J-15-1","红方辽宁舰"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,base=%q})\n"):format(_SIDE_RED,"J-15-1","红方辽宁舰"),
    -- J-15-2 RTB（三重保险）
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,course={{latitude=30.60,longitude=122.30}},altitude=8000,throttle='Cruise',speed=300})\n"):format(_SIDE_RED,"J-15-2"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,homebase=%q})\n"):format(_SIDE_RED,"J-15-2","红方辽宁舰"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,base=%q})\n"):format(_SIDE_RED,"J-15-2","红方辽宁舰"),
    -- 自清理
    ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(RTB_EV_NAME),
    ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(RTB_AC_NAME),
    ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(RTB_TR_NAME),
  })

  pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=RTB_TR_NAME, Time=RTB_FIRE})
  pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=RTB_AC_NAME, ScriptText=RTB_SCRIPT})
  pcall(ScenEdit_SetEvent,   RTB_EV_NAME, {mode="add", IsActive=true, IsRepeatable=false})
  pcall(ScenEdit_SetEventTrigger, RTB_EV_NAME, {mode="add", name=RTB_TR_NAME})
  pcall(ScenEdit_SetEventAction,  RTB_EV_NAME, {mode="add", name=RTB_AC_NAME})
  print(("[attack] ✓ J-15 RTB 已调度: T+%ds (homebase+base=红方辽宁舰)"):format(RTB_DELAY))

  -- ============================================================
  -- 时间线总结
  -- ============================================================
  print("\n========================================")
  print("[attack] TOT 时间线（contact_settle=" .. _CONTACT_SETTLE .. "s）")
  print("  T+150s  红方055南昌舰   8×YJ-18 → 蓝方CVN-70卡尔文森")
  print("  T+155s  红方052D-1昆明舰 8×YJ-18 → 蓝方CVN-70卡尔文森")
  print("  T+160s  红方052D-2南京舰 8×YJ-18 → 蓝方CVN-70卡尔文森")
  print("  T+170s  J-15-1          4×YJ-83K → 蓝方CG-59普林斯顿")
  print("  T+175s  J-15-2          4×YJ-83K → 蓝方DDG-113约翰芬恩")
  print("  T+~235s J-15×2 RTB（homebase+base=红方辽宁舰）")
  print("  T+~290s 航空 YJ-83K 命中 CG-59/DDG-113")
  print("  T+~350s 水面 YJ-18 命中 CVN-70")
  print("========================================")
  print("[attack] 完成。")
end

print("\n========================================")
print("[all] 全部完成（main→clear→reload→attack）")
print("DBID来源：用户JSON优先，MCP验证：")
print("  055 DBID=3883 | 052D-1 DBID=2296 | 052D-2 DBID=3587")
print("  辽宁舰 DBID=2007 | J-15 DBID=2496 | YJ-18 DBID=2868")
print("  CVN-70 DBID=3551 | CG-59 DBID=2862 | DDG-113 DBID=4299")
print("  YJ-83K DBID=2137 | contact_settle_delay=15s")
print("========================================")
