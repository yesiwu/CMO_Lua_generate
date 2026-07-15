-- ============================================================
-- attack.lua: 真延时打击（TOT 事件驱动）
-- 每次发射 qty=1，逐枚调度，靠仿真时间推进到 contact 稳定后再发射
-- contact_settle_delay = 15 秒（红方 OMNI + 蓝方 autodetectable=true）
-- 数据来源: JSON red_blue_5v3_liaoning1.json
-- ============================================================

_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

-- ---------- 全局打击函数（必须为全局，事件脚本可调用） ----------
-- ★ fireAt 必须是全局（红线 #15）
function fireAt(atkName, tgtName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side="红方", name=atkName})
    local tgt = ScenEdit_GetUnit({side="蓝方", name=tgtName})
    pcall(ScenEdit_SetUnit, {guid=tgt.guid, autodetectable=true})
    pcall(ScenEdit_SetSideOptions, {side="红方", awareness="OMNI"})

    local contactGuid
    local ok, s = pcall(VP_GetSide, {Side="红方"})
    if ok and s and type(s.contacts)=="table" then
        local tg = tostring(tgt.guid):lower()
        for _, c in ipairs(s.contacts) do
            local aid = c.actualunitid or c.actualUnitID or c.actualunitguid
            if aid and tostring(aid):lower()==tg then contactGuid=c.guid; break end
        end
        if not contactGuid then
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
    return string.format("%.0f", (t + 62135596801 + addSeconds) * 1e7)
end

-- ---------- 逐枚调度 ----------
local CONTACT_SETTLE = 15
local INTERVAL       = 1

local function scheduleOne(atkName, tgtName, wpnDbid, delay, k)
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

-- 1) Red-055-1 -> DDG 113-1  (13 枚 YJ-18)
--    注：Red-055-2 无坐标，055 双舰合计 13 枚全打 DDG 113-1
for k = 1, 13 do
    scheduleOne("Red-055-1", "DDG 113-1", 2868, CONTACT_SETTLE + (k-1)*INTERVAL, k)
end
print("[attack] Red-055-1 -> DDG 113-1: 13x YJ-18 调度完毕（T+" .. CONTACT_SETTLE .. "s起）")

-- 2) Red-052D-1 -> Blue-DBID-3551  (8 枚 YJ-18)
for k = 1, 8 do
    scheduleOne("Red-052D-1", "Blue-DBID-3551", 2868, CONTACT_SETTLE + (k-1)*INTERVAL, k)
end
print("[attack] Red-052D-1 -> Blue-DBID-3551: 8x YJ-18 调度完毕（T+" .. CONTACT_SETTLE .. "s起）")

-- 3) Red-052D-2 -> Blue-DBID-2862  (5 枚 YJ-18)
for k = 1, 5 do
    scheduleOne("Red-052D-2", "Blue-DBID-2862", 2868, CONTACT_SETTLE + (k-1)*INTERVAL, k)
end
print("[attack] Red-052D-2 -> Blue-DBID-2862: 5x YJ-18 调度完毕（T+" .. CONTACT_SETTLE .. "s起）")

-- 4) J-15-RED-01 -> Blue-DBID-3551  (4 枚 YJ-83K，loadoutId=9682)
for k = 1, 4 do
    scheduleOne("J-15-RED-01", "Blue-DBID-3551", 2137, CONTACT_SETTLE + (k-1)*INTERVAL, k)
end
print("[attack] J-15-RED-01 -> Blue-DBID-3551: 4x YJ-83K (dbid=2137) 调度完毕（T+" .. CONTACT_SETTLE .. "s起）")

-- 5) J-15-RED-02 -> Blue-DBID-2862  (4 枚 YJ-83K)
for k = 1, 4 do
    scheduleOne("J-15-RED-02", "Blue-DBID-2862", 2137, CONTACT_SETTLE + (k-1)*INTERVAL, k)
end
print("[attack] J-15-RED-02 -> Blue-DBID-2862: 4x YJ-83K (dbid=2137) 调度完毕（T+" .. CONTACT_SETTLE .. "s起）")

print("[attack] ===== 真延时打击调度完毕 =====")
print("[attack] 汇总: Red-055-1(13) + Red-052D-1(8) + Red-052D-2(5) + J-15-01(4) + J-15-02(4) = 34 枚")
print("[attack] contact_settle_delay = " .. CONTACT_SETTLE .. "s，红方 awareness=OMNI")
print("[attack] 执行顺序: main.lua -> clear.lua -> reload.lua -> attack.lua")
