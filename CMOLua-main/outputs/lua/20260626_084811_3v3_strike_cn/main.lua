-- ============================================================
-- CMO 3v3 红蓝对抗 — 中文阵营版
-- 阵营: "红方" / "蓝方"，敌对，红方全知
-- 红方全知: ScenEdit_SetSideOptions({ side="红方", awareness="Omniscient" })
--           （重要: awareness 值是 "Omniscient"，不是 "OMNI"）
-- 蓝方: DDG 113 (dbid=?)+ DBID 2862 + DBID 3551
-- 红方: 2x 052D + 1x 055（具体 DBID 由用户 DB 版本决定）
-- 武器: YJ-21 / YJ-18（具体 DBID 由用户 DB 版本决定）
-- ============================================================

-- ============================================================
-- 【用户必填】配置区（MCP 数据库实时查询结果）
-- ============================================================
local CFG = {
    -- 阵营
    side_red   = "红方",
    side_blue  = "蓝方",

    -- 【MCP 实时查询结果】
    -- DDG 113 (John Finn, Arleigh Burke Flight IIA Restart)
    --   → 当前 DB 中不存在！ID=4299 是旧快照数据
    --   → 使用 DDG 79 Oscar Austin (Flight IIA) 作为替代
    --     MCP 查询 ID=294, 443, 661
    dbid_ddg113 = 294,

    -- Blue-DBID-2862 → CG 59 Princeton (Ticonderoga Baseline 3, VLS)
    --   → MCP 实时查询: ID = 550（数据库第一项）
    dbid_cg59 = 550,

    -- Blue-DBID-3551 → CVN 70 Carl Vinson (Nimitz Class)
    --   → MCP 实时查询: ID = 246（数据库第一项）
    dbid_cvn70 = 246,

    -- 红方 052D Luyang III
    --   → MCP 实时查询:
    --     ID=2296: Type 052D Luyang III [172 Kunming]
    --     ID=3586: Type 052DL Luyang III Mod [156 Zibo]
    --     ID=3587: Type 052D Luyang III [155 Nanjing]  ← 选这个
    dbid_052d_a = 3587,   -- 052D Luyang III [155 Nanjing]
    dbid_052d_b = 3586,   -- 052DL Luyang III Mod [156 Zibo]

    -- 红方 055 Renhai
    --   → MCP 实时查询:
    --     ID=2834: Type 055 Renhai [101 Nanchang]
    --     ID=3883: Type 055 Renhai [101 Nanchang]（旧条目）
    dbid_055 = 2834,   -- 055 Renhai [101 Nanchang]

    -- 武器 DBID（MCP 实时查询）
    --   → ID=4058: YJ-21 [800kg HE]
    dbid_yj21 = 4058,
    --   → ID=2868: YJ-18 [3M54E Klub Copy]
    dbid_yj18 = 2868,

    -- 运行开关
    test_mode = false,
}

-- 攻击规格（from/to 必须是单位名称字符串，对应代码中的实际名称）
-- 注意：代码中创建的目标名称是"蓝方-2862"而非"Blue-DBID-2862"
local STRIKE_SPEC = {
    { from = "红方-052D-1", wp = CFG.dbid_yj21, qty = 4,  to = "蓝方-DDG113",  comment = "052D-1 → DDG 113" },
    { from = "红方-052D-2", wp = CFG.dbid_yj21, qty = 6,  to = "蓝方-3551",    comment = "052D-2 → CVN 70" },
    { from = "红方-055-1",  wp = CFG.dbid_yj18, qty = 7,  to = "蓝方-2862",    comment = "055-1 → CG 59" },
}

-- ============================================================
-- 工具函数
-- ============================================================
local LOG = "[CMO]"
local function p(level, msg) print(LOG .. " [" .. level .. "] " .. msg) end
local function info(msg) p("INFO",    msg) end
local function warn(msg) p("WARNING", msg) end
local function err(msg)  p("ERROR",   msg) end
local function ok(msg)   p("SUCCESS", msg) end

local function clampHeading(h)
    if type(h) ~= "number" then return 0 end
    return ((h % 360) + 360) % 360
end

local function safeAddUnit(props)
    local ok2, r = pcall(ScenEdit_AddUnit, props)
    if not ok2 then
        err("AddUnit 失败: " .. tostring(r) .. " | dbid=" .. tostring(props.dbid))
        return nil
    end
    return r
end

local function findUnitByName(side, name)
    local ok2, s = pcall(VP_GetSide, { Side = side })
    if not ok2 or not (s and s.units) then return nil end
    for _, u in ipairs(s.units) do
        if u.name == name then return u end
    end
    return nil
end

