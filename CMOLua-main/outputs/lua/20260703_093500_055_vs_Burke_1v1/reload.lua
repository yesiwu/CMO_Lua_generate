-- ============================================================
-- 055 vs Burke 1v1 场景 - 装弹脚本
-- 功能：为055装填16枚YJ-18反舰导弹
-- DBID 来源：MCP 查询 - YJ-18: DBID 2867 (3M54E Klub Copy, Rocket Boosted Penetrator)
-- ============================================================

local LOG = "[RELOAD]"
local SIDE_RED = "红方"
local UNIT_NAME = "南昌舰"

-- YJ-18 反舰导弹 DBID（MCP 查询结果）
local YJ18_DBID = 2867

-- ---------- 日志工具函数 ----------
local function log(level, msg) print(LOG .. " [" .. level .. "] " .. msg) end

-- ---------- 装弹后自检函数 ----------
local function dumpAmmo(side, name)
    local u = ScenEdit_GetUnit({side = side, name = name})
    if not u then return 0 end
    local total = 0
    local yj18_count = 0
    for i, m in ipairs(u.mounts or {}) do
        for _, w in ipairs(m.mount_weapons or {}) do
            local c = tonumber(w.wpn_current) or 0
            if c > 0 then
                if tostring(w.wpn_dbid) == tostring(YJ18_DBID) then
                    yj18_count = yj18_count + c
                end
                total = total + c
            end
        end
    end
    log("INFO", string.format("%s 当前待发弹合计 = %d (其中YJ-18=%d)", name, total, yj18_count))
    return total, yj18_count
end

-- ---------- 执行：装填 YJ-18 ----------
print("")
print("========================================")
log("INFO", "开始装填 YJ-18")
log("INFO", "目标: " .. UNIT_NAME)
log("INFO", "武器: YJ-18 (DBID=" .. YJ18_DBID .. ")")
log("INFO", "数量: 16枚")
print("========================================")

-- 检查当前状态
log("INFO", "装弹前状态:")
dumpAmmo(SIDE_RED, UNIT_NAME)

-- 执行装弹（分批装填，每批8枚）
-- 注意：实际装填数量受 VLS 格口限制
local LOAD_QTY = 16

print("")
log("INFO", "执行装弹: AddReloadsToUnit...")

_errnum_ = 0
local result = ScenEdit_AddReloadsToUnit({
    side     = SIDE_RED,
    unitname = UNIT_NAME,
    wpn_dbid = YJ18_DBID,
    number   = LOAD_QTY,
})

if result then
    log("OK", "装弹指令已发送: " .. LOAD_QTY .. "x YJ-18")
else
    log("WARN", "装弹可能受限，检查返回: " .. tostring(result))
end

-- 装弹后自检
print("")
log("INFO", "装弹后状态:")
local total, yj18_count = dumpAmmo(SIDE_RED, UNIT_NAME)

print("")
if yj18_count >= 13 then
    log("OK", "装弹成功! YJ-18数量足够进行打击(需13枚)")
else
    log("WARN", "YJ-18数量不足，当前=" .. yj18_count .. "，需要>=13枚")
end

print("")
print("========================================")
log("OK", "装弹流程完成")
print("========================================")
