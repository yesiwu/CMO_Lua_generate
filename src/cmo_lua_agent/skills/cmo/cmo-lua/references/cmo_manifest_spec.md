# CMO Manifest 规范 v3.0

> 适用范围：把 JSON / ScenarioIR 确定性转换为 manifest。manifest 是 Lua 生成的唯一事实源。LLM 应该从 manifest 填模板，不应该直接从原始 JSON 自由生成 Lua。

## 总体流程

推荐 Python 侧流程：

```text
load_json
  -> validate_schema
  -> normalize_sides
  -> normalize_units
  -> resolve_dbid/loadout/weapon
  -> derive_ammo_and_strike
  -> validate_manifest
  -> emit manifest.json / manifest.lua
  -> generate Lua from manifest
```

## Manifest 契约

生成 Lua 前必须先生成 `manifest.json` 或 `manifest.lua`。所有脚本必须引用同一份 manifest。禁止在 `main.lua`、`clear.lua`、`reload.lua`、`attack.lua` 中分别硬编码单位名、目标名、弹药量或武器 DBID。

推荐使用 `manifest.json` 作为生成器内部格式，再渲染为 Lua 表。

## 标准 Manifest Schema

```json
{
  "manifest_version": "3.0",
  "scenario": {
    "id": "...",
    "name": "...",
    "time": "...",
    "timezone": "...",
    "summary": "...",
    "source_hash": "..."
  },
  "sides": {
    "red": {"name": "红方", "role": "attacker"},
    "blue": {"name": "蓝方", "role": "target"}
  },
  "units": {
    "red_055_1": {
      "id": "red_055_1",
      "side_key": "red",
      "side": "红方",
      "name": "Red-055-1",
      "cmo_type": "Ship",
      "platform_type": "055",
      "dbid": 3883,
      "dbid_verified": true,
      "dbid_source": "dbid_map.json / MCP / manual_verified",
      "db_version": "DB3K_xxx",
      "latitude": 24.8324,
      "longitude": 128.583,
      "heading": 135,
      "speed": 20,
      "proficiency": "Veteran",
      "autodetectable": false,
      "base_unit_id": null,
      "base": null,
      "loadout_id": null,
      "loadout_verified": null,
      "source_path": "sides.red.units[0]"
    }
  },
  "weapons": {
    "YJ-18": {
      "name": "YJ-18",
      "weapon_dbid": 2868,
      "verified": true,
      "source": "dbid_map.json / MCP / manual_verified",
      "db_version": "DB3K_xxx"
    }
  },
  "ammo": [
    {
      "unit_id": "red_052d_1",
      "unitname": "Red-052D-1",
      "weapon": "YJ-18",
      "weapon_dbid": 2868,
      "number": 16,
      "source_path": "strikePlan[1].loaded"
    }
  ],
  "strike": [
    {
      "id": "strike_001",
      "attacker_id": "red_052d_1",
      "attacker": "Red-052D-1",
      "target_id": "blue_cvn70",
      "target": "Blue-DBID-3551",
      "weapon": "YJ-18",
      "weapon_dbid": 2868,
      "quantity": 8,
      "start_delay": 30,
      "interval": 1,
      "intent": "从 strikePlan[1] 推导的反舰打击任务",
      "source_path": "strikePlan[1]"
    }
  ],
  "clear_list": ["Red-052D-1", "Red-052D-2"],
  "warnings": []
}
```

## 阵营映射

阵营名的权威来源优先级：

```text
1. sides.red.name / sides.blue.name
2. participants
3. ScenarioIR.sides
4. 用户显式 override
```

如果 JSON 用 `red/blue` 作为 key，但 value 是中文阵营名，那么 Lua 的 `side=` 必须使用 value，例如 `"红方"`、`"蓝方"`。

禁止 LLM 自行翻译、简化或重命名阵营。

## 单位映射

每个 manifest unit 必须包含：

```text
id, side_key, side, name, cmo_type, platform_type, dbid, dbid_verified, dbid_source, source_path
```

合法 `cmo_type` 通常为：

```text
Aircraft, Ship, Submarine, Facility, Satellite
```

由 JSON 的 `type` 到 CMO `cmo_type` 的映射必须显式记录。例如：

```text
055 / 052D / CV / DDG / CG / CVN -> Ship
J-15 / J-16 / H-6K / KJ-500 -> Aircraft
UUV / SSN / SSK -> Submarine
Launcher / Radar / Airbase -> Facility
Satellite -> Satellite
```

## 舰载机 / 基地飞机字段

