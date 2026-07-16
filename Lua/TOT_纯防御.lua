-- ==========================================================================
-- all.lua  红蓝 7V4 辽宁舰协同反舰（四合一：main -> clear -> reload -> attack）
-- 执行顺序: 建阵营/单位 -> 清弹 -> 装弹 -> 真延时 TOT 调度齐射
-- 一次性 dofile/粘贴执行即可；contact_settle_delay=15s，推进仿真时间后逐枚发射
-- 数据来源: json/red_blue_5v3_liaoning1.json（052D DBID 用户指定 2296/3586）
-- 修复: 增加 tgt 非空检查，事件名称净化，所有 API 调用均 pcalled
-- ==========================================================================

--[[ ========== 全局配置 ========== ]]
_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"
_CONTACT_SETTLE = 15   -- 接触稳定延时（秒）
_INTERVAL       = 1    -- 每枚间隔（秒）
_YJ18  = 2868
_YJ83K = 2137

-- ==========================================================================
-- 第一段: main.lua  建阵营 + 建单位
-- ==========================================================================
local function getUnit(side, name)
  local ok, u = pcall(function() return ScenEdit_GetUnit({side=side, name=name}) end)
  if ok and u and u.guid then return u end
  return nil
end

local function ensureUnit(spec)
  local exist = getUnit(spec.side, spec.name)
  if exist then
    print(("[main] 已存在: %s"):format(spec.name))
    return exist
  end
  pcall(function() ScenEdit_AddUnit(spec) end)
  local u = getUnit(spec.side, spec.name)
  print(("[main] 创建 %s ok=%s"):format(spec.name, tostring(u ~= nil)))
  return u
end

-- 阵营
pcall(function() ScenEdit_AddSide({name=_SIDE_RED,  color="255,0,0"}) end)
pcall(function() ScenEdit_AddSide({name=_SIDE_BLUE, color="0,0,255"}) end)
pcall(function() VP_GetSide({Side=_SIDE_RED}) end)
pcall(function() VP_GetSide({Side=_SIDE_BLUE}) end)

-- 红方全知
pcall(function() ScenEdit_SetSideOptions({side=_SIDE_RED, awareness="OMNI"}) end)

-- 敌对关系
pcall(function() ScenEdit_SetSidePosture(_SIDE_RED,  _SIDE_BLUE, "H") end)
pcall(function() ScenEdit_SetSidePosture(_SIDE_BLUE, _SIDE_RED,  "H") end)

-- WCS = Free
pcall(function() ScenEdit_SetDoctrine({side=_SIDE_RED}, {
  weapon_control_status_air="0", weapon_control_status_surface="0",
  weapon_control_status_subsurface="0", weapon_control_status_land="0"}) end)
pcall(function() ScenEdit_SetDoctrine({side=_SIDE_BLUE}, {
  weapon_control_status_air="0", weapon_control_status_surface="0",
  weapon_control_status_subsurface="0", weapon_control_status_land="0"}) end)
print("[main] 阵营/敌对/WCS 设置完毕")

-- 红方水面舰
ensureUnit({type="Ship", side=_SIDE_RED, name="Red-055-1",  dbid=3883,
  latitude=24.8324, longitude=128.5830, heading=135, speed=20, proficiency="Veteran"})
ensureUnit({type="Ship", side=_SIDE_RED, name="Red-055-2",  dbid=3883,
  latitude=26.0,    longitude=130.0,    heading=135, speed=20, proficiency="Veteran"})
ensureUnit({type="Ship", side=_SIDE_RED, name="Red-052D-1", dbid=2296,
  latitude=21.1437, longitude=123.4510, heading=115, speed=20, proficiency="Veteran"})
ensureUnit({type="Ship", side=_SIDE_RED, name="Red-052D-2", dbid=3586,
  latitude=18.2035, longitude=123.9880, heading=50,  speed=20, proficiency="Veteran"})

-- 辽宁舰
local CARRIER_NAME = "红方辽宁舰"
ensureUnit({type="Ship", side=_SIDE_RED, name=CARRIER_NAME, dbid=2007,
  latitude=25.0, longitude=130.0, heading=90, speed=20, proficiency="Veteran"})

-- J-15 舰载机
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

-- 蓝方目标（自动可探测 + 雷达/声呐开机）
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

