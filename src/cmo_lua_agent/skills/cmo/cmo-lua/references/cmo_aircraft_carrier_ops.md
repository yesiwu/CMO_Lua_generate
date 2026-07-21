# CMO 航母舰载机作战模板 v3.0

> 适用范围：CMO Lua 中的航母/基地舰载机流程，包括航母创建、舰载机创建、挂载、起飞、航路、延时攻击和返航。仅当 manifest 中存在 `base_unit_id` 指向航母或基地的 Aircraft 时加载。

## 前置条件

使用本模板前，manifest 必须确认：

```text
base unit 存在于 UNITS
base.cmo_type = Ship 或 Facility
aircraft.cmo_type = Aircraft
aircraft.base_unit_id 能解析到 base.name
aircraft.dbid_verified = true
aircraft.loadout_verified = true
aircraft.loadout_id 非空
```

## 航母 / 基地创建

```lua
function ensureCarrier(carrier)
  if carrier.cmo_type ~= "Ship" and carrier.cmo_type ~= "Facility" then
    logError("carrier/base must be Ship or Facility: " .. tostring(carrier.name))
    return nil
  end
  return ensureUnitFromManifest(carrier)
end
```

## 舰载机创建

舰载机应通过 `base=<carrierName>` 创建。基于航母创建时，坐标可以省略；如果 Manifest 中有明确坐标，也可以传入。

```lua
function ensureCarrierAircraft(a)
  local existing = getUnit(a.side, a.name)
  if existing then
    logInfo("aircraft exists: " .. tostring(a.name))
    return existing
  end

  local spec = {
    type = "Aircraft",
    side = a.side,
    name = a.name,
    dbid = tonumber(a.dbid),
    base = a.base,
    loadoutid = tonumber(a.loadout_id),
    proficiency = a.proficiency or "Veteran",
  }

  if a.latitude then spec.latitude = tonumber(a.latitude) end
  if a.longitude then spec.longitude = tonumber(a.longitude) end
  if a.altitude then spec.altitude = tonumber(a.altitude) end
  if a.heading then spec.heading = tonumber(a.heading) end
  if a.speed then spec.speed = tonumber(a.speed) end

  _errmsg_ = nil; _errnum_ = 0
  local ok = pcall(function() ScenEdit_AddUnit(spec) end)
  local unit = getUnit(a.side, a.name)
  logInfo(("create carrier aircraft name=%s base=%s loadout=%s ok=%s exists=%s errnum=%s errmsg=%s"):format(
    tostring(a.name), tostring(a.base), tostring(a.loadout_id), tostring(ok), tostring(unit ~= nil), tostring(_errnum_ or 0), tostring(_errmsg_)))

  if unit and unit.guid then
    pcall(function() ScenEdit_LoadUnit(unit.guid, tonumber(a.loadout_id)) end)
  end

  return unit
end
```

如果带挂载创建失败，只有在用户明确允许 fallback 时才允许创建裸机，并且必须记录 warning。禁止静默降级。

## 起飞流程

舰载机起飞标准步骤：

```text
timetoready_minutes=0 -> launch=true -> course/altitude/throttle
```

```lua
function launchAircraft(a, route)
  local u = getUnit(a.side, a.name)
  if not (u and u.guid) then
    logError("launchAircraft unit not found: " .. tostring(a.name))
    return false
  end

  pcall(function()
    ScenEdit_SetUnit({side=a.side, unitname=a.name, timetoready_minutes=0})
  end)

  pcall(function()
    ScenEdit_SetUnit({side=a.side, unitname=a.name, launch=true})
  end)

  local opts = {
    side = a.side,
    unitname = a.name,
    altitude = tonumber(a.altitude or 8000),
    throttle = a.throttle or "Cruise",
  }
  if route and #route > 0 then opts.course = route end

  pcall(function() ScenEdit_SetUnit(opts) end)
  pcall(function() ScenEdit_SetEMCON("Unit", u.guid, "Radar=Active;OECM=Active") end)

  logInfo("launch aircraft=" .. tostring(a.name))
  return true
end
```

## 航路生成

如果 JSON/Manifest 有显式 route waypoints，必须使用原始航点。

如果没有航点，可以基于航母和目标坐标生成简单中间点/接近点，但必须标记为生成器推断，不得伪装成 JSON 事实。

