-- damage-assessment.lua
-- 毁伤评估与终止判断模板
-- 变量: {{SIDE}}, {{TARGET_SIDE}}, {{DAMAGE_THRESHOLD}}

local targets = { {{TARGETS}} }
local allDestroyed = true

for _, tgt in ipairs(targets) do
    local u = ScenEdit_GetUnit({side="{{TARGET_SIDE}}", name=tgt.name})
    if not u then
        print(("[ASSESS] %s: 已摧毁（单位不存在）"):format(tgt.name))
    else
        local damage = u.damage or 0
        local damagePct = damage * 100
        
        print(("[ASSESS] %s: 损伤 %.1f%%"):format(tgt.name, damagePct))
        
        if damagePct < {{DAMAGE_THRESHOLD}} then
            allDestroyed = false
            print(("[ASSESS] %s: 未达到阈值 (%d%%)"):format(tgt.name, {{DAMAGE_THRESHOLD}}))
        else
            print(("[ASSESS] %s: 达到阈值，判定摧毁"):format(tgt.name))
        end
    end
end

if allDestroyed then
    print("[MISSION] 所有目标达成毁伤阈值，任务完成")
    return "COMPLETE"
else
    print("[MISSION] 部分目标未达到阈值，继续打击")
    return "CONTINUE"
end
