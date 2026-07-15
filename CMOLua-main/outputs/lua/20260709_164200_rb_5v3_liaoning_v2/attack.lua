-- ============================================================
-- attack.lua: 真延时打击（TOT 事件驱动）
-- 每次发射 qty=1，逐枚调度，靠仿真时间推进到 contact 稳定后再发射
-- contact_settle_delay = 15 秒（红方 OMNI + 蓝方 autodetectable=true）
-- 注意：第二艘 DDG-113-2 无坐标，055-Nanchang 26 枚全打 DDG-113-1
-- ============================================================

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

-- ---------- 全局打击函数（必须为全局，事件脚本可调用） ----------
-- ★ fireAt 必须是全局（红线 #15）
-- 1) 蓝方 autodetectable=true  2) 红方 OMNI  3) 用 VP_GetSide().contacts
-- 4) 用【真延时触发器】把发射安排到未来，让游戏推进后再执行
--    （脚本只"预约"，玩家按播放让时间流逝，到点 contact 已生成）
function fireAt(atkName, tgtName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side="红方", name=atkName})
    local tgt = ScenEdit_GetUnit({side="蓝方", name=tgtName})
    pcall(ScenEdit_SetUnit, {guid=tgt.guid, autodetectable=true})
    pcall(ScenEdit_SetSideOptions, {side="红方", awareness="OMNI"})

    local contactGuid
    local ok, s = pcall(VP_GetSide, {Side="红方"})       -- ★ 不用 GetContacts
    if ok and s and type(s.contacts)=="table" then
        local tg = tostring(tgt.guid):lower()
        for _, c in ipairs(s.contacts) do                -- 先按 actualunitid 匹配
            local aid = c.actualunitid or c.actualUnitID or c.actualunitguid
            if aid and tostring(aid):lower()==tg then contactGuid=c.guid; break end
        end
        if not contactGuid then                          -- 再按名称匹配
            for _, c in ipairs(s.contacts) do
                local nm = tostring(c.name or "")
                if nm~="" and (nm==tgtName or nm:find(tgtName,1,true)) then contactGuid=c.guid; break end
            end
        end
    end
    if not contactGuid then print("无 contact，加大延迟或多推进游戏"); return false end

    _errnum_=0
    return ScenEdit_AttackContact(atk.guid, contactGuid, {mode="1", weapon=wpnDbid, qty=qty}) and true or false
end

-- ---------- TOT 时间换算 ----------
local function totTicks(addSeconds)
    local t = ScenEdit_CurrentTime()
    local offSet = 62135596801
    return string.format("%.0f", (t + offSet + addSeconds) * 1e7)
end

-- ---------- 逐枚调度（每枚独立触发器，qty=1） ----------
-- @param atkName  攻击方名称
-- @param tgtName  目标名称
-- @param wpnDbid  武器 DBID
-- @param qty      发射数量
-- @param baseDelay  基础延迟（秒，从现在开始）
-- @param interval   每枚间隔（秒）
local function scheduleWave(atkName, tgtName, wpnDbid, qty, baseDelay, interval)
    for k = 1, qty do
        local delay = baseDelay + (k - 1) * interval
        local ts = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
        local evName = "E_" .. atkName .. "_" .. tgtName .. "_" .. k .. "_" .. ts
        local trName = "T_" .. atkName .. "_" .. tgtName .. "_" .. k .. "_" .. ts
        local acName = "A_" .. atkName .. "_" .. tgtName .. "_" .. k .. "_" .. ts
        local script = ("fireAt(%q,%q,%d,1)\n"):format(atkName, tgtName, wpnDbid)
            .. ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName)
            .. ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName)
            .. ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)

        local fireTime = totTicks(delay)
        pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
        pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
        pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
        pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
        pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
    end
end

-- ---------- 打击计划 ----------
-- contact_settle_delay = 15 秒（真延时，齐射前让 contact 稳定刷新）
local CONTACT_SETTLE = 15
local INTERVAL       = 1   -- 每枚间隔 1 秒

-- 1) 055-Nanchang -> DDG-113-1  (13 枚 YJ-18，间隔 1s)
--    注：strikePlan 中第二艘 DDG-113-2 无坐标，26 枚全打 DDG-113-1
for k = 1, 13 do
    local delay = CONTACT_SETTLE + (k - 1) * INTERVAL
    scheduleWave("055-Nanchang", "DDG-113-1", 2868, 1, delay - delay, INTERVAL)
