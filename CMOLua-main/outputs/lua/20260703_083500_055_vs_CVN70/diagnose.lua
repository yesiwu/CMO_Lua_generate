-- ============================================================
-- diagnose.lua — 简化版诊断脚本
-- ============================================================

print("[CMO] 诊断开始...")

-- ============================================================
-- 诊断 1: 红方阵营
-- ============================================================
print("[CMO] === 诊断 1: 检查红方阵营 ===")
local ok1, sideRed = pcall(VP_GetSide, {Side = "红方"})
if ok1 and sideRed then
    print("[CMO] 红方存在, awareness=" .. tostring(sideRed.awareness))
else
    print("[CMO] [错误] 红方不存在")
end

-- ============================================================
-- 诊断 2: 蓝方 CVN-70
-- ============================================================
print("[CMO] === 诊断 2: 检查 CVN-70 ===")
local ok2, cvn70 = pcall(ScenEdit_GetUnit, {side = "蓝方", name = "CVN-70"})
if ok2 and cvn70 then
    print("[CMO] CVN-70 存在, GUID=" .. tostring(cvn70.guid))
    print("[CMO] CVN-70 位置: " .. string.format("%.4f", cvn70.latitude) .. ", " .. string.format("%.4f", cvn70.longitude))
    print("[CMO] CVN-70 speed=" .. tostring(cvn70.speed) .. ", heading=" .. tostring(cvn70.heading))
    print("[CMO] CVN-70 autodetectable=" .. tostring(cvn70.autodetectable))
else
    print("[CMO] [错误] 找不到 CVN-70")
end

-- ============================================================
-- 诊断 3: 红方 055
-- ============================================================
print("[CMO] === 诊断 3: 检查 055-Nanchang ===")
local ok3, red055 = pcall(ScenEdit_GetUnit, {side = "红方", name = "055-Nanchang"})
if ok3 and red055 then
    print("[CMO] 055 存在, GUID=" .. tostring(red055.guid))
    print("[CMO] 055 位置: " .. string.format("%.4f", red055.latitude) .. ", " .. string.format("%.4f", red055.longitude))
else
    print("[CMO] [错误] 找不到 055-Nanchang")
end

-- ============================================================
-- 诊断 4: 红方 contacts
-- ============================================================
print("[CMO] === 诊断 4: 检查红方 contacts ===")
local ok4, contacts = pcall(ScenEdit_GetContacts, {side = "红方"})
if ok4 then
    if contacts and #contacts > 0 then
        print("[CMO] 红方有 " .. #contacts .. " 个 contacts:")
        for i, c in ipairs(contacts) do
            print("[CMO]   [" .. i .. "] name=" .. tostring(c.name) .. ", guid=" .. tostring(c.guid) .. ", actualunitid=" .. tostring(c.actualunitid))
        end
    else
        print("[CMO] 红方没有任何 contacts")
    end
else
    print("[CMO] [错误] ScenEdit_GetContacts 调用失败")
end

-- ============================================================
-- 诊断 5: 尝试设置红方 awareness
-- ============================================================
print("[CMO] === 诊断 5: 尝试设置红方 OMNI ===")
local ok5, res5 = pcall(ScenEdit_SetSideOptions, "红方", "OMNI")
if ok5 then
    print("[CMO] ScenEdit_SetSideOptions('红方','OMNI') 成功")
else
    print("[CMO] ScenEdit_SetSideOptions('红方','OMNI') 失败: " .. tostring(res5))
end

-- ============================================================
-- 诊断 6: 尝试设置 CVN-70 autodetectable
-- ============================================================
print("[CMO] === 诊断 6: 尝试设置 CVN-70 autodetectable ===")
if ok2 and cvn70 and cvn70.guid then
    local ok6, res6 = pcall(ScenEdit_SetUnit, {guid = cvn70.guid, autodetectable = true})
    if ok6 then
        print("[CMO] ScenEdit_SetUnit autodetectable=true 成功")
    else
        print("[CMO] ScenEdit_SetUnit autodetectable=true 失败: " .. tostring(res6))
    end
else
    print("[CMO] 跳过 (CVN-70 不存在)")
end

-- ============================================================
-- 诊断 7: 再次检查 contacts
-- ============================================================
print("[CMO] === 诊断 7: 再次检查红方 contacts ===")
local ok7, contacts2 = pcall(ScenEdit_GetContacts, {side = "红方"})
if ok7 then
    if contacts2 and #contacts2 > 0 then
        print("[CMO] 红方现在有 " .. #contacts2 .. " 个 contacts")
        for i, c in ipairs(contacts2) do
            print("[CMO]   [" .. i .. "] " .. tostring(c.name))
        end
    else
        print("[CMO] 红方仍然没有 contacts")
    end
end

print("[CMO] 诊断完成!")
