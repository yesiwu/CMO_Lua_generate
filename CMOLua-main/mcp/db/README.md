# DB3K_504.db3 - CMO Database (DB3000)

## 概述

这是 **Command: Modern Operations (CMO)** 的核心数据库文件，基于 **DB3000 (DataBase 3000)** 构建，包含全球军事装备、传感器、武器、平台等详细技术参数。

- **文件大小**: 54.5 MB (54,554,624 bytes)
- **数据库类型**: SQLite 3
- **总表数**: 130+ 张表
- **数据记录**: 数十万条装备记录
- **数据覆盖**: 全球主要国家 1950-2030+ 年军事装备

---

## 数据库架构

### 1. 核心数据表 (Data*)

包含具体装备的技术参数：

| 表名 | 记录数 | 说明 |
|------|--------|------|
| **DataShip** | 4,571 | 舰船平台（驱逐舰、航母、潜艇等） |
| **DataAircraft** | 6,933 | 飞机平台（战斗机、轰炸机、直升机等） |
| **DataWeapon** | 4,219 | 武器系统（导弹、鱼雷、炸弹等） |
| **DataSensor** | 7,034 | 传感器（雷达、声呐、ESM、ECM等） |
| **DataSubmarine** | 728 | 潜艇平台 |
| **DataGroundUnit** | 437 | 地面单位 |
| **DataFacility** | 4,054 | 设施/建筑 |
| **DataSatellite** | 149 | 卫星平台 |
| **DataLoadout** | 32,335 | 挂载方案 |
| **DataMount** | 3,863 | 挂载点/发射架 |
| **DataPropulsion** | 3,880 | 推进系统 |
| **DataFuel** | 2,080 | 燃料类型 |
| **DataComm** | 452 | 通信设备 |
| **DataMagazine** | 1,656 | 弹舱/弹药库 |
| **DataWarhead** | 1,307 | 弹头 |
| **DataContainer** | 14 | 集装箱类型 |
| **DataDockingFacility** | 43 | 对接设施 |

### 2. 关联数据表 (Data*附属表)

记录平台与武器/传感器/挂载的关联关系：

