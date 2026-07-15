-- tot-strike.lua
-- TOT 时间协同攻击模板（多平台同时到达）
-- 变量: {{SIDE}}, {{TOT_TIME}}, {{TARGET_NAME}}

local attackers = { {{ATTACKERS}} }
local tot = {{TOT_TIME}}  -- 目标到达时间（秒，相对于当前）

for _, atk in ipairs(attackers) do
    -- 计算各平台发射延时
    -- 假设：导弹飞行时间 = 距离 / 速度
    local flightTime = atk.distance / atk.missileSpeed
    local launchDelay = tot - flightTime
    
    if launchDelay < 0 then
        print(("[WARN] %s 无法按时到达，需提前 %ds 发射"):format(atk.name, -launchDelay))
        launchDelay = 0
    end
    
    local body = ("fireAt(\"%s\", \"%s\", 0, %d)"):format(atk.name, "{{TARGET_NAME}}", atk.qty)
    
    -- scheduleLua
    local ts = tostring(ScenEdit_CurrentTime()) .. "_tot_" .. atk.name
    local evName, trName, acName = "Ev_"..ts, "Tr_"..ts, "Ac_"..ts
    local script = body .. "\n" ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName,
        Time=string.format("%.0f", (ScenEdit_CurrentTime() + launchDelay) * 1e7 + 621355968000000000)})
    pcall(ScenEdit_SetAction, {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction, evName, {mode="add", name=acName})
    
    print(("[TOT] %s: T+%ds 发射，飞行 %ds，预计同时到达"):format(
        atk.name, launchDelay, flightTime))
end

print("[TOT] 时间协同攻击已调度，目标到达时间 T+" .. tot .. "s")
