-- ============================================================
-- attack.lua — 真延时齐射打击（TOT 事件驱动）
-- 红线#9: qty=1 逐枚调度 + contact_settle_delay=15s
-- 红线#15: fireAt / totTicks / scheduleOne 必须是全局函数
-- ============================================================

print("\n===== [attack] 真延时齐射 =====")

-- ============================================================
-- ★★★ TOT 工具（全局函数，红线#15）★★★
-- ============================================================

-- .NET Ticks = Unix秒 * 1e7 + 621355968000000000
-- 公式来源：Matrix Games 论坛实测（https://forums.matrixgames.com/viewtopic.php?t=383299）
local _TOT_OFFSET = 621355968000000000
function totTicks(unixSec)
    return string.format("%.0f", unixSec * 1e7 + _TOT_OFFSET)
end

-- 真延时调度（每枚弹一个独立 Time 触发器）
-- @param delay 从脚本执行时起的延迟（秒）
-- @param tag 唯一标识
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

    print(("[attack] [TOT] %s@T+%ds → %s weapon=%d qty=%d fireTime=%s"):format(
        atkName, delay, tgtName, wpnDbid, qty, fireTime))
end

-- ============================================================
-- ★★★ fireAt（全局，红线#15）★★★
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

    -- 强制 autodetectable（红线#8：蓝方目标三重保证）
    pcall(ScenEdit_SetUnit, {guid=tgt.guid, autodetectable=true})

    -- 收集 contact
    local function sameGuid(a, b)
        if not (a and b) then return false end
        return string.lower(tostring(a)) == string.lower(tostring(b))
    end
    local function contactName(c)
        return c.name or c.Name or c.contact_name or ""
    end
    local function collectContacts(sideName)
        local ok, r = pcall(ScenEdit_GetContacts, {side=sideName})
        return (ok and r) and r or {}
    end
    local function findContact()
        local cs = collectContacts("红方")
        for _, c in ipairs(cs) do
            local fields = {"actualunitid","actualUnitID","actualunitguid",
                           "actualUnitGuid","actualguid","actualGuid"}
            for _, f in ipairs(fields) do
                if sameGuid(c[f], tgt.guid) then
                    return c.guid or c.Guid
                end
            end
        end
        for _, c in ipairs(cs) do
            local cg = c.guid or c.Guid
            local nm = contactName(c)
            if cg and nm and (nm == targetName or nm:find(targetName, 1, true)) then
                return cg
            end
        end
        return nil
    end

    local contactGuid = findContact()
    if not contactGuid then
        print(("[CMO] [WARN] fireAt: 未找到 %s contact，将尝试 BOL 攻击"):format(targetName))
    end

    _errnum_ = 0
    local r
    if contactGuid then
        r = ScenEdit_AttackContact(atk.guid, contactGuid, {mode="1", weapon=wpnDbid, qty=qty})
    else
        -- BOL 攻击：朝目标坐标发射（不跟踪）
        r = ScenEdit_AttackContact(atk.guid, tgt.guid, {mode="1", weapon=wpnDbid, qty=qty})
    end
    if not r then
        print(("[CMO] [WARN] fireAt: %s → %s weapon=%d qty=%d 返回nil，尝试 UNIT-GUID 后备"):format(
            attackerName, targetName, wpnDbid, qty))
        r = ScenEdit_AttackContact(atk.guid, tgt.guid, {mode="1", weapon=wpnDbid, qty=qty})
    end
    print(("[CMO] [FIRE] %s → %s weapon=%d qty=%d result=%s"):format(
        attackerName, targetName, wpnDbid, qty, tostring(r ~= nil)))
    return r ~= nil
end

-- ============================================================
-- TOT 配置
-- ============================================================
-- contact_settle_delay = 15s（用户指定）
local _CONTACT_SETTLE = 15

-- TOT 时间表（秒 = 从脚本执行起算）
-- 水面通道：T+135s 起跳（135 = 120+15），ripple 5s
-- 航空通道：T+145s（T+135+10），ripple 5s
--
-- TOT 对齐：水面+航空共 6 批，全在 ±30s 内
-- 水面批: T+135 / T+140 / T+145 → YJ-18 飞行 ~180s → 命中 T+315/320/325
-- 航空批: T+155 / T+160         → YJ-83K 飞行 ~120s → 命中 T+275/280
--
-- RTB: 攻击触发完+60s缓冲 = T+175+60 = T+235s
-- J-15 RTB 触发: T+235s → homebase/base 辽宁舰

-- 水面阵位：055/052D×2 各 8 枚 YJ-18，ripple 5s
local WATER_TOT = {
    {atk="红方055南昌舰",  tgt="蓝方CVN-70卡尔文森", wpn=2868, qty=8, delay=135},
    {atk="红方052D-1昆明舰", tgt="蓝方CVN-70卡尔文森", wpn=2868, qty=8, delay=140},
    {atk="红方052D-2南京舰", tgt="蓝方CVN-70卡尔文森", wpn=2868, qty=8, delay=145},
}

-- 航空阵位：J-15×2 各 4 枚 YJ-83K，ripple 5s
local AIR_TOT = {
    {atk="J-15-1", tgt="蓝方CG-59普林斯顿", wpn=2137, qty=4, delay=155},
    {atk="J-15-2", tgt="蓝方DDG-113约翰芬恩", wpn=2137, qty=4, delay=160},
}