| 表名 | 记录数 | 说明 |
|------|--------|------|
| DataShipMounts | 38,454 | 舰船挂载点配置 |
| DataShipSensors | 29,802 | 舰船传感器配置 |
| DataShipComms | 23,317 | 舰船通信配置 |
| DataShipFuel | 6,154 | 舰船燃料配置 |
| DataShipMagazines | 12,248 | 舰船弹舱配置 |
| DataShipPropulsion | 4,571 | 舰船推进系统配置 |
| DataShipAircraftFacilities | 7,151 | 舰船航空设施 |
| DataShipDockingFacilities | 1,458 | 舰船对接设施 |
| DataShipSignatures | 50,281 | 舰船信号特征 |
| DataShipCodes | 9,562 | 舰船代码 |
| DataAircraftLoadouts | 87,928 | 飞机挂载方案 |
| DataAircraftSensors | 18,703 | 飞机传感器配置 |
| DataAircraftMounts | 6,897 | 飞机挂载点 |
| DataAircraftFuel | 6,906 | 飞机燃料配置 |
| DataAircraftPropulsion | 6,933 | 飞机推进配置 |
| DataAircraftSignatures | 41,598 | 飞机信号特征 |
| DataAircraftComms | 15,010 | 飞机通信配置 |
| DataAircraftCodes | 18,589 | 飞机代码 |
| DataAircraftFacility | 146 | 飞机设施 |
| DataWeaponSensors | 2,175 | 武器传感器配置 |
| DataWeaponFuel | 2,546 | 武器燃料配置 |
| DataWeaponPropulsion | 2,338 | 武器推进配置 |
| DataWeaponSignatures | 46,409 | 武器信号特征 |
| DataWeaponComms | 717 | 武器通信配置 |
| DataWeaponCodes | 8,500 | 武器代码 |
| DataWeaponTargets | 13,175 | 武器目标类型 |
| DataWeaponWRA | 23,760 | 武器交战规则 |
| DataWeaponWarheads | 3,752 | 武器弹头配置 |
| DataWeaponRecord | 10,593 | 武器记录 |
| DataWeaponDirectors | 1,117 | 武器制导配置 |
| DataLoadoutWeapons | 88,983 | 挂载方案武器清单 |
| DataMountWeapons | 6,598 | 挂载点武器配置 |
| DataMountSensors | 1,901 | 挂载点传感器配置 |
| DataMountComms | 311 | 挂载点通信配置 |
| DataMountDirectors | 4,844 | 挂载点制导配置 |
| DataMountMagazineWeapons | 648 | 挂载点弹舱武器 |
| DataMagazineWeapons | 3,614 | 弹舱武器配置 |
| DataSensorCapabilities | 23,570 | 传感器能力配置 |
| DataSensorCodes | 9,522 | 传感器代码 |
| DataSensorFrequencyIlluminate | 420 | 传感器照射频率 |
| DataSensorFrequencySearchAndTrack | 13,956 | 传感器搜索跟踪频率 |
| DataSensorSensorGroups | 1,021 | 传感器组配置 |
| DataSubmarineMounts | 5,189 | 潜艇挂载点 |
| DataSubmarineSensors | 5,391 | 潜艇传感器 |
| DataSubmarineSignatures | 8,008 | 潜艇信号特征 |
| DataFacilityMounts | 13,060 | 设施挂载点 |
| DataFacilitySensors | 1,192 | 设施传感器 |
| DataFacilitySignatures | 24,324 | 设施信号特征 |
| DataSatelliteSensors | 162 | 卫星传感器 |
| DataSatelliteOrbits | 1,062 | 卫星轨道 |
| DataSatelliteSignatures | 894 | 卫星信号特征 |
| DataPropulsionPerformance | 22,474 | 推进性能参数 |
| DataCommCapabilities | 1,558 | 通信能力 |
| DataCommDirectors | 617 | 通信制导 |
| DataCommTypeCanTalkTo | 48 | 通信类型互操作 |

### 3. 枚举表 (Enum*)

定义分类体系和编码标准，共 60+ 张：

