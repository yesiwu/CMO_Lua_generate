-- ============================================================
-- manifest.lua — 南海 4V4 YJ-18 联合反舰打击 (v2.0)
-- 4 红方 (1×055 + 2×052D + 1×055)  vs  4 蓝方 (2×DDG-113 + CVN-70 + CG-59)
-- 实际是 4V4：用户要求 2 艘 055 打 2 艘 DDG-113，
--          + 052D-1 打 CVN-70
--          + 052D-2 打 CG-59
-- 单一数据源：main/clear/reload/attack 全部从此文件引用
-- DBID 全部经 MCP 查询确认（用户指定与 MCP 结果一致）
-- ============================================================

-- ============================================================
-- §A 场景元数据
-- ============================================================
SCENARIO = {
    title       = "南海 4V4 YJ-18 反舰饱和打击",
    location    = "南海",
    start_time  = "2026-07-07 08:30:00",
    duration    = "1小时",
    sides       = { "红方", "蓝方" },
    red_skill   = "OMNI",
    contact_settle_delay = 15,
}

-- ============================================================
-- §B 武器库（仅 YJ-18）
-- ============================================================
WEAPONS = {
    {
        dbid             = 2868,
        name             = "YJ-18 [3M54E Klub Copy]",
        category         = "Anti-ship missile",
        default_quantity = 8,
        loadout_verified = true,
    },
}

-- ============================================================
-- §C 单位清单（dict-keyed：UNITS[id] = {...}）
--   ★ id 字段即是 main.lua 的 ScenEdit_AddUnit({name=id}) 的 name=
--   ★ 红方全部 055 / 052D 系列（YJ-18 兼容挂载）
--   ★ 蓝方目标全部 autodetectable = true（红线 #8）
-- ============================================================
UNITS = {

    ---------- 红方水面舰艇编队 ----------
    -- 2 艘 055 打 2 艘 DDG-113
    ["Red-055-1"] = {
        side           = "红方",
        name           = "Red-055-1",
        type           = "Ship",
        dbid           = 3883,        -- MCP: Type 055 Renhai [101 Nanchang] (YJ-21 标签)
        latitude       = 18.50,
        longitude      = 113.00,
        heading        = 180,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "055 主力突击 DDG-113 #1",
    },
    ["Red-055-2"] = {
        side           = "红方",
        name           = "Red-055-2",
        type           = "Ship",
        dbid           = 3883,        -- 同型 055
        latitude       = 18.60,
        longitude      = 113.10,
        heading        = 180,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "055 主力突击 DDG-113 #2",
    },

    -- 2 艘 052D 分别打击 CVN-70 和 CG-59
    ["Red-052D-1"] = {
        side           = "红方",
        name           = "Red-052D-1",
        type           = "Ship",
        dbid           = 2296,        -- MCP: Type 052D Luyang III [172 Kunming]
        latitude       = 18.40,
        longitude      = 113.20,
        heading        = 180,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "052D-1 突击 CVN-70",
    },
    ["Red-052D-2"] = {
        side           = "红方",
        name           = "Red-052D-2",
        type           = "Ship",
        dbid           = 3586,        -- MCP: Type 052DL Luyang III Mod [156 Zibo] (052D 家族)
        latitude       = 18.70,
        longitude      = 113.20,
        heading        = 180,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "052D-2 突击 CG-59",
    },

    ---------- 蓝方目标编队（全部 autodetectable=true） ----------
    ["Blue-DDG113-1"] = {
        side           = "蓝方",
        name           = "Blue-DDG113-1",
        type           = "Ship",
        dbid           = 4299,        -- MCP: DDG 113 John Finn (ODIN Laser Dazzler)
        latitude       = -0.50,
        longitude      = 105.50,
        heading        = 0,
        speed          = 0,
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "伯克 IIA 驱逐舰 #1",
    },
    ["Blue-DDG113-2"] = {
        side           = "蓝方",
        name           = "Blue-DDG113-2",
        type           = "Ship",
        dbid           = 4299,        -- 同型 DDG-113
        latitude       = -0.40,
        longitude      = 105.80,
        heading        = 0,
        speed          = 0,
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "伯克 IIA 驱逐舰 #2",
    },
    ["Blue-CVN70"] = {
        side           = "蓝方",
        name           = "Blue-CVN70",
        type           = "Ship",
        dbid           = 3551,        -- MCP: CVN 70 Carl Vinson
        latitude       = -0.90,
        longitude      = 106.11,
        heading        = 0,
        speed          = 0,
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "航母（核心目标）",
    },
    ["Blue-CG59"] = {
        side           = "蓝方",
        name           = "Blue-CG59",
        type           = "Ship",
        dbid           = 2862,        -- MCP: CG 59 Princeton (SM-3 Blk IIA)
        latitude       = -0.66,
        longitude      = 105.95,
        heading        = 0,
        speed          = 0,
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "宙斯盾巡洋舰",
    },
}

