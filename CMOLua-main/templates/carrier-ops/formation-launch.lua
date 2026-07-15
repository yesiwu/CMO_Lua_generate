-- formation-launch.lua
-- 编队起飞模板（错开时间避免甲板拥堵）
-- 变量: {{SIDE}}, {{CARRIER_NAME}}, {{ALTITUDE}}

local aircraftList = { {{AIRCRAFT_LIST}} }
local delay = 0

for _, name in ipairs(aircraftList) do
    local body = table.concat({
        "pcall(ScenEdit_SetUnit, {side=\"{{SIDE}}\", unitname=\"", name, "\", timetoready_minutes=0})\n",
        "pcall(ScenEdit_SetUnit, {side=\"{{SIDE}}\", unitname=\"", name, "\", launch=true})\n",
        "print(\"[FORMATION] ", name, " 起飞\")"
    })
    
    -- 使用 scheduleLua 调度
    local ts = tostring(ScenEdit_CurrentTime()) .. "_launch_" .. name
    local evName, trName, acName = "Ev_"..ts, "Tr_"..ts, "Ac_"..ts
    local script = body .. "\n" ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, 
        Time=string.format("%.0f", (ScenEdit_CurrentTime() + delay) * 1e7 + 621355968000000000)})
    pcall(ScenEdit_SetAction, {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction, evName, {mode="add", name=acName})
    
    print("[SCHEDULE] T+" .. delay .. "s: " .. name .. " 起飞")
    delay = delay + {{LAUNCH_INTERVAL}}
end

print("[FORMATION] " .. #aircraftList .. " 架飞机编队起飞已调度")
