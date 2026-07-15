-- ============================================================
-- manifest.lua — A1 场景 YJ-18 联合反舰打击清单（v2.0）
-- 单一数据源：main.lua / clear.lua / reload.lua / attack.lua
-- 全部从此文件引用，禁止在其他脚本硬编码。
-- 红蓝方全部使用 MCP 真实查询得到的 DBID；
-- 武器全用 YJ-18（dbid=2868），不含 YJ-18 兼容挂载的舰艇不进 STRIKE。
-- ============================================================

-- ============================================================
-- §A 场景元数据
-- ============================================================
SCENARIO = {
    title       = "A1 场景 YJ-18 反舰饱和打击",
    location    = "南海",
    start_time  = "2026-07-07 08:00:00",
    duration    = "1小时",
    sides       = { "红方", "蓝方" },
    red_skill   = "OMNI",   -- 红方全知全能
    contact_settle_delay = 15,  -- 必须 ≥15 秒
}

-- ============================================================
-- §B 武器库（dbid_verified 必须为 true 才进 AMMO）
-- ============================================================
WEAPONS = {
    {
        dbid             = 2868,
        name             = "YJ-18 [3M54E Klub Copy]",
        category         = "Anti-ship missile",
        default_quantity = 8,         -- 052D VLS 通用格数
        loadout_verified = true,
    },
}

-- ============================================================
-- §C 单位清单（dict-keyed：UNITS[id] = {...}）
--   ★ 所有脚本必须 UNITS["<id>"] 引用，禁止 ipairs/下标遍历
--   ★ id 字段即是 main.lua 的 ScenEdit_AddUnit({name=id}) 的 name=
--   ★ dbid_verified 必须 true
--   ★ 红方全部为 055 / 052D / 054A 系列水面舰艇（YJ-18 兼容挂载）
--   ★ 蓝方目标全部 autodetectable = true（红线 #8）
-- ============================================================
UNITS = {

    ---------- 红方水面舰艇编队（DDG01: 1×055 + 2×052D + 2×054A） ----------
    ["Red-055-1"] = {
        side           = "红方",
        name           = "Red-055-1",
        type           = "Ship",
        dbid           = 3883,        -- MCP: Type 055 Renhai [101 Nanchang]
        latitude       = 18.50,
        longitude      = 113.00,
        heading        = 180,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "YJ-18 发射平台（055）",
    },
    ["Red-052D-1"] = {
        side           = "红方",
        name           = "Red-052D-1",
        type           = "Ship",
        dbid           = 3587,        -- MCP: Type 052D Luyang III [155 Nanjing]
        latitude       = 18.40,
        longitude      = 113.10,
        heading        = 180,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "YJ-18 发射平台（052D）",
    },
    ["Red-052D-2"] = {
        side           = "红方",
        name           = "Red-052D-2",
        type           = "Ship",
        dbid           = 2296,        -- MCP: Type 052D Luyang III [172 Kunming]
        latitude       = 18.60,
        longitude      = 113.10,
        heading        = 180,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "YJ-18 发射平台（052D）",
    },
    ["Red-054A-1"] = {
        side           = "红方",
        name           = "Red-054A-1",
        type           = "Ship",
        dbid           = 2495,        -- MCP: Type 054A Jiangkai II [576 Daqing]
        latitude       = 18.30,
        longitude      = 113.20,
        heading        = 180,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "YJ-18 发射平台（054A）",
    },
    ["Red-054A-2"] = {
        side           = "红方",
        name           = "Red-054A-2",
        type           = "Ship",
        dbid           = 2714,        -- MCP: Type 054A Jiangkai II [599 Anyang]
        latitude       = 18.70,
        longitude      = 113.20,
        heading        = 180,
        speed          = 18,
        proficiency    = "Veteran",
        autodetectable = false,
        dbid_verified  = true,
        role           = "YJ-18 发射平台（054A）",
    },

    ---------- 蓝方目标（CVN-72 Lincoln 编队，全部 autodetectable=true） ----------
    ["Blue-CVN72"] = {
        side           = "蓝方",
        name           = "Blue-CVN72",
        type           = "Ship",
        dbid           = 1644,        -- MCP: CVN 72 Abraham Lincoln
        latitude       = -0.90,
        longitude      = 106.11,
        heading        = 0,
        speed          = 0,
        proficiency    = "Veteran",
        autodetectable = true,        -- ★ 红线 #8
        dbid_verified  = true,
        role           = "航母（核心目标）",
    },
    ["Blue-CG70"] = {
        side           = "蓝方",
        name           = "Blue-CG70",
        type           = "Ship",
        dbid           = 2128,        -- MCP: CG 70 Lake Erie
        latitude       = -0.66,
        longitude      = 105.81,
        heading        = 0,
        speed          = 0,
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "宙斯盾巡洋舰",
    },
    ["Blue-DDG79"] = {
        side           = "蓝方",
        name           = "Blue-DDG79",
        type           = "Ship",
        dbid           = 2869,        -- MCP: DDG 79 Oscar Austin
        latitude       = -0.80,
        longitude      = 106.40,
        heading        = 0,
        speed          = 0,
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "伯克 IIA 驱逐舰",
    },
    ["Blue-FFG36"] = {
        side           = "蓝方",
        name           = "Blue-FFG36",
        type           = "Ship",
        dbid           = 457,         -- MCP: FFG 36 Underwood
        latitude       = -1.10,
        longitude      = 105.95,
        heading        = 0,
        speed          = 0,
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "佩里级护卫舰",
    },
    ["Blue-TAO187"] = {
        side           = "蓝方",
        name           = "Blue-TAO187",
        type           = "Ship",
        dbid           = 26,          -- MCP: T-AO 187 Henry J. Kaiser
        latitude       = -1.00,
        longitude      = 106.30,
        heading        = 0,
        speed          = 0,
        proficiency    = "Veteran",
        autodetectable = true,
        dbid_verified  = true,
        role           = "补给舰",
    },
}

