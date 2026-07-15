-- ==========================================================================
-- clear.lua — STEP 2/4 — 消耗与诱歼作战方案
--   清空 manifest.CLEAR_LIST 中所有单位挂载上的武器
--   为下一步 reload.lua 干净装弹做准备
--
-- 自审:
--   [x] 全部用 dofile("manifest.lua") 引用单位名
--   [x] clearUnitWeapons 函数从历史脚本 all.lua 第 131-160 行移植
--   [x] pcall 包裹关键操作
--   [x] 失败不回滚（仅 warn）
-- ==========================================================================

print("[CMO] [INFO] ============ clear.lua 开始 ============")

dofile("manifest.lua")

local function log(level, msg) print("[CMO] [" .. level .. "] " .. tostring(msg)) end
local function info(msg)  log("INFO",    msg) end
local function warn(msg)  log("WARNING", msg) end
local function ok(msg)    log("SUCCESS", msg) end
local function err(msg)   log("ERROR",   msg) end

local function clearUnitWeapons(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u or not u.guid then
        warn("找不到 " .. side .. "/" .. name)
        return false
    end

    local jobs = {}
    for _, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local cur = tonumber(w.wpn_current) or 0
            if cur > 0 then
                jobs[#jobs + 1] = {
                    dbid     = w.wpn_dbid,
                    num      = cur,
                    mountid  = m.mount_guid,
                }
            end
        end
    end

    if #jobs == 0 then
        info(name .. " 无武器,跳过")
        return true
    end

    local done, fail = 0, 0
    for _, j in ipairs(jobs) do
        _errnum_ = 0
        ScenEdit_AddReloadsToUnit({
            guid       = u.guid,
            wpn_dbid   = j.dbid,
            mount_guid = j.mountid,
            number     = j.num,
            remove     = true,
        })
        if (_errnum_ or 0) == 0 then done = done + 1 else fail = fail + 1 end
    end
    ok(("%s: 减载归零 %d 条 (失败 %d)"):format(name, done, fail))
    return fail == 0
end

local function dumpAmmo(side, name)
    local u = ScenEdit_GetUnit({ side = side, name = name })
    if not u then return end
    local total = 0
    for i, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then
                info(("  MOUNT %d dbid=%s cur=%d"):format(i, tostring(w.wpn_dbid), c))
                total = total + c
            end
        end
    end
    ok(name .. " 待发弹合计 = " .. total)
end

-- ==========================================================================
-- 清弹: CLEAR_LIST 中的所有单位
-- ==========================================================================
print()
print("[CMO] ---------- 清弹 " .. #CLEAR_LIST .. " 个单位 ----------")

local cleared = 0
for _, uid in ipairs(CLEAR_LIST) do
    local u = UNITS[uid]
    if u and clearUnitWeapons(u.side, u.name) then
        cleared = cleared + 1
    end
end

-- 自检: 弹清空了吗?
print()
print("[CMO] ---------- 清弹自检 ----------")
for _, uid in ipairs(CLEAR_LIST) do
    local u = UNITS[uid]
    if u then dumpAmmo(u.side, u.name) end
end

if cleared == #CLEAR_LIST then
    ok(string.format("STEP 2 完成: %d/%d 单位清弹成功", cleared, #CLEAR_LIST))
    print("[CMO] [INFO] 下一步: 跑 reload.lua (装弹)")
else
    warn(string.format("STEP 2 部分完成: %d/%d 单位清弹", cleared, #CLEAR_LIST))
end