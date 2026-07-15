-- weapon-clear.lua
-- 清弹模板（清空单位所有武器）
-- 变量: {{SIDE}}, {{UNIT_NAME}}

local u = ScenEdit_GetUnit({side="{{SIDE}}", name="{{UNIT_NAME}}"})
if not u or not u.guid then
    print("[WARN] 找不到: {{SIDE}}/{{UNIT_NAME}}")
    return false
end

local jobs = {}
for _, m in ipairs(u.mounts or {}) do
    for _, w in ipairs(m.mount_weapons or {}) do
        local cur = tonumber(w.wpn_current) or 0
        if cur > 0 then
            jobs[#jobs + 1] = {
                dbid = w.wpn_dbid,
                num = cur,
                mountid = m.mount_guid
            }
        end
    end
end

local done, fail = 0, 0
for _, j in ipairs(jobs) do
    _errnum_ = 0
    ScenEdit_AddReloadsToUnit({
        guid = u.guid,
        wpn_dbid = j.dbid,
        mount_guid = j.mountid,
        number = j.num,
        remove = true
    })
    if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
end

print(("[CLEAR] {{UNIT_NAME}}: 清空 %d 条 (失败 %d)"):format(done, fail))
return fail == 0
