-- aircraft-launch.lua
-- 舰载机起飞三步模板
-- 变量: {{SIDE}}, {{AIRCRAFT_NAME}}, {{DBID}}, {{LOADOUT_ID}}, {{CARRIER_NAME}}

local ok = pcall(ScenEdit_AddUnit, {
    type="Aircraft", side="{{SIDE}}", name="{{AIRCRAFT_NAME}}",
    dbid={{DBID}}, loadoutid={{LOADOUT_ID}}, base="{{CARRIER_NAME}}",
    proficiency="Veteran"
})
if not ok then print("[ERROR] 创建失败: {{AIRCRAFT_NAME}}"); return false end

local ok2 = pcall(ScenEdit_SetUnit, {
    side="{{SIDE}}", unitname="{{AIRCRAFT_NAME}}", timetoready_minutes=0
})
if not ok2 then print("[ERROR] 准备时间归零失败"); return false end

local ok3 = pcall(ScenEdit_SetUnit, {
    side="{{SIDE}}", unitname="{{AIRCRAFT_NAME}}", launch=true
})
if not ok3 then print("[ERROR] 起飞失败"); return false end

print("[LAUNCH] {{AIRCRAFT_NAME}} 已起飞")
return true
