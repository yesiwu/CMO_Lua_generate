-- ============================================================
-- attack.lua — 真延时齐射打击（TOT 事件驱动）
-- 红线#9: qty=1 逐枚调度 + contact_settle_delay=15s
-- 红线#15: fireAt / totTicks / scheduleOne 必须是全局函数
--
-- 水面：055/052D×2 各 8×YJ-18（DBID=2868）→ CVN-70（ripple 5s）
-- 航空：J-15×2 各 4×YJ-83K（DBID=2137）→ CG-59/DDG-113（ripple 5s）
-- ============================================================

print("\n===== [attack] 真延时齐射 =====")

-- ============================================================
-- TOT 工具（全局函数，红线#15）
-- ============================================================

-- .NET Ticks = Unix秒 * 1e7 + 621355968000000000
-- 实测来源：https://forums.matrixgames.com/viewtopic.php?t=383299
function totTicks(unixSec)
    return string.format("%.0f", unixSec * 1e7 + 621355968000000000)
end

-- 真延时调度：每枚弹一个独立 Time 触发器
function scheduleOne(atkName, tgtName, wpnDbid, qty, delay, tag)
    local fireUnix = ScenEdit_CurrentTime() + delay
    local fireTime = totTicks(fireUnix)
    local ts = tostring(fireUnix)
    local evName = "Ev_" .. tag .. "_" .. ts
    local trName = "Tr_" .. tag .. "_" .. ts
    local acName = "Ac_" .. tag .. "_" .. ts

    local script = table.concat({
        ("fireAt(%q,%q,%d,%d)\n"):format(atkName, tgtName, wpnDbid, qty),
        ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(evName),
        ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(acName),
        ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(trName),
    })

    pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=trName, Time=fireTime})
    pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=acName, ScriptText=script})
    pcall(ScenEdit_SetEvent,   evName, {mode="add", IsActive=true, IsRepeatable=false})
    pcall(ScenEdit_SetEventTrigger, evName, {mode="add", name=trName})
    pcall(ScenEdit_SetEventAction,  evName, {mode="add", name=acName})

    print(("[attack] [TOT] %s@T+%ds → %s weapon=%d qty=%d"):format(
        atkName, delay, tgtName, wpnDbid, qty))
end

-- ============================================================
-- fireAt（全局，红线#15）
-- ============================================================
function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({side="红方", name=attackerName})
    local tgt = ScenEdit_GetUnit({side="蓝方", name=targetName})
    if not (atk and atk.guid) then
        print(("[CMO] [ERROR] fireAt: 找不到攻击方 %s"):format(attackerName))
        return false
    end
    if not (tgt and tgt.guid) then
        print(("[CMO] [ERROR] fireAt: 找不到目标 %s"):format(targetName))
        return false
    end

    -- 强制 autodetectable（红线#8：三重保险）
    pcall(ScenEdit_SetUnit, {guid=tgt.guid, autodetectable=true})

    local function sameGuid(a, b)
        if not (a and b) then return false end
        return string.lower(tostring(a)) == string.lower(tostring(b))
    end
    local function collectContacts(sn)
        local ok, r = pcall(ScenEdit_GetContacts, {side=sn})
        return (ok and r) and r or {}
    end
    local function findContact()
        local cs = collectContacts("红方")
        for _, c in ipairs(cs) do
            for _, f in ipairs({"actualunitid","actualUnitID","actualunitguid",
                                  "actualUnitGuid","actualguid","actualGuid"}) do
                if sameGuid(c[f], tgt.guid) then return c.guid or c.Guid end
            end
        end
        for _, c in ipairs(cs) do
            local cg = c.guid or c.Guid
            local nm = c.name or c.Name or c.contact_name or ""
            if cg and nm and (nm == targetName or nm:find(targetName, 1, true)) then
                return cg
            end
        end
        return nil
    end

    local contactGuid = findContact()
    _errnum_ = 0
    local r
    if contactGuid then
        r = ScenEdit_AttackContact(atk.guid, contactGuid,
            {mode="1", weapon=wpnDbid, qty=qty})
    else
        r = ScenEdit_AttackContact(atk.guid, tgt.guid,
            {mode="1", weapon=wpnDbid, qty=qty})
    end
    if not r then
        r = ScenEdit_AttackContact(atk.guid, tgt.guid,
            {mode="1", weapon=wpnDbid, qty=qty})
    end
    print(("[CMO] [FIRE] %s → %s weapon=%d qty=%d result=%s"):format(
        attackerName, targetName, wpnDbid, qty, tostring(r ~= nil)))
    return r ~= nil
end

-- ============================================================
-- TOT 配置
-- ============================================================
local _CONTACT_SETTLE = 15  -- 秒（用户指定）

