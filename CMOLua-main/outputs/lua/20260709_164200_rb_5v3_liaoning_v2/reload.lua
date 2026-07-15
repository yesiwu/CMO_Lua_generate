-- ============================================================
-- reload.lua: 装弹（装填 JSON 指定的弹）
-- 装弹单位: 055-Nanchang / 052D-1 / 052D-2
-- 弹药: YJ-18 (dbid=2868)
-- J-15 使用 opts={mode="0"}，无需装弹
-- ============================================================

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

-- 装弹列表（与 CLEAR_LIST 对应）
local RELOAD_LIST = {
    {name="055-Nanchang", wpn=2868, qty=13},   -- 对 DDG-113-1+2 各发射 13 枚
    {name="052D-1",      wpn=2868, qty=8},     -- 对 CVN-70 发射 8 枚
    {name="052D-2",      wpn=2868, qty=5},     -- 对 CG-59 发射 5 枚
}

for _, entry in ipairs(RELOAD_LIST) do
    local u = ScenEdit_GetUnit({side=_SIDE_RED, name=entry.name})
    if u and u.guid then
        local r = ScenEdit_SetAircraftLoadout({
            unit_guid    = u.guid,
            weapon_db_id  = entry.wpn,
            loadout_id   = entry.wpn,
            mount_guid   = "",
            quantity     = entry.qty,
        })
        print("[reload] " .. entry.name .. " 装弹 " .. entry.qty .. "x YJ-18 -> " .. tostring(r))
    else
        print("[reload] [WARN] 找不到 " .. entry.name)
    end
end

print("[reload] ===== 装弹完毕 =====")
