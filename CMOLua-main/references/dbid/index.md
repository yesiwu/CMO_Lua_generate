# 常见装备 DBID 参考表

> **⚠ 本表仅收录最常用装备的速查参考，不可替代 MCP 查询。**
> 大多数场景下，**必须先通过 MCP 查询真实 DBID**，本表仅用于记忆最常见的几个值。
>
> 查询方法：`query_dbid("英文关键词")` 或 `read_query("SELECT ...")`
>
> ⚠ **MCP 查询必须使用英文！** 数据库字段为英文，中文搜索无结果。

---

## 中国装备

### 中国舰艇（type="Ship"，不需要 LoadoutID）

|| 装备 | DBID | 说明 |
||------|------|------|
|| Type 055 Renhai [101 Nanchang] | 3883 | 055 型南昌舰 |
|| Type 052D Luyang III [172 Kunming] | 2296 | 052D 型昆明舰 |
|| Type 052C [170 Lanzhou] | 2249 | 052C 型兰州舰 |
|| Type 054A [568 Huainan] | 2292 | 054A 型护卫舰 |

### 中国潜艇（type="Submarine"，不需要 LoadoutID）

|| 装备 | DBID | 说明 |
||------|------|------|
|| Type 039G1 Song | 124 | 宋级潜艇 |
|| Type 039A Yuan | 2151 | 元级潜艇（AIP） |
|| Type 093 Shang | 2166 | 商级核潜艇 |

### 中国飞机（type="Aircraft"，必须指定 LoadoutID）

> ⚠ Aircraft 必须通过 MCP `read_query("SELECT ID FROM DataAircraftLoadouts WHERE ComponentID=<dbid>")` 查询 LoadoutID。

|| 装备 | DBID | LoadoutID（部分已知） | 说明 |
||------|------|----------------------|------|
|| J-16 Flying Shark | 2853 | 1821, 3272 | 战斗机 |
|| J-16D (咆哮石榴) | 4632 | 查询获取 | 电子战型 |
|| J-15 Flying Shark | 2861 | 查询获取 | 舰载战斗机 |
|| J-11BS Shark | 2758 | 查询获取 | 战斗机 |
|| JH-7A | 2852 | 查询获取 | 战斗轰炸机 |
|| H-6K | 2859 | 查询获取 | 轰炸机 |
|| KJ-500 | 4633 | 查询获取 | 预警机 |
|| KJ-2000 | 2860 | 查询获取 | 预警机 |
|| Y-8 DJ | 2856 | 查询获取 | 电子战机 |
|| Y-9JZ | 4680 | 查询获取 | 战场监视机 |
|| JH-7 | 2851 | 查询获取 | 战斗轰炸机 |

### 中国武器

|| 武器 | DBID | 说明 |
||------|------|------|
|| YJ-18 [3M54E Klub Copy] | 2868 | 反舰导弹 |
|| YJ-83 [C-802A] | 541 | 反舰导弹 |
|| YJ-12 | 2865 | 超音速反舰导弹 |
|| PL-15 | 2867 | 超视距空空导弹 |
|| PL-12/SD-10 | 5418 | 中距空空导弹 |
|| CJ-10 | 2787 | 陆基巡航导弹 |
|| YJ-91 | 2857 | 反辐射导弹 |

---

## 美国装备

### 空军基地 / 地面设施（type="Facility"，不需要 LoadoutID）

|| 装备 | DBID | 说明 |
||------|------|------|
|| Runway (3200m) | 35 | 通用跑道 |
|| Runway (1400m) | 945 | 短跑道 |
|| Runway Access Point (Medium Aircraft) | 307 | 停机坪连接点 |
|| Single-Unit Airfield (2x 3201-4000m Runways) | 430 | 双跑道空军基地 |
|| Single-Unit Airfield (1x 4000m+ Runway) | 1995 | 大型单跑道基地 |
|| Single-Unit Airfield (Heliport) | 1957 | 直升机停机坪 |

### 美国舰艇