| 表名 | 记录数 | 说明 |
|------|--------|------|
| EnumShipType | 179 | 舰船类型 |
| EnumShipCategory | 9 | 舰船大类 |
| EnumShipCode | 59 | 舰船代码 |
| EnumShipCSGen | 10 | 舰船指挥系统世代 |
| EnumShipPhysicalSize | 11 | 舰船物理尺寸 |
| EnumAircraftType | 36 | 飞机类型 |
| EnumAircraftCategory | 8 | 飞机大类 |
| EnumAircraftCode | 45 | 飞机代码 |
| EnumAircraftCockpitGen | 7 | 座舱世代 |
| EnumAircraftCockpitVisibility | 10 | 座舱视野 |
| EnumAircraftPhysicalSize | 9 | 飞机物理尺寸 |
| EnumAircraftAutonomousControlLevel | 8 | 自主控制等级 |
| EnumAircraftFacilityType | 16 | 航空设施类型 |
| EnumWeaponType | 47 | 武器类型 |
| EnumWeaponCode | 79 | 武器代码 |
| EnumWeaponGeneration | 19 | 武器世代 |
| EnumWeaponImpactType | 4 | 武器撞击类型 |
| EnumWeaponTarget | 18 | 武器目标类型 |
| EnumWeaponWRA | 93 | 武器交战规则 |
| EnumWeaponWRASelfDefenceRange | 13 | 自卫射程 |
| EnumWeaponWRAShooterQty | 4 | 射击者数量 |
| EnumWeaponWRAWeaponQty | 15 | 武器数量 |
| EnumSensorType | 43 | 传感器类型 |
| EnumSensorCode | 28 | 传感器代码 |
| EnumSensorCapability | 24 | 传感器能力 |
| EnumSensorGeneration | 32 | 传感器世代 |
| EnumSensorRole | 299 | 传感器角色 |
| EnumSensorFrequency | 36 | 传感器频率 |
| EnumSubmarineType | 21 | 潜艇类型 |
| EnumSubmarineCategory | 4 | 潜艇大类 |
| EnumSubmarineCode | 13 | 潜艇代码 |
| EnumGroundUnitCategory | 32 | 地面单位大类 |
| EnumGroundUnitCode | 12 | 地面单位代码 |
| EnumFacilityType | 31 | 设施类型 |
| EnumFacilityCategory | 20 | 设施大类 |
| EnumLoadoutRole | 55 | 挂载任务角色 |
| EnumLoadoutMissionProfile | 174 | 任务剖面 |
| EnumLoadoutTimeOfDay | 4 | 时间条件 |
| EnumLoadoutWeather | 4 | 天气条件 |
| EnumLoadoutWinchesterShotgun | 20 | 弹药耗尽策略 |
| EnumOperatorCountry | 179 | 国家/操作者 |
| EnumOperatorService | 56 | 军种 |
| EnumPropulsionType | 24 | 推进类型 |
| EnumPropulsionCombinedType | 14 | 联合推进类型 |
| EnumFuelType | 12 | 燃料类型 |
| EnumCommType | 108 | 通信类型 |
| EnumCommCapability | 23 | 通信能力 |
| EnumCommLatency | 6 | 通信延迟 |
| EnumCommQuality | 6 | 通信质量 |
| EnumArcs | 8 | 射界 |
| EnumArmorType | 12 | 装甲类型 |
| EnumCargoType | 6 | 货物类型 |
| EnumContainerType | 4 | 集装箱类型 |
| EnumDockingFacilityType | 6 | 对接设施类型 |
| EnumDockingFacilityPhysicalSize | 13 | 对接设施尺寸 |
| EnumErgonomics | 5 | 人机工程 |
| EnumSignatureType | 11 | 信号类型 |
| EnumWarheadType | 41 | 弹头类型 |
| EnumWarheadCaliber | 17 | 口径 |
| EnumWarheadExplosivesType | 62 | 炸药类型 |
| EnumRunwayLength | 13 | 跑道长度 |
| EnumSatelliteType | 10 | 卫星类型 |
| EnumSatelliteCategory | 4 | 卫星大类 |
| EnumSatelliteOrbitPlane | 4 | 轨道平面 |

---

## 核心字段说明

### 平台通用字段

| 字段 | 说明 | 示例 |
|------|------|------|
| ID | 唯一标识符 (DBID) | 3883 = 055型驱逐舰 |
| Name | 装备全称 | "Type 055 Renhai [101 Nanchang]" |
| Category | 大类编码 | 2002=舰船, 2003=飞机 |
| Type | 细分类型编码 | 3202=驱逐舰, 6001=直升机 |
| Comments | 备注 | "1995" 或 "-" |
| OperatorCountry | 所属国家编码 | 对应 EnumOperatorCountry |
| OperatorService | 军种编码 | 对应 EnumOperatorService |
| YearCommissioned | 服役年份 | 2020 |
| YearDecommissioned | 退役年份 | 空=未退役 |
| Hypothetical | 是否虚构 | 0=真实, 1=虚构 |
| Cost | 造价 | 百万美元 |
| Deprecated | 是否弃用 | 0=当前, 1=弃用 |

### DataShip 完整字段 (45列)

