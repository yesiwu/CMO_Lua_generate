-- ==========================================================================
-- all.lua  红蓝 7V4 辽宁舰协同反舰（四合一执行脚本）
-- 执行顺序: main → clear → reload → attack
-- 红线 #20: 所有 ScenEdit_* 调用用 pcall(function() ... end) 包裹
-- MCP 验证: J-15(2496)+loadout(9682) ✓  YJ-18(2868) ✓  YJ-83K(2137) ✓
-- 打击计划: 055-1(7)+055-2(6)+052D-1(8)+052D-2(5)+J15-01(4)+J15-02(4) = 34 枚
-- ==========================================================================

local SIDE_RED  = "红方"
local SIDE_BLUE = "蓝方"

-- ============================================================
-- § 辅助函数（全局，供事件脚本调用）
-- ============================================================

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
  local ok = pcall(function() return ScenEdit_AddUnit(spec) end)
  print(("[main] 创建 %s ok=%s err=%s"):format(spec.name, tostring(ok), tostring(_errmsg_)))
  return getUnit(spec.side, spec.name)
end

-- ============================================================
-- § 一：main — 创建红蓝双方作战单位
-- ============================================================

-- 阵营
pcall(function() ScenEdit_AddSide({name=SIDE_RED,  color="255,0,0"}) end)
pcall(function() ScenEdit_AddSide({name=SIDE_BLUE, color="0,0,255"}) end)

-- 红方全知全能（红线 #6）
pcall(function() ScenEdit_SetSideOptions({side=SIDE_RED, awareness="OMNI"}) end)

-- 敌对关系
pcall(function() ScenEdit_SetSidePosture(SIDE_RED,  SIDE_BLUE, "H") end)
pcall(function() ScenEdit_SetSidePosture(SIDE_BLUE, SIDE_RED,  "H") end)

-- 双方 WCS = Free(0)（红线 #12）
pcall(function() ScenEdit_SetDoctrine({side=SIDE_RED}, {
  weapon_control_status_air="0", weapon_control_status_surface="0",
  weapon_control_status_subsurface="0", weapon_control_status_land="0"
}) end)
pcall(function() ScenEdit_SetDoctrine({side=SIDE_BLUE}, {
  weapon_control_status_air="0", weapon_control_status_surface="0",
  weapon_control_status_subsurface="0", weapon_control_status_land="0"
}) end)

-- 红方水面舰艇（DBID 来自用户方案，优先于 MCP）
ensureUnit({type="Ship", side=SIDE_RED, name="Red-055-1",  dbid=3883,
  latitude=24.8324, longitude=128.5830, heading=135, speed=20, proficiency="Veteran"})
ensureUnit({type="Ship", side=SIDE_RED, name="Red-055-2",  dbid=3883,
  latitude=26.0,    longitude=130.0,    heading=135, speed=20, proficiency="Veteran"})
ensureUnit({type="Ship", side=SIDE_RED, name="Red-052D-1", dbid=2296,
  latitude=21.1437, longitude=123.4510, heading=115, speed=20, proficiency="Veteran"})
ensureUnit({type="Ship", side=SIDE_RED, name="Red-052D-2", dbid=3586,
  latitude=18.2035, longitude=123.9880, heading=50,  speed=20, proficiency="Veteran"})

-- 红方辽宁舰（母舰，不装反舰弹）
local CARRIER_NAME = "红方辽宁舰"
ensureUnit({type="Ship", side=SIDE_RED, name=CARRIER_NAME, dbid=2007,
  latitude=25.0, longitude=130.0, heading=90, speed=20, proficiency="Veteran"})

-- 红方 J-15 舰载机（loadoutId=9682 YJ-83K，opts={mode="0"} 不触发清弹/装弹）
local J15_DBID   = 2496
local LOADOUT_ID = 9682   -- MCP 已验证

local function ensureJ15(nm)
  if getUnit(SIDE_RED, nm) then
    print(("[main] J-15 %s 已存在"):format(nm)); return
  end
  local ok = pcall(function() return ScenEdit_AddUnit({
    type="Aircraft", side=SIDE_RED, name=nm,
    dbid=J15_DBID, loadoutid=LOADOUT_ID,
    base=CARRIER_NAME, proficiency="Veteran",
    opts={mode="0"},
  }) end)
  print(("[main] J-15 %s 创建 ok=%s err=%s"):format(nm, tostring(ok), tostring(_errmsg_)))
end
ensureJ15("J-15-RED-01")
ensureJ15("J-15-RED-02")

