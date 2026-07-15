-- ==========================================================================
-- attack.lua  真延时打击（TOT 事件驱动, qty=1 逐枚调度）
-- contact_settle_delay = 15 秒（红线 #9）
-- 红方 awareness=OMNI, 蓝方 autodetectable=true
--
-- 打击计划（来自 JSON strikePlan）:
--   Red-055-1   → DDG 113-1      7x YJ-18  (dbid=2868)
--   Red-055-2   → DDG 113-2      6x YJ-18
--   Red-052D-1  → Blue-DBID-3551 8x YJ-18
--   Red-052D-2  → Blue-DBID-2862 5x YJ-18
--   J-15-RED-01 → Blue-DBID-3551 4x YJ-83K (dbid=2137)
--   J-15-RED-02 → Blue-DBID-2862 4x YJ-83K
-- 合计: 34 枚
--
-- 红线 #20: 所有 ScenEdit_* 用 pcall(function() ... end) 包裹
-- 红线 #15: fireAt 必须是全局函数（不带 local）
-- 红线 #13: ScenEdit_AttackContact 的 mode 必须是字符串 "1"
-- ==========================================================================

local CONTACT_SETTLE = 15   -- 秒
local INTERVAL       = 1    -- 每枚间隔秒

-- ---------- totTicks: 仿真时间换算 ----------
local function totTicks(addSec)
  return string.format("%.0f", (ScenEdit_CurrentTime() + 62135596801 + addSec) * 1e7)
end

-- ---------- 全局 fireAt（红线 #15）----------
-- 负责：确认 contact 存在 → 调用 AttackContact
function fireAt(atkName, tgtName, wpnDbid, qty)
  -- 发射前再次确保蓝方 autodetectable=true（红线 #8）
  local tgt = nil
  pcall(function() tgt = ScenEdit_GetUnit({side="蓝方", name=tgtName}) end)
  if tgt and tgt.guid then
    pcall(function() ScenEdit_SetUnit({guid=tgt.guid, autodetectable=true}) end)
  end
  -- 确保红方 OMNI
  pcall(function() ScenEdit_SetSideOptions({side="红方", awareness="OMNI"}) end)

  -- 拿 contact guid（按 actualunitid 匹配，退而求其次按名称匹配）
  local contactGuid = nil
  local ok, s = pcall(function() return VP_GetSide({Side="红方"}) end)
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
    print("[fireAt] 无 contact 可攻击: " .. tostring(tgtName) .. "，请加大 contact_settle_delay")
    return false
  end

  local atk = nil
  pcall(function() atk = ScenEdit_GetUnit({side="红方", name=atkName}) end)
  if not (atk and atk.guid) then
    print("[fireAt] 攻击方单位找不到: " .. tostring(atkName))
    return false
  end

  _errnum_ = 0
  local result = false
  pcall(function()
    result = ScenEdit_AttackContact(atk.guid, contactGuid,
      {mode="1", weapon=wpnDbid, qty=qty})   -- 红线 #13: mode 必须是字符串 "1"
  end)
  print(("[fireAt] %s → %s ×%d (dbid=%d) result=%s err=%s"):format(
    atkName, tgtName, qty, wpnDbid, tostring(result), tostring(_errmsg_)))
  return result
end

-- ---------- scheduleOne: 注册单枚 TOT 时间触发器 ----------
local function scheduleOne(atkName, tgtName, wpnDbid, delayBase, k)
  local delay   = CONTACT_SETTLE + delayBase + (k - 1) * INTERVAL
  local ts      = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
  local tag     = atkName .. "_" .. tgtName .. "_" .. k .. "_" .. ts
  local evName  = "E_" .. tag
  local trName  = "T_" .. tag
  local acName  = "A_" .. tag
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

-- ---------- 打击调度（JSON strikePlan 逐条执行）----------
-- 1) Red-055-1 → DDG 113-1  7x YJ-18
for k = 1, 7 do
  scheduleOne("Red-055-1", "DDG 113-1", 2868, 0, k)
end
print("[attack] Red-055-1 → DDG 113-1: 7x YJ-18 调度完毕 (T+" .. CONTACT_SETTLE .. "s 起)")

-- 2) Red-055-2 → DDG 113-2  6x YJ-18
for k = 1, 6 do
  scheduleOne("Red-055-2", "DDG 113-2", 2868, 0, k)
end
print("[attack] Red-055-2 → DDG 113-2: 6x YJ-18 调度完毕 (T+" .. CONTACT_SETTLE .. "s 起)")

-- 3) Red-052D-1 → Blue-DBID-3551 (CVN-70)  8x YJ-18
for k = 1, 8 do
  scheduleOne("Red-052D-1", "Blue-DBID-3551", 2868, 0, k)
end
print("[attack] Red-052D-1 → Blue-DBID-3551: 8x YJ-18 调度完毕")

-- 4) Red-052D-2 → Blue-DBID-2862 (CG-59)  5x YJ-18
for k = 1, 5 do
  scheduleOne("Red-052D-2", "Blue-DBID-2862", 2868, 0, k)
end
print("[attack] Red-052D-2 → Blue-DBID-2862: 5x YJ-18 调度完毕")

-- 5) J-15-RED-01 → Blue-DBID-3551 (CVN-70)  4x YJ-83K (dbid=2137)
for k = 1, 4 do
  scheduleOne("J-15-RED-01", "Blue-DBID-3551", 2137, 0, k)
end
print("[attack] J-15-RED-01 → Blue-DBID-3551: 4x YJ-83K 调度完毕")

-- 6) J-15-RED-02 → Blue-DBID-2862 (CG-59)  4x YJ-83K
for k = 1, 4 do
  scheduleOne("J-15-RED-02", "Blue-DBID-2862", 2137, 0, k)
end
print("[attack] J-15-RED-02 → Blue-DBID-2862: 4x YJ-83K 调度完毕")

print("[attack] ===== 真延时打击调度完毕 =====")
print("[attack] 汇总: 055-1(7)+055-2(6)+052D-1(8)+052D-2(5)+J15-01(4)+J15-02(4) = 34 枚")
print("[attack] contact_settle_delay=" .. CONTACT_SETTLE .. "s | 仿真时间到达后自动发射")