|| 装备 | DBID | 说明 |
||------|------|------|
|| CVN 68 Nimitz | 429 | 尼米兹级首舰 |
|| CVN 70 Carl Vinson | 246, 423 | 尼米兹级 |
|| CVN 71 Theodore Roosevelt | 37, 381 | 尼米兹级 |
|| CVN 73 George Washington | 657, 658 | 尼米兹级 |
|| CVN 76 Ronald Reagan | 341 | 尼米兹级 |
|| CVN 77 George Bush | 505 | 尼米兹级末舰 |
|| DDG 51 Arleigh Burke (Flight I) | 112 | 伯克级驱逐舰 |
|| DDG 51 Arleigh Burke (Flight IIA) | 438, 561, 797, 798 | 伯克级驱逐舰 |
|| DDG 72 Mahan (Flight II) | 111 | 伯克 Flight II |
|| DDG 79 Oscar Austin (Flight IIA) | 294, 443 | 伯克 Flight IIA |
|| DDG 85 McCampbell (Flight IIA) | 445 | 伯克 Flight IIA |
|| CG 47 Ticonderoga (Baseline 0) | 42 | 提康德罗加级巡洋舰 |
|| CG 56 San Jacinto (Baseline 2) | 40 | 提康德罗加级 |
|| FFG 36 Underwood (Perry Class) | 116, 457, 560, 563 | 佩里级护卫舰 |
|| FFG 01 Adelaide (Perry Class) | 540 | 澳大利亚佩里级 |
|| T-AO 187 Henry J. Kaiser (Mod Cimarron) | 26 | 亨利·J·凯泽级补给舰 |

### 美国潜艇

|| 装备 | DBID | 说明 |
||------|------|------|
|| SSN 688 Los Angeles (Flight I) | 22, 33, 71, 76 | 洛杉矶级攻击核潜艇 |
|| SSN 719 Providence (Flight II) | 24, 25, 109 | 洛杉矶 Flight II |
|| SSN 774 Virginia (Flight I) | 40, 74, 561 | 弗吉尼亚级攻击核潜艇 |
|| SSN 778 New Hampshire (Flight II) | 551, 562 | 弗吉尼亚 Flight II |
|| SSN 784 North Dakota (Flight III) | 552, 563 | 弗吉尼亚 Flight III |

### 美国飞机

> ⚠ **所有 Aircraft 都必须通过 MCP 查询 LoadoutID！** 下表只列出已知的 LoadoutID，仍需用 `read_query("SELECT ID FROM DataAircraftLoadouts WHERE ComponentID=<dbid>")` 验证。

|| 装备 | DBID | LoadoutID（部分已知） | 说明 |
||------|------|----------------------|------|
|| F-16A Falcon | 158 | 33, 757, 1988 | F-16A |
|| F-16CM Blk 52 Falcon | 322 | 122, 2284, 3417 | F-16C |
|| F-15C Eagle | 2708 | 查询获取 | 防空战斗机 |
|| F-15E Strike Eagle | 2709 | 查询获取 | 战斗轰炸机 |
|| F-35A Lightning II | 278 | 查询获取 | 美国空军 F-35A |
|| F-35B Lightning II | 534 | 查询获取 | 短距起降型 |
|| F-35C Lightning II | 824 | 查询获取 | 舰载型 |
|| F-22A Raptor | 333 | 查询获取 | 美国隐身战斗机 |
|| F/A-18C Hornet | 377 | 查询获取 | 舰载战斗机 |
|| F/A-18E Super Hornet | 378 | 查询获取 | 超级大黄蜂 |
|| EA-18G Growler | 343 | 102, 963, 995 | 电子战机 |
|| E-3C Sentry (AWACS) | 209, 304 | 查询获取 | 美国预警机 |
|| E-2D Hawkeye | 2706 | 查询获取 | 舰载预警机 |
|| KC-135R Stratotanker | 1692 | 查询获取 | 加油机 |
|| KC-135E Stratotanker | 159 | 查询获取 | 加油机 |
|| KC-130J Hercules | 2786 | 查询获取 | 加油机 |
|| A-10A Thunderbolt II | 445, 717 | 查询获取 | 攻击机 |
|| MQ-9A Reaper UAV | 1719 | 2230 | 死神无人机 |
|| MQ-1C Gray Eagle | 2845 | 查询获取 | 灰鹰无人机 |
|| F-4 Phantom II | 266 | 查询获取 | 鬼怪式（美/以/德/韩） |

---

## 俄罗斯装备

### 舰艇

|| 装备 | DBID | 说明 |
||------|------|------|
|| TAKR Admiral Kuznetsov (Pr.1143.5) | 147, 656, 2633 | 库兹涅佐夫号航母 |
|| 955 Borei (Aleksandr Nevsky) | 2616 | 北风之神级弹道导弹核潜艇 |
|| 971 Shchuka-B (Akula) | 2164 | 阿库拉级攻击核潜艇 |
|| 636.3 Varshavyanka (Kilo改进型) | 2153 | 基洛级改进型柴电潜艇 |

### 飞机