-- ============================================================
-- §D 清弹 / 装弹 / 打击清单
-- ============================================================

-- 1) 需要清弹的红方单位
CLEAR_LIST = {
    "Red-055-1",
    "Red-055-2",
    "Red-052D-1",
    "Red-052D-2",
}

-- 2) 装弹清单（用户指定：只装 YJ-18）
--   2 艘 055 装 16 枚 YJ-18 / 052D-1 装 16 枚 YJ-18 / 052D-2 装 10 枚 YJ-18
AMMO = {
    { unitname = "Red-055-1",  wpn_dbid = 2868, number = 16 },  -- YJ-18 ×16
    { unitname = "Red-055-2",  wpn_dbid = 2868, number = 16 },  -- YJ-18 ×16
    { unitname = "Red-052D-1", wpn_dbid = 2868, number = 16 },  -- YJ-18 ×16
    { unitname = "Red-052D-2", wpn_dbid = 2868, number = 10 },  -- YJ-18 ×10
}

-- ============================================================
-- ★★★ 打击清单（命名键，禁止下标访问 s[1]/s[2]） ★★★
-- 真延时：qty=N 拆成 N 个独立 Time 触发器
-- ============================================================
STRIKE = {
    -- 055#1 打击 DDG-113#1：16 → 13
    {
        attacker    = "Red-055-1",
        target      = "Blue-DDG113-1",
        weapon_dbid = 2868,
        quantity    = 13,         -- 装 16 击 13（用户指定）
        startDelay  = 0,
        interval    = 1,
        intent      = "055-1 突击 DDG-113-1",
    },
    -- 055#2 打击 DDG-113#2：16 → 13
    {
        attacker    = "Red-055-2",
        target      = "Blue-DDG113-2",
        weapon_dbid = 2868,
        quantity    = 13,         -- 装 16 击 13（用户指定）
        startDelay  = 2,
        interval    = 1,
        intent      = "055-2 突击 DDG-113-2",
    },
    -- 052D-1 打击 CVN-70：16 → 8
    {
        attacker    = "Red-052D-1",
        target      = "Blue-CVN70",
        weapon_dbid = 2868,
        quantity    = 8,          -- 装 16 击 8（用户指定）
        startDelay  = 5,
        interval    = 1,
        intent      = "052D-1 突击 CVN-70",
    },
    -- 052D-2 打击 CG-59：10 → 5
    {
        attacker    = "Red-052D-2",
        target      = "Blue-CG59",
        weapon_dbid = 2868,
        quantity    = 5,          -- 装 10 击 5（用户指定）
        startDelay  = 8,
        interval    = 1,
        intent      = "052D-2 突击 CG-59",
    },
}

-- ============================================================
-- §E 弹药余额自检
-- ============================================================
local function checkAmmoBalance()
    local ammoByUnit = {}
    for _, a in ipairs(AMMO) do
        ammoByUnit[a.unitname] = (ammoByUnit[a.unitname] or 0) + a.number
    end
    local strikeByUnit = {}
    for _, s in ipairs(STRIKE) do
        strikeByUnit[s.attacker] = (strikeByUnit[s.attacker] or 0) + s.quantity
    end
    local all_ok = true
    for unit, totalStrike in pairs(strikeByUnit) do
        local totalAmmo = ammoByUnit[unit] or 0
        if totalAmmo < totalStrike then
            print(("[manifest] 弹药不足! %s 装弹 %d 但 STRIKE 需要 %d"):format(
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
    error("[manifest] 弹药预算不通过，请修正 AMMO/STRIKE 后重跑")
end
print("[manifest] 清单校验通过: " .. countKeys(UNITS) .. " 单位, "
    .. #AMMO .. " 装弹项, " .. #STRIKE .. " 打击项")