如果单位是 Aircraft，必须额外校验：

```text
loadout_id 存在
loadout_verified = true
base_unit_id 可以解析到某个已存在单位或基地
base = 被解析出的 CMO 单位名/基地名
```

如果 JSON 中写 `base: "red_liaoning"`，manifest 必须解析为：

```json
{
  "base_unit_id": "red_liaoning",
  "base": "红方辽宁舰"
}
```

Lua 中必须使用 `base="红方辽宁舰"`，不得使用内部 id。

## DBID 与 Override

Manifest 中的 DBID 只能来自三种来源：

```text
1. MCP/数据库查询结果；
2. verified dbid_map.json；
3. 人工确认的 override。
```

如果 JSON 自带 DBID，但与 verified cache 冲突，必须生成：

```json
{
  "override_type": "dbid_override",
  "unit_id": "red_052d_1",
  "json_dbid": 4936,
  "resolved_dbid": 2296,
  "reason": "本地 CMO DB/黄金脚本已验证该场景使用 2296",
  "approved_by": "manual/human",
  "db_version": "DB3K_xxx"
}
```

## 武器与装弹映射

`weapons` 必须包含每种武器的已验证 `weapon_dbid`。`ammo` 表示装弹清单，`strike` 表示发射计划。

对每个攻击方必须满足：

```text
sum(ammo.number where unit_id=X and weapon_dbid=W)
  >=
sum(strike.quantity where attacker_id=X and weapon_dbid=W)
```

若弹药不足，生成器必须报错，不得输出 Lua。

## strikePlan 推导规则

支持两种 JSON 写法：

```json
{"shooter": "red_052d_1", "weapon": "YJ-18", "loaded": 16, "fired": 8, "targets": ["blue_cvn70"]}
```

和：

```json
{"shooters": ["red_055_1", "red_055_2"], "weapon": "YJ-18", "loaded": 16, "fired": 13, "targets": ["blue_ddg113_1", "blue_ddg113_2"]}
```

单 shooter：生成一条或多条 strike。若多个 targets，默认平均或按策略拆分，必须记录 `split_reason`。

多 shooters：必须展开为多条 strike。拆分策略必须确定性，例如：

```text
quantity 按 shooter/target 轮转分配；
或按用户给定分配表；
或按平台弹药量比例分配。
```

禁止让 LLM 随机决定每艘舰打几枚。

## clear_list 推导

默认只把需要重新装填的红方发射平台加入 `clear_list`。例如：

```text
有 AMMO 或 STRIKE 的舰艇/飞机 -> 进入 clear_list
航母仅作为 base，不发射武器 -> 不进入 clear_list
蓝方目标 -> 不进入 clear_list
```

## Manifest 校验清单

生成 Lua 前必须通过：

```text
[ ] scenario.id/name 非空
[ ] sides.red.name / sides.blue.name 非空
[ ] units 中每个 id 唯一
[ ] units 中每个 name 在同一 side 下唯一
[ ] 每个 unit 的 dbid_verified = true
[ ] 每个 Aircraft 的 loadout_id 已验证，除非明确允许裸机 fallback
[ ] 每个 strike.attacker_id 和 target_id 都存在于 units
[ ] 每个 strike.weapon_dbid 存在于 weapons 且 verified = true
[ ] ammo 覆盖 strike 的发射量
[ ] 蓝方目标 autodetectable = true
[ ] 坐标均为数字且范围合法
[ ] warnings 中没有 high severity 未处理项
```

## 输出给 Lua 的 Manifest 表建议

Lua 侧建议使用命名键，不使用位置数组：

```lua
UNITS = {
  ["red_052d_1"] = {
    id="red_052d_1", side="红方", name="Red-052D-1",
    cmo_type="Ship", dbid=2296, latitude=21.1437, longitude=123.4510,
    heading=115, speed=20, proficiency="Veteran", autodetectable=false,
  }
}

WEAPONS = {
  ["YJ-18"] = {name="YJ-18", weapon_dbid=2868, verified=true}
}

AMMO = {
  {unit_id="red_052d_1", unitname="Red-052D-1", weapon="YJ-18", weapon_dbid=2868, number=16}
}

STRIKE = {
  {
    id="strike_001", attacker_id="red_052d_1", attacker="Red-052D-1",
    target_id="blue_cvn70", target="Blue-DBID-3551",
    weapon="YJ-18", weapon_dbid=2868, quantity=8,
    start_delay=30, interval=1, intent="source-grounded strike"
  }
}
```