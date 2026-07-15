-- mission-termination.lua
-- 任务终止条件检查模板
-- 变量: {{SIDE}}, {{TARGET_SIDE}}, {{MAX_LOSSES}}, {{DAMAGE_THRESHOLD}}

local function checkTermination()
    -- 检查 1: 我方损失是否超限
    local friendlyLosses = 0
    local friendlyUnits = { {{FRIENDLY_UNITS}} }
    
    for _, name in ipairs(friendlyUnits) do
        local u = ScenEdit_GetUnit({side="{{SIDE}}", name=name})
        if not u then
            friendlyLosses = friendlyLosses + 1
            print(("[TERM] 我方损失: %s"):format(name))
        end
    end
    
    if friendlyLosses >= {{MAX_LOSSES}} then
        print(("[TERM] 我方损失 %d 个单位，超过阈值 %d，任务失败"):format(
            friendlyLosses, {{MAX_LOSSES}}))
        return "FAILED"
    end
    
    -- 检查 2: 敌方毁伤是否达标
    local targetDestroyed = 0
    local targetTotal = 0
    local targets = { {{TARGETS}} }
    
    for _, tgt in ipairs(targets) do
        targetTotal = targetTotal + 1
        local u = ScenEdit_GetUnit({side="{{TARGET_SIDE}}", name=tgt.name})
        if not u or (u.damage or 0) * 100 >= {{DAMAGE_THRESHOLD}} then
            targetDestroyed = targetDestroyed + 1
        end
    end
    
    if targetDestroyed >= targetTotal then
        print("[TERM] 所有目标达成毁伤阈值，任务完成")
        return "COMPLETE"
    end
    
    -- 检查 3: 时间限制（可选）
    local elapsed = ScenEdit_CurrentTime() - {{START_TIME}}
    if elapsed > {{MAX_DURATION}} then
        print(("[TERM] 任务超时 %ds，强制终止"):format(elapsed))
        return "TIMEOUT"
    end
    
    return "CONTINUE"
end

local status = checkTermination()
print(("[STATUS] 任务状态: %s"):format(status))
return status
