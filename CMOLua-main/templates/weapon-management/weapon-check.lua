-- weapon-check.lua
-- 弹药检查模板
-- 变量: {{SIDE}}, {{UNIT_NAME}}

local u = ScenEdit_GetUnit({side="{{SIDE}}", name="{{UNIT_NAME}}"})
if not u then print("[ERROR] 找不到: {{UNIT_NAME}}"); return nil end

local totalWpn = 0
for _, m in ipairs(u.mounts or {}) do
    for _, w in ipairs(m.mount_weapons or {}) do
        totalWpn = totalWpn + (tonumber(w.wpn_current) or 0)
    end
end

local fuelPct = (u.fuel or 0) / (u.fuelmax or 1) * 100

print(("[STATUS] {{UNIT_NAME}}: 弹药=%d, 燃油=%.1f%%"):format(totalWpn, fuelPct))

if totalWpn == 0 then
    print("[STATUS] {{UNIT_NAME}}: Winchester (弹药耗尽)")
    return "Winchester"
elseif fuelPct < 30 then
    print("[STATUS] {{UNIT_NAME}}: Bingo (燃油不足)")
    return "Bingo"
else
    return "OK"
end
