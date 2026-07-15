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
