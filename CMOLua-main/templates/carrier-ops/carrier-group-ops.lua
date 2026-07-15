-- carrier-group-ops.lua
-- 航母打击群完整作业模板
-- 变量: {{SIDE}}, {{CARRIER_NAME}}, {{AIR_WING}}, {{TARGETS}}

local side = "{{SIDE}}"
local carrier = "{{CARRIER_NAME}}"

-- 1. 检查航母状态
local c = ScenEdit_GetUnit({side=side, name=carrier})
if not c then print("[ERROR] 航母不存在"); return false end
if (c.damage or 0) > 0.8 then print("[ERROR] 航母严重损伤"); return false end

print("[CSG] 航母打击群作业开始")

-- 2. 第一波：CAP（战斗空中巡逻）
local capAircraft = { {{CAP_AIRCRAFT}} }
for _, ac in ipairs(capAircraft) do
    pcall(ScenEdit_AddUnit, {
        type="Aircraft", side=side, name=ac.name, dbid=ac.dbid,
        loadoutid=ac.loadout, base=carrier, proficiency="Veteran"
    })
    pcall(ScenEdit_SetUnit, {side=side, unitname=ac.name, timetoready_minutes=0})
    pcall(ScenEdit_SetUnit, {side=side, unitname=ac.name, launch=true})
    pcall(ScenEdit_SetUnit, {
        side=side, unitname=ac.name,
        course=ac.course, altitude=ac.alt, throttle="Cruise"
    })
    print("[CAP] " .. ac.name .. " 起飞")
end

-- 3. 第二波：反舰打击
local strikeAircraft = { {{STRIKE_AIRCRAFT}} }
for _, ac in ipairs(strikeAircraft) do
    pcall(ScenEdit_AddUnit, {
        type="Aircraft", side=side, name=ac.name, dbid=ac.dbid,
        loadoutid=ac.loadout, base=carrier, proficiency="Veteran"
    })
    pcall(ScenEdit_SetUnit, {side=side, unitname=ac.name, timetoready_minutes=0})
    pcall(ScenEdit_SetUnit, {side=side, unitname=ac.name, launch=true})
    pcall(ScenEdit_SetUnit, {
        side=side, unitname=ac.name,
        course=ac.course, altitude=ac.alt, throttle="Cruise"
    })
    print("[STRIKE] " .. ac.name .. " 起飞")
end

-- 4. 延时攻击
local targets = { {{TARGETS}} }
for i, ac in ipairs(strikeAircraft) do
    local tgt = targets[i] or targets[1]
    local delay = {{SETTLE_AIR}} + (i-1)*5
    local body = ("fireAt(\"%s\", \"%s\", 0, %d)"):format(ac.name, tgt.name, tgt.qty or 4)
    
    local ts = tostring(ScenEdit_CurrentTime()) .. "_csg_" .. ac.name
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
    
    print("[SCHEDULE] T+" .. delay .. "s: " .. ac.name .. " -> " .. tgt.name)
end

-- 5. 延时返航
for _, ac in ipairs(strikeAircraft) do
    local rtbDelay = {{SETTLE_AIR}} + 120
    local body = table.concat({
        ("pcall(ScenEdit_SetUnit, {side=\"%s\", unitname=\"%s\", base=\"%s\"})\n"):format(side, ac.name, carrier),
        ("pcall(ScenEdit_SetUnit, {side=\"%s\", unitname=\"%s\", rtb=true})\n"):format(side, ac.name),
        ("print(\"[RTB] %s 返航\")"):format(ac.name)
    })
    
    local ts = tostring(ScenEdit_CurrentTime()) .. "_rtb_" .. ac.name
    local evName, trName, acName = "Ev_"..ts, "Tr_"..ts, "Ac_"..ts
    local script = body .. "\n" ..
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName,
        Time=string.format("%.0f", (ScenEdit_CurrentTime() + rtbDelay) * 1e7 + 621355968000000000)})
    pcall(ScenEdit_SetAction, {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction, evName, {mode="add", name=acName})
end

print("[CSG] 航母打击群作业已调度")
