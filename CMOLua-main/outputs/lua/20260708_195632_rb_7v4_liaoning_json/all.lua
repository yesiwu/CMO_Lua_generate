-- ==========================================================================
-- all.lua  红蓝 7V4 辽宁舰协同反舰（四合一：main -> clear -> reload -> attack）
-- 执行顺序: 建阵营/单位 -> 清弹 -> 装弹 -> 真延时 TOT 调度齐射
-- 一次性 dofile/粘贴执行即可；contact_settle_delay=15s，推进仿真时间后逐枚发射
-- 数据来源: json/red_blue_5v3_liaoning1.json（052D DBID 用户指定 2296/3586）
-- ==========================================================================

--[[ ========== 第一段: main.lua ========== ]]
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
  _errmsg_ = nil
  pcall(function() ScenEdit_AddUnit(spec) end)
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

--[[ ========== 第二段: clear.lua ========== ]]
-- ==========================================================================
-- clear.lua  清弹（只清舰艇 YJ-18；J-15 用 opts={mode="0"} 不清弹）
-- 红线 #21: 清弹只能用 AddReloadsToUnit + remove=true 遍历 mounts 逐条归零；
--          严禁用 DumpAmmo / remove_weapon 清弹（会删格子导致装不回弹）。
-- 红线 #20: 所有 ScenEdit_* 用 pcall(function() ... end) 包裹
-- ==========================================================================

local SIDE_RED   = "红方"
local CLEAR_LIST = {"Red-055-1", "Red-055-2", "Red-052D-1", "Red-052D-2"}

local function clearUnitWeapons(name)
  local u = nil
  pcall(function() u = ScenEdit_GetUnit({side=SIDE_RED, name=name}) end)
  if not (u and u.guid) then
    print("[clear] [WARN] 找不到: " .. name); return false
  end

  -- 1) 快照所有 mount 中 cur>0 的武器（边减边遍历原表不安全）
  local jobs = {}
  for _, m in ipairs(u.mounts or {}) do
    for _, w in ipairs(m.mount_weapons or {}) do
      local cur = tonumber(w.wpn_current) or 0
      if cur > 0 then
        jobs[#jobs + 1] = {dbid=w.wpn_dbid, num=cur, mountid=m.mount_guid}
      end
    end
  end

  -- 2) 逐条把数量减到 0（remove=true 仅扣减、保留格子）
  local done, fail = 0, 0
  for _, j in ipairs(jobs) do
    _errnum_ = 0
    pcall(function() ScenEdit_AddReloadsToUnit({
      guid=u.guid, wpn_dbid=j.dbid, mount_guid=j.mountid,
      number=j.num, remove=true}) end)
    if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
  end
  print(("[clear] %s: 减载归零 %d 项 (失败 %d)"):format(name, done, fail))
  return fail == 0
end

for _, name in ipairs(CLEAR_LIST) do clearUnitWeapons(name) end
print("[clear] ===== 清弹完毕（J-15 跳过）=====")

--[[ ========== 第三段: reload.lua ========== ]]
-- ==========================================================================
-- reload.lua  装弹（只装方案指定弹药 YJ-18；J-15 用 opts={mode="0"} 不装弹）
-- 装弹量（JSON loaded）:
--   Red-055-1  YJ-18 x8   Red-055-2  YJ-18 x8   （055 编队 loaded=16 平分）
--   Red-052D-1 YJ-18 x16  Red-052D-2 YJ-18 x10
-- 合计 YJ-18 = 8+8+16+10 = 42（与 missileSummary.YJ-18.loaded=42 吻合）
-- 红线 #21: 舰艇补弹统一用 ScenEdit_AddReloadsToUnit（不用 SetAircraftLoadout）
-- 红线 #20: 所有 ScenEdit_* 用 pcall(function() ... end) 包裹
-- ==========================================================================

local SIDE_RED  = "红方"
local YJ18_DBID = 2868
local RELOAD_LIST = {
  {name="Red-055-1",  qty=8},
  {name="Red-055-2",  qty=8},
  {name="Red-052D-1", qty=16},
  {name="Red-052D-2", qty=10},
}

