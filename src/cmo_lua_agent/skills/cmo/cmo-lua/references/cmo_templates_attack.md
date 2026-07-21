# CMO Lua 攻击与事件模板 v3.0

> 适用范围：基于已验证 manifest 生成 all-in-one 或四件套 Lua 脚本，包括 main、clear、reload、contact attack、真延时调度和诊断日志。本文件是模板库，不是场景事实来源。

## 模板使用规则

```text
所有 CMO API 调用使用 pcall(function() ... end)
被事件调用的函数必须是全局函数
STRIKE 使用命名键，不使用 s[1]/s[2] 位置数组
quantity=N 拆成 N 个事件，每个事件 fireAt(..., qty=1)
模板不得引入 manifest 中不存在的单位、目标、武器或任务
```

## 通用全局变量与日志

```lua
_SIDE_RED  = SIDES.red
_SIDE_BLUE = SIDES.blue
_CONTACT_SETTLE = _CONTACT_SETTLE or 15
_DEFAULT_INTERVAL = _DEFAULT_INTERVAL or 1

function logInfo(msg) print("[CMO] [INFO] " .. tostring(msg)) end
function logWarn(msg) print("[CMO] [WARN] " .. tostring(msg)) end
function logError(msg) print("[CMO] [ERROR] " .. tostring(msg)) end
```

## 安全查询函数

```lua
function getUnit(side, name)
  local ok, u = pcall(function()
    return ScenEdit_GetUnit({side=side, name=name})
  end)
  if ok and u and u.guid then return u end
  return nil
end

function getSide(sideName)
  local ok, s = pcall(function()
    return VP_GetSide({Side=sideName})
  end)
  if ok and s then return s end
  return nil
end
```

## 阵营、敌对关系与 Doctrine

```lua
function ensureSides()
  pcall(function() ScenEdit_AddSide({name=_SIDE_RED, color="255,0,0"}) end)
  pcall(function() ScenEdit_AddSide({name=_SIDE_BLUE, color="0,0,255"}) end)

  local redSide = getSide(_SIDE_RED)
  local blueSide = getSide(_SIDE_BLUE)
  logInfo(("side check: red=%s blue=%s"):format(tostring(redSide ~= nil), tostring(blueSide ~= nil)))

  pcall(function() ScenEdit_SetSideOptions({side=_SIDE_RED, awareness="OMNI"}) end)
  pcall(function() ScenEdit_SetSidePosture(_SIDE_RED, _SIDE_BLUE, "H") end)
  pcall(function() ScenEdit_SetSidePosture(_SIDE_BLUE, _SIDE_RED, "H") end)

  pcall(function() ScenEdit_SetDoctrine({side=_SIDE_RED}, {
    weapon_control_status_air="0",
    weapon_control_status_surface="0",
    weapon_control_status_subsurface="0",
    weapon_control_status_land="0",
  }) end)
  pcall(function() ScenEdit_SetDoctrine({side=_SIDE_BLUE}, {
    weapon_control_status_air="0",
    weapon_control_status_surface="0",
    weapon_control_status_subsurface="0",
    weapon_control_status_land="0",
  }) end)
end
```

## 从 Manifest 创建单位

```lua
function ensureUnitFromManifest(u)
  local existing = getUnit(u.side, u.name)
  if existing then
    logInfo("unit exists: " .. u.name)
    return existing
  end

  local spec = {
    type = u.cmo_type,
    side = u.side,
    name = u.name,
    dbid = tonumber(u.dbid),
    proficiency = u.proficiency or "Veteran",
  }

  if u.cmo_type == "Aircraft" then
    if u.base then spec.base = u.base end
    if u.loadout_id then spec.loadoutid = tonumber(u.loadout_id) end
    if u.latitude then spec.latitude = tonumber(u.latitude) end
    if u.longitude then spec.longitude = tonumber(u.longitude) end
    if u.altitude then spec.altitude = tonumber(u.altitude) end
    if u.heading then spec.heading = tonumber(u.heading) end
    if u.speed then spec.speed = tonumber(u.speed) end
  else
    spec.latitude = tonumber(u.latitude)
    spec.longitude = tonumber(u.longitude)
    if u.heading then spec.heading = tonumber(u.heading) end
    if u.speed then spec.speed = tonumber(u.speed) end
  end

  if u.autodetectable ~= nil then spec.autodetectable = u.autodetectable end

  _errmsg_ = nil; _errnum_ = 0
  local ok = pcall(function() ScenEdit_AddUnit(spec) end)
  local created = getUnit(u.side, u.name)
  logInfo(("create unit name=%s type=%s dbid=%s ok=%s exists=%s errnum=%s errmsg=%s"):format(
    tostring(u.name), tostring(u.cmo_type), tostring(u.dbid), tostring(ok), tostring(created ~= nil), tostring(_errnum_ or 0), tostring(_errmsg_)))

  if created and created.guid and u.side == _SIDE_BLUE then
    pcall(function() ScenEdit_SetUnit({guid=created.guid, autodetectable=true}) end)
    pcall(function() ScenEdit_SetEMCON("Unit", created.guid, "Radar=Active;Sonar=Active") end)
  end

  return created
end

function createAllUnits()
  for _, u in pairs(UNITS) do
    ensureUnitFromManifest(u)
  end
end
```