-- ============================================================
-- §D 清弹 / 装弹 / 打击清单
-- ============================================================

-- 1) 需要清弹的红方单位（必须与 main.lua name= 完全一致）
CLEAR_LIST = {
    "Red-055-1",
    "Red-052D-1",
    "Red-052D-2",
    "Red-054A-1",
    "Red-054A-2",
}

-- 2) 装弹清单：每艘红方水面舰统一装 YJ-18 ×8
--    055 通用 VLS 112 格，052D 64 格，054A 32 格；保守按 8 枚/舰装填
--    （实际装载量由 ScenEdit_AddReloadsToUnit 决定，不超过可用 VLS）
AMMO = {
    { unitname = "Red-055-1",  wpn_dbid = 2868, number = 16 },  -- YJ-18 ×16
    { unitname = "Red-052D-1", wpn_dbid = 2868, number = 8  },  -- YJ-18 ×8
    { unitname = "Red-052D-2", wpn_dbid = 2868, number = 8  },  -- YJ-18 ×8
    { unitname = "Red-054A-1", wpn_dbid = 2868, number = 8  },  -- YJ-18 ×8
    { unitname = "Red-054A-2", wpn_dbid = 2868, number = 8  },  -- YJ-18 ×8
}

-- ============================================================
-- ★★★ 打击清单（命名键，禁止下标访问 s[1]/s[2]） ★★★
-- 真延时：qty=N 拆成 N 个独立 Time 触发器
-- 红方 5 艘舰齐射 YJ-18 打击蓝方 5 个目标
-- ============================================================
STRIKE = {
    {
        attacker    = "Red-055-1",
        target      = "Blue-CVN72",
        weapon_dbid = 2868,
        quantity    = 8,
        startDelay  = 0,
        interval    = 1,
        intent      = "055 主力突击蓝方航母 CVN-72",
    },
    {
        attacker    = "Red-052D-1",
        target      = "Blue-CG70",
        weapon_dbid = 2868,
        quantity    = 8,
        startDelay  = 5,
        interval    = 1,
        intent      = "052D-1 突击蓝方宙斯盾巡洋舰 CG-70",
    },
    {
        attacker    = "Red-052D-2",
        target      = "Blue-DDG79",
        weapon_dbid = 2868,
        quantity    = 8,
        startDelay  = 10,
        interval    = 1,
        intent      = "052D-2 突击蓝方伯克驱逐舰 DDG-79",
    },
    {
        attacker    = "Red-054A-1",
        target      = "Blue-FFG36",
        weapon_dbid = 2868,
        quantity    = 6,
        startDelay  = 15,
        interval    = 1,
        intent      = "054A-1 突击蓝方佩里护卫舰 FFG-36",
    },
    {
        attacker    = "Red-054A-2",
        target      = "Blue-TAO187",
        weapon_dbid = 2868,
        quantity    = 6,
        startDelay  = 20,
        interval    = 1,
        intent      = "054A-2 突击蓝方补给舰 T-AO-187",
    },
}

-- ============================================================
-- §E 弹药余额自检（红线：AMMO.sum >= STRIKE.sum）
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
    local ok = true
    for unit, totalStrike in pairs(strikeByUnit) do
        local totalAmmo = ammoByUnit[unit] or 0
        if totalAmmo < totalStrike then
            print(("[manifest] 弹药不足! %s 装弹 %d 但 STRIKE 需要 %d"):format(
                unit, totalAmmo, totalStrike))
            ok = false
        else
            print(("[manifest] %s 弹药余额 = %d"):format(unit, totalAmmo - totalStrike))
        end
    end
    return ok
end

local function tableCountKeys(t)
    local n = 0
    for _ in pairs(t) do n = n + 1 end
    return n
end

if not checkAmmoBalance() then
    error("[manifest] 弹药预算不通过，请修正 AMMO/STRIKE 后重跑")
end
print("[manifest] 清单校验通过: " .. tableCountKeys(UNITS) .. " 单位, "
    .. #AMMO .. " 装弹项, " .. #STRIKE .. " 打击项")