| 字段 | 类型 | 说明 | 单位 |
|------|------|------|------|
| ID | INTEGER | **DBID** - 唯一标识符 | - |
| Category | INTEGER | 大类 | 2002=舰船 |
| Type | INTEGER | 类型 | 3202=驱逐舰... |
| Name | TEXT | 装备名称 | - |
| Comments | TEXT | 备注 | - |
| OperatorCountry | INTEGER | 国家 | 枚举 |
| OperatorService | INTEGER | 军种 | 枚举 |
| YearCommissioned | INTEGER | 服役年份 | - |
| YearDecommissioned | INTEGER | 退役年份 | - |
| Length | DOUBLE | 长度 | 米 |
| Beam | DOUBLE | 宽度 | 米 |
| Draft | DOUBLE | 吃水深度 | 米 |
| Height | DOUBLE | 高度 | 米 |
| DisplacementEmpty | INTEGER | 空载排水量 | 吨 |
| DisplacementStandard | INTEGER | 标准排水量 | 吨 |
| DisplacementFull | INTEGER | 满载排水量 | 吨 |
| Crew | INTEGER | 乘员数 | 人 |
| ArmorBelt | INTEGER | 舷侧装甲 | 枚举 |
| ArmorBulkheads | INTEGER | 舱壁装甲 | 枚举 |
| ArmorDeck | INTEGER | 甲板装甲 | 枚举 |
| ArmorBridge | INTEGER | 舰桥装甲 | 枚举 |
| ArmorCIC | INTEGER | 指挥中心装甲 | 枚举 |
| ArmorEngineering | INTEGER | 轮机舱装甲 | 枚举 |
| ArmorRudder | INTEGER | 舵机装甲 | 枚举 |
| DamagePoints | INTEGER | 损伤点 | 耐久度 |
| FOCSeaState | INTEGER | 燃料消耗海况 | - |
| MaxSeaState | INTEGER | 最大耐波海况 | 0-9 |
| RepairCapacity | INTEGER | 维修能力 | - |
| TroopCapacity | INTEGER | 载兵量 | 人 |
| CargoCapacity | INTEGER | 载货量 | 吨 |
| MissileDefense | INTEGER | 导弹防御等级 | 编码 |
| CSGen | INTEGER | 指挥系统世代 | 枚举 |
| Ergonomics | INTEGER | 人机工程 | 枚举 |
| OODADetectionCycle | INTEGER | OODA探测周期 | 秒 |
| OODATargetingCycle | INTEGER | OODA瞄准周期 | 秒 |
| OODAEvasiveCycle | INTEGER | OODA规避周期 | 秒 |
| PhysicalSizeCode | INTEGER | 物理尺寸编码 | 枚举 |
| Hypothetical | BOOLEAN | 是否虚构 | 0/1 |
| Cargo_Type | INTEGER | 货物类型 | 枚举 |
| Cargo_Mass | DOUBLE | 货物质量 | 吨 |
| Cargo_Area | DOUBLE | 货物面积 | 平方米 |
| Cargo_Crew | DOUBLE | 货物乘员 | 人 |
| Cargo_Volume | INTEGER | 货物体积 | 立方米 |
| Cost | INTEGER | 造价 | 百万美元 |
| Deprecated | BOOLEAN | 是否弃用 | 0/1 |

### 飞机特有字段 (DataAircraft)

| 字段 | 说明 | 单位 |
|------|------|------|
| Length | 机长 | 米 |
| Span | 翼展 | 米 |
| Height | 机高 | 米 |
| WeightEmpty | 空重 | 千克 |
| WeightMax | 最大起飞重量 | 千克 |
| WeightPayload | 最大载荷 | 千克 |
| Crew | 乘员 | 人 |
| Agility | 机动性 | 编码 |
| ClimbRate | 爬升率 | 米/秒 |
| AutonomousControlLevel | 自主控制等级 | 枚举 |
| CockpitGen | 座舱世代 | 枚举 |
| Ergonomics | 人机工程 | 枚举 |
| OODADetectionCycle | 探测周期 | 秒 |
| OODATargetingCycle | 瞄准周期 | 秒 |
| OODAEvasiveCycle | 规避周期 | 秒 |
| TotalEndurance | 总续航 | 分钟 |
| PhysicalSizeCode | 物理尺寸 | 枚举 |
| RunwayLengthCode | 跑道长度 | 枚举 |
| FuelOffloadRate | 燃油转移率 | - |
| DamagePoints | 损伤点 | - |
| AircraftEngineArmor | 发动机装甲 | 枚举 |
| AircraftFuselageArmor | 机身装甲 | 枚举 |
| AircraftCockpitArmor | 座舱装甲 | 枚举 |
| Visibility | 视野 | 枚举 |

### 武器特有字段 (DataWeapon)