## 蓝方目标 autodetectable 双保险

```lua
function forceBlueTargetsAutodetectable()
  for _, u in pairs(UNITS) do
    if u.side == _SIDE_BLUE then
      local unit = getUnit(u.side, u.name)
      if unit and unit.guid then
        pcall(function() ScenEdit_SetUnit({guid=unit.guid, autodetectable=true}) end)
        pcall(function() ScenEdit_SetEMCON("Unit", unit.guid, "Radar=Active;Sonar=Active") end)
      end
    end
  end
end
```

## 清弹模板

```lua
function clearUnitWeapons(side, name)
  local u = getUnit(side, name)
  if not (u and u.guid) then
    logWarn("clearUnitWeapons: unit not found " .. tostring(side) .. "/" .. tostring(name))
    return false
  end

  local jobs = {}
  for _, m in ipairs(u.mounts or {}) do
    for _, w in ipairs(m.mount_weapons or {}) do
      local cur = tonumber(w.wpn_current) or 0
      if cur > 0 then
        jobs[#jobs + 1] = {
          dbid = w.wpn_dbid,
          num = cur,
          mountid = m.mount_guid,
        }
      end
    end
  end

  local done, fail = 0, 0
  for _, j in ipairs(jobs) do
    _errmsg_ = nil; _errnum_ = 0
    local ok = pcall(function()
      ScenEdit_AddReloadsToUnit({
        guid = u.guid,
        wpn_dbid = j.dbid,
        mount_guid = j.mountid,
        number = j.num,
        remove = true,
      })
    end)
    if ok and (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
  end

  logInfo(("clear %s done=%d fail=%d"):format(tostring(name), done, fail))
  return fail == 0
end

function clearAllWeapons()
  for _, name in ipairs(CLEAR_LIST or {}) do
    clearUnitWeapons(_SIDE_RED, name)
  end
end
```

## 装弹模板

```lua
function reloadAllWeapons()
  for _, a in ipairs(AMMO or {}) do
    _errmsg_ = nil; _errnum_ = 0
    local ok = pcall(function()
      ScenEdit_AddReloadsToUnit({
        side = _SIDE_RED,
        unitname = a.unitname,
        wpn_dbid = tonumber(a.weapon_dbid),
        number = tonumber(a.number),
      })
    end)
    logInfo(("reload unit=%s weapon=%s number=%s ok=%s errnum=%s errmsg=%s"):format(
      tostring(a.unitname), tostring(a.weapon_dbid), tostring(a.number), tostring(ok), tostring(_errnum_ or 0), tostring(_errmsg_)))
  end
end
```

## contact 获取函数

```lua
function findContactGuidForTarget(targetName)
  local tgt = getUnit(_SIDE_BLUE, targetName)
  if not (tgt and tgt.guid) then
    logError("target unit not found: " .. tostring(targetName))
    return nil
  end

  pcall(function() ScenEdit_SetUnit({guid=tgt.guid, autodetectable=true}) end)
  pcall(function() ScenEdit_SetSideOptions({side=_SIDE_RED, awareness="OMNI"}) end)

  local side = getSide(_SIDE_RED)
  if not (side and type(side.contacts) == "table") then
    logWarn("no contacts table for side: " .. tostring(_SIDE_RED))
    return nil
  end

  local targetGuid = tostring(tgt.guid):lower()
  for _, c in ipairs(side.contacts) do
    local aid = c.actualunitid or c.actualUnitID or c.actualunitguid or c.actualUnitGuid
    if aid and tostring(aid):lower() == targetGuid then
      return c.guid or c.Guid
    end
  end

  for _, c in ipairs(side.contacts) do
    local nm = tostring(c.name or c.Name or "")
    if nm ~= "" and (nm == targetName or nm:find(targetName, 1, true)) then
      return c.guid or c.Guid
    end
  end

  logWarn("contact not found for target=" .. tostring(targetName) .. " contact_count=" .. tostring(#side.contacts))
  return nil
end
```

