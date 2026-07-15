-- ============================================================
-- main.lua — 生成红蓝方单位 (4V3 反航母编队)
-- 数据来自 manifest.lua（与 JSON 同步）
-- 红方全知全能 (OMNI)；蓝方目标 autodetectable=true
-- 蓝方单位传感器默认开启（用户要求）
-- ============================================================

dofile("manifest.lua")

local LOG = "[main]"
local function info(msg) print(LOG .. " [INFO] "  .. msg) end
local function warn(msg) print(LOG .. " [WARN] "  .. msg) end
local function err(msg)  print(LOG .. " [ERROR] " .. msg) end
local function ok(msg)   print(LOG .. " [OK] "    .. msg) end

local function unitExists(side, name)
    local ok2, u = pcall(ScenEdit_GetUnit, { side = side, name = name })
    return ok2 and u and u.guid
end

local function safeAddUnit(spec)
    if unitExists(spec.side, spec.name) then
        warn(("单位已存在，跳过: %s/%s"):format(spec.side, spec.name))
        return ScenEdit_GetUnit({ side = spec.side, name = spec.name })
    end

    -- 关键：ScenEdit_AddUnit 调用飞机/舰船都需要 type
    local args = {
        side           = spec.side,
        type           = spec.type,
        name           = spec.name,
        dbid           = spec.dbid,
        latitude       = spec.latitude,
        longitude      = spec.longitude,
        heading        = spec.heading,
        speed          = spec.speed,
        proficiency    = spec.proficiency,
        autodetectable = spec.autodetectable,
    }
    if spec.altitude then args.altitude = spec.altitude end
    if spec.loadout_id then
        -- 飞机在 AddUnit 时即可应用 LoadoutID（红线：Aircraft 必须 LoadoutID）
        args.loadout_id = spec.loadout_id
    end

    _errnum_ = 0
    local ok2, u = pcall(ScenEdit_AddUnit, args)
    if not ok2 or not u or not u.guid then
        err(("AddUnit 失败: %s/%s dbid=%s err=%s"):format(
            spec.side, spec.name, tostring(spec.dbid), tostring(_errmsg_)))
        return nil
    end

    -- 二次确认 autodetectable
    pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = spec.autodetectable })

    -- 飞机补打一次 Loadout（保险：部分版本 AddUnit 不接受 loadout_id）
    if spec.type == "Aircraft" and spec.loadout_id then
        _errnum_ = 0
        local okLoad = pcall(ScenEdit_LoadUnit, u.guid, spec.loadout_id)
        if okLoad and (_errnum_ or 0) ~= 0 then
            warn(("%s: LoadoutID=%d 应用失败 err=%s（继续，弹可能为空）"):format(
                spec.name, spec.loadout_id, tostring(_errmsg_)))
        end
    end

    -- 给飞机派任务（避免静止浮空看不见）
    if spec.type == "Aircraft" and spec.mission then
        _errnum_ = 0
        local okMis = pcall(ScenEdit_AddMission, u.guid, spec.mission)
        if okMis and (_errnum_ or 0) == 0 then
            ok(("%s 已派任务: %s"):format(spec.name, spec.mission.type or "?"))
        else
            warn(("%s 派任务失败 err=%s"):format(spec.name, tostring(_errmsg_)))
        end
    end

    ok(("创建: %s/%s dbid=%s type=%s"):format(
        spec.side, spec.name, tostring(spec.dbid), spec.type))
    return u
end

-- ============================================================
-- §1 创建阵营
-- ============================================================
info("=== 创建阵营 ===")
pcall(ScenEdit_AddSide, { name = "红方", color = "255,0,0" })
pcall(ScenEdit_AddSide, { name = "蓝方", color = "0,0,255" })
ok("阵营已就绪")

-- ============================================================
-- §2 阵营设置
-- ============================================================
info("=== 阵营设置 ===")

-- 红方 OMNI（全知全能）
pcall(ScenEdit_SetSideOptions, { side = "红方", awareness = "OMNI" })
ok("红方 awareness = OMNI")

-- 蓝方 WCS = Hold（不主动还击，避免 AI 自动反击污染数据）
pcall(ScenEdit_SetDoctrine, { side = "蓝方" }, {
    weapon_control_status_air        = 2,
    weapon_control_status_surface    = 2,
    weapon_control_status_subsurface = 2,
})
pcall(ScenEdit_SetDoctrine, { side = "红方" }, {
    weapon_control_status_air        = 0,
    weapon_control_status_surface    = 0,
    weapon_control_status_subsurface = 0,
})
ok("Doctrine 已设置（红方 Free，蓝方 Hold）")

-- 敌对关系（双向）
pcall(ScenEdit_SetSidePosture, "红方", "蓝方", "H")
pcall(ScenEdit_SetSidePosture, "蓝方", "红方", "H")
ok("红蓝双方敌对 (H)")

-- ============================================================
-- §3 创建所有单位
-- ============================================================
info("=== 创建单位 ===")
local createCount = 0
local totalCount  = 0
for _, spec in pairs(UNITS) do
    if safeAddUnit(spec) then createCount = createCount + 1 end
    totalCount = totalCount + 1
end
ok(("创建 %d / %d 单位"):format(createCount, totalCount))

-- ============================================================
-- §4 蓝方 autodetectable 二次确认（红线 #8）
-- ============================================================
info("=== 蓝方 autodetectable 二次确认 ===")
local blueCount = 0
for _, spec in pairs(UNITS) do
    if spec.side == "蓝方" then
        local ok2, u = pcall(ScenEdit_GetUnit, { side = spec.side, name = spec.name })
        if ok2 and u and u.guid then
            pcall(ScenEdit_SetUnit, { guid = u.guid, autodetectable = true })
            blueCount = blueCount + 1
        end
    end
end
ok("蓝方 " .. blueCount .. " 个单位已强制设置 autodetectable = true")

-- ============================================================
-- §5 蓝方传感器默认开启（用户要求）
-- ============================================================
info("=== 蓝方传感器默认开启 ===")
for _, spec in pairs(UNITS) do
    if spec.side == "蓝方" then
        local ok2, u = pcall(ScenEdit_GetUnit, { side = spec.side, name = spec.name })
        if ok2 and u and u.guid then
            pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active;Sonar=Active;OECM=Passive")
        end
    end
end
ok("蓝方所有单位 EMCON = Radar=Active;Sonar=Active;OECM=Passive")

-- ============================================================
-- §6 完成
-- ============================================================
info("=== main.lua 完成 ===")
print(LOG .. " 下一步: clear.lua → reload.lua → attack.lua")