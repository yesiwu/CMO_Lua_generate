-- ==========================================================================
-- reload.lua  装弹（只装 JSON 指定弹药）
-- 装弹单位/数量:
--   Red-055-1   YJ-18 ×7
--   Red-055-2   YJ-18 ×6    （055 双舰合计 13 枚，7+6 分配）
--   Red-052D-1  YJ-18 ×8    → 打 Blue-DBID-3551 (CVN-70)
--   Red-052D-2  YJ-18 ×5    → 打 Blue-DBID-2862 (CG-59)
-- J-15 不装弹，loadoutId=9682 已在 main.lua 中设定
-- 红线 #20: 所有 ScenEdit_* 用 pcall(function() ... end) 包裹
-- ==========================================================================

local SIDE_RED  = "红方"
local YJ18_DBID = 2868   -- YJ-18 [3M54E Klub Copy]，MCP 已验证

local RELOAD_LIST = {
  {name="Red-055-1",  qty=7},
  {name="Red-055-2",  qty=6},
  {name="Red-052D-1", qty=8},
  {name="Red-052D-2", qty=5},
}

for _, entry in ipairs(RELOAD_LIST) do
  local u = nil
  pcall(function() u = ScenEdit_GetUnit({side=SIDE_RED, name=entry.name}) end)
  if u and u.guid then
    pcall(function() ScenEdit_AddReloadsToUnit({
      side      = SIDE_RED,
      unitname  = entry.name,
      wpn_dbid  = YJ18_DBID,
      number    = entry.qty,
    }) end)
    print("[reload] " .. entry.name .. " 装弹 " .. entry.qty .. "x YJ-18 完毕")
  else
    print("[reload] [WARN] 找不到: " .. entry.name)
  end
end

print("[reload] ===== 装弹完毕 =====")
print("[reload] 汇总: 055-1(7)+055-2(6)+052D-1(8)+052D-2(5) = 26x YJ-18")