-- ============================================================
-- 验证单位存在
-- ============================================================
local function getUnit(side, name)
    local ok, u = pcall(ScenEdit_GetUnit, {side=side, name=name})
    if ok and u and u.guid then return u end
    return nil
end

for _, t in ipairs(WATER_TOT) do
    if not getUnit("红方", t.atk) then print("[attack] !! 找不到红方单位: " .. t.atk) end
    if not getUnit("蓝方", t.tgt) then print("[attack] !! 找不到蓝方目标: " .. t.tgt) end
end
for _, t in ipairs(AIR_TOT) do
    if not getUnit("红方", t.atk) then print("[attack] !! 找不到红方单位: " .. t.atk) end
    if not getUnit("蓝方", t.tgt) then print("[attack] !! 找不到蓝方目标: " .. t.tgt) end
end

-- ============================================================
-- 执行水面通道 TOT 调度
-- ============================================================
print("\n[attack] === 水面通道 TOT 调度（YJ-18 → CVN-70）===")
for i, t in ipairs(WATER_TOT) do
    local tag = ("WATER_%d"):format(i)
    scheduleOne(t.atk, t.tgt, t.wpn, t.qty, t.delay + _CONTACT_SETTLE, tag)
end

-- ============================================================
-- 执行航空通道 TOT 调度
-- ============================================================
print("\n[attack] === 航空通道 TOT 调度（J-15 YJ-83K）===")
for i, t in ipairs(AIR_TOT) do
    local tag = ("AIR_%d"):format(i)
    scheduleOne(t.atk, t.tgt, t.wpn, t.qty, t.delay + _CONTACT_SETTLE, tag)
end

-- ============================================================
-- J-15 RTB 调度（红线#19：base + homebase 双重）
-- ============================================================
print("\n[attack] === J-15 RTB 调度 ===")

local RTB_DELAY = 175 + 60  -- 攻击完+60s缓冲
local RTB_TR_NAME  = "Tr_RTB_" .. tostring(ScenEdit_CurrentTime())
local RTB_AC_NAME  = "Ac_RTB_" .. tostring(ScenEdit_CurrentTime())
local RTB_EV_NAME  = "Ev_RTB_" .. tostring(ScenEdit_CurrentTime())
local RTB_FIRE_TIME = totTicks(ScenEdit_CurrentTime() + RTB_DELAY)

local RTB_SCRIPT = table.concat({
    -- J-15-1 RTB（三重保险）
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,course={{latitude=30.60,longitude=122.30}},altitude=8000,throttle='Cruise',speed=300})\n"):format("红方","J-15-1"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,homebase=%q})\n"):format("红方","J-15-1","红方辽宁舰"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,base=%q})\n"):format("红方","J-15-1","红方辽宁舰"),
    -- J-15-2 RTB（三重保险）
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,course={{latitude=30.60,longitude=122.30}},altitude=8000,throttle='Cruise',speed=300})\n"):format("红方","J-15-2"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,homebase=%q})\n"):format("红方","J-15-2","红方辽宁舰"),
    ("pcall(ScenEdit_SetUnit,{side=%q,unitname=%q,base=%q})\n"):format("红方","J-15-2","红方辽宁舰"),
    -- 自清理
    ("ScenEdit_SetEvent(%q,{mode='remove'})\n"):format(RTB_EV_NAME),
    ("ScenEdit_SetAction({mode='remove',type='LuaScript',name=%q})\n"):format(RTB_AC_NAME),
    ("ScenEdit_SetTrigger({mode='remove',type='Time',name=%q})\n"):format(RTB_TR_NAME),
})

pcall(ScenEdit_SetTrigger, {mode="add", type="Time", name=RTB_TR_NAME, Time=RTB_FIRE_TIME})
pcall(ScenEdit_SetAction,  {mode="add", type="LuaScript", name=RTB_AC_NAME, ScriptText=RTB_SCRIPT})
pcall(ScenEdit_SetEvent,   RTB_EV_NAME, {mode="add", IsActive=true, IsRepeatable=false})
pcall(ScenEdit_SetEventTrigger, RTB_EV_NAME, {mode="add", name=RTB_TR_NAME})
pcall(ScenEdit_SetEventAction,  RTB_EV_NAME, {mode="add", name=RTB_AC_NAME})

print(("[attack] ✓ J-15 RTB 已调度: T+%ds (homebase=红方辽宁舰)"):format(RTB_DELAY))

-- ============================================================
-- 时间线总结
-- ============================================================
print("\n========================================")
print("[attack] TOT 时间线（contact_settle=15s）")
print("  T+150s  红方055南昌舰 8×YJ-18 → CVN-70")
print("  T+155s  红方052D-1昆明舰 8×YJ-18 → CVN-70")
print("  T+160s  红方052D-2南京舰 8×YJ-18 → CVN-70")
print("  T+170s  J-15-1 4×YJ-83K → CG-59")
print("  T+175s  J-15-2 4×YJ-83K → DDG-113")
print("  T+~235s J-15×2 RTB（homebase=辽宁舰）")
print("  T+~300s 航空 YJ-83K 命中")
print("  T+~350s 水面 YJ-18 命中")
print("========================================")
print("\n[attack] 完成。")
