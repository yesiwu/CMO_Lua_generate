-- ============================================================
-- candidate_baseline_template.lua
-- 固定脚本骨架 + 显式策略槽位；用于 Baseline 与四候选的可控渲染。
-- scenario_id: red_blue_6v4_liaoning
-- runtime: cmo_naval_air_anti_surface_instrumented@3.0.0
--
-- 设计约束：
--  1) 只使用 canonical side: red / blue；检测到红方/蓝方旧资产立即失败。
--  2) awareness=Normal，不启用全知或强制可探测。
--  3) 所有未来事件只调用 baseline_* 全局入口，避免局部函数在事件脚本中不可见。
--  4) J-15 低空前出、跃升开雷达，建立真实 contact；舰艇等待共享 contact 后攻击。
--  5) 官方分数只表示任务结果；[ATTACK-TRACE]/[PROCESS-VECTOR] 表示执行过程。
--  6) 候选只能替换 STRATEGY 中映射过的槽位，固定状态机不允许修改。
-- ============================================================

local SIDE_RED = 'red'
local SIDE_BLUE = 'blue'
local SIDE_RED_ALIAS = '红方'
local SIDE_BLUE_ALIAS = '蓝方'
local SHIP_WEAPON_DBID = 2868
local JSON_NULL = {}

-- ============================================================
-- STRATEGY SLOTS: renderer 只替换本表中的占位符
-- ============================================================
local STRATEGY = {
    candidate_id = 'baseline',
    hypothesis = '真实传感器与共享航迹能够使红方至少形成一次有效武器释放',
    mechanism = 'J-15低空前出后跃升开雷达，红方舰艇利用共享contact实施超视距反舰打击',
    attacks = {
        {
            id='red_055_attack', kind='ship', attacker_id='red_055_nanchang',
            target_id='blue_ddg113_1', delay_seconds=30,
            quantity=8, weapon_dbid=SHIP_WEAPON_DBID,
            max_range_nm=285, poll_seconds=15, max_attempts=120,
        },
        {
            id='red_052d_1_attack', kind='ship', attacker_id='red_052d_1',
            target_id='blue_cg59', delay_seconds=45,
            quantity=8, weapon_dbid=SHIP_WEAPON_DBID,
            max_range_nm=285, poll_seconds=15, max_attempts=120,
        },
        {
            id='red_052d_2_attack', kind='ship', attacker_id='red_052d_2',
            target_id='blue_cg59', delay_seconds=60,
            quantity=5, weapon_dbid=SHIP_WEAPON_DBID,
            max_range_nm=285, poll_seconds=15, max_attempts=120,
        },
        {
            id='red_j15_1_attack', kind='air', attacker_id='red_j15_1',
            target_id='blue_cvn70', delay_seconds=5,
            quantity=4, weapon_dbid=nil, base_id='red_liaoning',
            ingress_altitude_m=200, popup_altitude_m=9500,
            popup_range_nm=95, attack_range_nm=80,
            mid_lat_offset=1.5, mid_lon_offset=0.0,
            approach_lat_offset=0.7, approach_lon_offset=0.0,
            poll_seconds=10, max_attempts=210, return_delay_seconds=120,
        },
        {
            id='red_j15_2_attack', kind='air', attacker_id='red_j15_2',
            target_id='blue_ddg113_2', delay_seconds=20,
            quantity=4, weapon_dbid=nil, base_id='red_liaoning',
            ingress_altitude_m=200, popup_altitude_m=9500,
            popup_range_nm=95, attack_range_nm=80,
            mid_lat_offset=1.5, mid_lon_offset=0.05,
            approach_lat_offset=0.7, approach_lon_offset=0.05,
            poll_seconds=10, max_attempts=210, return_delay_seconds=120,
        },
    },
}

local UNIT_CATALOG = {
    red_055_nanchang={side=SIDE_RED,name='红方055南昌舰',type='Ship',dbid=3883,lat=23.8000,lon=128.5000,heading=135,speed=25,proficiency='Veteran',route_lat=22.3500,route_lon=129.1500,weapon_quantity=16},
    red_052d_1={side=SIDE_RED,name='红方052D-1昆明舰',type='Ship',dbid=2296,lat=23.5000,lon=128.1000,heading=115,speed=25,proficiency='Veteran',route_lat=22.4500,route_lon=129.0000,weapon_quantity=16},
    red_052d_2={side=SIDE_RED,name='红方052D-2南京舰',type='Ship',dbid=3586,lat=23.2000,lon=128.0000,heading=80,speed=25,proficiency='Veteran',route_lat=22.0500,route_lon=129.0500,weapon_quantity=10},
    red_liaoning={side=SIDE_RED,name='红方辽宁舰',type='Ship',dbid=2007,lat=25.0000,lon=130.0000,heading=180,speed=20,proficiency='Veteran',route_lat=24.0000,route_lon=129.8500},
    red_j15_1={side=SIDE_RED,name='J-15-1',type='Air',dbid=2496,base_id='red_liaoning',loadoutid=9682,proficiency='Veteran'},
    red_j15_2={side=SIDE_RED,name='J-15-2',type='Air',dbid=2496,base_id='red_liaoning',loadoutid=9682,proficiency='Veteran'},
    blue_cvn70={side=SIDE_BLUE,name='蓝方CVN-70卡尔文森',type='Ship',dbid=3551,lat=21.5419,lon=129.9125,heading=294,speed=0,proficiency='Veteran',score_value=200},
    blue_cg59={side=SIDE_BLUE,name='蓝方CG-59普林斯顿',type='Ship',dbid=2862,lat=21.6100,lon=130.1791,heading=295,speed=0,proficiency='Veteran',score_value=100},
    blue_ddg113_1={side=SIDE_BLUE,name='蓝方DDG-113-1约翰芬恩',type='Ship',dbid=4299,lat=21.4200,lon=130.1713,heading=293,speed=0,proficiency='Veteran',score_value=75},
    blue_ddg113_2={side=SIDE_BLUE,name='蓝方DDG-113-2约翰芬恩',type='Ship',dbid=4299,lat=21.6000,lon=130.2000,heading=293,speed=0,proficiency='Veteran',score_value=75},
}

