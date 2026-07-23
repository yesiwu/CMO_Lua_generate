-- CMO native scoring instrumentation; generated deterministically.
-- score_spec_checksum: 168f7761a7414a234cc411a19224a4dc75a1aad54b7379ec84d36de3dfc45153
local SCORE_RULES = {{["action_name"]="p3score_act_46443fcc97b174b2",["event_name"]="p3score_evt_46443fcc97b174b2",["objective_id"]="destroy-blue-cg59",["point_change"]=100,["rule_id"]="native_score/blue_cg59",["score_side_id"]="red",["target_side_id"]="blue",["target_unit_id"]="blue_cg59",["target_unit_name"]="Blue CG-59 Princeton",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_46443fcc97b174b2"},{["action_name"]="p3score_act_06db9413ee376cc5",["event_name"]="p3score_evt_06db9413ee376cc5",["objective_id"]="destroy-blue-cvn70",["point_change"]=200,["rule_id"]="native_score/blue_cvn70",["score_side_id"]="red",["target_side_id"]="blue",["target_unit_id"]="blue_cvn70",["target_unit_name"]="Blue CVN-70 Carl Vinson",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_06db9413ee376cc5"},{["action_name"]="p3score_act_5c16b9c6b5869b50",["event_name"]="p3score_evt_5c16b9c6b5869b50",["objective_id"]="destroy-blue-ddg113-1",["point_change"]=75,["rule_id"]="native_score/blue_ddg113_1",["score_side_id"]="red",["target_side_id"]="blue",["target_unit_id"]="blue_ddg113_1",["target_unit_name"]="Blue DDG-113-1 John Finn",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_5c16b9c6b5869b50"},{["action_name"]="p3score_act_16e96bd8535f3788",["event_name"]="p3score_evt_16e96bd8535f3788",["objective_id"]="destroy-blue-ddg113-2",["point_change"]=75,["rule_id"]="native_score/blue_ddg113_2",["score_side_id"]="red",["target_side_id"]="blue",["target_unit_id"]="blue_ddg113_2",["target_unit_name"]="Blue DDG-113-2 John Finn",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_16e96bd8535f3788"},{["action_name"]="p3score_act_9916e76cc4d72b57",["event_name"]="p3score_evt_9916e76cc4d72b57",["objective_id"]="preserve-red-052d-1",["point_change"]=-75,["rule_id"]="native_score/red_052d_1",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_052d_1",["target_unit_name"]="Red 052D Kunming",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_9916e76cc4d72b57"},{["action_name"]="p3score_act_3afb4c76dde2edbb",["event_name"]="p3score_evt_3afb4c76dde2edbb",["objective_id"]="preserve-red-052d-2",["point_change"]=-75,["rule_id"]="native_score/red_052d_2",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_052d_2",["target_unit_name"]="Red 052D Nanjing",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_3afb4c76dde2edbb"},{["action_name"]="p3score_act_54a28cfffebb8665",["event_name"]="p3score_evt_54a28cfffebb8665",["objective_id"]="preserve-red-055",["point_change"]=-100,["rule_id"]="native_score/red_055_nanchang",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_055_nanchang",["target_unit_name"]="Red 055 Nanchang",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_54a28cfffebb8665"},{["action_name"]="p3score_act_e840d2e41229a643",["event_name"]="p3score_evt_e840d2e41229a643",["objective_id"]="preserve-red-j15-1",["point_change"]=-20,["rule_id"]="native_score/red_j15_1",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_j15_1",["target_unit_name"]="J-15-1",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_e840d2e41229a643"},{["action_name"]="p3score_act_3d061cadaad4600f",["event_name"]="p3score_evt_3d061cadaad4600f",["objective_id"]="preserve-red-j15-2",["point_change"]=-20,["rule_id"]="native_score/red_j15_2",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_j15_2",["target_unit_name"]="J-15-2",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_3d061cadaad4600f"},{["action_name"]="p3score_act_674ff2766687a9bd",["event_name"]="p3score_evt_674ff2766687a9bd",["objective_id"]="preserve-red-liaoning",["point_change"]=-200,["rule_id"]="native_score/red_liaoning",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_liaoning",["target_unit_name"]="Red Liaoning",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_674ff2766687a9bd"}}
local function score_log(message)
    print('[CMO-NATIVE-SCORE] ' .. tostring(message))
end
local function score_required(label, callback)
    _errnum_ = 0
    _errmsg_ = ''
    local ok, result = pcall(callback)
    local errnum = tonumber(_errnum_) or 0
    if not ok or result == nil or result == false or errnum ~= 0 then
        error('[CMO-NATIVE-SCORE] registration failed: ' .. label .. ' err=' .. tostring(_errmsg_ or ''))
    end
    score_log(label .. ' registered')
end
-- 先清理同单位旧计分事件，避免重复计分
local function remove_previous(rule)
    local event_name = rule.event_name
    local trigger_name = rule.trigger_name
    local action_name = rule.action_name
    pcall(ScenEdit_SetEvent, event_name, {mode='remove'})
    pcall(ScenEdit_SetAction, {mode='remove', type='Points', name=action_name})
    pcall(ScenEdit_SetTrigger, {mode='remove', type='UnitDestroyed', name=trigger_name})
    score_log('removed previous rule ' .. rule.rule_id)
end
-- 单条计分规则完整注册流程：触发器→计分动作→事件绑定→激活
local function install_score_rule(rule)
    remove_previous(rule)
    local ok, unit = pcall(ScenEdit_GetUnit, {side=rule.target_side_id, name=rule.target_unit_name})
    if not ok or not unit or not unit.guid then
        error('[CMO-NATIVE-SCORE] unit lookup failed: ' .. rule.target_unit_id)
    end
    score_required('trigger ' .. rule.rule_id, function() return ScenEdit_SetTrigger({mode='add', type='UnitDestroyed', name=rule.trigger_name, TargetFilter={TargetSide=rule.target_side_id, SpecificUnitID=unit.guid}}) end)
    score_required('action ' .. rule.rule_id, function() return ScenEdit_SetAction({mode='add', type='Points', name=rule.action_name, SideID=rule.score_side_id, PointChange=rule.point_change}) end)
    score_required('event ' .. rule.rule_id, function() return ScenEdit_SetEvent(rule.event_name, {mode='add', IsActive=false, IsRepeatable=false}) end)
    score_required('event trigger link ' .. rule.rule_id, function() return ScenEdit_SetEventTrigger(rule.event_name, {mode='add', name=rule.trigger_name}) end)
    score_required('event action link ' .. rule.rule_id, function() return ScenEdit_SetEventAction(rule.event_name, {mode='add', name=rule.action_name}) end)
    score_required('event activation ' .. rule.rule_id, function() return ScenEdit_SetEvent(rule.event_name, {IsActive=true}) end)
end
-- 批量安装所有计分规则
for _, rule in ipairs(SCORE_RULES) do install_score_rule(rule) end
score_log('installed native score rules=' .. tostring(#SCORE_RULES))
