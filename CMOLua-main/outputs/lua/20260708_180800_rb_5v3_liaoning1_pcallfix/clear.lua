-- ==========================================================================
-- clear.lua  清弹（只清 YJ-18，J-15 不清弹）
-- 清弹单位: Red-055-1 / Red-055-2 / Red-052D-1 / Red-052D-2
-- 弹药: YJ-18 dbid=2868
-- 红线 #20: 所有 ScenEdit_* 用 pcall(function() ... end) 包裹
-- ==========================================================================

local SIDE_RED  = "红方"
local YJ18_DBID = 2868   -- YJ-18 [3M54E Klub Copy]，MCP 已验证

local CLEAR_LIST = {
  "Red-055-1",
  "Red-055-2",
  "Red-052D-1",
  "Red-052D-2",
}

-- 正确清弹逻辑（此前已总结过，务必遵守）：
--   * 不能用 remove_weapon / DumpAmmo 删记录——那会把 mount 格子也删掉，
--     导致后续 AddReloadsToUnit 找不到兼容 mount，弹装不回去。
--   * 正确做法：遍历 u.mounts -> m.mount_weapons，快照 wpn_current>0 的武器，
--     再逐条 AddReloadsToUnit({guid, wpn_dbid, mount_guid, number, remove=true})
--     仅扣减数量、保留格子。
local function clearUnitWeapons(name)
  local u = nil
  pcall(function() u = ScenEdit_GetUnit({side=SIDE_RED, name=name}) end)
  if not (u and u.guid) then
    print("[clear] [WARN] 找不到: " .. name)
    return false
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
  for _, j in ipairs(jobs) do
    _errnum_ = 0
    pcall(function() ScenEdit_AddReloadsToUnit({
      guid       = u.guid,
      wpn_dbid   = j.dbid,
      mount_guid = j.mountid,
      number     = j.num,
      remove     = true,
    }) end)
    if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
  end
  print(("[clear] %s: 减载归零 %d 项 (失败 %d)"):format(name, done, fail))
  return fail == 0
end

for _, name in ipairs(CLEAR_LIST) do
  clearUnitWeapons(name)
end

print("[clear] ===== 清弹完毕 =====")