local EXPECTED_RED_IDS={'red_055_nanchang','red_052d_1','red_052d_2','red_liaoning','red_j15_1','red_j15_2'}
local EXPECTED_BLUE_IDS={'blue_cvn70','blue_cg59','blue_ddg113_1','blue_ddg113_2'}
local ATTACK_BY_ID={}
local ATTACK_RUNTIME={}
local TRACE={}

local function runtime_log(message)
    print('[BASELINE] ' .. tostring(message))
end

local function json_escape(value)
    local s=tostring(value or '')
    s=s:gsub('\\','\\\\'):gsub('"','\\"'):gsub('\r','\\r'):gsub('\n','\\n'):gsub('\t','\\t')
    return s
end

local function json_scalar(value)
    if value == JSON_NULL then return 'null' end
    local t=type(value)
    if t == 'boolean' then return value and 'true' or 'false' end
    if t == 'number' then return tostring(value) end
    return '"' .. json_escape(value) .. '"'
end

local TRACE_KEYS={
    'candidate_id','attack_id','kind','attacker_id','target_id','stage','scheduled','triggered',
    'attacker_found','target_found','contact_acquired','airborne','reached_attack_range',
    'fire_called','fire_accepted','weapon_released','hit','damage_percent','failure_stage',
    'attempt','range_nm','contact_guid','classification','detail'
}