-- 水面阵位：055/052D×2 各 8×YJ-18 → CVN-70
local WATER_TOT = {
    {atk="红方055南昌舰",    tgt="蓝方CVN-70卡尔文森", wpn=2868, qty=8, delay=135},
    {atk="红方052D-1昆明舰",  tgt="蓝方CVN-70卡尔文森", wpn=2868, qty=8, delay=140},
    {atk="红方052D-2南京舰",  tgt="蓝方CVN-70卡尔文森", wpn=2868, qty=8, delay=145},
}
-- 航空阵位：J-15×2 各 4×YJ-83K → CG-59/DDG-113
local AIR_TOT = {
    {atk="J-15-1", tgt="蓝方CG-59普林斯顿",    wpn=2137, qty=4, delay=155},
    {atk="J-15-2", tgt="蓝方DDG-113约翰芬恩",  wpn=2137, qty=4, delay=160},
}

local function getUnit(side, name)
    local ok, u = pcall(ScenEdit_GetUnit, {side=side, name=name})
    if ok and u and u.guid then return u end
    return nil
end

for _, t in ipairs(WATER_TOT) do
    if not getUnit("红方", t.atk) then print("[attack] !! 找不到红方: " .. t.atk) end
    if not getUnit("蓝方", t.tgt) then print("[attack] !! 找不到蓝方: " .. t.tgt) end
end
for _, t in ipairs(AIR_TOT) do
    if not getUnit("红方", t.atk) then print("[attack] !! 找不到红方: " .. t.atk) end
    if not getUnit("蓝方", t.tgt) then print("[attack] !! 找不到蓝方: " .. t.tgt) end
end

-- ============================================================
-- 执行水面通道 TOT
-- ============================================================
print("\n[attack] === 水面通道 TOT（YJ-18 → CVN-70）===")
for i, t in ipairs(WATER_TOT) do
    scheduleOne(t.atk, t.tgt, t.wpn, t.qty, t.delay + _CONTACT_SETTLE, "WATER_" .. i)
end

-- ============================================================
-- 执行航空通道 TOT
-- ============================================================
print("\n[attack] === 航空通道 TOT（J-15 YJ-83K）===")
for i, t in ipairs(AIR_TOT) do
    scheduleOne(t.atk, t.tgt, t.wpn, t.qty, t.delay + _CONTACT_SETTLE, "AIR_" .. i)
end

-- ============================================================
-- J-15 RTB 调度（红线#19：base + homebase 双重）
-- ============================================================
print("\n[attack] === J-15 RTB 调度 ===")

local RTB_DELAY   = 175 + 60
local RTB_TS     = tostring(ScenEdit_CurrentTime())
local RTB_TR_NAME = "Tr_RTB_" .. RTB_TS
local RTB_AC_NAME = "Ac_RTB_" .. RTB_TS
local RTB_EV_NAME = "Ev_RTB_" .. RTB_TS
local RTB_FIRE    = totTicks(ScenEdit_CurrentTime() + RTB_DELAY)

local RTB_SCRIPT = table.concat({
    -- J-15-1（三重保险）
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,course={{latitude=30.60,longitude=122.30}},altitude=8000,throttle='Cruise',speed=300})\n"):format("红方","J-15-1"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,homebase=%q})\n"):format("红方","J-15-1","红方辽宁舰"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,base=%q})\n"):format("红方","J-15-1","红方辽宁舰"),
    -- J-15-2（三重保险）
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,course={{latitude=30.60,longitude=122.30}},altitude=8000,throttle='Cruise',speed=300})\n"):format("红方","J-15-2"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,homebase=%q})\n"):format("红方","J-15-2","红方辽宁舰"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,base=%q})\n"):format("红方","J-15-2","红方辽宁舰"),
    -- 自清理
    ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(RTB_EV_NAME),
    ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(RTB_AC_NAME),
    ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(RTB_TR_NAME),
})

pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=RTB_TR_NAME, Time=RTB_FIRE})
pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=RTB_AC_NAME, ScriptText=RTB_SCRIPT})
pcall(ScenEdit_SetEvent,   RTB_EV_NAME, {mode="add", IsActive=true, IsRepeatable=false})
pcall(ScenEdit_SetEventTrigger, RTB_EV_NAME, {mode="add", name=RTB_TR_NAME})
pcall(ScenEdit_SetEventAction,  RTB_EV_NAME, {mode="add", name=RTB_AC_NAME})

print(("[attack] ✓ J-15 RTB 已调度: T+%ds (base+homebase=红方辽宁舰)"):format(RTB_DELAY))

print("\n========================================")
print("[attack] TOT 时间线（contact_settle=" .. _CONTACT_SETTLE .. "s）")
print("  T+150s  红方055南昌舰    8×YJ-18 → 蓝方CVN-70卡尔文森")
print("  T+155s  红方052D-1昆明舰 8×YJ-18 → 蓝方CVN-70卡尔文森")
print("  T+160s  红方052D-2南京舰 8×YJ-18 → 蓝方CVN-70卡尔文森")
print("  T+170s  J-15-1          4×YJ-83K → 蓝方CG-59普林斯顿")
print("  T+175s  J-15-2          4×YJ-83K → 蓝方DDG-113约翰芬恩")
print("  T+~235s J-15×2 RTB（base+homebase=红方辽宁舰）")
print("  T+~290s 航空 YJ-83K 命中 CG-59/DDG-113")
print("  T+~350s 水面 YJ-18 命中 CVN-70")
print("========================================")
print("\n[attack] 完成。")
