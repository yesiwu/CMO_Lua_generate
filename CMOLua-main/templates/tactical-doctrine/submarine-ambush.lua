-- submarine-ambush.lua
-- 潜艇伏击 + 电磁压制组合模板
-- 变量: {{SIDE}}, {{SUB_NAME}}, {{SUB_DBID}}, {{JAMMER_NAME}}, {{TARGET_SIDE}}

-- 1. 创建潜艇并部署到伏击区
pcall(ScenEdit_AddUnit, {
    type="Submarine",
    side="{{SIDE}}",
    name="{{SUB_NAME}}",
    dbid={{SUB_DBID}},
    latitude={{SUB_LAT}},
    longitude={{SUB_LON}},
    heading={{SUB_HEADING}},
    speed={{SUB_SPEED}},
    manualAltitude={{SUB_DEPTH}}
})

-- 2. 潜艇静默
pcall(ScenEdit_SetEMCON, "Unit", "{{SUB_NAME}}", "Sonar=Passive;Radar=Passive")
print("[SUB] {{SUB_NAME}} 已部署，静默待机")

-- 3. 创建电子战飞机（电磁压制）
pcall(ScenEdit_AddUnit, {
    type="Aircraft",
    side="{{SIDE}}",
    name="{{JAMMER_NAME}}",
    dbid={{JAMMER_DBID}},
    loadoutid={{JAMMER_LOADOUT}},
    base="{{JAMMER_BASE}}",
    proficiency="Veteran"
})

pcall(ScenEdit_SetUnit, {side="{{SIDE}}", unitname="{{JAMMER_NAME}}", timetoready_minutes=0})
pcall(ScenEdit_SetUnit, {side="{{SIDE}}", unitname="{{JAMMER_NAME}}", launch=true})

-- 4. 电磁压制航线（目标区域上空）
pcall(ScenEdit_SetUnit, {
    side="{{SIDE}}",
    unitname="{{JAMMER_NAME}}",
    course={{JAMMER_COURSE}},
    altitude={{JAMMER_ALT}},
    throttle="Cruise"
})

pcall(ScenEdit_SetEMCON, "Unit", "{{JAMMER_NAME}}", "OECM=Active")
print("[EW] {{JAMMER_NAME}} 电磁压制启动")

-- 5. 延时：潜艇发射
local attackDelay = {{ATTACK_DELAY}} or 180
local body = ("fireAt(\"{{SUB_NAME}}\", \"{{TARGET_NAME}}\", 0, {{QTY}})")

local ts = tostring(ScenEdit_CurrentTime()) .. "_sub_attack"
local evName, trName, acName = "Ev_"..ts, "Tr_"..ts, "Ac_"..ts
local script = body .. "\n" ..
    ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
    ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
    ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)

pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName,
    Time=string.format("%.0f", (ScenEdit_CurrentTime() + attackDelay) * 1e7 + 621355968000000000)})
pcall(ScenEdit_SetAction, {mode="add", type="LuaScript", name=acName, ScriptText=script})
pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
pcall(ScenEdit_SetEventAction, evName, {mode="add", name=acName})

print("[SUB-AMBUSH] 潜艇 T+" .. attackDelay .. "s 后发射")
