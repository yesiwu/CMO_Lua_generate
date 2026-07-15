-- weapon-reload.lua
-- 装弹模板
-- 变量: {{SIDE}}, {{UNIT_NAME}}, {{WPN_DBID}}, {{QTY}}

_errnum_ = 0
local ok = pcall(ScenEdit_AddReloadsToUnit, {
    side = "{{SIDE}}",
    unitname = "{{UNIT_NAME}}",
    wpn_dbid = {{WPN_DBID}},
    number = {{QTY}}
})

print(("[RELOAD] {{UNIT_NAME}} x%d (wpn={{WPN_DBID}}) ok=%s"):format({{QTY}}, tostring(ok)))
return ok
