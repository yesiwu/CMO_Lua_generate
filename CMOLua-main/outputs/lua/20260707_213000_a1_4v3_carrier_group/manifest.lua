-- ============================================================
-- manifest.lua — 4V3 反航母编队 (v2.0 单一数据源)
-- 数据源: json/red_blue_4v3_carrier_group.json
-- 4 红方 vs 3 蓝方: 1×055 + 2×052D + 1×J-16 vs CVN-70 + CG-59 + DDG-113
-- ============================================================

-- ============================================================
-- §A 场景元数据
-- ============================================================
SCENARIO = {
    title       = "4V3 反航母编队协同饱和打击",
    location    = "东海",
    start_time  = "2026-07-07 09:00:00",
    duration    = "1小时15分",
    sides       = { "红方", "蓝方" },
    red_skill   = "OMNI",
    contact_settle_delay = 15,
}

-- ============================================================
-- §B 武器库（YJ-18 / YJ-83K 同 SKU dbid=2868）
-- ============================================================
WEAPONS = {
    {
        dbid             = 2868,
        name             = "YJ-18 [3M54E Klub Copy] / YJ-83K [C-802AK]",
        category         = "Anti-ship missile",
        default_quantity = 8,
        loadout_verified = true,
        note             = "JSON 中 YJ-83K 反舰弹映射为 YJ-18 SKU 2868",
    },
}

-- ============================================================
-- §C 单位清单（dict-keyed：UNITS[id] = {...}）
--   经 MCP 查询确认所有 DBID：
--     055=3883 / 052D-1=2296 / 052D-2=3586 / J-16=2853
--     CVN-70=3551 / CG-59=2862 / DDG-113=4299
-- ============================================================
UNITS = {

    ---------- 红方水面舰艇 ----------
    ["red_055_1"] = {
        side           = "红方",
        name           = "red_055_1",
        type           = "Ship",
        dbid           = 3883,        -- MCP: Type 055 Renhai [101 Nanchang]
        latitude       = 30.316,
        longitude      = 122.650,
        heading        = 90,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "055 主力突击",
    },
    ["red_052d_1"] = {
        side           = "红方",
        name           = "red_052d_1",
        type           = "Ship",
        dbid           = 2296,        -- MCP: Type 052D Luyang III [172 Kunming]
        latitude       = 30.372,
        longitude      = 122.800,
        heading        = 90,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "052D-1 突击",
    },
    ["red_052d_2"] = {
        side           = "红方",
        name           = "red_052d_2",
        type           = "Ship",
        dbid           = 3586,        -- MCP: Type 052DL Luyang III Mod [156 Zibo]
        latitude       = 30.428,
        longitude      = 122.950,
        heading        = 90,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "052D-2 突击",
    },

    ---------- 红方航空 ----------
    -- ★ Aircraft 必须 LoadoutID，不能用 wpn_dbid 直接装弹（SKILL 红线）
    -- 注意：CMO ScenEdit_AddUnit 创建飞机时必须 altitude=0，
    --         高度值会让 AddUnit 拒绝创建！
    ["red_j16_1"] = {
        side           = "红方",
        name           = "red_j16_1",
        type           = "Aircraft",
        dbid           = 2853,        -- MCP: J-16 Flying Shark [Su-30MKK Copy]
        latitude       = 30.484,
        longitude      = 123.100,
        altitude       = 0,           -- ★ 修正：必须 0，飞机创建后用 mission 起降
        heading        = 90,
        speed          = 250,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        loadout_id     = 14059,       -- JSON 给的 LoadoutID（YJ-83K 反舰挂载）
        mission        = {
            type      = "ASW",        -- 用 ASW 任务类型作为巡逻/待机
            latitude  = 30.484,
            longitude = 123.100,
            altitude  = 8000,         -- 任务巡航高度 8000m
        },
        role           = "J-16 投放 YJ-83K",
    },

    ---------- 蓝方目标编队（全部 autodetectable=true） ----------
    ["blue_cvn_1"] = {
        side           = "蓝方",
        name           = "blue_cvn_1",
        type           = "Ship",
        dbid           = 3551,        -- MCP: CVN 70 Carl Vinson
        latitude       = 30.320,
        longitude      = 124.300,
        heading        = 0,
        speed          = 14,          -- JSON motion.speed
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "航母（首要目标）",
    },
    ["blue_cg59_1"] = {
        side           = "蓝方",
        name           = "blue_cg59_1",
        type           = "Ship",
        dbid           = 2862,        -- MCP: CG 59 Princeton (SM-3 Blk IIA)
        latitude       = 30.400,
        longitude      = 124.500,
        heading        = 0,
        speed          = 14,
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "宙斯盾巡洋舰",
    },
    ["blue_ddg113_1"] = {
        side           = "蓝方",
        name           = "blue_ddg113_1",
        type           = "Ship",
        dbid           = 4299,        -- MCP: DDG 113 John Finn (ODIN)
        latitude       = 30.480,
        longitude      = 124.700,
        heading        = 0,
        speed          = 14,
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "伯克 IIA 驱逐舰",
    },
}

-- ============================================================
-- §D 清弹 / 装弹 / 打击清单
-- ============================================================

