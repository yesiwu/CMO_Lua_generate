-- bait-and-ambush.lua
-- 消耗与诱歼模板
-- 变量: {{SIDE}}, {{BAIT_UNITS}}, {{AMBUSH_UNITS}}, {{TARGET_SIDE}}

-- 阶段 1: 诱饵出动（暴露位置吸引火力）
local baitUnits = { {{BAIT_UNITS}} }

for _, bait in ipairs(baitUnits) do
    -- 诱饵前出，主动暴露
    pcall(ScenEdit_SetUnit, {
        side="{{SIDE}}",
        unitname=bait.name,
        course=bait.course,
        speed=bait.speed or 20,
        throttle="Cruise"
    })
    pcall(ScenEdit_SetEMCON, "Unit", bait.guid, "Radar=Active")
    print("[BAIT] " .. bait.name .. " 前出诱敌")
end

-- 阶段 2: 等待敌方消耗弹药（延时）
local ambushDelay = {{AMBUSH_DELAY}} or 300  -- 默认 5 分钟

-- 阶段 3: 伏击群突击
local ambushBody = ""
local ambushUnits = { {{AMBUSH_UNITS}} }

for _, ambush in ipairs(ambushUnits) do
    ambushBody = ambushBody .. ("fireAt(\"%s\", \"%s\", 0, %d)\n"):format(
        ambush.name, ambush.target, ambush.qty or 8)
end

-- 调度伏击
local ts = tostring(ScenEdit_CurrentTime()) .. "_ambush"
local evName, trName, acName = "Ev_"..ts, "Tr_"..ts, "Ac_"..ts
local script = ambushBody ..
    ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName) ..
    ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName) ..
    ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)

pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName,
    Time=string.format("%.0f", (ScenEdit_CurrentTime() + ambushDelay) * 1e7 + 621355968000000000)})
pcall(ScenEdit_SetAction, {mode="add", type="LuaScript", name=acName, ScriptText=script})
pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
pcall(ScenEdit_SetEventAction, evName, {mode="add", name=acName})

print("[AMBUSH] 伏击群 T+" .. ambushDelay .. "s 后突击")