## 全局 fireAt 函数

```lua
function fireAt(attackerName, targetName, wpnDbid, qty)
  local atk = getUnit(_SIDE_RED, attackerName)
  local tgt = getUnit(_SIDE_BLUE, targetName)
  if not (atk and atk.guid) then
    logError("attacker not found: " .. tostring(attackerName))
    return false
  end
  if not (tgt and tgt.guid) then
    logError("target not found: " .. tostring(targetName))
    return false
  end

  pcall(function() ScenEdit_SetUnit({guid=tgt.guid, autodetectable=true}) end)
  pcall(function() ScenEdit_SetSideOptions({side=_SIDE_RED, awareness="OMNI"}) end)

  local contactGuid = findContactGuidForTarget(targetName)
  if not contactGuid then
    logError("fireAt no contact attacker=" .. tostring(attackerName) .. " target=" .. tostring(targetName))
    return false
  end

  local opts
  if wpnDbid and tonumber(wpnDbid) and tonumber(wpnDbid) > 0 then
    opts = {mode="1", weapon=tonumber(wpnDbid), qty=tonumber(qty or 1)}
  else
    opts = {mode="0"}
  end

  _errmsg_ = nil; _errnum_ = 0
  local ok, r = pcall(function()
    return ScenEdit_AttackContact(atk.guid, contactGuid, opts)
  end)

  logInfo(("fire attacker=%s target=%s contact=%s weapon=%s qty=%s ok=%s result=%s errnum=%s errmsg=%s"):format(
    tostring(attackerName), tostring(targetName), tostring(contactGuid), tostring(wpnDbid), tostring(qty),
    tostring(ok), tostring(r), tostring(_errnum_ or 0), tostring(_errmsg_)))

  return ok and r and true or false
end
```

## Time Trigger 时间换算

```lua
function totTicks(addSeconds)
  return string.format("%.0f", (ScenEdit_CurrentTime() + tonumber(addSeconds or 0)) * 1e7 + 621355968000000000)
end
```

## 真延时事件调度

```lua
function scheduleLua(luaBody, delay, tag)
  local suffix = tostring(ScenEdit_CurrentTime()) .. "_" .. tostring(tag)
  local evName = "Ev_" .. suffix
  local trName = "Tr_" .. suffix
  local acName = "Ac_" .. suffix

  local script = table.concat({
    luaBody, "\n",
    ("pcall(function() ScenEdit_SetEvent(%q,{mode='remove'}) end)\n"):format(evName),
    ("pcall(function() ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q}) end)\n"):format(acName),
    ("pcall(function() ScenEdit_SetTrigger({mode='remove',type='Time',name=%q}) end)\n"):format(trName),
  })

  local fireTime = totTicks(delay)
  pcall(function() ScenEdit_SetTrigger({mode="add", type="Time", name=trName, Time=fireTime}) end)
  pcall(function() ScenEdit_SetAction({mode="add", type="LuaScript", name=acName, ScriptText=script}) end)
  pcall(function() ScenEdit_SetEvent(evName, {mode="add", IsActive=true, IsRepeatable=false}) end)
  pcall(function() ScenEdit_SetEventTrigger(evName, {mode="add", name=trName}) end)
  pcall(function() ScenEdit_SetEventAction(evName, {mode="add", name=acName}) end)

  logInfo(("scheduled tag=%s delay=%s ticks=%s"):format(tostring(tag), tostring(delay), tostring(fireTime)))
end
```

## 齐射调度

```lua
function scheduleStrikeSalvo()
  for i, s in ipairs(STRIKE or {}) do
    local qty = tonumber(s.quantity or 1) or 1
    local startDelay = tonumber(s.start_delay or s.startDelay or 0) or 0
    local interval = tonumber(s.interval or _DEFAULT_INTERVAL) or _DEFAULT_INTERVAL

    for k = 1, qty do
      local delay = startDelay + _CONTACT_SETTLE + (k - 1) * interval
      local body = ("fireAt(%q,%q,%d,1)"):format(s.attacker, s.target, tonumber(s.weapon_dbid or 0) or 0)
      local tag = ("STRIKE_%d_%d_%s"):format(i, k, tostring(s.id or "task"))
      scheduleLua(body, delay, tag)
    end
  end
end
```

## 主入口模板

```lua
function main()
  logInfo("=== CMO generated script start ===")
  ensureSides()
  createAllUnits()
  forceBlueTargetsAutodetectable()
  clearAllWeapons()
  reloadAllWeapons()
  scheduleStrikeSalvo()
  logInfo("=== all scheduled; press Play to advance simulation time ===")
end

main()
```