end
-- 简化写法：直接循环 13 次
for k = 1, 13 do
    local ts = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
    local evName = "E_055_DDG113_" .. k .. "_" .. ts
    local trName = "T_055_DDG113_" .. k .. "_" .. ts
    local acName = "A_055_DDG113_" .. k .. "_" .. ts
    local delay  = CONTACT_SETTLE + (k - 1) * INTERVAL
    local script = ("fireAt(%q,%q,%d,1)\n"):format("055-Nanchang","DDG-113-1",2868)
        .. ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName)
        .. ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName)
        .. ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    local fireTime = totTicks(delay)
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
end
print("[attack] 055-Nanchang -> DDG-113-1: 13x YJ-18 调度完毕（首枚 T+" .. CONTACT_SETTLE .. "s）")

-- 2) 052D-1 -> CVN-70  (8 枚 YJ-18)
for k = 1, 8 do
    local ts = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
    local evName = "E_052D1_CVN70_" .. k .. "_" .. ts
    local trName = "T_052D1_CVN70_" .. k .. "_" .. ts
    local acName = "A_052D1_CVN70_" .. k .. "_" .. ts
    local delay  = CONTACT_SETTLE + (k - 1) * INTERVAL
    local script = ("fireAt(%q,%q,%d,1)\n"):format("052D-1","CVN-70",2868)
        .. ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName)
        .. ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName)
        .. ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    local fireTime = totTicks(delay)
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
end
print("[attack] 052D-1 -> CVN-70: 8x YJ-18 调度完毕（首枚 T+" .. CONTACT_SETTLE .. "s）")

-- 3) 052D-2 -> CG-59  (5 枚 YJ-18)
for k = 1, 5 do
    local ts = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
    local evName = "E_052D2_CG59_" .. k .. "_" .. ts
    local trName = "T_052D2_CG59_" .. k .. "_" .. ts
    local acName = "A_052D2_CG59_" .. k .. "_" .. ts
    local delay  = CONTACT_SETTLE + (k - 1) * INTERVAL
    local script = ("fireAt(%q,%q,%d,1)\n"):format("052D-2","CG-59",2868)
        .. ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName)
        .. ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName)
        .. ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    local fireTime = totTicks(delay)
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
end
print("[attack] 052D-2 -> CG-59: 5x YJ-18 调度完毕（首枚 T+" .. CONTACT_SETTLE .. "s）")

-- 4) J-15-RED-01 -> CVN-70  (4 枚 YJ-83K，来自 loadoutId=9682)
--    J-15 opts={mode="0"}，导弹来自挂载，无需手动装弹
for k = 1, 4 do
    local ts = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
    local evName = "E_J15R1_CVN70_" .. k .. "_" .. ts
    local trName = "T_J15R1_CVN70_" .. k .. "_" .. ts
    local acName = "A_J15R1_CVN70_" .. k .. "_" .. ts
    local delay  = CONTACT_SETTLE + (k - 1) * INTERVAL
    -- loadoutId=9682 = YJ-83K (CMO DB 中 J-15 反舰挂载)
    local script = ("fireAt(%q,%q,%d,1)\n"):format("J-15-RED-01","CVN-70",2137)
        .. ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName)
        .. ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName)
        .. ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    local fireTime = totTicks(delay)
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
end
print("[attack] J-15-RED-01 -> CVN-70: 4x YJ-83K 调度完毕（首枚 T+" .. CONTACT_SETTLE .. "s）")

-- 5) J-15-RED-02 -> CG-59  (4 枚 YJ-83K)
for k = 1, 4 do
    local ts = tostring(ScenEdit_CurrentTime()):gsub("[^%d]", "")
    local evName = "E_J15R2_CG59_" .. k .. "_" .. ts
    local trName = "T_J15R2_CG59_" .. k .. "_" .. ts
    local acName = "A_J15R2_CG59_" .. k .. "_" .. ts
    local delay  = CONTACT_SETTLE + (k - 1) * INTERVAL
    local script = ("fireAt(%q,%q,%d,1)\n"):format("J-15-RED-02","CG-59",2137)
        .. ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName)
        .. ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName)
        .. ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName)
    local fireTime = totTicks(delay)
    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent, evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})
end
print("[attack] J-15-RED-02 -> CG-59: 4x YJ-83K 调度完毕（首枚 T+" .. CONTACT_SETTLE .. "s）")

print("[attack] ===== 真延时打击调度完毕 =====")
print("[attack] 汇总: 055(13) + 052D-1(8) + 052D-2(5) + J-15-01(4) + J-15-02(4) = 34 枚")
print("[attack] contact_settle_delay = " .. CONTACT_SETTLE .. "s，红方 awareness=OMNI")
print("[attack] 执行顺序: main.lua -> clear.lua -> reload.lua -> attack.lua")