```lua
function simpleApproachRoute(carrier, target)
  local cLat = tonumber(carrier.latitude)
  local cLon = tonumber(carrier.longitude)
  local tLat = tonumber(target.latitude)
  local tLon = tonumber(target.longitude)
  if not (cLat and cLon and tLat and tLon) then return nil end

  local mid = {
    latitude = cLat + (tLat - cLat) * 0.45,
    longitude = cLon + (tLon - cLon) * 0.45,
  }
  local approach = {
    latitude = cLat + (tLat - cLat) * 0.75,
    longitude = cLon + (tLon - cLon) * 0.75,
  }
  return {mid, approach}
end
```

## 舰载机攻击调度

舰载机通常比舰艇需要更长 settle 时间：起飞、爬升、飞向发射阵位都需要仿真时间推进。

推荐：

```text
舰艇首发延迟：30s+
舰载机首发延迟：150s ~ 240s+
```

```lua
function scheduleAircraftStrike(a, targetName, weaponDbid, quantity, delay, tag)
  local qty = tonumber(quantity or 1) or 1
  for k = 1, qty do
    local d = tonumber(delay or 180) + _CONTACT_SETTLE + (k - 1)
    local body = ("fireAt(%q,%q,%d,1)"):format(a.name, targetName, tonumber(weaponDbid or 0) or 0)
    scheduleLua(body, d, tostring(tag) .. "_AIR_" .. tostring(k))
  end
end
```

## 自动返航 RTB

舰载机返航必须同时设置 `homebase` 和 `base`。只设置其中一个可能导致飞机盘旋或不回收。

```lua
function scheduleAircraftRtb(a, carrier, delay, tag)
  local cLat = tonumber(carrier.latitude)
  local cLon = tonumber(carrier.longitude)
  local routeSnippet = ""
  if cLat and cLon then
    routeSnippet = ("pcall(function() ScenEdit_SetUnit({side=%q, unitname=%q, course={{latitude=%f, longitude=%f}}, altitude=8000, throttle='Cruise'}) end)\n")
      :format(a.side, a.name, cLat, cLon)
  end

  local body = table.concat({
    routeSnippet,
    ("pcall(function() ScenEdit_SetUnit({side=%q, unitname=%q, homebase=%q}) end)\n"):format(a.side, a.name, carrier.name),
    ("pcall(function() ScenEdit_SetUnit({side=%q, unitname=%q, base=%q}) end)\n"):format(a.side, a.name, carrier.name),
    ("pcall(function() ScenEdit_SetUnit({side=%q, unitname=%q, rtb=true}) end)\n"):format(a.side, a.name),
    ("print('[CMO] [RTB] %s return to %s')"):format(a.name, carrier.name),
  })
  scheduleLua(body, tonumber(delay or 300), tag or ("RTB_" .. a.name))
end
```

## 舰载机完整流程

```lua
function runCarrierAircraftOps()
  for _, u in pairs(UNITS) do
    if u.cmo_type == "Aircraft" and u.base_unit_id then
      local carrier = UNITS[u.base_unit_id]
      if not carrier then
        logError("base_unit_id unresolved for aircraft=" .. tostring(u.name))
      else
        ensureCarrier(carrier)
        ensureCarrierAircraft(u)

        local firstStrike = nil
        for _, s in ipairs(STRIKE or {}) do
          if s.attacker_id == u.id then firstStrike = s; break end
        end

        local route = nil
        if firstStrike and firstStrike.target_id and UNITS[firstStrike.target_id] then
          route = simpleApproachRoute(carrier, UNITS[firstStrike.target_id])
        end

        launchAircraft(u, route)

        if firstStrike then
          scheduleAircraftStrike(u, firstStrike.target, firstStrike.weapon_dbid, firstStrike.quantity, firstStrike.start_delay or 180, firstStrike.id)
          scheduleAircraftRtb(u, carrier, (firstStrike.start_delay or 180) + 180, "RTB_" .. tostring(u.id))
        end
      end
    end
  end
end
```

## 自审清单

```text
[ ] 航母/基地已在 UNITS 中创建，且 name 与 aircraft.base 一致
[ ] aircraft.dbid_verified = true
[ ] aircraft.loadout_id 存在且 loadout_verified = true
[ ] ScenEdit_AddUnit 使用 type="Aircraft"、base=<航母名>、loadoutid=<挂载ID>
[ ] 起飞流程包含 timetoready_minutes=0、launch=true、course/altitude/throttle
[ ] 如果航路是生成器推断，已记录 warning 或 intent
[ ] 舰载机攻击延迟明显大于舰艇攻击延迟
[ ] RTB 同时设置 homebase 与 base
[ ] RTB 脚本由 Time Trigger 调度，不能依赖人工手动运行
```