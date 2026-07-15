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