| 字段 | 说明 | 单位 |
|------|------|------|
| Type | 武器类型 | 2001=导弹 |
| Generation | 世代 | 1001-1005 |
| Length | 长度 | 米 |
| Span | 翼展 | 米 |
| Diameter | 直径 | 米 |
| Weight | 重量 | 千克 |
| BurnoutTime | 燃尽时间 | 秒 |
| BurnoutWeight | 燃尽重量 | 千克 |
| CruiseAltitude | 巡航高度 | 米 |
| WaypointNumber | 航路点数 | - |
| IlluminationTime | 照射时间 | 秒 |
| CEP | 圆概率误差 | 米 |
| CEPSurface | 对海CEP | 米 |
| AirPoK | 对空杀伤概率 | 0-1 |
| SurfacePoK | 对海杀伤概率 | 0-1 |
| LandPoK | 对陆杀伤概率 | 0-1 |
| SubsurfacePoK | 对潜杀伤概率 | 0-1 |
| ClimbRate | 爬升率 | 米/秒 |
| AirRangeMax/Min | 对空射程 | 海里 |
| SurfaceRangeMax/Min | 对海射程 | 海里 |
| LandRangeMax/Min | 对陆射程 | 海里 |
| SubsurfaceRangeMax/Min | 对潜射程 | 海里 |
| LaunchSpeedMax/Min | 发射速度 | 节 |
| LaunchAltitudeMax/Min | 发射高度 | 米 |
| TargetSpeedMax/Min | 目标速度 | 节 |
| TargetAltitudeMax/Min | 目标高度 | 米 |
| SnapUpDownAltitude | 俯仰高度 | 米 |
| CanActAsSensor | 可作传感器 | 0/1 |
| MaxFlightTime | 最大飞行时间 | 秒 |
| DetonationDelay | 起爆延迟 | 秒 |
| TorpedoSpeedCruise | 鱼雷巡航速度 | 节 |
| TorpedoRangeCruise | 鱼雷巡航射程 | 海里 |
| TorpedoSpeedFull | 鱼雷全速 | 节 |
| TorpedoRangeFull | 鱼雷全射程 | 海里 |
| BuddyIlluminationForCEC | 协同照射 | 0/1 |

### 传感器特有字段 (DataSensor)

| 字段 | 说明 | 单位 |
|------|------|------|
| Type | 传感器类型 | 2001=雷达 |
| Role | 角色 | 2035=搜索 |
| Generation | 世代 | 编码 |
| MasqueradeAs | 伪装为 | - |
| RangeMin/Max | 探测距离 | 海里 |
| AltitudeMin/Max | 高度范围 | 米 |
| ScanInterval | 扫描间隔 | 秒 |
| ResolutionRange | 距离分辨率 | 米 |
| ResolutionHeight | 高度分辨率 | 米 |
| ResolutionAngle | 角度分辨率 | 度 |
| DirectionFindingAccuracy | 测向精度 | 度 |
| MaxContactsAir | 最大空目标 | 数量 |
| MaxContactsSurface | 最大面目标 | 数量 |
| MaxContactsSubmarine | 最大潜目标 | 数量 |
| MaxContactsIlluminate | 最大照射目标 | 数量 |
| Availability | 可用性 | 编码 |
| FrequencyUpper/Lower | 频率范围 | MHz |
| RadarHorizontalBeamwidth | 水平波束宽度 | 度 |
| RadarVerticalBeamwidth | 垂直波束宽度 | 度 |
| RadarSystemNoiseLevel | 系统噪声 | dB |
| RadarProcessingGainLoss | 处理增益/损耗 | dB |
| RadarPeakPower | 峰值功率 | kW |
| RadarPulseWidth | 脉冲宽度 | 微秒 |
| RadarBlindTime | 盲区时间 | 秒 |
| RadarPRF | 脉冲重复频率 | Hz |
| ESMSensitivity | ESM灵敏度 | dBm |
| ESMNumberOfChannels | ESM通道数 | - |
| ESMPreciseEmitterID | 精确辐射源识别 | 0/1 |
| ECMGain | ECM增益 | dB |
| ECMNumberOfTargets | ECM目标数 | - |
| ECMPoKReduction | 杀伤概率降低 | 百分比 |
| SonarSourceLevel | 声源级 | dB |
| SonarPulseLength | 声脉冲长度 | 秒 |
| SonarDirectivityIndex | 指向性指数 | dB |
| VisualDetectionZoomLevel | 视觉探测放大 | - |
| IRDetectionZoomLevel | 红外探测放大 | - |
| MinimumSignature_* | 最小信号特征 | 各类型 |

