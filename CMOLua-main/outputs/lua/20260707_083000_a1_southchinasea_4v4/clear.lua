-- ============================================================
-- clear.lua — 清弹脚本
-- 数据来自 manifest.lua 的 CLEAR_LIST（与 main.lua name= 完全一致）
-- 用 ScenEdit_AddReloadsToUnit + remove=true 把所有挂载弹药减到 0
-- 保留 mount 格子（红线：严禁 remove_weapon 删格子）
-- ============================================================

dofile("manifest.lua")

local LOG = "[clear]"
local function info(msg) print(LOG .. " [INFO] " .. msg) end
local function warn(msg) print(LOG .. " [WARN] " .. msg) end
local function ok(msg)   print(LOG .. " [OK] "   .. msg) end

-- ---------- 清空某单位的所有挂载弹药（保留 mount） ----------
local function clearUnitWeapons(side, name)
    local ok2, u = pcall(ScenEdit_GetUnit, { side = side, name = name })
    if not ok2 or not u or not u.guid then
        warn("找不到单位 " .. side .. "/" .. name)
        return false
    end

    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs + 1] = { dbid = w.wpn_dbid, num = cur, mountid = m.mount_guid }
            end
        end
    end

    if #jobs == 0 then
        info(("  %s 原本无弹药，跳过清弹"):format(name))
        return true
    end

    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        local ok3 = pcall(ScenEdit_AddReloadsToUnit, {
            guid       = u.guid,
            wpn_dbid   = j.dbid,
            mount_guid = j.mountid,
            number     = j.num,
            remove     = true,
        })
        if ok3 and (_errnum_ or 0) == 0 then
            done = done + 1
        else
            fail = fail + 1
            warn(("  减载失败: dbid=%s num=%d err=%s"):format(
                tostring(j.dbid), j.num, tostring(_errmsg_)))
        end
    end

    ok(("%s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
end

-- ---------- 自检 ----------
local function dumpAmmo(side, name)
    local ok2, u = pcall(ScenEdit_GetUnit, { side = side, name = name })
    if not ok2 or not u then return end
    local total = 0
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then total = total + c end
        end
    end
    info(("  %s 待发弹合计 = %d"):format(name, total))
end

-- ============================================================
-- 执行
-- ============================================================
info("=== 清空待发弹 ===")
for _, name in ipairs(CLEAR_LIST) do
    clearUnitWeapons("红方", name)
end

info("=== 清弹自检 ===")
for _, name in ipairs(CLEAR_LIST) do
    dumpAmmo("红方", name)
end

print(LOG .. " === clear.lua 完成 ===")
print(LOG .. " 下一步: reload.lua")