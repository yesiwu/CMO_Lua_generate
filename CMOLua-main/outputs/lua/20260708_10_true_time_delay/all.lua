-- ============================================================
-- all.lua — 一体化脚本（main + clear + reload + attack + rtb 真延时）
-- 场景：辽宁舰 + 055 + J-15 反舰齐射 CG-59 Princeton + 返航
-- 模式：CMO 事件触发器 TOT（qty=1 逐枚，contact_settle_delay=15s）
-- 一次性 dofile，依次执行 init/clear/reload/attack/rtb
-- ============================================================

do
  print("========================================")
  print("[CMO] all.lua 启动 v4 (真延时 + RTB)")
  print("========================================")

  ----------------------------------------------------------------
  -- ★ 全局配置（事件沙箱必须可访问，提升为全局）★
  ----------------------------------------------------------------
  _SIDE_RED = "红方"
  _SIDE_BLUE = "蓝方"
  _CONTACT_SETTLE_DELAY = 15   -- ≥15s 等待 contact 稳定
  _BANDIT_RETRY = 3            -- 单次发射重试次数
  _RETRY_INTERVAL = 2          -- 重试间隔秒

  -- 单位硬编码（来自 MCP DB3K_504.db3 实测）
  _CARRIER_DBID = 2007          -- 辽宁舰 Type 001 [16 Liaoning]
  _SHIP_055_DBID = 3883         -- 055 Renhai [101 Nanchang]
  _J15_DBID = 2496              -- J-15 主型 Flying Shark
  _LOADOUT_ID = 9682            -- YJ-83K [C-802AK] 反舰挂载
  _WEAPON_DBID = 2137           -- YJ-83K [C-802AK] 武器
  _CG59_DBID = 2862             -- CG-59 Princeton (Ticonderoga Baseline 3 VLS)

  _CARRIER_NAME = "红方辽宁舰"
  _SHIP_055_NAME = "红方055D"
  _J15_NAME = "J-15-RED-01"
  _CG_NAME = "CG59_Princeton"

  -- 航母坐标（RTB 用），与 main 段一致
  _CARRIER_LAT = 30.60
  _CARRIER_LON = 122.50

  ----------------------------------------------------------------
  -- ★★★ fireAt 函数（必须全局，红线 #15）★★★
  ----------------------------------------------------------------
  function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side = _SIDE_RED, name = attackerName})
    local tgt = ScenEdit_GetUnit({side = _SIDE_BLUE, name = targetName})

    if not (atk and atk.guid) then
      print("[CMO] [ERROR] 找不到攻击方 " .. tostring(attackerName))
      return false
    end
    if not (tgt and tgt.guid) then
      print("[CMO] [ERROR] 找不到目标 " .. tostring(targetName))
      return false
    end

    pcall(ScenEdit_SetUnit, {guid = tgt.guid, autodetectable = true})

    local function sameGuid(a, b)
      if not a or not b then return false end
      return tostring(a) == tostring(b)
    end
    local function contactName(c)
      return tostring(c.name or c.Name or c.actualunitname or "")
    end
    local function addContact(dst, seen, cc)
      if type(cc) ~= "table" then return end
      local cg = cc.guid or cc.Guid
      if not cg or seen[cg] then return end
      seen[cg] = true
      dst[#dst + 1] = cc
    end
    local function collectRec(dst, seen, tt, d)
      if type(tt) ~= "table" or d > 3 then return end
      addContact(dst, seen, tt)
      for _, vv in pairs(tt) do
        if type(vv) == "table" then collectRec(dst, seen, vv, d + 1) end
      end
    end
    local function collectContacts(sn)
      local out, seen = {}, {}
      local funcs = {
        function() return ScenEdit_GetContacts({side = sn}) end,
        function() return ScenEdit_GetContacts({Side = sn}) end,
        function() return ScenEdit_GetContacts(sn) end,
      }
      for _, fn in ipairs(funcs) do
        local ok2, r = pcall(fn)
        if ok2 and type(r) == "table" then
          collectRec(out, seen, r, 0)
        end
      end
      local ok2, s = pcall(VP_GetSide, {Side = sn})
      if ok2 and s and type(s.contacts) == "table" then
        collectRec(out, seen, s.contacts, 0)
      end
      return out
    end
    local function findContact()
      local cs = collectContacts(_SIDE_RED)
      for _, c in ipairs(cs) do
        local fields = {"actualunitid","actualUnitID","actualunitguid",
                       "actualUnitGuid","actualguid","actualGuid"}
        for _, f in ipairs(fields) do
          if sameGuid(c[f], tgt.guid) then return c.guid or c.Guid end
        end
      end
      for _, c in ipairs(cs) do
        local cg = c.guid or c.Guid
        local nm = contactName(c)
        if cg and nm and (nm == targetName or nm:find(targetName, 1, true)) then
          return cg
        end
      end
      return nil
    end

    local contactGuid = nil
    for attempt = 1, _BANDIT_RETRY do
      contactGuid = findContact()
      if contactGuid then break end
      if attempt < _BANDIT_RETRY then
        print(("[CMO] [WARN] Attempt %d/%d 没找到 contact，%ds 后重试"):format(
          attempt, _BANDIT_RETRY, _RETRY_INTERVAL))
      end
    end

    local r
    if contactGuid then
      _errnum_ = 0
      r = ScenEdit_AttackContact(atk.guid, contactGuid, {
        mode = "1",
        weapon = wpnDbid,
        qty = qty,
      })
      print(("[CMO] [INFO] %s -> CONTACT=%s weapon=%d qty=%d r=%s"):format(
        attackerName, tostring(contactGuid), wpnDbid, qty, tostring(r)))
    else
      _errnum_ = 0
      r = ScenEdit_AttackContact(atk.guid, tgt.guid, {
        mode = "1",
        weapon = wpnDbid,
        qty = qty,
      })
      print(("[CMO] [WARN] 用 UNIT-GUID 后备 %s -> %s weapon=%d qty=%d r=%s"):format(
        attackerName, targetName, wpnDbid, qty, tostring(r)))
    end
    return r ~= nil
  end

  ----------------------------------------------------------------
  -- ★★★ TOT 调度工具（红线 #9 + #11）★★★
  ----------------------------------------------------------------
  local function totTicks(addSec)
    return string.format("%.0f", (ScenEdit_CurrentTime() + 62135596801 + addSec) * 1e7)
  end

  local function scheduleOne(atkName, tgtName, wpn, delay, tag)
    delay = delay + _CONTACT_SETTLE_DELAY
    local ts = tostring(ScenEdit_CurrentTime())
    local evName = "Event " .. tag .. "_" .. ts
    local trName = "Trig "  .. tag .. "_" .. ts
    local acName = "Act "   .. tag .. "_" .. ts
    local fireTime = totTicks(delay)
    local script =
      ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpn) ..
      ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
      ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
      ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent,   evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
  end

  ----------------------------------------------------------------
  -- ★★★ RTB 调度工具（用于返航段）★★★
  ----------------------------------------------------------------
  local function scheduleRtb(rtbDelay, tag)
    local ts = tostring(ScenEdit_CurrentTime())
    local evName = "Event " .. tag .. "_" .. ts
    local trName = "Trig "  .. tag .. "_" .. ts
    local acName = "Act "   .. tag .. "_" .. ts
    local fireTime = totTicks(rtbDelay)
    local script = table.concat({
      -- 强设 J-15 航向回航母坐标
      ("local ok1, r1 = pcall(ScenEdit_SetUnit, {side=%q, unitname=%q, course={ {latitude=%f, longitude=%f} }, altitude=8000, throttle='Cruise', speed=300})\n"):format(
        _SIDE_RED, _J15_NAME, _CARRIER_LAT, _CARRIER_LON),
      ("print('[CMO] [RTB] J-15 -> 辽宁舰 ok=' .. tostring(ok1) .. ' err=' .. tostring(_errmsg_))\n"),
      -- 把 homebase 设回航母
      ("pcall(ScenEdit_SetUnit, {side=%q, unitname=%q, homebase=%q})\n"):format(
        _SIDE_RED, _J15_NAME, _CARRIER_NAME),
      ("pcall(ScenEdit_SetUnit, {side=%q, unitname=%q, base=%q})\n"):format(
        _SIDE_RED, _J15_NAME, _CARRIER_NAME),
      -- 自清理
      ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName),
      ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName),
      ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName),
    })
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent,   evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
  end

  ----------------------------------------------------------------
  -- 通用工具
  ----------------------------------------------------------------
  local function getUnit(side, name)
    local ok, u = pcall(ScenEdit_GetUnit, {side=side, name=name})
    if ok and u and u.guid then return u end
    return nil
  end
  local function log(tag, ok, r)
    print(tag .. " ok=" .. tostring(ok)
          .. " 返回=" .. tostring(r)
          .. " err=" .. tostring(_errmsg_))
  end

  ----------------------------------------------------------------
  -- === main.lua：建单位 + 建阵营 ===
  ----------------------------------------------------------------
  do
    print("\n===== [main] 建单位 + 建阵营 =====")

    -- ★ 红线 #5：ScenEdit_AddSide 必须用 table，不能传字符串
    pcall(ScenEdit_AddSide, {name=_SIDE_RED, color="255,0,0"})
    pcall(ScenEdit_AddSide, {name=_SIDE_BLUE, color="0,0,255"})

    pcall(ScenEdit_SetSideOptions, {side=_SIDE_RED, awareness="OMNI"})
    pcall(ScenEdit_SetSidePosture, _SIDE_RED, _SIDE_BLUE, "H")
    pcall(ScenEdit_SetSidePosture, _SIDE_BLUE, _SIDE_RED, "H")

    -- 红蓝双方 wcs=0 自由开火（红线 #12）
    pcall(ScenEdit_SetDoctrine, {side=_SIDE_RED}, {
      weapon_control_status_air="0",
      weapon_control_status_surface="0",
      weapon_control_status_subsurface="0",
      weapon_control_status_land="0"
    })
    pcall(ScenEdit_SetDoctrine, {side=_SIDE_BLUE}, {
      weapon_control_status_air="0",
      weapon_control_status_surface="0",
      weapon_control_status_subsurface="0",
      weapon_control_status_land="0"
    })

    -- 阵营诊断
    local sR = (VP_GetSide and pcall(VP_GetSide, {Side=_SIDE_RED}))
    local sB = (VP_GetSide and pcall(VP_GetSide, {Side=_SIDE_BLUE}))
    print(("[main] 阵营诊断: 红方存在=%s 蓝方存在=%s"):format(
      tostring(sR and true or false),
      tostring(sB and true or false)))

    -- 辽宁舰
    local carrier = getUnit(_SIDE_RED, _CARRIER_NAME)
    if not carrier then
      _errnum_ = 0
      local ok, r = pcall(ScenEdit_AddUnit, {
        type="Ship", side=_SIDE_RED, name=_CARRIER_NAME,
        dbid=_CARRIER_DBID,
        latitude=_CARRIER_LAT, longitude=_CARRIER_LON,
        heading=90, speed=18, proficiency="Veteran"
      })
      log("[main] 辽宁舰", ok, r)
      carrier = getUnit(_SIDE_RED, _CARRIER_NAME)
    else
      print("[main] 辽宁舰已存在 guid=" .. tostring(carrier.guid))
    end

    -- 055 护航
    local ship055 = getUnit(_SIDE_RED, _SHIP_055_NAME)
    if not ship055 then
      _errnum_ = 0
      local ok, r = pcall(ScenEdit_AddUnit, {
        type="Ship", side=_SIDE_RED, name=_SHIP_055_NAME,
        dbid=_SHIP_055_DBID,
        latitude=30.55, longitude=122.55,
        heading=90, speed=18, proficiency="Veteran"
      })
      log("[main] 055", ok, r)
    else
      print("[main] 055 已存在 guid=" .. tostring(ship055.guid))
    end

    -- 蓝方 CG-59
    local cg = getUnit(_SIDE_BLUE, _CG_NAME)
    if not cg then
      _errnum_ = 0
      local ok, r = pcall(ScenEdit_AddUnit, {
        type="Ship", side=_SIDE_BLUE, name=_CG_NAME,
        dbid=_CG59_DBID,
        latitude=30.35, longitude=122.95,
        heading=180, speed=14,
        autodetectable=true, proficiency="Veteran"
      })
      log("[main] CG-59", ok, r)
      cg = getUnit(_SIDE_BLUE, _CG_NAME)
    else
      pcall(ScenEdit_SetUnit, {side=_SIDE_BLUE, unitname=_CG_NAME, autodetectable=true})
      print("[main] CG-59 已存在 guid=" .. tostring(cg.guid))
    end

    -- J-15 挂到辽宁舰（带 Loadout，base=航母）
    local j15 = getUnit(_SIDE_RED, _J15_NAME)
    if not j15 then
      _errnum_ = 0
      local ok, r = pcall(ScenEdit_AddUnit, {
        type="Aircraft", side=_SIDE_RED, name=_J15_NAME,
        dbid=_J15_DBID, loadoutid=_LOADOUT_ID,
        base=_CARRIER_NAME, proficiency="Veteran"
      })
      log("[main] J-15 创建(loadout)", ok, r)
      j15 = getUnit(_SIDE_RED, _J15_NAME)
      if not j15 then
        _errnum_ = 0
        local ok2, r2 = pcall(ScenEdit_AddUnit, {
          type="Aircraft", side=_SIDE_RED, name=_J15_NAME,
          dbid=_J15_DBID, base=_CARRIER_NAME, proficiency="Veteran"
        })
        log("[main] J-15 创建(裸机)", ok2, r2)
        j15 = getUnit(_SIDE_RED, _J15_NAME)
      end
    else
      print("[main] J-15 已存在 guid=" .. tostring(j15.guid))
    end

    if not j15 then
      print("[main] !! J-15 创建失败")
    else
      _errnum_ = 0
      local okLoad = pcall(ScenEdit_LoadUnit, j15.guid, _LOADOUT_ID)
      print("[main] J-15 应用 Loadout=" .. tostring(_LOADOUT_ID)
            .. " ok=" .. tostring(okLoad)
            .. " err=" .. tostring(_errmsg_))

      pcall(ScenEdit_SetUnit, {
        side=_SIDE_RED, unitname=_J15_NAME, timetoready_minutes=0
      })
      _errnum_ = 0
      local okL, rL = pcall(ScenEdit_SetUnit, {
        side=_SIDE_RED, unitname=_J15_NAME, launch=true
      })
      log("[main] J-15 起飞", okL, rL)

      pcall(ScenEdit_SetEMCON, "Unit", _J15_NAME, "Radar=Active")
      pcall(ScenEdit_SetUnit, {
        side=_SIDE_RED, unitname=_J15_NAME,
        course={
          {latitude=30.50, longitude=122.65},
          {latitude=30.42, longitude=122.82}
        },
        altitude=8000, throttle="Cruise"
      })
    end

    print("[main] 完成。\n")
  end

  ----------------------------------------------------------------
  -- === clear + reload ===
  ----------------------------------------------------------------
  do
    print("===== [clear+reload] 清/装弹 =====")
    local j15 = getUnit(_SIDE_RED, _J15_NAME)
    if not j15 then
      print("[reload] 找不到 J-15，跳过")
    else
      local function dumpAmmo()
        local total = 0
        for _, m in ipairs(j15.mounts or {}) do
          for _, w in ipairs(m.mount_weapons or {}) do
            total = total + (tonumber(w.wpn_current) or 0)
            print(("   挂架[%s] dbid=%s 数量=%s"):format(
              tostring(m.mount_dbid or m.name),
              tostring(w.wpn_dbid),
              tostring(w.wpn_current)))
          end
        end
        print("[reload] 当前挂弹合计 = " .. tostring(total))
        return total
      end
      dumpAmmo()

      _errnum_ = 0
      local okLoad = pcall(ScenEdit_LoadUnit, j15.guid, _LOADOUT_ID)
      print("[reload] 重新装上 Loadout=" .. tostring(_LOADOUT_ID)
            .. " ok=" .. tostring(okLoad)
            .. " err=" .. tostring(_errmsg_))
      dumpAmmo()
    end
    print("[clear+reload] 完成。\n")
  end

  ----------------------------------------------------------------
  -- === attack.lua：真延时齐射 ===
  ----------------------------------------------------------------
  local attackStartTime = nil
  do
    print("===== [attack] 真延时齐射 =====")
    local j15 = getUnit(_SIDE_RED, _J15_NAME)
    local cg = getUnit(_SIDE_BLUE, _CG_NAME)
    if not j15 then print("[attack] !! 找不到 J-15"); return end
    if not cg then print("[attack] !! 找不到 CG-59"); return end

    local quantity   = 2
    local startDelay = 0
    local interval   = 1
    local intent     = "J15_to_CG59_ASM"

    print(("[attack] TOT 配置：弹数=%d 首发延迟=%ds 间隔=%ds contact_settle=%ds"):format(
      quantity, startDelay, interval, _CONTACT_SETTLE_DELAY))

    for k = 1, quantity do
      local delay = startDelay + (k - 1) * interval
      local tag = ("TOT_attack_%d_%s"):format(k, intent)
      scheduleOne(_J15_NAME, _CG_NAME, _WEAPON_DBID, delay, tag)
      print(("[attack] 已调度：tag=%s delay=%ds（含稳定期）weapon=%d"):format(
        tag, delay + _CONTACT_SETTLE_DELAY, _WEAPON_DBID))
    end

    -- 攻击完成的仿真时间（用于 RTB 段）
    attackStartTime = _CONTACT_SETTLE_DELAY + (quantity - 1) * interval
    -- YJ-83K 飞行约 60s，加上导弹飞行时间
    local missileFlightTime = 60
    attackStartTime = attackStartTime + missileFlightTime
    print(("[attack] 攻击完毕预计 T+%ds（导弹飞行 + 命中）"):format(attackStartTime))
    print("[attack] 完成。\n")
  end

  ----------------------------------------------------------------
  -- === rtb.lua：真延时返航 ===
  ----------------------------------------------------------------
  do
    print("===== [rtb] 返航辽宁舰 =====")
    if not attackStartTime then
      print("[rtb] attackStartTime 未定义，跳过 RTB")
    else
      -- T+attackStartTime 再等 10s 缓冲（确保导弹已打完）
      local rtbDelay = attackStartTime + 10
      local tag = "RTB_J15_ReturnToCarrier"

      scheduleRtb(rtbDelay, tag)
      print(("[rtb] ✓ 已调度 RTB：tag=%s delay=%ds 目标=%s"):format(
        tag, rtbDelay, _CARRIER_NAME))
      print(("[rtb] 时间线：攻击完@T+%ds → RTB 触发@T+%ds"):format(
        attackStartTime, rtbDelay))
    end
    print("[rtb] 完成。\n")
  end

  print("\n========================================")
  print("[CMO] all.lua 全部完成。")
  print("时间线：")
  print("  T+15s     第 1 枚 YJ-83K 离架")
  print("  T+16s     第 2 枚 YJ-83K 离架")
  print("  T+~76s    导弹命中 CG-59")
  print("  T+86s     J-15 自动 RTB 朝辽宁舰")
  print("========================================")
end