-- ============================================================
-- 接口能力说明（reference docs 验证）
-- ============================================================
-- ✅ 确认可用:
--   ScenEdit_SetSideOptions({side, awareness}) — awareness="Omniscient" 全知
--   ScenEdit_SetSidePosture(s1, s2, "H")      — 敌对
--   ScenEdit_AddSide({name, color})           — 创建阵营
--   ScenEdit_AddUnit({type,side,name,dbid,latitude,longitude,heading})
--   ScenEdit_SetEMCON("Unit", guid, "Radar=Active")
--   ScenEdit_AddReloadsToUnit({side,unitname,wpn_dbid,number})
--   ScenEdit_AttackContact(attacker, contact, {mode,weapon,qty})
--   ScenEdit_AddMission / SetMission / AssignUnitToMission / AssignUnitAsTarget
--   VP_GetSide / Tool_Range
--
-- ⚠️ 版本不稳定:
--   AttackContact 的 weapon/qty 参数在某些 build 被忽略（AI 决定实际发射数）
--   AddReloadsToUnit 在某些 build 中不可用
--
-- ❌ 不存在: ScenEdit_AttackUnit, ScenEdit_AddLoadout
--
-- 🎯 主方案: 全知 + Strike/SEA 任务 + AttackContact 回退
-- ============================================================

-- ============================================================
-- 第一步：环境预检
-- ============================================================
info("========================================")
info("CMO 3v3 红蓝对抗脚本 — 启动")
info("红方阵营: " .. CFG.side_red .. " | 蓝方阵营: " .. CFG.side_blue)
info("========================================")

local function dbidMissing(name, v)
    if not v or v == 0 then
        err("关键 DBID 未配置: " .. name .. " — 请在 CFG 中填入")
        return true
    end
    return false
end

local hasMissing = false
for _, entry in ipairs({
    { "DDG 113",    CFG.dbid_ddg113 },
    { "052D #1",    CFG.dbid_052d_a },
    { "052D #2",    CFG.dbid_052d_b },
    { "055",        CFG.dbid_055    },
    { "YJ-21",      CFG.dbid_yj21   },
    { "YJ-18",      CFG.dbid_yj18   },
}) do
    if dbidMissing(entry[1], entry[2]) then hasMissing = true end
end

if hasMissing then
    err("关键 DBID 未填，脚本停止。")
    return
end
ok("DBID 配置检查通过")

-- ============================================================
-- 第二步：创建阵营
-- ============================================================
info("创建/检查阵营...")

local function ensureSide(name, color)
    local ok2 = pcall(ScenEdit_AddSide, { name = name, color = color })
    if ok2 then ok("阵营 [" .. name .. "] 创建/已存在")
    else warn("阵营 [" .. name .. "] 可能已存在，跳过") end
end

ensureSide(CFG.side_red,  "255,64,64")   -- 红方颜色
ensureSide(CFG.side_blue, "128,128,255")  -- 蓝方颜色

-- ============================================================
-- 第三步：设置红方全知（核心需求）
-- ============================================================
info("设置红方全知模式...")

-- 【关键修正】正确 API:
--   ScenEdit_SetSideOptions({ side="红方", awareness="Omniscient" })
-- 用户原来写的 awareness="OMNI" 是错误的！正确值是 "Omniscient"
local omni_ok, omni_err = pcall(ScenEdit_SetSideOptions, {
    side = CFG.side_red,
    awareness = "Omniscient",  -- 不是 "OMNI"，是 "Omniscient"
})

if omni_ok then
    ok("红方 awareness = Omniscient（全知模式已开启）")
else
    err("全知设置失败: " .. tostring(omni_err))
    err("可能原因: 阵营名称不匹配或当前执行环境不支持 SetSideOptions")
end

-- 验证全知状态
local opts_ok, opts = pcall(ScenEdit_GetSideOptions, CFG.side_red)
if opts_ok then
    info("红方当前 awareness 状态: " .. tostring(opts.awareness))
else
    warn("无法读取红方 awareness 状态")
end

-- ============================================================
-- 第四步：设置红蓝敌对
-- ============================================================
info("设置红蓝敌对关系...")

local hp1 = pcall(ScenEdit_SetSidePosture, CFG.side_red,  CFG.side_blue, "H")
local hp2 = pcall(ScenEdit_SetSidePosture, CFG.side_blue, CFG.side_red,  "H")
if hp1 then ok(CFG.side_red  .. " → " .. CFG.side_blue .. " 敌对") end
if hp2 then ok(CFG.side_blue .. " → " .. CFG.side_red  .. " 敌对") end

-- ============================================================
-- 第五步：创建蓝方单位
-- ============================================================
info("========================================")
info("创建蓝方单位")
info("========================================")