for _, e in ipairs(RELOAD_LIST) do
  local u = nil
  pcall(function() u = ScenEdit_GetUnit({side=SIDE_RED, name=e.name}) end)
  if u and u.guid then
    _errnum_ = 0
    pcall(function() ScenEdit_AddReloadsToUnit({
      side=SIDE_RED, unitname=e.name, wpn_dbid=YJ18_DBID, number=e.qty}) end)
    print(("[reload] %s 装弹 %dx YJ-18 (errnum=%s)"):format(e.name, e.qty, tostring(_errnum_ or 0)))
  else
    print("[reload] [WARN] 找不到: " .. e.name)
  end
end

-- 装弹后自检（dumpAmmo 仅用于读数验证，不是清弹）
for _, e in ipairs(RELOAD_LIST) do
  local u = nil
  pcall(function() u = ScenEdit_GetUnit({side=SIDE_RED, name=e.name}) end)
  if u then
    local total = 0
    for _, m in ipairs(u.mounts or {}) do
      for _, w in ipairs(m.mount_weapons or {}) do
        if tonumber(w.wpn_dbid) == YJ18_DBID then total = total + (tonumber(w.wpn_current) or 0) end
      end
    end
    print(("[reload] 自检 %s YJ-18 待发=%d"):format(e.name, total))
  end
end

print("[reload] ===== 装弹完毕，合计 42x YJ-18（J-15 跳过）=====")

--[[ ========== 第四段: attack.lua ========== ]]
-- ==========================================================================
-- attack.lua  真延时打击（TOT 事件驱动，qty=1 逐枚调度）
-- 红线 #9: Time Trigger + LuaScript Action，qty=N 拆成 N 个 qty=1
-- 红线 #13: ScenEdit_AttackContact mode 必须字符串 "1"
-- 红线 #15: fireAt/scheduleOne + 配置变量必须全局
-- contact_settle_delay = 15 秒（红线：TOT 必须 >=15）
-- 打击方案（JSON strikePlan，fired 数）:
--   Red-055-1  -> DDG 113-1      7x YJ-18
--   Red-055-2  -> DDG 113-2      6x YJ-18
--   Red-052D-1 -> Blue-DBID-3551 8x YJ-18  (CVN-70)
--   Red-052D-2 -> Blue-DBID-2862 5x YJ-18  (CG-59)
--   J-15-RED-01-> Blue-DBID-3551 4x YJ-83K (2137)
--   J-15-RED-02-> Blue-DBID-2862 4x YJ-83K (2137)
-- 合计 34 枚
-- ==========================================================================

_SIDE_RED  = _SIDE_RED  or "红方"
_SIDE_BLUE = _SIDE_BLUE or "蓝方"
_CONTACT_SETTLE = 15   -- 全局（红线 #15）
_INTERVAL       = 1

-- 全局 fireAt（红线 #15：不加 local，事件脚本可调用）
function fireAt(atkName, tgtName, wpnDbid, qty)
  local tgt = nil
  pcall(function() tgt = ScenEdit_GetUnit({side=_SIDE_BLUE, name=tgtName}) end)
  if tgt and tgt.guid then
    pcall(function() ScenEdit_SetUnit({guid=tgt.guid, autodetectable=true}) end)
  end
  pcall(function() ScenEdit_SetSideOptions({side=_SIDE_RED, awareness="OMNI"}) end)

  -- 找 contact：先按 actualunitid，再按名称
  local contactGuid = nil
  local ok, s = pcall(function() return VP_GetSide({Side=_SIDE_RED}) end)
  if ok and s and type(s.contacts) == "table" then
    local tg = tgt and tostring(tgt.guid):lower() or ""
    for _, c in ipairs(s.contacts) do
      local aid = c.actualunitid or c.actualUnitID or c.actualunitguid
      if aid and tostring(aid):lower() == tg then contactGuid = c.guid; break end
    end
    if not contactGuid then
      for _, c in ipairs(s.contacts) do
        local nm = tostring(c.name or "")
        if nm ~= "" and (nm == tgtName or nm:find(tgtName, 1, true)) then contactGuid = c.guid; break end
      end
    end
  end
  if not contactGuid then
    print("[fireAt] 无 contact: " .. tgtName .. "，请加大 contact_settle_delay 或多推进游戏时间")
    return false
  end

  local atk = nil
  pcall(function() atk = ScenEdit_GetUnit({side=_SIDE_RED, name=atkName}) end)
  if not (atk and atk.guid) then print("[fireAt] 攻击方找不到: " .. atkName); return false end

  _errnum_ = 0
  local result = false
  pcall(function()
    result = ScenEdit_AttackContact(atk.guid, contactGuid, {mode="1", weapon=wpnDbid, qty=qty})
  end)
  print(("[fireAt] %s -> %s x%d wpn=%d ok=%s"):format(atkName, tgtName, qty, wpnDbid, tostring(result)))
  return result
