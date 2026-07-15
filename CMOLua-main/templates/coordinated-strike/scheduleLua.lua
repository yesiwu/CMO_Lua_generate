-- scheduleLua.lua
-- 通用延时调度器模板
-- 变量: {{LUA_BODY}}, {{DELAY}}, {{TAG}}

function totTicks(addSeconds)
    return string.format("%.0f", (ScenEdit_CurrentTime() + addSeconds) * 1e7 + 621355968000000000)
end

local ts = tostring(ScenEdit_CurrentTime()) .. "_" .. "{{TAG}}"
local evName, trName, acName = "Ev_"..ts, "Tr_"..ts, "Ac_"..ts

local script = table.concat({
    "{{LUA_BODY}}", "\n",
    ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName),
    ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName),
    ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName),
})

pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=totTicks({{DELAY}})})
pcall(ScenEdit_SetAction, {mode="add", type="LuaScript", name=acName, ScriptText=script})
pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
pcall(ScenEdit_SetEventAction, evName, {mode="add", name=acName})

print(("[SCHEDULE] T+%ds: {{TAG}}"):format({{DELAY}}))