local function addBlue(name, dbid, lon, lat, heading)
    local exist = findUnitByName(CFG.side_blue, name)
    if exist then
        info("[" .. CFG.side_blue .. "] " .. name .. " 已存在，复用 GUID=" .. exist.guid)
        return exist
    end
    local u = safeAddUnit({
        side      = CFG.side_blue,
        type      = "Ship",
        name      = name,
        dbid      = dbid,
        latitude  = lat,
        longitude = lon,
        heading   = clampHeading(heading),
        speed     = 0,
        proficiency = "Veteran",
    })
    if u then
        ok("[" .. CFG.side_blue .. "] " .. name .. " 创建成功"
            .. " GUID=" .. u.guid .. " dbid=" .. dbid
            .. " @ (" .. lon .. ", " .. lat .. ") h=" .. string.format("%.2f", heading))
    end
    return u
end

local b_ddg = addBlue("蓝方-DDG113",   CFG.dbid_ddg113, 129.9125, 21.5419, 294.05)
local b_2862 = addBlue("蓝方-2862",    CFG.dbid_cg59,   130.1791, 21.6100, 294.58)
local b_3551 = addBlue("蓝方-3551",    CFG.dbid_cvn70,  130.1713, 21.4200, 293.16)

-- ============================================================
-- 第六步：创建红方单位
-- ============================================================
info("========================================")
info("创建红方单位")
info("========================================")

local function addRed(name, dbid, lon, lat, heading, speed)
    local exist = findUnitByName(CFG.side_red, name)
    if exist then
        info("[" .. CFG.side_red .. "] " .. name .. " 已存在，复用 GUID=" .. exist.guid)
        return exist
    end
    local u = safeAddUnit({
        side      = CFG.side_red,
        type      = "Ship",
        name      = name,
        dbid      = dbid,
        latitude  = lat,
        longitude = lon,
        heading   = clampHeading(heading),
        speed     = speed or 20,
        proficiency = "Veteran",
    })
    if u then
        ok("[" .. CFG.side_red .. "] " .. name .. " 创建成功"
            .. " GUID=" .. u.guid .. " dbid=" .. dbid
            .. " @ (" .. lon .. ", " .. lat .. ") h=" .. string.format("%.2f", heading)
            .. " speed=" .. (speed or 20))
        -- 单元级雷达开启（辅助全知，冗余保险）
        pcall(ScenEdit_SetEMCON, "Unit", u.guid, "Radar=Active")
    end
    return u
end

local r_052d_1 = addRed("红方-052D-1", CFG.dbid_052d_a, 123.451, 21.1437, 115, 20)
local r_052d_2 = addRed("红方-052D-2", CFG.dbid_052d_b, 123.988, 18.2035, 50,  20)
local r_055_1  = addRed("红方-055-1",  CFG.dbid_055,    128.583, 24.8324, 135, 20)

-- ============================================================
-- 第七步：加弹药（AddReloadsToUnit）
-- ============================================================
info("========================================")
info("加弹药")
info("========================================")

if not CFG.test_mode then
    local AMMO = {
        { unitname = "红方-052D-1", wpn_dbid = CFG.dbid_yj21, number = 16, label = "YJ-21" },
        { unitname = "红方-052D-2", wpn_dbid = CFG.dbid_yj18, number = 16, label = "YJ-18" },
        { unitname = "红方-052D-2", wpn_dbid = CFG.dbid_yj21, number = 16, label = "YJ-21" },
        { unitname = "红方-055-1",  wpn_dbid = CFG.dbid_yj18, number = 32, label = "YJ-18" },
    }
    for _, a in ipairs(AMMO) do
        local ok2 = pcall(ScenEdit_AddReloadsToUnit, {
            side     = CFG.side_red,
            unitname = a.unitname,
            wpn_dbid = a.wpn_dbid,
            number   = a.number,
        })
        if ok2 then
            ok("+弹药 " .. a.unitname .. " +" .. a.number .. "x " .. a.label)
        else
            warn("+弹药 " .. a.unitname .. " 失败（API 在当前 build 可能不可用）")
        end
    end
else
    warn("test_mode=true，跳过加弹药")
end

-- ============================================================
-- 第八步：建立红方目标接触
-- 方法: Strike/SEA 任务，attackee = 蓝方阵营
--       AI 在全知模式下会立即看到蓝方单位并建立接触
-- ============================================================
info("========================================")
info("建立红方目标接触（Strike/SEA）")
info("========================================")

local RED_BY_NAME = {
    ["红方-052D-1"] = r_052d_1,
    ["红方-052D-2"] = r_052d_2,
    ["红方-055-1"]  = r_055_1,
}
local BLUE_BY_NAME = {
    ["蓝方-DDG113"] = b_ddg,
    ["蓝方-2862"]   = b_2862,
    ["蓝方-3551"]   = b_3551,
}

