-- carrier-strike-cycle.lua
-- 完整舰载机打击周期模板
-- 变量: {{SIDE}}, {{CARRIER_NAME}}, {{AIRCRAFT_NAME}}, {{TARGET_NAME}}, {{DBID}}, {{LOADOUT_ID}}, {{SETTLE_AIR}}

-- 1. 起飞
local ok = pcall(ScenEdit_AddUnit, {
    type="Aircraft", side="{{SIDE}}", name="{{AIRCRAFT_NAME}}",
    dbid={{DBID}}, loadoutid={{LOADOUT_ID}}, base="{{CARRIER_NAME}}",
    proficiency="Veteran"
})
if not ok then print("[ERROR] 创建失败"); return false end

pcall(ScenEdit_SetUnit, {side="{{SIDE}}", unitname="{{AIRCRAFT_NAME}}", timetoready_minutes=0})
pcall(ScenEdit_SetUnit, {side="{{SIDE}}", unitname="{{AIRCRAFT_NAME}}", launch=true})
print("[LAUNCH] {{AIRCRAFT_NAME}} 已起飞")

-- 2. 设置航路（朝目标方向）
pcall(ScenEdit_SetUnit, {
    side="{{SIDE}}", unitname="{{AIRCRAFT_NAME}}",
    course={{ {{WAYPOINTS}} }},
    altitude={{ALTITUDE}}, throttle="Cruise"
})

-- 3. 延时攻击（等飞到射程）
function totTicks(addSeconds)
    return string.format("%.0f", (ScenEdit_CurrentTime() + addSeconds) * 1e7 + 621355968000000000)
end

function scheduleLua(luaBody, delay, tag)
    local ts = tostring(ScenEdit_CurrentTime()) .. "_" .. tag
    local evName, trName, acName = "Ev_"..ts, "Tr_"..ts, "Ac_"..ts
    local script = table.concat({
        luaBody, "\n",
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName),
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName),
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName),
    })
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=totTicks(delay)})
    pcall(ScenEdit_SetAction, {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction, evName, {mode="add", name=acName})
end

-- 4. 调度攻击
local attackBody = "fireAt(\"{{AIRCRAFT_NAME}}\", \"{{TARGET_NAME}}\", 0, {{QTY}})"
scheduleLua(attackBody, {{SETTLE_AIR}}, "air_attack_{{AIRCRAFT_NAME}}")
print("[SCHEDULE] T+{{SETTLE_AIR}}s: {{AIRCRAFT_NAME}} -> {{TARGET_NAME}}")

-- 5. 延时返航（攻击后 120 秒）
local rtbBody = table.concat({
    "pcall(ScenEdit_SetUnit, {side=\"{{SIDE}}\", unitname=\"{{AIRCRAFT_NAME}}\", base=\"{{CARRIER_NAME}}\"})\n",
    "pcall(ScenEdit_SetUnit, {side=\"{{SIDE}}\", unitname=\"{{AIRCRAFT_NAME}}\", rtb=true})\n",
    "print(\"[RTB] {{AIRCRAFT_NAME}} 返航\")"
})
scheduleLua(rtbBody, {{SETTLE_AIR}} + 120, "rtb_{{AIRCRAFT_NAME}}")
print("[SCHEDULE] T+" .. ({{SETTLE_AIR}} + 120) .. "s: {{AIRCRAFT_NAME}} 返航")