local function emit_json(prefix, object, ordered_keys)
    local parts={}
    local keys=ordered_keys or {}
    for _,key in ipairs(keys) do
        local value=object[key]
        if value ~= nil then parts[#parts+1]='"'..json_escape(key)..'":'..json_scalar(value) end
    end
    print(prefix .. ' {' .. table.concat(parts, ',') .. '}')
end

local function trace_update(attack_id, patch)
    local state=TRACE[attack_id]
    if not state then return end
    for key,value in pairs(patch or {}) do state[key]=value end
    emit_json('[ATTACK-TRACE]', state, TRACE_KEYS)
end

local function lookup_unit(side, name)
    local ok, unit=pcall(ScenEdit_GetUnit,{side=side,name=name})
    if ok and unit and unit.guid then return unit end
    return nil
end

local function unit_by_id(unit_id)
    local spec=UNIT_CATALOG[unit_id]
    if not spec then return nil end
    return lookup_unit(spec.side,spec.name)
end

local function checked_cmo_call(label, fn, args)
    _errnum_=0
    _errmsg_=''
    local ok,result=pcall(fn,args)
    local errnum=tonumber(_errnum_) or 0
    local success=ok and result ~= nil and result ~= false and errnum == 0
    runtime_log(label .. ' success=' .. tostring(success) .. ' pcall=' .. tostring(ok) .. ' errnum=' .. tostring(errnum) .. ' errmsg=' .. tostring(_errmsg_ or ''))
    return success,result,tostring(_errmsg_ or '')
end

local function absolute_time_ticks(add_seconds)
    return string.format('%.0f',(ScenEdit_CurrentTime()+tonumber(add_seconds or 0))*1e7+621355968000000000)
end

local function schedule_lua(event_name,lua_script,delay_seconds)
    local trigger_name=event_name..'_trigger'
    local action_name=event_name..'_action'
    pcall(ScenEdit_SetEvent,event_name,{mode='remove'})
    pcall(ScenEdit_SetAction,{mode='remove',type='LuaScript',name=action_name})
    pcall(ScenEdit_SetTrigger,{mode='remove',type='Time',name=trigger_name})
    local script=table.concat({lua_script,'\n',
        string.format('ScenEdit_SetEvent(%q,{mode=%q})\n',event_name,'remove'),
        string.format('ScenEdit_SetAction({mode=%q,type=%q,name=%q})\n','remove','LuaScript',action_name),
        string.format('ScenEdit_SetTrigger({mode=%q,type=%q,name=%q})\n','remove','Time',trigger_name),
    })
    checked_cmo_call('ScheduleTrigger/'..event_name,ScenEdit_SetTrigger,{mode='add',type='Time',name=trigger_name,Time=absolute_time_ticks(delay_seconds)})
    checked_cmo_call('ScheduleAction/'..event_name,ScenEdit_SetAction,{mode='add',type='LuaScript',name=action_name,ScriptText=script})
    checked_cmo_call('ScheduleEvent/'..event_name,function(args) return ScenEdit_SetEvent(args.name,args.options) end,{name=event_name,options={mode='add',IsActive=true,IsRepeatable=false}})
    checked_cmo_call('LinkTrigger/'..event_name,function(args) return ScenEdit_SetEventTrigger(args.event,{mode='add',name=args.trigger}) end,{event=event_name,trigger=trigger_name})
    checked_cmo_call('LinkAction/'..event_name,function(args) return ScenEdit_SetEventAction(args.event,{mode='add',name=args.action}) end,{event=event_name,action=action_name})
end

local function side_wrapper(side_name)
    local ok,side=pcall(VP_GetSide,{side=side_name})
    if ok and side and side.guid then return side end
    return nil
end

local function side_unit_count(side_name)
    local side=side_wrapper(side_name)
    if not side or type(side.units) ~= 'table' then return 0 end
    local count=0
    for _,_ in pairs(side.units) do count=count+1 end
    return count
end

local function assert_or_error(condition,code,detail)
    local row={status=condition and 'PASS' or 'FAIL',code=code,detail=detail or ''}
    emit_json('[SCENARIO-ASSERT]',row,{'status','code','detail'})
    if not condition then error('[SCENARIO-ASSERT] '..code..' '..tostring(detail or '')) end
end

local function normalize_sides()
    -- 本脚本是场景构建基线。发现旧的中文别名 Side 时，整侧删除后只重建清单资产，
    -- 防止 blue/蓝方、red/红方同时参与交战。删除行为会写入事实日志。
    for _,alias in ipairs({SIDE_RED_ALIAS,SIDE_BLUE_ALIAS}) do
        local side=side_wrapper(alias)
        if side then
            local count=side_unit_count(alias)
            emit_json('[SCENARIO-ASSERT]',{status='NORMALIZE',code='remove_alias_side',detail=alias..' units_removed='..tostring(count)},{'status','code','detail'})
            local ok,result=pcall(ScenEdit_RemoveSide,{side=alias})
            assert_or_error(ok and result ~= false,'remove_alias_side_complete',alias)
        end
    end
    if not side_wrapper(SIDE_RED) then checked_cmo_call('AddSide/red',ScenEdit_AddSide,{side=SIDE_RED}) end
    if not side_wrapper(SIDE_BLUE) then checked_cmo_call('AddSide/blue',ScenEdit_AddSide,{side=SIDE_BLUE}) end
    assert_or_error(side_wrapper(SIDE_RED) ~= nil,'canonical_red_exists',SIDE_RED)
    assert_or_error(side_wrapper(SIDE_BLUE) ~= nil,'canonical_blue_exists',SIDE_BLUE)
end

local function validate_strategy()
    local seen={}
    assert_or_error(type(STRATEGY.candidate_id)=='string' and STRATEGY.candidate_id:match('^[%w_%-]+$') ~= nil,'candidate_id_safe',STRATEGY.candidate_id)
    assert_or_error(#STRATEGY.attacks==5,'planned_attack_count',tostring(#STRATEGY.attacks))
    for _,attack in ipairs(STRATEGY.attacks) do
        assert_or_error(not seen[attack.id],'unique_attack_id',attack.id)
        seen[attack.id]=true
        assert_or_error(UNIT_CATALOG[attack.attacker_id] ~= nil,'known_attacker',attack.id..'/'..tostring(attack.attacker_id))
        assert_or_error(UNIT_CATALOG[attack.target_id] ~= nil and UNIT_CATALOG[attack.target_id].side==SIDE_BLUE,'known_blue_target',attack.id..'/'..tostring(attack.target_id))
        assert_or_error(tonumber(attack.delay_seconds) and attack.delay_seconds>=0 and attack.delay_seconds<=600,'delay_bounds',attack.id..'/'..tostring(attack.delay_seconds))
        assert_or_error(tonumber(attack.quantity) and attack.quantity>=1 and attack.quantity<=16,'quantity_bounds',attack.id..'/'..tostring(attack.quantity))
        if attack.kind=='ship' then
            local capacity=UNIT_CATALOG[attack.attacker_id].weapon_quantity or 0
            assert_or_error(attack.quantity<=capacity,'ship_quantity_capacity',attack.id..'/'..tostring(attack.quantity)..'<='..tostring(capacity))
        else
            assert_or_error(attack.popup_range_nm>attack.attack_range_nm or attack.popup_range_nm==attack.attack_range_nm,'air_popup_before_attack',attack.id)
        end
        ATTACK_BY_ID[attack.id]=attack
        ATTACK_RUNTIME[attack.id]={popup=false,last_airborne_seconds=0,was_airborne=false,release_check_attempt=0}
        TRACE[attack.id]={
            candidate_id=STRATEGY.candidate_id,attack_id=attack.id,kind=attack.kind,
            attacker_id=attack.attacker_id,target_id=attack.target_id,stage='validated',
            scheduled=false,triggered=false,attacker_found=false,target_found=false,
            contact_acquired=false,airborne=false,reached_attack_range=false,
            fire_called=false,fire_accepted=false,weapon_released=JSON_NULL,hit=JSON_NULL,
            damage_percent=0,failure_stage=JSON_NULL,attempt=0,range_nm=JSON_NULL,
            contact_guid=JSON_NULL,classification=JSON_NULL,detail='strategy_validated',
        }
        trace_update(attack.id,{})
    end
    emit_json('[STRATEGY-META]',{candidate_id=STRATEGY.candidate_id,hypothesis=STRATEGY.hypothesis,mechanism=STRATEGY.mechanism},{'candidate_id','hypothesis','mechanism'})
end

local function ensure_ship(unit_id)
    local spec=UNIT_CATALOG[unit_id]
    local unit=unit_by_id(unit_id)
    if not unit then
        local ok,result=checked_cmo_call('AddShip/'..unit_id,ScenEdit_AddUnit,{
            type='Ship',side=spec.side,unitname=spec.name,dbid=spec.dbid,
            latitude=spec.lat,longitude=spec.lon,heading=spec.heading,speed=spec.speed,
            proficiency=spec.proficiency,
        })
        if ok then unit=result or unit_by_id(unit_id) end
    end
    assert_or_error(unit ~= nil,'unit_exists',unit_id)
    checked_cmo_call('ResetShip/'..unit_id,ScenEdit_SetUnit,{
        guid=unit.guid,latitude=spec.lat,longitude=spec.lon,heading=spec.heading,speed=spec.speed,
        autodetectable=false,holdposition=false,
        course={{latitude=spec.route_lat,longitude=spec.route_lon}},
    })
    pcall(ScenEdit_SetEMCON,'Unit',unit.guid,'Radar=Active')
    return unit
end

local function ensure_aircraft(unit_id)
    local spec=UNIT_CATALOG[unit_id]
    local base_spec=UNIT_CATALOG[spec.base_id]
    local unit=unit_by_id(unit_id)
    if not unit then
        local ok,result=checked_cmo_call('AddAircraft/'..unit_id,ScenEdit_AddUnit,{
            type='Air',side=spec.side,unitname=spec.name,dbid=spec.dbid,
            loadoutid=spec.loadoutid,base=base_spec.name,proficiency=spec.proficiency,
        })
        if ok then unit=result or unit_by_id(unit_id) end
    end
    assert_or_error(unit ~= nil,'unit_exists',unit_id)
    if not unit.isOperating then
        checked_cmo_call('SetBase/'..unit_id,ScenEdit_SetUnit,{guid=unit.guid,base=base_spec.name,autodetectable=false})
        checked_cmo_call('SetLoadout/'..unit_id,ScenEdit_SetLoadout,{unitname=unit.guid,LoadoutID=spec.loadoutid,TimeToReady_Minutes=0,IgnoreMagazines=true})
        checked_cmo_call('ReadyNow/'..unit_id,ScenEdit_SetUnit,{guid=unit.guid,timetoready_minutes=0})
    end
    pcall(ScenEdit_SetEMCON,'Unit',unit.guid,'Radar=Passive')
    return unit
end

local function set_weapon_quantity(unit_id,weapon_dbid,desired)
    local spec=UNIT_CATALOG[unit_id]
    local unit=unit_by_id(unit_id)
    assert_or_error(unit ~= nil,'inventory_unit_exists',unit_id)
    for _,mount in ipairs(unit.mounts or {}) do
        for _,weapon in ipairs(mount.mount_weapons or {}) do
            if tonumber(weapon.wpn_dbid)==tonumber(weapon_dbid) then
                local current=tonumber(weapon.wpn_current) or 0
                if current>0 then
                    checked_cmo_call('RemoveWeapon/'..unit_id..'/'..tostring(mount.mount_guid),ScenEdit_AddReloadsToUnit,{guid=unit.guid,wpn_dbid=weapon_dbid,mount_guid=mount.mount_guid,number=current,remove=true})
                end
            end
        end
    end
    local ok,result=checked_cmo_call('AddWeapon/'..unit_id,ScenEdit_AddReloadsToUnit,{side=spec.side,unitname=spec.name,wpn_dbid=weapon_dbid,number=desired})
    assert_or_error(ok,'inventory_configured',unit_id..' qty='..tostring(desired)..' result='..tostring(result))
end

local function assert_scenario_facts()
    for _,unit_id in ipairs(EXPECTED_RED_IDS) do
        local spec=UNIT_CATALOG[unit_id]
        assert_or_error(lookup_unit(SIDE_RED,spec.name) ~= nil,'red_unit_present',unit_id)
        assert_or_error(lookup_unit(SIDE_BLUE,spec.name) == nil,'red_unit_not_on_blue',unit_id)
        assert_or_error(lookup_unit(SIDE_RED_ALIAS,spec.name) == nil,'red_unit_not_on_alias',unit_id)
    end
    for _,unit_id in ipairs(EXPECTED_BLUE_IDS) do
        local spec=UNIT_CATALOG[unit_id]
        assert_or_error(lookup_unit(SIDE_BLUE,spec.name) ~= nil,'blue_unit_present',unit_id)
        assert_or_error(lookup_unit(SIDE_RED,spec.name) == nil,'blue_unit_not_on_red',unit_id)
        assert_or_error(lookup_unit(SIDE_BLUE_ALIAS,spec.name) == nil,'blue_unit_not_on_alias',unit_id)
    end
    assert_or_error(side_unit_count(SIDE_RED)==#EXPECTED_RED_IDS,'red_unit_count',tostring(side_unit_count(SIDE_RED)))
    assert_or_error(side_unit_count(SIDE_BLUE)==#EXPECTED_BLUE_IDS,'blue_unit_count',tostring(side_unit_count(SIDE_BLUE)))
end

local function contact_guid_for_target(observer_side,target_unit,target_name)
    local side=side_wrapper(observer_side)
    if not side or type(side.contacts) ~= 'table' then return nil,nil end
    local target_guid=tostring(target_unit.guid):lower()
    for _,ref in pairs(side.contacts) do
        local ref_guid=ref.guid or ref.Guid or ref.objectid or ref.ObjectID
        if ref_guid then
            local ok,contact=pcall(ScenEdit_GetContact,{side=observer_side,guid=ref_guid})
            if ok and contact then
                local actual=contact.actualunitid or contact.actualUnitID or contact.actualunitguid or contact.actualUnitGuid
                if actual and tostring(actual):lower()==target_guid then return ref_guid,contact end
            end
        end
    end
    for _,ref in pairs(side.contacts) do
        local ref_guid=ref.guid or ref.Guid or ref.objectid or ref.ObjectID
        if ref_guid then
            local ok,contact=pcall(ScenEdit_GetContact,{side=observer_side,guid=ref_guid})
            if ok and contact then
                local name=tostring(contact.name or ref.name or '')
                if name==target_name or (target_name~='' and name:find(target_name,1,true)) then return ref_guid,contact end
            end
        end
    end
    return nil,nil
end

local function unit_weapon_count(unit,weapon_dbid)
    if not unit then return 0 end
    local total=0
    for _,mount in ipairs(unit.mounts or {}) do
        for _,weapon in ipairs(mount.mount_weapons or {}) do
            if tonumber(weapon.wpn_dbid)==tonumber(weapon_dbid) then total=total+(tonumber(weapon.wpn_current) or 0) end
        end
    end
    return total
end

local function damage_percent(unit)
    if not unit or type(unit.damage) ~= 'table' then return 0 end
    return tonumber(unit.damage.DP_PERCENT_NOW or unit.damage.DP_PERCENT or 0) or 0
end

local function attack_context(attack_id)
    local attack=ATTACK_BY_ID[attack_id]
    if not attack then return nil end
    local attacker_spec=UNIT_CATALOG[attack.attacker_id]
    local target_spec=UNIT_CATALOG[attack.target_id]
    return attack,attacker_spec,target_spec,unit_by_id(attack.attacker_id),unit_by_id(attack.target_id)
end

local function call_attack_contact(attack_id,attacker,target,contact_guid)
    local attack=ATTACK_BY_ID[attack_id]
    local options
    if attack.weapon_dbid then
        options={mode='1',weapon=tonumber(attack.weapon_dbid),qty=tonumber(attack.quantity)}
    else
        options={mode='0'}
    end
    trace_update(attack_id,{stage='fire_called',fire_called=true,contact_guid=contact_guid,damage_percent=damage_percent(target)})
    _errnum_=0
    _errmsg_=''
    local ok,result=pcall(ScenEdit_AttackContact,attacker.guid,contact_guid,options)
    local success=ok and result ~= nil and result ~= false and (tonumber(_errnum_) or 0)==0
    trace_update(attack_id,{stage=success and 'fire_accepted' or 'fire_rejected',fire_accepted=success,detail=tostring(_errmsg_ or ''),failure_stage=success and JSON_NULL or 'attack_contact_rejected'})
    return success
end

-- ============================================================
-- GLOBAL SCHEDULED ENTRY POINTS
-- ============================================================
function baseline_confirm_ship_release(attack_id,before_count,attempt)
    local attack=ATTACK_BY_ID[attack_id]
    if not attack then return end
    local attacker=unit_by_id(attack.attacker_id)
    if not attacker then
        trace_update(attack_id,{stage='release_check_failed',failure_stage='attacker_missing_after_fire',attempt=attempt})
        return
    end
    local current=unit_weapon_count(attacker,attack.weapon_dbid)
    if current < tonumber(before_count) then
        trace_update(attack_id,{stage='weapon_released',weapon_released=true,detail='inventory '..tostring(before_count)..'->'..tostring(current),attempt=attempt})
        return
    end
    if attempt>=12 then
        trace_update(attack_id,{stage='attack_order_no_release',weapon_released=false,failure_stage='attack_order_accepted_but_no_inventory_change',detail='inventory='..tostring(current),attempt=attempt})
        return
    end
    schedule_lua('baseline_release_'..attack_id..'_'..tostring(attempt+1),string.format('baseline_confirm_ship_release(%q,%d,%d)',attack_id,before_count,attempt+1),10)
end

function baseline_ship_attack_poll(attack_id,attempt)
    local attack,attacker_spec,target_spec,attacker,target=attack_context(attack_id)
    if not attack then return end
    trace_update(attack_id,{stage='ship_poll',triggered=true,attempt=attempt,attacker_found=attacker~=nil,target_found=target~=nil})
    if not attacker then trace_update(attack_id,{stage='failed',failure_stage='attacker_not_found'}); return end
    if not target then trace_update(attack_id,{stage='target_gone',failure_stage=JSON_NULL,damage_percent=100}); return end
    local ok_range,range_nm=pcall(Tool_Range,attacker.guid,target.guid)
    if not ok_range then range_nm=nil end
    local contact_guid,contact=contact_guid_for_target(SIDE_RED,target,target_spec.name)
    local in_range=range_nm and tonumber(range_nm)<=tonumber(attack.max_range_nm)
    trace_update(attack_id,{
        range_nm=range_nm or JSON_NULL,contact_acquired=contact_guid~=nil,contact_guid=contact_guid or JSON_NULL,
        classification=contact and tostring(contact.classificationlevel or '') or JSON_NULL,
        reached_attack_range=in_range and true or false,damage_percent=damage_percent(target),
        detail='ship_wait_contact_and_range',
    })
    if contact_guid and in_range then
        local before=unit_weapon_count(attacker,attack.weapon_dbid)
        if call_attack_contact(attack_id,attacker,target,contact_guid) then
            schedule_lua('baseline_release_'..attack_id..'_1',string.format('baseline_confirm_ship_release(%q,%d,1)',attack_id,before),10)
            return
        end
    end
    if attempt>=attack.max_attempts then
        local failure=not contact_guid and 'contact_not_acquired' or (not in_range and 'attack_range_not_reached' or 'fire_not_accepted')
        trace_update(attack_id,{stage='not_reached',failure_stage=failure,detail='ship_poll_timeout'})
        return
    end
    schedule_lua('baseline_ship_poll_'..attack_id..'_'..tostring(attempt+1),string.format('baseline_ship_attack_poll(%q,%d)',attack_id,attempt+1),attack.poll_seconds)
end

function baseline_air_rtb(attack_id)
    local attack=ATTACK_BY_ID[attack_id]
    if not attack then return end
    local unit=unit_by_id(attack.attacker_id)
    local base=unit_by_id(attack.base_id)
    if unit then
        pcall(ScenEdit_SetEMCON,'Unit',unit.guid,'Radar=Passive')
        checked_cmo_call('AirDescend/'..attack_id,ScenEdit_SetUnit,{guid=unit.guid,altitude=attack.ingress_altitude_m,moveto=true,throttle='Full'})
        checked_cmo_call('AirRTB/'..attack_id,ScenEdit_SetUnit,{guid=unit.guid,base=base and base.guid or UNIT_CATALOG[attack.base_id].name,rtb=true})
        trace_update(attack_id,{stage='rtb_ordered',detail='radar_passive_low_altitude_rtb'})
    end
end

function baseline_air_attack_poll(attack_id,attempt)
    local attack,attacker_spec,target_spec,aircraft,target=attack_context(attack_id)
    if not attack then return end
    local runtime=ATTACK_RUNTIME[attack_id]
    trace_update(attack_id,{stage='air_poll',triggered=true,attempt=attempt,attacker_found=aircraft~=nil,target_found=target~=nil,airborne=aircraft and aircraft.isOperating or false})
    if not aircraft then trace_update(attack_id,{stage='failed',failure_stage='aircraft_missing_before_attack'}); return end
    if not target then trace_update(attack_id,{stage='target_gone',damage_percent=100,failure_stage=JSON_NULL}); baseline_air_rtb(attack_id); return end
    if aircraft.isOperating then
        runtime.was_airborne=true
        runtime.last_airborne_seconds=math.max(runtime.last_airborne_seconds or 0,tonumber(aircraft.airbornetime_v or 0) or 0)
    elseif runtime.was_airborne then
        trace_update(attack_id,{stage='aircraft_no_longer_operating',failure_stage='aircraft_lost_or_landed_before_attack'})
        return
    else
        trace_update(attack_id,{stage='launch_not_completed',failure_stage='aircraft_not_airborne'})
        return
    end
    local ok_range,range_nm=pcall(Tool_Range,aircraft.guid,target.guid)
    if not ok_range then range_nm=nil end
    local contact_guid,contact=contact_guid_for_target(SIDE_RED,target,target_spec.name)
    if not runtime.popup and range_nm and tonumber(range_nm)<=tonumber(attack.popup_range_nm) then
        runtime.popup=true
        checked_cmo_call('AirPopup/'..attack_id,ScenEdit_SetUnit,{guid=aircraft.guid,altitude=attack.popup_altitude_m,moveto=true,throttle='Full'})
        pcall(ScenEdit_SetEMCON,'Unit',aircraft.guid,'Radar=Active')
        trace_update(attack_id,{stage='sensor_popup',detail='radar_active altitude='..tostring(attack.popup_altitude_m)})
    elseif runtime.popup then
        pcall(ScenEdit_SetEMCON,'Unit',aircraft.guid,'Radar=Active')
    else
        pcall(ScenEdit_SetEMCON,'Unit',aircraft.guid,'Radar=Passive')
    end
    contact_guid,contact=contact_guid_for_target(SIDE_RED,target,target_spec.name)
    local in_range=range_nm and tonumber(range_nm)<=tonumber(attack.attack_range_nm)
    trace_update(attack_id,{
        range_nm=range_nm or JSON_NULL,contact_acquired=contact_guid~=nil,contact_guid=contact_guid or JSON_NULL,
        classification=contact and tostring(contact.classificationlevel or '') or JSON_NULL,
        reached_attack_range=in_range and true or false,damage_percent=damage_percent(target),
        detail=runtime.popup and 'radar_active_search' or 'low_altitude_passive_ingress',
    })
    if contact_guid and in_range then
        if call_attack_contact(attack_id,aircraft,target,contact_guid) then
            schedule_lua('baseline_air_rtb_'..attack_id,string.format('baseline_air_rtb(%q)',attack_id),attack.return_delay_seconds)
            return
        end
    end
    if attempt>=attack.max_attempts then
        local failure=not contact_guid and 'contact_not_acquired' or (not in_range and 'attack_range_not_reached' or 'fire_not_accepted')
        trace_update(attack_id,{stage='not_reached',failure_stage=failure,detail='air_poll_timeout'})
        baseline_air_rtb(attack_id)
        return
    end
    schedule_lua('baseline_air_poll_'..attack_id..'_'..tostring(attempt+1),string.format('baseline_air_attack_poll(%q,%d)',attack_id,attempt+1),attack.poll_seconds)
end

function baseline_air_launch_poll(attack_id,attempt)
    local attack,attacker_spec,target_spec,aircraft,target=attack_context(attack_id)
    if not attack then return end
    trace_update(attack_id,{stage='launch_poll',triggered=true,attempt=attempt,attacker_found=aircraft~=nil,target_found=target~=nil,airborne=aircraft and aircraft.isOperating or false})
    if not aircraft then trace_update(attack_id,{stage='failed',failure_stage='aircraft_not_found'}); return end
    if not target then trace_update(attack_id,{stage='failed',failure_stage='target_not_found'}); return end
    if aircraft.isOperating then
        ATTACK_RUNTIME[attack_id].was_airborne=true
        pcall(ScenEdit_SetEMCON,'Unit',aircraft.guid,'Radar=Passive')
        local mid_lat=tonumber(target.latitude)+tonumber(attack.mid_lat_offset)
        local mid_lon=tonumber(target.longitude)+tonumber(attack.mid_lon_offset)
        local app_lat=tonumber(target.latitude)+tonumber(attack.approach_lat_offset)
        local app_lon=tonumber(target.longitude)+tonumber(attack.approach_lon_offset)
        checked_cmo_call('AirRoute/'..attack_id,ScenEdit_SetUnit,{
            guid=aircraft.guid,course={{latitude=mid_lat,longitude=mid_lon},{latitude=app_lat,longitude=app_lon}},
            altitude=attack.ingress_altitude_m,moveto=true,throttle='Full',
        })
        trace_update(attack_id,{stage='airborne_route_set',airborne=true,detail=string.format('target_relative_route %.4f,%.4f -> %.4f,%.4f',mid_lat,mid_lon,app_lat,app_lon)})
        schedule_lua('baseline_air_poll_'..attack_id..'_1',string.format('baseline_air_attack_poll(%q,1)',attack_id),attack.poll_seconds)
        return
    end
    if attempt>=24 then trace_update(attack_id,{stage='not_reached',failure_stage='launch_timeout'}); return end
    checked_cmo_call('ReadyRetry/'..attack_id,ScenEdit_SetUnit,{guid=aircraft.guid,timetoready_minutes=0})
    checked_cmo_call('Launch/'..attack_id,ScenEdit_SetUnit,{guid=aircraft.guid,launch=true})
    schedule_lua('baseline_air_launch_'..attack_id..'_'..tostring(attempt+1),string.format('baseline_air_launch_poll(%q,%d)',attack_id,attempt+1),15)
end

local function count_trace(field,value)
    local count=0
    for _,state in pairs(TRACE) do if state[field]==value then count=count+1 end end
    return count
end

local function emit_side_expenditures(side_name,tag)
    local side=side_wrapper(side_name)
    if not side or type(side.expenditures) ~= 'table' then return end
    for _,item in pairs(side.expenditures) do
        emit_json('[EXPENDITURE]',{
            tag=tag,side=side_name,type=tostring(item.type or ''),dbid=tonumber(item.dbid or 0) or 0,
            name=tostring(item.name or ''),number=tonumber(item.number or item.count or 0) or 0,
        },{'tag','side','type','dbid','name','number'})
    end
end

function baseline_process_snapshot(tag)
    local enemy_damage_value=0
    local own_loss_value=0
    local aircraft_returned=0
    local max_aircraft_survival_seconds=0
    for _,unit_id in ipairs(EXPECTED_BLUE_IDS) do
        local spec=UNIT_CATALOG[unit_id]
        local unit=unit_by_id(unit_id)
        local damage=unit and damage_percent(unit) or 100
        enemy_damage_value=enemy_damage_value+(tonumber(spec.score_value or 0)*damage/100)
        emit_json('[TARGET-STATE]',{tag=tag,unit_id=unit_id,present=unit~=nil,damage_percent=damage},{'tag','unit_id','present','damage_percent'})
    end
    local own_values={red_055_nanchang=100,red_052d_1=75,red_052d_2=75,red_liaoning=200,red_j15_1=20,red_j15_2=20}
    for unit_id,value in pairs(own_values) do
        local unit=unit_by_id(unit_id)
        if not unit or unit.IsDestroyed then own_loss_value=own_loss_value+value end
    end
    for _,attack_id in ipairs({'red_j15_1_attack','red_j15_2_attack'}) do
        local runtime=ATTACK_RUNTIME[attack_id]
        local unit=unit_by_id(ATTACK_BY_ID[attack_id].attacker_id)
        max_aircraft_survival_seconds=math.max(max_aircraft_survival_seconds,runtime.last_airborne_seconds or 0)
        if runtime.was_airborne and unit and not unit.isOperating and not unit.IsDestroyed then aircraft_returned=aircraft_returned+1 end
    end
    local ok_score,score=pcall(ScenEdit_GetScore,SIDE_RED)
    emit_json('[PROCESS-VECTOR]',{
        tag=tag,candidate_id=STRATEGY.candidate_id,official_score=ok_score and tonumber(score or 0) or 0,
        enemy_damage_value=enemy_damage_value,own_loss_value=own_loss_value,planned_attacks=#STRATEGY.attacks,
        triggered_attacks=count_trace('triggered',true),contacts_acquired=count_trace('contact_acquired',true),
        fire_calls=count_trace('fire_called',true),fire_accepted=count_trace('fire_accepted',true),
        confirmed_weapon_releases=count_trace('weapon_released',true),aircraft_returned=aircraft_returned,
        max_aircraft_survival_seconds=max_aircraft_survival_seconds,
    },{'tag','candidate_id','official_score','enemy_damage_value','own_loss_value','planned_attacks','triggered_attacks','contacts_acquired','fire_calls','fire_accepted','confirmed_weapon_releases','aircraft_returned','max_aircraft_survival_seconds'})
    emit_side_expenditures(SIDE_RED,tag)
    emit_side_expenditures(SIDE_BLUE,tag)
end

function phase3_collect_final_state()
    baseline_process_snapshot('initial')
    schedule_lua('baseline_snapshot_300',"baseline_process_snapshot('t300')",300)
    schedule_lua('baseline_snapshot_900',"baseline_process_snapshot('t900')",900)
    schedule_lua('baseline_snapshot_1800',"baseline_process_snapshot('t1800')",1800)
    schedule_lua('baseline_snapshot_2400',"baseline_process_snapshot('t2400')",2400)
end

-- ============================================================
-- SETUP
-- ============================================================
runtime_log('candidate='..STRATEGY.candidate_id)
normalize_sides()
validate_strategy()
pcall(ScenEdit_SetSidePosture,SIDE_RED,SIDE_BLUE,'H')
pcall(ScenEdit_SetSidePosture,SIDE_BLUE,SIDE_RED,'H')
pcall(ScenEdit_SetSideOptions,{side=SIDE_RED,awareness='Normal'})
pcall(ScenEdit_SetSideOptions,{side=SIDE_BLUE,awareness='Normal'})
for _,side in ipairs({SIDE_RED,SIDE_BLUE}) do
    pcall(ScenEdit_SetDoctrine,{side=side},{weapon_control_status_air='0',weapon_control_status_surface='0',weapon_control_status_subsurface='0'})
end

for _,unit_id in ipairs({'red_055_nanchang','red_052d_1','red_052d_2','red_liaoning','blue_cvn70','blue_cg59','blue_ddg113_1','blue_ddg113_2'}) do ensure_ship(unit_id) end
for _,unit_id in ipairs({'red_j15_1','red_j15_2'}) do ensure_aircraft(unit_id) end
set_weapon_quantity('red_055_nanchang',SHIP_WEAPON_DBID,16)
set_weapon_quantity('red_052d_1',SHIP_WEAPON_DBID,16)
set_weapon_quantity('red_052d_2',SHIP_WEAPON_DBID,10)
assert_scenario_facts()

-- CMO native scoring instrumentation; generated deterministically.
-- score_spec_checksum: 9a7f68a20cea722df7ae77c28a93199b1042258bd153973e25021b5e498762df
local SCORE_RULES = {{["action_name"]="p3score_act_46443fcc97b174b2",["event_name"]="p3score_evt_46443fcc97b174b2",["objective_id"]="destroy-blue-cg59",["point_change"]=100,["rule_id"]="native_score/blue_cg59",["score_side_id"]="red",["target_side_id"]="blue",["target_unit_id"]="blue_cg59",["target_unit_name"]="蓝方CG-59普林斯顿",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_46443fcc97b174b2"},{["action_name"]="p3score_act_06db9413ee376cc5",["event_name"]="p3score_evt_06db9413ee376cc5",["objective_id"]="destroy-blue-cvn70",["point_change"]=200,["rule_id"]="native_score/blue_cvn70",["score_side_id"]="red",["target_side_id"]="blue",["target_unit_id"]="blue_cvn70",["target_unit_name"]="蓝方CVN-70卡尔文森",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_06db9413ee376cc5"},{["action_name"]="p3score_act_5c16b9c6b5869b50",["event_name"]="p3score_evt_5c16b9c6b5869b50",["objective_id"]="destroy-blue-ddg113-1",["point_change"]=75,["rule_id"]="native_score/blue_ddg113_1",["score_side_id"]="red",["target_side_id"]="blue",["target_unit_id"]="blue_ddg113_1",["target_unit_name"]="蓝方DDG-113-1约翰芬恩",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_5c16b9c6b5869b50"},{["action_name"]="p3score_act_16e96bd8535f3788",["event_name"]="p3score_evt_16e96bd8535f3788",["objective_id"]="destroy-blue-ddg113-2",["point_change"]=75,["rule_id"]="native_score/blue_ddg113_2",["score_side_id"]="red",["target_side_id"]="blue",["target_unit_id"]="blue_ddg113_2",["target_unit_name"]="蓝方DDG-113-2约翰芬恩",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_16e96bd8535f3788"},{["action_name"]="p3score_act_9916e76cc4d72b57",["event_name"]="p3score_evt_9916e76cc4d72b57",["objective_id"]="preserve-red-052d-1",["point_change"]=-75,["rule_id"]="native_score/red_052d_1",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_052d_1",["target_unit_name"]="红方052D-1昆明舰",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_9916e76cc4d72b57"},{["action_name"]="p3score_act_3afb4c76dde2edbb",["event_name"]="p3score_evt_3afb4c76dde2edbb",["objective_id"]="preserve-red-052d-2",["point_change"]=-75,["rule_id"]="native_score/red_052d_2",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_052d_2",["target_unit_name"]="红方052D-2南京舰",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_3afb4c76dde2edbb"},{["action_name"]="p3score_act_54a28cfffebb8665",["event_name"]="p3score_evt_54a28cfffebb8665",["objective_id"]="preserve-red-055",["point_change"]=-100,["rule_id"]="native_score/red_055_nanchang",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_055_nanchang",["target_unit_name"]="红方055南昌舰",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_54a28cfffebb8665"},{["action_name"]="p3score_act_e840d2e41229a643",["event_name"]="p3score_evt_e840d2e41229a643",["objective_id"]="preserve-red-j15-1",["point_change"]=-20,["rule_id"]="native_score/red_j15_1",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_j15_1",["target_unit_name"]="J-15-1",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_e840d2e41229a643"},{["action_name"]="p3score_act_3d061cadaad4600f",["event_name"]="p3score_evt_3d061cadaad4600f",["objective_id"]="preserve-red-j15-2",["point_change"]=-20,["rule_id"]="native_score/red_j15_2",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_j15_2",["target_unit_name"]="J-15-2",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_3d061cadaad4600f"},{["action_name"]="p3score_act_674ff2766687a9bd",["event_name"]="p3score_evt_674ff2766687a9bd",["objective_id"]="preserve-red-liaoning",["point_change"]=-200,["rule_id"]="native_score/red_liaoning",["score_side_id"]="red",["target_side_id"]="red",["target_unit_id"]="red_liaoning",["target_unit_name"]="红方辽宁舰",["trigger_kind"]="unit_destroyed",["trigger_name"]="p3score_trg_674ff2766687a9bd"}}
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

-- ============================================================
-- SCHEDULE ACTIVE ATTACKS
-- ============================================================
for _,attack in ipairs(STRATEGY.attacks) do
    trace_update(attack.id,{stage='scheduled',scheduled=true,detail='delay_seconds='..tostring(attack.delay_seconds)})
    if attack.kind=='ship' then
        schedule_lua('baseline_ship_start_'..attack.id,string.format('baseline_ship_attack_poll(%q,1)',attack.id),attack.delay_seconds)
    else
        schedule_lua('baseline_air_start_'..attack.id,string.format('baseline_air_launch_poll(%q,1)',attack.id),attack.delay_seconds)
    end
end

phase3_collect_final_state()
runtime_log('instrumented baseline scheduled; press Play to advance simulation')
