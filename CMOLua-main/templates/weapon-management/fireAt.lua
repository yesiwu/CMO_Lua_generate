-- fireAt.lua
-- 攻击模板（自动选弹 / 指定弹种）
-- 变量: {{SIDE}}, {{ATTACKER_NAME}}, {{TARGET_NAME}}, {{QTY}}, {{MODE}}

local atk = ScenEdit_GetUnit({side="{{SIDE}}", name="{{ATTACKER_NAME}}"})
local tgt = ScenEdit_GetUnit({side="{{TARGET_SIDE}}", name="{{TARGET_NAME}}"})

if not (atk and atk.guid) then
    print("[ERROR] 找不到攻击方: {{ATTACKER_NAME}}")
    return false
end
if not (tgt and tgt.guid) then
    print("[ERROR] 找不到目标: {{TARGET_NAME}}")
    return false
end

-- 强制目标可探测
pcall(ScenEdit_SetUnit, {guid=tgt.guid, autodetectable=true})

-- 获取 contact
local contactGuid = nil
local ok, s = pcall(VP_GetSide, {Side="{{SIDE}}"})
if ok and s and s.contacts then
    for _, c in ipairs(s.contacts) do
        local aid = c.actualunitid or c.actualUnitID
        if aid and tostring(aid):lower() == tostring(tgt.guid):lower() then
            contactGuid = c.guid or c.Guid
            break
        end
    end
end

if not contactGuid then
    print("[ERROR] 无 contact，加大 settle 时间")
    return false
end

-- 攻击选项
local opts
if "{{MODE}}" == "auto" then
    opts = { mode="0" }
    if {{QTY}} > 0 then opts.qty = {{QTY}} end
else
    opts = { mode="1", weapon=tonumber({{WPN_DBID}}), qty={{QTY}} }
end

local r = ScenEdit_AttackContact(atk.guid, contactGuid, opts)
print(("[FIRE] {{ATTACKER_NAME}} -> {{TARGET_NAME}}, result=%s"):format(tostring(r ~= nil)))
return r ~= nil
