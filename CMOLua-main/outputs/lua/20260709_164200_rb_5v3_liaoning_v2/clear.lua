-- ============================================================
-- clear.lua: 清弹（只清发射过的弹，YJ-18 齐射前必须清弹）
-- 清弹单位: 055-Nanchang / 052D-1 / 052D-2
-- J-15 使用 opts={mode="0"}，无需清弹
-- ============================================================

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

-- 清弹列表（发射过 YJ-18 的舰艇）
local CLEAR_LIST = {
    "055-Nanchang",
    "052D-1",
    "052D-2",
}

-- 弹舱列表（每个发射架都要清空）
local MAGAZINE_LIST = {
    "055-Nanchang",
    "052D-1",
    "052D-2",
}

for _, name in ipairs(CLEAR_LIST) do
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
