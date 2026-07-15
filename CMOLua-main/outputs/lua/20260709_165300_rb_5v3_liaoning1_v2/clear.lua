-- ============================================================
-- clear.lua: 清弹（只清发射过的弹，YJ-18 齐射前必须清弹）
-- 清弹单位: Red-055-1 / Red-052D-1 / Red-052D-2
-- J-15 使用 opts={mode="0"}，无需清弹
-- ============================================================

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

for _, name in ipairs({"Red-055-1", "Red-052D-1", "Red-052D-2"}) do
    local u = ScenEdit_GetUnit({side=_SIDE_RED, name=name})
    if u and u.guid then
        local r = ScenEdit_DumpAmmo({
            unit_guid = u.guid,
            quantity  = "all",
            weaponDbId = 2868,   -- YJ-18 dbid
        })
        print("[clear] " .. name .. " 清弹 YJ-18 -> " .. tostring(r))
    else
        print("[clear] [WARN] 找不到 " .. name)
    end
end

print("[clear] ===== 清弹完毕 =====")