-- 1) 需要清弹的红方单位（J-16 用 LoadoutID 不进 CLEAR_LIST，
--    但仍清弹以防数据库自带默认挂载）
CLEAR_LIST = {
    "red_055_1",
    "red_052d_1",
    "red_052d_2",
    -- "red_j16_1", -- J-16 走 LoadoutID，跳过直接清弹
}

-- 2) 装弹清单（只装 YJ-18 = dbid 2868）
--   水面舰艇用 ScenEdit_AddReloadsToUnit + wpn_dbid=2868
--   J-16 走 LoadoutID=14059（独立处理，不在此处）
--   但保留 AMMO 记录以便预算自检包含 J-16
AMMO = {
    { unitname = "red_055_1",  wpn_dbid = 2868, number = 8,   isLoadout = false },   -- 055 VLS ×8
    { unitname = "red_052d_1", wpn_dbid = 2868, number = 8,   isLoadout = false },   -- 052D-1 VLS ×8
    { unitname = "red_052d_2", wpn_dbid = 2868, number = 8,   isLoadout = false },   -- 052D-2 VLS ×8
    -- J-16：AMMO 占位（让预算检查覆盖），实际装填走 LoadoutID
    { unitname = "red_j16_1",  wpn_dbid = 2868, number = 2,   isLoadout = true  },   -- J-16 LoadoutID=14059
}

-- 3) Aircraft Loadout 挂载清单（独立项，红线：Aircraft 必须用 LoadoutID）
MOUNT_LOADOUTS = {
    {
        unitname   = "red_j16_1",
        loadout_id = 14059,
        note       = "YJ-83K 反舰挂载（JSON 给定 LoadoutID）",
    },
}

-- ============================================================
-- ★★★ 打击清单（命名键，禁止下标访问 s[1]/s[2]） ★★★
-- 4 个发射平台全部集中打击 blue_cvn_1（首要目标）
-- JSON KC003: 水面+航空同一时间窗口同时发起，多方向 TOT
-- ============================================================
STRIKE = {
    {
        attacker    = "red_055_1",
        target      = "blue_cvn_1",
        weapon_dbid = 2868,
        quantity    = 8,             -- JSON platformExecution.qty=8
        startDelay  = 0,
        interval    = 2,
        intent      = "055-1 突击 CVN-70",
    },
    {
        attacker    = "red_052d_1",
        target      = "blue_cvn_1",
        weapon_dbid = 2868,
        quantity    = 8,             -- JSON qty=8
        startDelay  = 1,
        interval    = 2,
        intent      = "052D-1 突击 CVN-70",
    },
    {
        attacker    = "red_052d_2",
        target      = "blue_cvn_1",
        weapon_dbid = 2868,
        quantity    = 8,             -- JSON qty=8
        startDelay  = 2,
        interval    = 2,
        intent      = "052D-2 突击 CVN-70",
    },
    {
        attacker    = "red_j16_1",
        target      = "blue_cvn_1",
        weapon_dbid = 2868,          -- YJ-83K 在 DB 中映射到 YJ-18 SKU 2868
        quantity    = 2,             -- JSON qty=2
        startDelay  = 3,
        interval    = 2,
        intent      = "J-16 投放 YJ-83K",
    },
}

-- ============================================================
-- §E 弹药预算自检
-- ============================================================
local function checkAmmoBalance()
    local ammoByUnit = {}
    for _, a in ipairs(AMMO) do
        ammoByUnit[a.unitname] = (ammoByUnit[a.unitname] or 0) + a.number
    end

    -- J-16 通过 Loadout 提供的弹药（按 strike.quantity 标定）
    local loadoutAmmoByUnit = {}
    for _, s in ipairs(STRIKE) do
        local isLoadout = false
        for _, m in ipairs(MOUNT_LOADOUTS) do
            if m.unitname == s.attacker then isLoadout = true; break end
        end
        if isLoadout then
            loadoutAmmoByUnit[s.attacker] = (loadoutAmmoByUnit[s.attacker] or 0) + s.quantity
        end
    end

    local strikeByUnit = {}
    for _, s in ipairs(STRIKE) do
        strikeByUnit[s.attacker] = (strikeByUnit[s.attacker] or 0) + s.quantity
    end

    local all_ok = true
    for unit, totalStrike in pairs(strikeByUnit) do
        local totalAmmo = (ammoByUnit[unit] or 0) + (loadoutAmmoByUnit[unit] or 0)
        if totalAmmo < totalStrike then
            print(("[manifest] 弹药不足! %s 装 %d 但 STRIKE 需要 %d"):format(
                unit, totalAmmo, totalStrike))
            all_ok = false
        else
            print(("[manifest] %s 装弹=%d 打击=%d 余=%d"):format(
                unit, totalAmmo, totalStrike, totalAmmo - totalStrike))
        end
    end
    return all_ok
end

local function countKeys(t) local n = 0 for _ in pairs(t) do n = n + 1 end return n end

if not checkAmmoBalance() then
    error("[manifest] 弹药预算不通过，请修正 AMMO/STRIKE/MOUNT_LOADOUTS 后重跑")
end
print("[manifest] 清单校验通过: " .. countKeys(UNITS) .. " 单位, "
    .. #AMMO .. " 水面装弹项, " .. #MOUNT_LOADOUTS .. " 挂载项, "
    .. #STRIKE .. " 打击项")