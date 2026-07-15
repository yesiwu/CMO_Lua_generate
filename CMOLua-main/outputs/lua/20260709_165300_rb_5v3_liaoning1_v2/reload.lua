-- ============================================================
-- reload.lua: 装弹（装填 JSON 指定的弹）
-- 装弹单位: Red-055-1 / Red-052D-1 / Red-052D-2
-- 弹药: YJ-18 (dbid=2868)
-- J-15 使用 opts={mode="0"}，无需装弹
-- ============================================================

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

local RELOAD_LIST = {
    {name="Red-055-1",  wpn=2868, qty=13},   -- 055 双舰合计 13 枚（仅 055-1 有坐标，全打 DDG 113-1）
    {name="Red-052D-1", wpn=2868, qty=8},    -- 对 CVN-70 发射 8 枚
    {name="Red-052D-2", wpn=2868, qty=5},    -- 对 CG-59 发射 5 枚
}

for _, entry in ipairs(RELOAD_LIST) do
    local u = ScenEdit_GetUnit({side=_SIDE_RED, name=entry.name})
    if u and u.guid then
        local r = ScenEdit_SetAircraftLoadout({
            unit_guid   = u.guid,
            weapon_db_id = entry.wpn,
            loadout_id  = entry.wpn,
            mount_guid  = "",
            quantity    = entry.qty,
        })
        print("[reload] " .. entry.name .. " 装弹 " .. entry.qty .. "x YJ-18 -> " .. tostring(r))
    else
        print("[reload] [WARN] 找不到 " .. entry.name)
    end
end

print("[reload] ===== 装弹完毕 =====")