|| 装备 | DBID | LoadoutID | 说明 |
||------|------|-----------|------|
|| Su-27S Flanker B | 134 | 查询获取 | 侧卫 |
|| Su-30SM Flanker C | 2707 | 查询获取 | 侧卫 |
|| Su-35S Flanker M | 2689 | 查询获取 | 侧卫 |
|| Su-33 Flanker D | 2855 | 查询获取 | 舰载型 |
|| Su-25T Frogfoot | 2838 | 查询获取 | 攻击机 |
|| Tu-95MS Bear H | 2860 | 查询获取 | 轰炸机 |
|| A-50 | 2854 | 查询获取 | 预警机 |
|| MiG-31BM Foxhound | 2700 | 查询获取 | 截击机 |

---

## 武器速查

|| 武器 | DBID | 说明 |
||------|------|------|
|| AIM-120D AMRAAM | 51 | 中距空空导弹（最新型） |
|| AIM-120C-7 AMRAAM | 718 | 中距空空导弹 |
|| AIM-9X Sidewinder | 2023 | 近距空空导弹 |
|| AGM-65D Maverick | 1876 | 空对地导弹（红外型） |
|| AGM-65F Maverick | 1874 | 空对地导弹（海基型） |
|| AGM-88C HARM | 2857 | 反辐射导弹 |
|| AGM-158 JASSM | 2863 | 防区外空地导弹 |
|| AGM-84L Harpoon | 540 | 反舰导弹 |
|| R-77 (AA-12 Adder) | 2871 | 俄制中距空空导弹 |
|| R-27ER (AA-10C) | 2869 | 俄制中距空空导弹 |
|| Mine [Floating, Contact Fuze] | 634 | 通用漂雷 |
|| Mine [Bottom, Magnetic Fuze] | 632 | 底雷 |
|| Mine [Moored, Contact Fuze] | 633 | 锚雷 |

---

## 数据库查询方法

### 1. 查询装备 DBID（通过 MCP）

```python
# 使用英文关键词，通过 MCP query_dbid 查询
query_dbid("F-16C Fighting Falcon")
query_dbid("Arleigh Burke destroyer")
query_dbid("Virginia class submarine")
query_dbid("Type 055 destroyer")
```

### 2. 查询 LoadoutID（通过 MCP read_query）

```sql
-- ① 查 DBID 对应的所有 LoadoutID
SELECT ID, Name FROM DataAircraftLoadouts WHERE ComponentID = 2853;

-- ② 查某个 LoadoutID 里装了什么武器
SELECT lw.Quantity, w.Name AS WeaponName
FROM DataLoadoutWeapons lw
JOIN DataWeapon w ON lw.WeaponID = w.ID
WHERE lw.LoadoutID = 1821
ORDER BY lw.Quantity DESC;

-- ③ 验证 DBID 存在
SELECT ID, Name FROM DataAircraft WHERE Name LIKE '%F-16%';
SELECT ID, Name FROM DataShip WHERE Name LIKE '%Arleigh Burke%';
```

### 3. 查询所有表

```sql
-- 通过 MCP list_tables() 可列出所有表
-- 主要表：DataAircraft, DataShip, DataSubmarine, DataFacility,
--         DataWeapon, DataAircraftLoadouts, DataLoadout, DataLoadoutWeapons
```

### 4. 常见查询示例

```sql
-- 找所有中国飞机的 DBID
SELECT ID, Name FROM DataAircraft WHERE OperatorCountry LIKE '%China%';

-- 找 F-16 的所有 Loadout
SELECT l.ID, l.Name, w.Name AS WeaponName, lw.Quantity
FROM DataAircraftLoadouts l
JOIN DataLoadoutWeapons lw ON lw.LoadoutID = l.ID
JOIN DataWeapon w ON lw.WeaponID = w.ID
WHERE l.ComponentID = 322
ORDER BY l.ID;
```

### 5. Facility / Ship / Submarine 不需要 LoadoutID

```lua
-- ✅ Facility 正确写法（不需要 LoadoutID）
ScenEdit_AddUnit({
    side = "Blue",
    type = "Facility",
    dbid = 35,       -- Runway (3200m)
    name = "Main Runway",
    latitude = 35.6762,
    longitude = 139.6503
})

-- ✅ Ship / Submarine 不需要 LoadoutID
ScenEdit_AddUnit({
    side = "红方",
    type = "Ship",
    dbid = 3883,    -- Type 055
    name = "055-1",
    latitude = 30.25,
    longitude = 124.75,
    heading = 45,
    speed = 20,
    proficiency = "Veteran",
})

-- ❌ Aircraft 必须有 LoadoutID（必须先查）
ScenEdit_AddUnit({
    side = "红方",
    type = "Aircraft",
    dbid = 2853,            -- J-16
    LoadoutID = 1821,      -- 必须通过 DataAircraftLoadouts 查询
    name = "J-16 #1",
    latitude = 29.0,
    longitude = 123.5,
    altitude = 7620,
})
```
