-- ============================================================
-- main.lua — 红方5V3（辽宁舰+J-15×2 vs CVN-70编队）
-- 方案：055/052D×2 水面饱和 YJ-18 主攻 CVN-70；J-15×2 YJ-83K 分别打 CG-59/DDG-113
-- MCP验证：DBID全部来自 DB3K_504.db3 查询（见 §5.7 / 红线#1）
-- TOT基准：T+120s（第1枚 YJ-18 离架）
-- ============================================================

-- ============================================================
-- MANIFEST（全局数据源，4个脚本全部引用此表）
-- ============================================================
_SIDE_RED  = "红方"
_SIDE_BLUE = "蓝方"

-- 红方舰艇（Ship × 4）
_MANIFEST_SHIPS = {
  {
    name = "红方055南昌舰", dbid = 3883,
    lat = 30.55, lon = 122.40, heading = 90, speed = 18, prof = "Veteran",
    intent = "VLS发射 YJ-18 饱和攻击 CVN-70",
  },
  {
    name = "红方052D-1昆明舰", dbid = 2296,
    lat = 30.52, lon = 122.35, heading = 90, speed = 16, prof = "Veteran",
    intent = "VLS发射 YJ-18 饱和攻击 CVN-70",
  },
  {
    name = "红方052D-2南京舰", dbid = 3587,
    lat = 30.58, lon = 122.45, heading = 90, speed = 16, prof = "Veteran",
    intent = "VLS发射 YJ-18 饱和攻击 CVN-70",
  },
  {
    name = "红方辽宁舰", dbid = 2007,
    lat = 30.60, lon = 122.30, heading = 90, speed = 18, prof = "Veteran",
    intent = "放飞 J-15 双机",
  },
}

-- 红方舰载机（Aircraft × 2）
_MANIFEST_AIRCRAFT = {
  {
    name = "J-15-1", dbid = 2496,
    base = "红方辽宁舰",
    prof = "Veteran",
    intent = "YJ-83K 打击 CG-59",
  },
  {
    name = "J-15-2", dbid = 2496,
    base = "红方辽宁舰",
    prof = "Veteran",
    intent = "YJ-83K 打击 DDG-113",
  },
}

-- 蓝方舰艇（Ship × 3）
_MANIFEST_BLUE = {
  {
    name = "蓝方CVN-70卡尔文森", dbid = 3551,
    lat = 30.40, lon = 124.50, heading = 270, speed = 14, prof = "Veteran",
    intent = "主攻目标（YJ-18饱和攻击）",
  },
  {
    name = "蓝方CG-59普林斯顿", dbid = 2862,
    lat = 30.38, lon = 124.20, heading = 270, speed = 14, prof = "Veteran",
    intent = "J-15-1 打击目标（YJ-83K）",
  },
  {
    name = "蓝方DDG-113约翰芬恩", dbid = 4299,
    lat = 30.42, lon = 124.80, heading = 270, speed = 14, prof = "Veteran",
    intent = "J-15-2 打击目标（YJ-83K）",
  },
}

-- 武器配置（舰艇用 YJ-18，飞机用 YJ-83K）
-- YJ-18 DBID=2868：水面舰 VLS 发射（3艘各8枚，共24枚）
-- YJ-83K DBID=2137：J-15 机载反舰（每机4枚）
_WEAPON_YJ18 = 2868
_WEAPON_YJ83K = 2137

-- TOT配置（真延时打击参考）
-- 基准：T+120s，第1枚 YJ-18 离架
_TOT_BASE_DELAY    = 120       -- 秒（TOT基准，从脚本执行时起算）
_RIPPLE_INTERVAL   = 5         -- 秒（055/052D 齐射间隔）
_CONTACT_SETTLE    = 15        -- 秒（contact_settle_delay，红线#9）
_ATTACK_START      = _TOT_BASE_DELAY + _CONTACT_SETTLE  -- = 135s（攻击触发时刻）

