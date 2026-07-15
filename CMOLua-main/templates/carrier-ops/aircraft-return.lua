-- aircraft-return.lua
-- 舰载机返航两步模板
-- 变量: {{SIDE}}, {{AIRCRAFT_NAME}}, {{CARRIER_NAME}}

-- Step 1: 设置基地（必须先做！）
local ok1 = pcall(ScenEdit_SetUnit, {
    side="{{SIDE}}",
    unitname="{{AIRCRAFT_NAME}}",
    base="{{CARRIER_NAME}}"
})
if not ok1 then print("[ERROR] 设置基地失败: {{AIRCRAFT_NAME}}"); return false end

-- Step 2: 设置返航标志
local ok2 = pcall(ScenEdit_SetUnit, {
    side="{{SIDE}}",
    unitname="{{AIRCRAFT_NAME}}",
    rtb=true
})
if not ok2 then print("[ERROR] 返航失败: {{AIRCRAFT_NAME}}"); return false end

print("[RTB] {{AIRCRAFT_NAME}} 返航至 {{CARRIER_NAME}}")
return true