-- ==========================================================================
-- 第二段: clear.lua  清弹（只清舰艇，J-15 跳过）
-- ==========================================================================
local CLEAR_LIST = {"Red-055-1", "Red-055-2", "Red-052D-1", "Red-052D-2"}

local function clearUnitWeapons(name)
  local u = nil
  pcall(function() u = ScenEdit_GetUnit({side=_SIDE_RED, name=name}) end)
  if not (u and u.guid) then
    print("[clear] [WARN] 找不到: " .. name); return false
  end

  local jobs = {}
  for _, m in ipairs(u.mounts or {}) do
    for _, w in ipairs(m.mount_weapons or {}) do
      local cur = tonumber(w.wpn_current) or 0
      if cur > 0 then
        jobs[#jobs + 1] = {dbid=w.wpn_dbid, num=cur, mountid=m.mount_guid}
      end
    end
  end

  local done, fail = 0, 0
  for _,
      ScenEdit_AddReloadsToUnit({
        guid=u.guid, wpn_dbid=j.dbid, mount_guid=j.mountid,
        number=j.num, remove=true})
    end)
    if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
  end
  print(("[clear] %s: 减载归零 %d 项 (失败 %d)"):format(name, done, fail))
  return fail == 0
end

for _, name in ipairs(CLEAR_LIST) do clearUnitWeapons(name) end
print("[clear] ===== 清弹完毕（J-15 跳过）=====")

-- ==========================================================================
-- 第三段: reload.lua  装弹（舰艇 YJ-18，J-15 跳过）
-- ==========================================================================
local RELOAD_LIST = {
  {name="Red-055-1",  qty=8},
  {name="Red-055-2",  qty=8},
  {name="Red-052D-1", qty=16},
  {name="Red-052D-2", qty=10},
}

for _, e in ipairs(RELOAD_LIST) do
  local u = nil
  pcall(function() u = ScenEdit_GetUnit({side=_SIDE_RED, name=e.name}) end)
  if u and u.guid then
    _errnum_ = 0
    pcall(function()
      ScenEdit_AddReloadsToUnit({
        side=_SIDE_RED, unitname=e.name, wpn_dbid=_YJ18, number=e.qty})
    end)
    print(("[reload] %s 装弹 %dx YJ-18 (errnum=%s)"):format(e.name, e.qty, tostring(_errnum_ or 0)))
  else
    print("[reload] [WARN] 找不到: " .. e.name)
  end
end

-- 自检
for _, e in ipairs(RELOAD_LIST) do
  local u = nil
  pcall(function() u = ScenEdit_GetUnit({side=_SIDE_RED, name=e.name}) end)
  if u then
    local total = 0
    for _, m in ipairs(u.mounts or {}) do
      for _, w in ipairs(m.mount_weapons or {}) do
        if tonumber(w.wpn_dbid) == _YJ18 then total = total + (tonumber(w.wpn_current) or 0) end
      end
    end
    print(("[reload] 自检 %s YJ-18 待发=%d"):format(e.name, total))
  end
end

print("[reload] ===== 装弹完毕，合计 42x YJ-18（J-15 跳过）=====")

-- ==========================================================================
-- 第四段: attack.lua  真延时打击（事件驱动，逐枚调度）
-- ==========================================================================
-- 全局 fireAt（供事件脚本调用）
function fireAt(atkName, tgtName, wpnDbid, qty)
  -- 获取攻击方
  local atk = nil
  pcall(function() atk = ScenEdit_GetUnit({side=_SIDE_RED, name=atkName}) end)
  if not (atk and atk.guid) then
    print("[fireAt] 攻击方不存在: " .. atkName)
    return false
  end

  -- 获取目标，若不存在则直接返回
  local tgt = nil
  pcall(function() tgt = ScenEdit_GetUnit({side=_SIDE_BLUE, name=tgtName}) end)
  if not tgt then
    print("[fireAt] 目标不存在: " .. tgtName)
    return false
  end

  -- 确保目标可探测（辅助 contact 生成）
  pcall(function() ScenEdit_SetUnit({guid=tgt.guid, autodetectable=true}) end)
  pcall(function() ScenEdit_SetSideOptions({side=_SIDE_RED, awareness="OMNI"}) end)

  -- 查找 contact
  local contactGuid = nil
  local ok, s = pcall(function() return VP_GetSide({Side=_SIDE_RED}) end)
  if ok and s and type(s.contacts) == "table" then
    local tg = tostring(tgt.guid):lower()
    for _, c in ipairs(s.contacts) do
      local aid = c.actualunitid or c.actualUnitID or c.actualunitguid
      if aid and tostring(aid):lower() == tg then
        contactGuid = c.guid
        break
      end
    end
    if not contactGuid then
      for _, c in ipairs(s.contacts) do
        local nm = tostring(c.name or "")
        if nm ~= "" and (nm == tgtName or nm:find(tgtName, 1, true)) then
          contactGuid = c.guid
          break
        end
      end
    end
  end

  if not contactGuid then
    print(("[fireAt] 无 contact 目标 %s，请增大 contact_settle_delay 或推进时间"):format(tgtName))
    return false
  end

  -- 执行攻击
  _errnum_ = 0
  local result = false
  pcall(function()
    result = ScenEdit_AttackContact(atk.guid, contactGuid, {mode="1", weapon=wpnDbid, qty=qty})
  end)
  print(("[fireAt] %s -> %s x%d wpn=%d ok=%s"):format(atkName, tgtName, qty, wpnDbid, tostring(result)))
  return result