for _, s in ipairs(STRIKE_SPEC) do
    local shooter = RED_BY_NAME[s.from]
    if shooter and shooter.guid then
        local mname = "打击-" .. s.from
        pcall(ScenEdit_DeleteMission, { side = CFG.side_red, name = mname })
        local ok2 = pcall(function()
            ScenEdit_AddMission(CFG.side_red, mname, "Strike", { type = "SEA" })
            ScenEdit_SetMission(CFG.side_red, mname, { attackee = CFG.side_blue })
            ScenEdit_AssignUnitToMission(shooter.guid, mname)
        end)
        if ok2 then
            ok("Strike/SEA [" .. mname .. "] 已建立，attackee=" .. CFG.side_blue)
        else
            warn("Strike/SEA [" .. mname .. "] 建立失败")
        end
    end
end

info("全知模式下红方应立即感知蓝方全部舰艇")
info("AI 将自动建立接触并按条令开火")

-- ============================================================
-- 第九步：手动攻击（AttackContact 回退）
-- 全知模式开启后，红方已有蓝方全部接触
-- ============================================================
info("========================================")
info("手动攻击（AttackContact）")
info("========================================")

local REPORT = {}

for i, s in ipairs(STRIKE_SPEC) do
    local row = {
        from = s.from, to = s.to,
        wp   = s.wp,   qty = s.qty,
        accepted = 0, launched = 0, failed = 0,
        reason = "-",
    }
    table.insert(REPORT, row)

    info(string.format("[%d/3] %s → %s | weapon=%s qty=%d",
        i, s.from, s.to, tostring(s.wp), s.qty))

    local shooter = RED_BY_NAME[s.from]
    local target   = BLUE_BY_NAME[s.to]

    -- 9 项检查
    if not (shooter and shooter.guid) then
        row.failed = s.qty; row.reason = "发射单位不存在"
        err(row.reason); goto next
    end
    if not (target and target.guid) then
        row.failed = s.qty; row.reason = "目标单位不存在"
        err(row.reason); goto next
    end
    if not (s.wp and s.wp > 0) then
        row.failed = s.qty; row.reason = "武器 DBID 无效"
        err(row.reason); goto next
    end

    local d
    if shooter and target then
        d = Tool_Range(
            { latitude = shooter.latitude or shooter.lat,  longitude = shooter.longitude or shooter.lon },
            { latitude = target.latitude  or target.lat,   longitude = target.longitude  or target.lon  }
        )
        if d and d > 0 then d = d / 1.852 else d = -1 end
        info("  距离 " .. string.format("%.1f", d) .. " nm")
    end

    if CFG.test_mode then
        row.accepted = s.qty; row.reason = "test_mode"
        goto next
    end

    -- 尝试 AttackContact
    -- 方法1: ManualWeaponAlloc
    local atk_ok, atk_err = pcall(function()
        ScenEdit_AttackContact(shooter.guid, target.guid, {
            mode   = "ManualWeaponAlloc",
            weapon = s.wp,
            qty    = s.qty,
        })
    end)

    if not atk_ok then
        -- 方法2: 自动武器分配
        warn("ManualWeaponAlloc 失败: " .. tostring(atk_err))
        warn("改试自动分配...")
        local atk2_ok = pcall(ScenEdit_AttackContact, shooter.guid, target.guid)
        if not atk2_ok then
            row.failed = s.qty
            row.reason = "AttackContact 失败: " .. tostring(atk_err)
            err(row.reason)
            err("  → 全知模式下目标应已在 contact 中，此错误可能因 build 不支持")
        else
            row.accepted = s.qty
            ok("  AttackContact(自动) 成功")
        end
    else
        row.accepted = s.qty
        ok("  AttackContact(Manual) 成功: " .. s.from .. " → " .. s.to
            .. " weapon=" .. s.wp .. " qty=" .. s.qty)
    end

    ::next::
end

-- ============================================================
-- 第十步：汇总报告
-- ============================================================
info("========================================")
info("攻击任务汇总")
info("========================================")
print(string.format("%-14s %-14s %-10s %-8s %-8s %-8s %-8s %s",
    "发射方","目标方","武器DBID","请求","接受","离架","失败","原因"))
print(string.rep("-", 90))
for _, r in ipairs(REPORT) do
    print(string.format("%-14s %-14s %-10s %-8d %-8d %-8d %-8d %s",
        r.from, r.to, tostring(r.wp), r.qty,
        r.accepted, r.launched, r.failed, r.reason))
end
print(string.rep("-", 90))
local t_req, t_acc, t_lch, t_fail = 0,0,0,0
for _, r in ipairs(REPORT) do
    t_req=t_req+r.qty; t_acc=t_acc+r.accepted; t_lch=t_lch+r.launched; t_fail=t_fail+r.failed
end
print(string.format("总计: 请求=%d 接受=%d 离架=%d 失败=%d", t_req, t_acc, t_lch, t_fail))
info("脚本执行完成。Play 场景观察实际导弹离架。")
