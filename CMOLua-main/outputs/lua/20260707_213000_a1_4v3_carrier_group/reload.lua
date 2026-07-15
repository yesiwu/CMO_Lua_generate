-- ============================================================
-- reload.lua — 装弹脚本（4V3 反航母编队）
-- 装填策略：
--   * 水面舰艇 (Ship)  → ScenEdit_AddReloadsToUnit + wpn_dbid=2868 (YJ-18)
--   * 飞机 (Aircraft)   → ScenEdit_LoadUnit + loadout_id (YJ-83K, 必须 LoadoutID)
-- 数据来自 manifest.lua 的 AMMO 和 MOUNT_LOADOUTS
-- ============================================================

dofile("manifest.lua")

local LOG = "[reload]"
local function info(msg) print(LOG .. " [INFO] " .. msg) end
local function warn(msg) print(LOG .. " [WARN] " .. msg) end
local function ok(msg)   print(LOG .. " [OK] "   .. msg) end

local function dumpAmmo(side, name)
    local ok2, u = pcall(ScenEdit_GetUnit, { side = side, name = name })
    if not ok2 or not u then return 0 end
    local total = 0
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then
                info(("    MOUNT dbid=%s cur=%d"):format(tostring(w.wpn_dbid), c))
                total = total + c
            end
        end
    end
    ok(name .. " 待发弹合计 = " .. total)
    return total
end

-- ============================================================
-- §1 AMMO 装弹清单核查
-- ============================================================
info("=== AMMO 装弹清单核查（仅 YJ-18/2868） ===")
for _, a in ipairs(AMMO) do
    if a.wpn_dbid ~= 2868 then
        warn(("  ⚠ %s 装填 dbid=%s (不是 YJ-18/2868)"):format(a.unitname, tostring(a.wpn_dbid)))
    else
        info(("  ✓ %s → YJ-18 ×%d"):format(a.unitname, a.number))
    end
end

info("=== MOUNT_LOADOUTS 清单核查（Aircraft） ===")
for _, m in ipairs(MOUNT_LOADOUTS) do
    info(("  ✓ %s → LoadoutID=%d (%s)"):format(m.unitname, m.loadout_id, m.note or ""))
end

-- ============================================================
-- §2 执行装弹（水面舰艇 + Loadout 跳过）
-- ============================================================
info("=== 水面舰艇装弹（isLoadout=false 项） ===")
local reloaded = 0
local failed   = 0
for _, a in ipairs(AMMO) do
    if a.isLoadout then
        info(("  ⊙ 跳过 %s (isLoadout=true，由 MOUNT_LOADOUTS 处理)"):format(a.unitname))
    else
        _errnum_ = 0
        local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
            side     = "红方",
            unitname = a.unitname,
            wpn_dbid = a.wpn_dbid,
            number   = a.number,
        })
        if ok2 and (_errnum_ or 0) == 0 then
            ok(("+ %d × [%d] → %s"):format(a.number, a.wpn_dbid, a.unitname))
            reloaded = reloaded + 1
        else
            warn(("× 装填失败: %s dbid=%d err=%s"):format(
                a.unitname, a.wpn_dbid, tostring(_errmsg_)))
            failed = failed + 1
        end
    end
end
ok(("水面舰艇 %d 项成功 / %d 项失败"):format(reloaded, failed))

-- ============================================================
-- §3 执行挂载（飞机 Loadout）
-- ============================================================
info("=== 飞机挂载 LoadoutID ===")
local mount_ok = 0
local mount_fail = 0
for _, m in ipairs(MOUNT_LOADOUTS) do
    local ok2, u = pcall(ScenEdit_GetUnit, { side = "红方", name = m.unitname })
    if not ok2 or not u or not u.guid then
        warn(("× 单位不存在: %s"):format(m.unitname))
        mount_fail = mount_fail + 1
        goto continue
    end

    -- 保险：先清空飞机的所有挂载
    for _, mm in ipairs(u.mounts or {}) do
        for _, w in ipairs(mm.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                pcall(ScenEdit_AddReloadsToUnit, {
                    guid       = u.guid,
                    wpn_dbid   = w.wpn_dbid,
                    mount_guid = mm.mount_guid,
                    number     = cur,
                    remove     = true,
                })
            end
        end
    end

    -- 应用 LoadoutID（红线：Aircraft 必须用 LoadoutID）
    _errnum_ = 0
    local ok3 = pcall(ScenEdit_LoadUnit, u.guid, m.loadout_id)
    if ok3 and (_errnum_ or 0) == 0 then
        ok(("%s → LoadoutID=%d 挂载成功"):format(m.unitname, m.loadout_id))
        mount_ok = mount_ok + 1
    else
        warn(("× Loadout 失败: %s loadout=%d err=%s"):format(
            m.unitname, m.loadout_id, tostring(_errmsg_)))
        mount_fail = mount_fail + 1
    end

    ::continue::
end
ok(("飞机挂载 %d 成功 / %d 失败"):format(mount_ok, mount_fail))

-- ============================================================
-- §4 装弹后自检
-- ============================================================
info("=== 装弹后自检 ===")
for _, name in ipairs(CLEAR_LIST) do
    dumpAmmo("红方", name)
end
dumpAmmo("红方", "red_j16_1")

print(LOG .. " === reload.lua 完成 ===")
print(LOG .. " 下一步: attack.lua")