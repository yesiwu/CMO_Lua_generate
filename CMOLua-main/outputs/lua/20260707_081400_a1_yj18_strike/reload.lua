-- ============================================================
-- reload.lua — 装弹脚本（只装 YJ-18）
-- 数据来自 manifest.lua 的 AMMO（与 main.lua name= 完全一致）
-- 装填完成后 dumpAmmo 自检
-- ============================================================

dofile("manifest.lua")

local LOG = "[reload]"
local function info(msg) print(LOG .. " [INFO] "  .. msg) end
local function warn(msg) print(LOG .. " [WARN] "  .. msg) end
local function ok(msg)   print(LOG .. " [OK] "    .. msg) end

-- ---------- 装弹后自检 ----------
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
-- §1 检查 AMMO 装弹方案是否合理（是否含非 YJ-18 弹）
-- ============================================================
info("=== AMMO 装弹清单核查 ===")
for _, a in ipairs(AMMO) do
    if a.wpn_dbid ~= 2868 then
        warn(("  ⚠ %s 装填 dbid=%s（不是 YJ-18/2868）"):format(a.unitname, tostring(a.wpn_dbid)))
    else
        info(("  ✓ %s → YJ-18 ×%d"):format(a.unitname, a.number))
    end
end

-- ============================================================
-- §2 执行装弹（pcall 包装，沙箱可能静默失败）
-- ============================================================
info("=== 执行装弹 ===")
local reloaded = 0
local failed   = 0
for _, a in ipairs(AMMO) do
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
ok(("%d 项装填成功 / %d 项失败"):format(reloaded, failed))

-- ============================================================
-- §3 装弹后自检
-- ============================================================
info("=== 装弹后自检 ===")
for _, name in ipairs(CLEAR_LIST) do
    dumpAmmo("红方", name)
end

print(LOG .. " === reload.lua 完成 ===")
print(LOG .. " 下一步: attack.lua")