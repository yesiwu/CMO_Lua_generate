-- ============================================================
-- CMO 通用装弹脚本（先清空 → 再装填 → 自检）
-- 使用方式：修改 CFG 区后直接在 CMO Lua 控制台运行
-- 适用场景：主脚本已创建单元，需更新装弹方案时执行本段
-- ============================================================

-- ============================================================
-- 【配置区】按实际场景修改以下两项
-- ============================================================

-- 阵营名（中文/英文均可，与主脚本一致）
local CFG_SIDE = "红方"

-- 装弹清单：{ 单元名, 武器DBID, 数量, 武器标签 }
-- 武器 DBID 必须通过 MCP query_dbid() 查询，严禁硬编码
local AMMO = {
    -- 示例：
    -- { "红方-052D-1", 4058, 16, "YJ-21" },
    -- { "红方-052D-2", 2868, 16, "YJ-18" },
    -- { "红方-052D-2", 4058, 16, "YJ-21" },
    -- { "红方-055-1",  2868, 32, "YJ-18" },
}

-- ============================================================
-- 以下为通用逻辑，无需修改
-- ============================================================

local LOG = "[CMO]"

-- ---------- 清空：遍历 mounts，批量 remove ----------
local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        print(LOG .. " [WARNING] 清空: 找不到 " .. name); return false
    end
    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs+1] = { dbid = w.wpn_dbid, num = cur, mountid = m.mount_guid }
            end
        end
    end
    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({
            guid = u.guid, wpn_dbid = j.dbid,
            mount_guid = j.mountid, number = j.num, remove = true,
        })
        if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
    end
    print(LOG .. " [OK] " .. name .. " 清空 " .. done .. " 条 (失败 " .. fail .. ")")
    return fail == 0
end

-- ---------- 装弹 ----------
local function reloadWeapon(side, name, dbid, qty)
    _errnum_ = 0
    ScenEdit_AddReloadsToUnit({
        side = side, unitname = name, wpn_dbid = dbid, number = qty,
    })
    if (_errnum_ or 0) == 0 then
        print(LOG .. " [OK] +" .. qty .. " x [" .. dbid .. "] → " .. name)
    else
        print(LOG .. " [WARNING] 装弹失败 " .. name .. " (dbid=" .. dbid .. ")")
    end
end

-- ---------- 自检：打印某舰实际待发弹 ----------
local function dumpAmmo(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u then print(LOG .. " [WARNING] 自检: 找不到 " .. name); return end
    local total = 0
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then
                print(LOG .. " [INFO]   " .. name .. " dbid=" .. tostring(w.wpn_dbid) .. " 数量=" .. c)
                total = total + c
            end
        end
    end
    print(LOG .. " [INFO] " .. name .. " 合计=" .. total)
end

-- ---------- 收集所有要操作的舰名（去重） ----------
local UNIQUENAME = {}
for _, a in ipairs(AMMO) do
    local name = a[1]
    if not UNIQUENAME[name] then UNIQUENAME[name] = true end
end

-- ---------- 执行：清空 → 装弹 → 自检 ----------
print(LOG .. " === 清空待发弹 ===")
for name, _ in pairs(UNIQUENAME) do
    clearUnitWeapons(CFG_SIDE, name)
end

print(LOG .. " === 装弹 ===")
for _, a in ipairs(AMMO) do
    reloadWeapon(CFG_SIDE, a[1], a[2], a[3])
end

print(LOG .. " === 装弹自检 ===")
for name, _ in pairs(UNIQUENAME) do
    dumpAmmo(CFG_SIDE, name)
end