---

## DBID 命名与可读性问题

### 问题

CMO 数据库使用纯数字 DBID，难以区分：
```
DataShip.ID = 3883        -- 这是055？052D？还是航母？
DataAircraft.ID = 2496   -- 这是J-15？F-35？还是直升机？
```

### 建议的命名规范

如果重新设计，应采用**表名前缀**：
```
DataShip_ID = 3883        -- 清晰表明"舰船3883"
DataAircraft_ID = 2496    -- 清晰表明"飞机2496"
DataWeapon_ID = 2868      -- 清晰表明"武器2868"
```

### Lua 脚本的解决方案

由于 CMO 运行时只能使用数字 DBID，建议在 Lua 脚本中**封装常量**：

```lua
-- dbid_constants.lua
DBID = {
    SHIP = {
        TYPE_055 = 3883,        -- Type 055 Renhai [Nanchang]
        TYPE_052D = 2296,        -- Type 052D Luyang III [Kunming]
        TYPE_052DL = 3586,       -- Type 052DL Luyang III Mod [Zibo]
        TYPE_001 = 2007,         -- Type 001 Kuznetsov [Liaoning]
        TYPE_002 = 2008,         -- Type 002 [Shandong]
        TYPE_003 = 2009,         -- Type 003 [Fujian]
        TYPE_054A = 2010,        -- Type 054A Jiangkai II
        TYPE_056 = 2011,         -- Type 056 Jiangdao
        CG_59 = 2862,            -- Ticonderoga class
        DDG_51 = 4299,           -- Arleigh Burke class
        CVN_68 = 3551,           -- Nimitz class
        CVN_70 = 3552,           -- Carl Vinson
    },
    AIRCRAFT = {
        J_15 = 2496,             -- J-15 Flying Shark
        J_20 = 2497,             -- J-20 Mighty Dragon
        J_16 = 2498,             -- J-16
        SU_33 = 2499,            -- Su-33 Flanker D
        F_18E = 2500,            -- F/A-18E Super Hornet
        F_35C = 2501,            -- F-35C Lightning II
        SH_60B = 3,              -- SH-60B Seahawk
        KA_27 = 4,               -- Ka-27PL Helix A
    },
    WEAPON = {
        YJ_18 = 2868,            -- 鹰击-18
        YJ_83 = 2869,            -- 鹰击-83
        YJ_83K = 2137,           -- 鹰击-83K (空射)
        HQ_9 = 2870,             -- 海红旗-9
        HHQ_10 = 2871,           -- 海红旗-10
        PL_12 = 2872,            -- 霹雳-12
        PL_15 = 2873,            -- 霹雳-15
        AIM_120D = 2874,         -- AIM-120D AMRAAM
        Tomahawk = 2875,         -- BGM-109 Tomahawk
        Harpoon = 2876,          -- AGM-84 Harpoon
    },
    SENSOR = {
        Type_346A = 7001,        -- 346A型相控阵雷达
        Type_517 = 7002,         -- 517型雷达
        APG_79 = 7003,           -- APG-79 AESA
        APG_81 = 7004,           -- APG-81 AESA
    }
}

-- 使用方式
{name="红方055南昌舰", dbid=DBID.SHIP.TYPE_055, ...}
{name="J-15-1", dbid=DBID.AIRCRAFT.J_15, ...}
```

### 验证 DBID 的脚本

