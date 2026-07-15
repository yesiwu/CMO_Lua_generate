-- ============================================================
-- CMO 通用打击脚本（contact 优先 → BOL 兜底）
-- 使用方式：修改 CFG 区后直接在 CMO Lua 控制台运行
-- 适用场景：红方全知 / BOL 均可发射
-- ============================================================

-- ============================================================
-- 【配置区】按实际场景修改以下两项
-- ============================================================

local CFG_SIDE_RED  = "红方"
local CFG_SIDE_BLUE = "蓝方"

-- 打击清单：{ 攻击方, 目标, 武器DBID, 数量 }
-- 武器 DBID 必须通过 MCP query_dbid() 查询，严禁硬编码
local STRIKE = {
    -- 示例：
    -- { "红方-055-1",  "蓝方-CG59",  2868, 7 },
    -- { "红方-052D-1", "蓝方-DD113",  4058, 4 },
    -- { "红方-052D-2", "蓝方-CV70",   4058, 6 },
}

-- ============================================================
-- 以下为通用逻辑，无需修改
-- ============================================================

local LOG = "[CMO]"

local function fireAt(attackerName, targetName, wpnDbid, qty)
    local atk = ScenEdit_GetUnit({ side = CFG_SIDE_RED, name = attackerName })
    local tgt = ScenEdit_GetUnit({ side = CFG_SIDE_BLUE, name = targetName })

    if not (atk and atk.guid) then
        print(LOG .. " [ERROR] 找不到攻击方 " .. attackerName); return false
    end
    if not (tgt and tgt.guid) then
        print(LOG .. " [ERROR] 找不到目标 " .. targetName); return false
    end

    -- 优先：从红方 contact 列表中找指向该目标的 contact
    local contactGuid
    local pok, cs = pcall(ScenEdit_GetContacts, { side = CFG_SIDE_RED })
    if pok and type(cs) == "table" then
        for _, c in ipairs(cs) do
            if c.actualunitid == tgt.guid then contactGuid = c.guid; break end
        end
    end

    _errnum_ = 0
    local r
    if contactGuid then
        -- contact 存在：精确跟踪发射
        r = ScenEdit_AttackContact(atk.guid, contactGuid,
                { mode = 1, weapon = wpnDbid, qty = qty })
        print(LOG .. " [INFO] " .. attackerName .. " → contact 攻击 " .. targetName)
    else
        -- contact 不存在（蓝方未全开 / 未被探测）：朝坐标 BOL 发射
        print(LOG .. " [WARNING] " .. attackerName .. " 未探测到 " .. targetName
            .. "，改用 BOL 朝坐标发射")
        r = ScenEdit_AttackContact(atk.guid, "BOL", {
                latitude  = tgt.latitude,
                longitude = tgt.longitude,
                mode      = 1,
                weapon    = wpnDbid,
                qty       = qty,
            })
    end

    if r and (_errnum_ or 0) == 0 then
        print(LOG .. " [OK] " .. attackerName .. " 发射 " .. qty .. "x ["
            .. wpnDbid .. "] → " .. targetName)
        return true
    else
        print(LOG .. " [ERROR] " .. attackerName .. " 攻击 " .. targetName
            .. " 失败: " .. tostring(_errmsg_))
        return false
    end
end

-- ============================================================
-- 执行
-- ============================================================
print(LOG .. " === 下达打击指令 ===")
for _, s in ipairs(STRIKE) do
    fireAt(s[1], s[2], s[3], s[4])
end
print(LOG .. " === 打击指令下达完毕 ===")
