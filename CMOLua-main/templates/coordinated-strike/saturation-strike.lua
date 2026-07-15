-- saturation-strike.lua
-- 饱和攻击模板（多波次、多方向、时间协同）
-- 变量: {{SIDE}}, {{SETTLE_TIME}}, {{WAVE_INTERVAL}}

local waves = { {{WAVES}} }
local baseDelay = {{SETTLE_TIME}}

for waveNum, wave in ipairs(waves) do
    local waveDelay = baseDelay + (waveNum - 1) * {{WAVE_INTERVAL}}
    
    print(("[WAVE] 第%d波 调度，T+%ds"):format(waveNum, waveDelay))
    
    for _, attacker in ipairs(wave.attackers) do
        -- 每架/舰错开 5 秒
        for i, unitName in ipairs(attacker.units) do
            local unitDelay = waveDelay + (i - 1) * 5
            local body = ("fireAt(\"%s\", \"%s\", 0, %d)"):format(
                unitName, attacker.target, attacker.qty or 4)
            
            -- scheduleLua 调用
            local ts = tostring(ScenEdit_CurrentTime()) .. "_wave" .. waveNum .. "_" .. unitName
            local evName, trName, acName = "Ev_"..ts, "Tr_"..ts, "Ac_"..ts
            local script = body .. "\n" ..
                ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
                ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
                ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
            
            pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName,
                Time=string.format("%.0f", (ScenEdit_CurrentTime() + unitDelay) * 1e7 + 621355968000000000)})
            pcall(ScenEdit_SetAction, {mode="add", type="LuaScript", name=acName, ScriptText=script})
            pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
            pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
            pcall(ScenEdit_SetEventAction, evName, {mode="add", name=acName})
            
            print(("  [SCHEDULE] %s -> %s, T+%ds"):format(unitName, attacker.target, unitDelay))
        end
    end
end

print("[SATURATION] 饱和攻击已调度")