-- 蓝方水面目标（autodetectable=true + 传感器开启）
local BLUE_UNITS = {
  {name="DDG 113-1",      dbid=4299, lat=21.5419, lon=129.9125, hdg=294.05},
  {name="DDG 113-2",      dbid=4299, lat=22.0,    lon=131.0,    hdg=294.05},
  {name="Blue-DBID-2862", dbid=2862, lat=21.61,   lon=130.1791, hdg=294.58},
  {name="Blue-DBID-3551", dbid=3551, lat=21.42,   lon=130.1713, hdg=293.16},
}
for _, b in ipairs(BLUE_UNITS) do
  local u = ensureUnit({type="Ship", side=SIDE_BLUE, name=b.name, dbid=b.dbid,
    latitude=b.lat, longitude=b.lon, heading=b.hdg, speed=0, proficiency="Veteran"})
  if u and u.guid then
    pcall(function() ScenEdit_SetUnit({guid=u.guid, autodetectable=true}) end)
    pcall(function() ScenEdit_SetEMCON("Unit", b.name, "Radar=Active;Sonar=Active") end)
  end
end

print("[main] ===== 所有单位创建完毕 =====")

-- ============================================================
-- § 二：clear — 清弹（只清 YJ-18，J-15 不清弹）
-- ============================================================

local YJ18_DBID = 2868   -- YJ-18 [3M54E Klub Copy]，MCP 已验证

local CLEAR_LIST = {"Red-055-1", "Red-055-2", "Red-052D-1", "Red-052D-2"}

for _, name in ipairs(CLEAR_LIST) do
  local u = getUnit(SIDE_RED, name)
  if u and u.guid then
    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
      for _, w in ipairs(m.mount_weapons or {}) do
        local cur = tonumber(w.wpn_current) or 0
        if cur > 0 then
          jobs[#jobs + 1] = {dbid=w.wpn_dbid, num=cur, mountid=m.mount_guid}
        end
      end
    end
    for _, j in ipairs(jobs) do
      _errnum_ = 0
      pcall(function() ScenEdit_AddReloadsToUnit({
        guid       = u.guid,
        wpn_dbid   = j.dbid,
        mount_guid = j.mountid,
        number     = j.num,
        remove     = true,
      }) end)
    end
    print("[clear] " .. name .. " 清弹 YJ-18 完毕")
  else
    print("[clear] [WARN] 找不到: " .. name)
  end
end

print("[clear] ===== 清弹完毕 =====")

-- ============================================================
-- § 三：reload — 装弹（装 JSON 指定弹量）
-- ============================================================

local RELOAD_LIST = {
  {name="Red-055-1",  qty=7},   -- 055 双舰合计 13 枚，7+6 分配
  {name="Red-055-2",  qty=6},
  {name="Red-052D-1", qty=8},   -- 打 Blue-DBID-3551 (CVN-70)
  {name="Red-052D-2", qty=5},   -- 打 Blue-DBID-2862 (CG-59)
}

for _, entry in ipairs(RELOAD_LIST) do
  local u = getUnit(SIDE_RED, entry.name)
  if u and u.guid then
    pcall(function() ScenEdit_AddReloadsToUnit({
      side     = SIDE_RED,
      unitname = entry.name,
      wpn_dbid = YJ18_DBID,
      number   = entry.qty,
    }) end)
    print("[reload] " .. entry.name .. " 装弹 " .. entry.qty .. "x YJ-18 完毕")
  else
    print("[reload] [WARN] 找不到: " .. entry.name)
  end
end

print("[reload] ===== 装弹完毕 =====")
print("[reload] 汇总: 055-1(7)+055-2(6)+052D-1(8)+052D-2(5) = 26x YJ-18")

-- ============================================================
-- § 四：attack — 真延时打击（TOT 事件驱动，qty=1 逐枚调度）
-- ============================================================

local CONTACT_SETTLE = 15   -- 秒（红线 #9 要求 >= 15）
local INTERVAL       = 1    -- 每枚间隔秒

-- totTicks: 仿真时间 → CMO 内部 tick
local function totTicks(addSec)
  return string.format("%.0f", (ScenEdit_CurrentTime() + 62135596801 + addSec) * 1e7)
end

-- ★ 全局 fireAt（红线 #15：不带 local，事件脚本可调用）
function fireAt(atkName, tgtName, wpnDbid, qty)
  -- 确保蓝方 autodetectable（红线 #8）
  local tgt = nil
  pcall(function() tgt = ScenEdit_GetUnit({side=SIDE_BLUE, name=tgtName}) end)
  if tgt and tgt.guid then
    pcall(function() ScenEdit_SetUnit({guid=tgt.guid, autodetectable=true}) end)
  end
  -- 确保红方 OMNI
  pcall(function() ScenEdit_SetSideOptions({side=SIDE_RED, awareness="OMNI"}) end)

  -- 查 contact（先按 actualunitid，再按名称）
  local contactGuid = nil
  local ok, s = pcall(function() return VP_GetSide({Side=SIDE_RED}) end)
  if ok and s and type(s.contacts) == "table" then
    local tgGuid = tgt and tostring(tgt.guid):lower() or ""
    for _, c in ipairs(s.contacts) do
      local aid = c.actualunitid or c.actualUnitID or c.actualunitguid
      if aid and tostring(aid):lower() == tgGuid then
        contactGuid = c.guid; break
      end
    end
    if not contactGuid then
      for _, c in ipairs(s.contacts) do
        local nm = tostring(c.name or "")
        if nm ~= "" and (nm == tgtName or nm:find(tgtName, 1, true)) then
          contactGuid = c.guid; break
        end
      end
    end
  end

  if not contactGuid then
    print("[fireAt] 无 contact: " .. tgtName .. "，请加大 contact_settle_delay")
    return false
  end

  local atk = nil
  pcall(function() atk = ScenEdit_GetUnit({side=SIDE_RED, name=atkName}) end)
  if not (atk and atk.guid) then
    print("[fireAt] 攻击方找不到: " .. atkName); return false
  end

  _errnum_ = 0
  local result = false
  pcall(function()
    result = ScenEdit_AttackContact(atk.guid, contactGuid,
      {mode="1", weapon=wpnDbid, qty=qty})   -- 红线 #13：mode 必须是字符串 "1"
  end)
  print(("[fireAt] %s → %s ×%d wpn=%d result=%s err=%s"):format(
    atkName, tgtName, qty, wpnDbid, tostring(result), tostring(_errmsg_)))
  return result
end

-- scheduleOne: 注册单枚 TOT 时间触发器
local function scheduleOne(atkName, tgtName, wpnDbid, delayBase, k)
  local delay    = CONTACT_SETTLE + delayBase + (k - 1) * INTERVAL
  local ts       = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
  local tag      = atkName .. "_" .. tgtName .. "_" .. k .. "_" .. ts
  local evName   = "E_" .. tag
  local trName   = "T_" .. tag
  local acName   = "A_" .. tag
  local fireTime = totTicks(delay)

  -- 事件脚本：发完即自毁
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

-- 打击调度（JSON strikePlan）
-- 1) Red-055-1 → DDG 113-1  7x YJ-18
for k = 1, 7 do scheduleOne("Red-055-1", "DDG 113-1", YJ18_DBID, 0, k) end
print("[attack] Red-055-1 → DDG 113-1: 7x YJ-18 (T+" .. CONTACT_SETTLE .. "s 起)")