end

-- totTicks: 仿真时间 -> CMO 内部 tick
local function totTicks(addSec)
  return string.format("%.0f", (ScenEdit_CurrentTime() + 62135596801 + addSec) * 1e7)
end

-- scheduleOne: 注册单枚 TOT 时间触发器（delay 已叠加 contact_settle_delay）
function scheduleOne(atkName, tgtName, wpnDbid, delayBase, k)
  local delay    = _CONTACT_SETTLE + delayBase + (k - 1) * _INTERVAL
  local ts       = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
  local tag      = atkName .. "_" .. tgtName .. "_" .. k .. "_" .. ts
  local evName   = "E_" .. tag
  local trName   = "T_" .. tag
  local acName   = "A_" .. tag
  local fireTime = totTicks(delay)

  local script =
    ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpnDbid) ..
    ("pcall(function() ScenEdit_SetEvent(%q,{mode='remove'}) end)\n"):format(evName) ..
    ("pcall(function() ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q}) end)\n"):format(acName) ..
    ("pcall(function() ScenEdit_SetTrigger({mode='remove',type='Time',name=%q}) end)\n"):format(trName)

  pcall(function() ScenEdit_SetTrigger({mode="add", type="Time", name=trName, Time=fireTime}) end)
  pcall(function() ScenEdit_SetAction({mode="add", type="LuaScript", name=acName, ScriptText=script}) end)
  pcall(function() ScenEdit_SetEvent(evName, {mode="add", IsActive=true, IsRepeatable=false}) end)
  pcall(function() ScenEdit_SetEventTrigger(evName, {mode="add", name=trName}) end)
  pcall(function() ScenEdit_SetEventAction(evName, {mode="add", name=acName}) end)
end

local YJ18, YJ83K = 2868, 2137

-- STRIKE: {攻击方, 目标, 弹dbid, 数量}
local STRIKE = {
  {"Red-055-1",   "DDG 113-1",      YJ18,  7},
  {"Red-055-2",   "DDG 113-2",      YJ18,  6},
  {"Red-052D-1",  "Blue-DBID-3551", YJ18,  8},
  {"Red-052D-2",  "Blue-DBID-2862", YJ18,  5},
  {"J-15-RED-01", "Blue-DBID-3551", YJ83K, 4},
  {"J-15-RED-02", "Blue-DBID-2862", YJ83K, 4},
}

for _, s in ipairs(STRIKE) do
  local atkName, tgtName, wpn, qty = s[1], s[2], s[3], s[4]
  for k = 1, qty do scheduleOne(atkName, tgtName, wpn, 0, k) end
  print(("[attack] %s -> %s: %dx wpn=%d 调度完毕（T+%ds 起）"):format(atkName, tgtName, qty, wpn, _CONTACT_SETTLE))
end

print("[attack] ===== 真延时打击调度完毕 =====")
print("[attack] 汇总: 055-1(7)+055-2(6)+052D-1(8)+052D-2(5)+J15-01(4)+J15-02(4) = 34 枚")
print("[attack] contact_settle_delay=" .. _CONTACT_SETTLE .. "s | 推进仿真时间后逐枚发射")

