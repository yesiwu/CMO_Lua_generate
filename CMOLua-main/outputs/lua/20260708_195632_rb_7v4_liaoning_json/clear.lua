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