print("[main] MANIFEST 加载完成")
print("  红方舰艇: " .. #_MANIFEST_SHIPS .. " 艘")
print("  红方舰载机: " .. #_MANIFEST_AIRCRAFT .. " 架")
print("  蓝方舰艇: " .. #_MANIFEST_BLUE .. " 艘")
print("  TOT基准: T+" .. _TOT_BASE_DELAY .. "s  contact_settle=" .. _CONTACT_SETTLE .. "s")

-- ============================================================
-- 工具函数（幂等）
-- ============================================================
local function getUnit(side, name)
  local ok, u = pcall(ScenEdit_GetUnit, {side=side, name=name})
  if ok and u and u.guid then return u end
  return nil
end

local function log(tag, ok, r)
  print(tag .. " ok=" .. tostring(ok) .. " 返回=" .. tostring(r) .. " err=" .. tostring(_errmsg_))
end

-- ============================================================
-- 建阵营（红线#5 + #18）
-- ============================================================
print("\n===== [main] 建阵营 =====")

-- ★ 红线#18：必须传 table，不能传字符串
pcall(ScenEdit_AddSide, {name=_SIDE_RED,  color="255,0,0"})
pcall(ScenEdit_AddSide, {name=_SIDE_BLUE, color="0,0,255"})

-- ★ 红线#6：红方全知全能（找蓝方 contact 不依赖雷达）
pcall(ScenEdit_SetSideOptions, {side=_SIDE_RED,  awareness="OMNI"})
pcall(ScenEdit_SetSideOptions, {side=_SIDE_BLUE, awareness="OMNI"})

-- 互为敌对
pcall(ScenEdit_SetSidePosture, _SIDE_RED,  _SIDE_BLUE, "H")
pcall(ScenEdit_SetSidePosture, _SIDE_BLUE, _SIDE_RED,  "H")

-- ★ 红线#12：红蓝双方 wcs=0（自由开火）
for _, side in ipairs({_SIDE_RED, _SIDE_BLUE}) do
  pcall(ScenEdit_SetDoctrine, {side=side}, {
    weapon_control_status_air="0",
    weapon_control_status_surface="0",
    weapon_control_status_subsurface="0",
    weapon_control_status_land="0",
  })
end

-- ★ 红线#18 实施细则：阵营诊断
local sR = pcall(VP_GetSide, {Side=_SIDE_RED})
local sB = pcall(VP_GetSide, {Side=_SIDE_BLUE})
print(("[main] 阵营诊断: 红方=%s 蓝方=%s"):format(
  tostring(sR and true or false),
  tostring(sB and true or false)))
if not (sR and sB) then
  print("[main] !! 阵营创建失败，请检查 AddSide 是否传 table")
end

-- ============================================================
-- 建红方舰艇（Ship × 4）
-- ============================================================
print("\n===== [main] 建红方舰艇 =====")
for _, s in ipairs(_MANIFEST_SHIPS) do
  local u = getUnit(_SIDE_RED, s.name)
  if not u then
    _errnum_ = 0
    local ok, r = pcall(ScenEdit_AddUnit, {
      type       = "Ship",
      side       = _SIDE_RED,
      name       = s.name,
      dbid       = s.dbid,
      latitude   = s.lat,
      longitude  = s.lon,
      heading    = s.heading,
      speed      = s.speed,
      proficiency = s.prof,
    })
    log("[main] " .. s.name, ok, r)
    u = getUnit(_SIDE_RED, s.name)
  else
    print("[main] " .. s.name .. " 已存在 guid=" .. tostring(u.guid))
  end

  -- 开雷达（主动）
  if u then
    pcall(ScenEdit_SetEMCON, "Unit", s.name, "Radar=Active")
  end
end

-- ============================================================
-- 建蓝方舰艇（Ship × 3）
-- ============================================================
print("\n===== [main] 建蓝方舰艇 =====")
for _, s in ipairs(_MANIFEST_BLUE) do
  local u = getUnit(_SIDE_BLUE, s.name)
  if not u then
    _errnum_ = 0
    local ok, r = pcall(ScenEdit_AddUnit, {
      type          = "Ship",
      side          = _SIDE_BLUE,
      name          = s.name,
      dbid          = s.dbid,
      latitude      = s.lat,
      longitude     = s.lon,
      heading       = s.heading,
      speed         = s.speed,
      autodetectable = true,     -- ★ 红线#8：蓝方目标 autodetectable=true
      proficiency   = s.prof,
    })
    log("[main] " .. s.name, ok, r)
    u = getUnit(_SIDE_BLUE, s.name)
  else
    pcall(ScenEdit_SetUnit, {guid=u.guid, autodetectable=true})  -- ★ 保险：已存在也再设一次
    print("[main] " .. s.name .. " 已存在 guid=" .. tostring(u.guid))
  end

  -- 蓝方传感器开启（默认就开，强制显式）
  if u then
    pcall(ScenEdit_SetEMCON, "Unit", s.name, "Radar=Active")
  end
end

-- ============================================================
-- 建红方舰载机（Aircraft × 2）
-- ============================================================
print("\n===== [main] 建红方舰载机 =====")
for _, a in ipairs(_MANIFEST_AIRCRAFT) do
  local u = getUnit(_SIDE_RED, a.name)
  if not u then
    _errnum_ = 0
    -- J-15 无 YJ-18 默认 Loadout，建裸机（loadout 在 reload.lua 装）
    local ok, r = pcall(ScenEdit_AddUnit, {
      type       = "Aircraft",
      side       = _SIDE_RED,
      name       = a.name,
      dbid       = a.dbid,
      base       = a.base,
      proficiency = a.prof,
    })
    log("[main] " .. a.name, ok, r)
    u = getUnit(_SIDE_RED, a.name)
  else
    print("[main] " .. a.name .. " 已存在 guid=" .. tostring(u.guid))
  end

  if u then
    -- 准备时间归零
    pcall(ScenEdit_SetUnit, {
      side="红方", unitname=a.name, timetoready_minutes=0
    })
    -- 起飞
    pcall(ScenEdit_SetUnit, {
      side="红方", unitname=a.name, launch=true
    })
    -- 开雷达
    pcall(ScenEdit_SetEMCON, "Unit", a.name, "Radar=Active")
  else
    print("[main] !! " .. a.name .. " 创建失败")
  end
end

-- ============================================================
-- 全部完成
-- ============================================================
print("\n[main] 全部完成。")
print("  TOT基准: T+" .. _TOT_BASE_DELAY .. "s（_ATTACK_START=T+" .. _ATTACK_START .. "s）")
print("  下一步: 执行 clear.lua（清弹） → reload.lua（装弹） → attack.lua（打击）")