-- 2) Red-055-2 → DDG 113-2  6x YJ-18
for k = 1, 6 do scheduleOne("Red-055-2", "DDG 113-2", YJ18_DBID, 0, k) end
print("[attack] Red-055-2 → DDG 113-2: 6x YJ-18")

-- 3) Red-052D-1 → Blue-DBID-3551 (CVN-70)  8x YJ-18
for k = 1, 8 do scheduleOne("Red-052D-1", "Blue-DBID-3551", YJ18_DBID, 0, k) end
print("[attack] Red-052D-1 → Blue-DBID-3551: 8x YJ-18")

-- 4) Red-052D-2 → Blue-DBID-2862 (CG-59)  5x YJ-18
for k = 1, 5 do scheduleOne("Red-052D-2", "Blue-DBID-2862", YJ18_DBID, 0, k) end
print("[attack] Red-052D-2 → Blue-DBID-2862: 5x YJ-18")

-- 5) J-15-RED-01 → Blue-DBID-3551 (CVN-70)  4x YJ-83K (dbid=2137)
local YJ83K_DBID = 2137   -- YJ-83K [C-802AK]，MCP 已验证
for k = 1, 4 do scheduleOne("J-15-RED-01", "Blue-DBID-3551", YJ83K_DBID, 0, k) end
print("[attack] J-15-RED-01 → Blue-DBID-3551: 4x YJ-83K")

-- 6) J-15-RED-02 → Blue-DBID-2862 (CG-59)  4x YJ-83K
for k = 1, 4 do scheduleOne("J-15-RED-02", "Blue-DBID-2862", YJ83K_DBID, 0, k) end
print("[attack] J-15-RED-02 → Blue-DBID-2862: 4x YJ-83K")

print("[attack] ===== 真延时打击调度完毕 =====")
print("[attack] 汇总: 055-1(7)+055-2(6)+052D-1(8)+052D-2(5)+J15-01(4)+J15-02(4) = 34 枚")
print("[attack] contact_settle_delay=" .. CONTACT_SETTLE .. "s | 仿真时间推进后自动发射")
print("")
print("===== all.lua 执行完毕（main → clear → reload → attack）=====")