```python
import sqlite3

def verify_dbid(table, dbid):
    conn = sqlite3.connect('DB3K_504.db3')
    cursor = conn.cursor()
    cursor.execute(f'SELECT Name FROM "{table}" WHERE ID = ?', (dbid,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# 验证
print(verify_dbid('DataShip', 3883))      # Type 055 Renhai
print(verify_dbid('DataAircraft', 2496))   # J-15 Flying Shark
print(verify_dbid('DataWeapon', 2868))     # YJ-18
```

---

## 典型查询示例

### 1. 查询特定舰船
```sql
SELECT * FROM DataShip WHERE Name LIKE '%055%';
```

### 2. 查询武器挂载方案
```sql
SELECT l.Name, w.Name, lw.Quantity 
FROM DataLoadout l
JOIN DataLoadoutWeapons lw ON l.ID = lw.LoadoutID
JOIN DataWeapon w ON lw.WeaponID = w.ID
WHERE l.Name LIKE '%J-15%';
```

### 3. 查询传感器配置
```sql
SELECT s.Name, s.Type, s.RangeMax, s.Generation
FROM DataShipSensors ss
JOIN DataSensor s ON ss.SensorID = s.ID
WHERE ss.ShipID = 3883;  -- 055型驱逐舰
```

### 4. 查询国家所有舰船
```sql
SELECT Name, Type, YearCommissioned 
FROM DataShip 
WHERE OperatorCountry = 2024  -- 中国
ORDER BY YearCommissioned;
```

### 5. 查询武器射程统计
```sql
SELECT Name, SurfaceRangeMax, AirRangeMax, CEP
FROM DataWeapon
WHERE Type = 2001 AND SurfaceRangeMax > 100  -- 对海射程>100海里的导弹
ORDER BY SurfaceRangeMax DESC;
```

### 6. 查询飞机挂载能力
```sql
SELECT a.Name, l.Name, lw.Quantity, w.Name
FROM DataAircraft a
JOIN DataAircraftLoadouts al ON a.ID = al.AircraftID
JOIN DataLoadout l ON al.LoadoutID = l.ID
JOIN DataLoadoutWeapons lw ON l.ID = lw.LoadoutID
JOIN DataWeapon w ON lw.WeaponID = w.ID
WHERE a.ID = 2496 AND l.Name LIKE '%Strike%';  -- J-15 打击挂载
```

---

## 使用场景

1. **Lua 脚本开发**: 通过 DBID 引用装备，创建想定场景
2. **AI 辅助生成**: 为 LLM 提供装备知识库，生成战术脚本
3. **数据分析**: 统计各国海军力量对比、武器射程分析等
4. **仿真验证**: 校验脚本中使用的装备参数是否合理
5. **教学研究**: 查询真实装备参数，用于军事教学

---

## 注意事项

- **DBID 版本绑定**: 不同版本的 DB3K 数据库，DBID 可能不同。Build 1328.18 的 DBID 在其他版本可能指向不同装备
- **Category/Type 编码**: 需结合 Enum 表解析实际含义
- **Hypothetical 字段**: 1 表示虚构/计划装备，0 表示真实存在
- **Deprecated 字段**: 1 表示已弃用，不应在新脚本中使用
- **数据库只读**: 不要在运行时修改，可能导致 CMO 崩溃
- **硬编码路径**: JSON 配置文件中的路径需根据实际安装位置修改

---

## 版本信息

- **数据库版本**: DB3K_504
- **CMO Build**: 1328.18
- **最后更新**: 2026-07-07
- **数据覆盖**: 全球主要国家 1950-2030+ 年军事装备
- **数据库文件**: `DB3K_504.db3` (54.5 MB)

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `inspect_db.py` | 数据库结构扫描脚本 |
| `inspect_ship.py` | DataShip 表详细分析 |
| `verify_dbid.py` | DBID 验证脚本 |
| `dbid_constants.lua` | DBID 常量定义（建议创建） |

---

*本数据库由 Matrix Games / WarfareSims 维护，用于 Command: Modern Operations 模拟系统。*
*本文档由 AI 助手生成，仅供学习和研究使用。*