end

-- 时间转换
local function totTicks(addSec)
  return string.format("%.0f", (ScenEdit_CurrentTime() + 62135596801 + addSec) * 1e7)
end

-- 调度单枚发射（创建一次性时间事件）
function scheduleOne(atkName, tgtName, wpnDbid, delayBase, k)
  local delay    = _CONTACT_SETTLE + delayBase + (k - 1) * _INTERVAL
  local ts       = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
  -- 净化事件名称：仅保留字母数字下划线
  local function sanitize(s)
    return s:gsub("[^%w_]", "_")
  end
  local tag      = sanitize(atkName) .. "_" .. sanitize(tgtName) .. "_" .. k .. "_" .. ts
  local evName   = "E_" .. tag
  local trName   = "T_" .. tag
  local acName   = "A_" .. tag
  local fireTime = totTicks(delay)

  local script =
    ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpnDbid) ..
    ("pcall(function() ScenEdit_SetEvent(%q,{mode='remove'}) end)\n"):format(evName) ..
    ("pcall(function() ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q}) end)\n"):format(acName) ..
    ("pcall(function() ScenEdit_SetTrigger({mode='remove',type='Time',name=%q}) end)\n"):format(trName)

  -- 所有 API 调用均用 pcall 保护
  pcall(function() ScenEdit_SetTrigger({mode="add", type="Time", name=trName, Time=fireTime}) end)
  pcall(function() ScenEdit_SetAction({mode="add", type="LuaScript", name=acName, ScriptText=script}) end)
  pcall(function() ScenEdit_SetEvent(evName, {mode="add", IsActive=true, IsRepeatable=false}) end)
  pcall(function() ScenEdit_SetEventTrigger(evName, {mode="add", name=trName}) end)
  pcall(function() ScenEdit_SetEventAction(evName, {mode="add", name=acName}) end)

  -- 简单记录，即使创建失败也不中断脚本
  print(("[attack] 调度 %s 第%d枚 @T+%.1fs -> %s"):format(atkName, k, delay, tgtName))
  return true
end

-- 打击方案
local STRIKE = {
  {"Red-055-1",   "DDG 113-1",      _YJ18,  7},
  {"Red-055-2",   "DDG 113-2",      _YJ18,  6},
  {"Red-052D-1",  "Blue-DBID-3551", _YJ18,  8},
  {"Red-052D-2",  "Blue-DBID-2862", _YJ18,  5},
  {"J-15-RED-01", "Blue-DBID-3551", _YJ83K, 4},
  {"J-15-RED-02", "Blue-DBID-2862", _YJ83K, 4},
}

for _, s in ipairs(STRIKE) do
  local atkName, tgtName, wpn, qty = s[1], s[2], s[3], s[4]
  for k = 1, qty do
    scheduleOne(atkName, tgtName, wpn, 0, k)
  end
  print(("[attack] %s -> %s: %dx wpn=%d 调度完毕（T+%ds 起）"):format(atkName, tgtName, qty, wpn, _CONTACT_SETTLE))
end

print("[attack] ===== 真延时打击调度完毕 =====")
print("[attack] 汇总: 055-1(7)+055-2(6)+052D-1(8)+052D-2(5)+J15-01(4)+J15-02(4) = 34 枚")
print("[attack] contact_settle_delay=" .. _CONTACT_SETTLE .. "s | 推进仿真时间后逐枚发射")