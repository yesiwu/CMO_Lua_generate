# CMO DBID / MCP 查询策略 v3.0

> 适用范围：解析平台 DBID、武器 DBID、飞机 LoadoutID，以及维护已验证映射缓存。该文件应在生成 manifest 前加载。

## 核心原则

CMO Lua 生成依赖数据库。生成器不得猜测 DBID 或 LoadoutID。任何装备数值必须来自：

```text
1. MCP 查询；
2. 只读 SQLite 直连查询；
3. 已验证 dbid_map.json；
4. 人工确认 override。
```

## 映射状态

每个装备、武器、挂载都必须有状态：

| 状态 | 含义 | 是否允许生成 Lua |
|---|---|---|
| `verified` | 来自 MCP/数据库查询，或已在本地 CMO 测试通过 | 允许 |
| `overridden_verified` | JSON 值被已验证本地值覆盖，并记录原因 | 允许 |
| `candidate` | 可能匹配但未确认 | 默认不允许，除非用户明确要求实验运行 |
| `unknown` | 无映射 | 不允许 |
| `conflicting` | JSON 与数据库/缓存冲突 | 不允许，直到解决或记录 override |

## dbid_map.json 推荐格式

```json
{
  "platforms": {
    "055": {
      "cmo_type": "Ship",
      "dbid": 3883,
      "verified": true,
      "source": "MCP query_dbid / manual CMO test / golden script",
      "db_version": "DB3K_514",
      "notes": "Type 055 destroyer"
    }
  },
  "weapons": {
    "YJ-18": {
      "weapon_dbid": 2868,
      "verified": true,
      "source": "MCP / manual test",
      "db_version": "DB3K_514"
    }
  },
  "loadouts": {
    "J-15:YJ-83K": {
      "aircraft_dbid": 2496,
      "loadout_id": 9682,
      "weapons": [{"name": "YJ-83K", "weapon_dbid": 2137}],
      "verified": true,
      "source": "DataAircraftLoadouts + DataLoadoutWeapons / manual test",
      "db_version": "DB3K_514"
    }
  },
  "overrides": [
    {
      "source_id": "red_052d_1",
      "json_dbid": 4936,
      "resolved_dbid": 2296,
      "reason": "Local DB verified value for this scenario",
      "approved_by": "human/manual",
      "db_version": "DB3K_514"
    }
  ]
}
```

## 查询策略

### 平台 DBID

必须用英文关键词查询。示例：

```python
query_dbid("Type 055 destroyer")
query_dbid("Type 052D destroyer")
query_dbid("J-15 Flying Shark")
query_dbid("CVN-70 Carl Vinson")
```

若 MCP 不可用，但本地 SQLite 路径已知，可直接使用只读 sqlite3 查询。

### 武器 DBID

示例：

```python
query_dbid("YJ-18 anti ship missile")
query_dbid("YJ-83K anti ship missile")
```

未验证 `weapon_dbid` 的武器不得进入 `STRIKE`。

### 飞机 LoadoutID

`DataAircraftLoadouts` 等关联表在不同 DB 版本中可能存在列名语义混淆。不要凭表名猜测，必须先 inspect schema，然后使用本地已验证约定。

常见已验证查询模式：

```sql
SELECT al.ComponentID AS LoadoutID,
       dl.Name AS LoadoutName,
       w.ComponentNumber AS mount,
       dw.ID AS WeaponDBID,
       dw.Name AS WeaponName
FROM DataAircraftLoadouts al
JOIN DataLoadout dl ON dl.ID = al.ComponentID
LEFT JOIN DataLoadoutWeapons w ON w.ID = dl.ID
LEFT JOIN DataWeapon dw ON dw.ID = w.ComponentID
WHERE al.ID = :aircraft_dbid
  AND (dl.Deprecated = 0 OR dl.Deprecated IS NULL)
ORDER BY al.ComponentID, w.ComponentNumber;
```

如果本地 DB 使用相反约定，必须在查询适配器和 `dbid_map.json` 里显式记录，不得在生成过程中静默切换。

## 映射解析优先级

对每个 unit 或 weapon：

```text
1. dbid_map.json 中按 JSON id 精确命中的 verified 映射；
2. dbid_map.json 中按平台类型/武器名命中的 verified 映射；
3. MCP/SQLite 查询的精确匹配；
4. 人工选择候选项并写入 override；
5. unresolved，禁止生成 Lua。
```

## JSON 自带 DBID 的处理

JSON 自带 DBID 时必须检查：

```text
如果 JSON dbid == verified dbid -> 状态 verified_json_consistent
如果 JSON dbid != verified dbid -> 状态 conflicting，需要 override
如果无 verified dbid -> 状态 candidate_json_only，不得默认可信
```

override 示例：

```json
{
  "source_id": "red_052d_1",
  "json_dbid": 4936,
  "resolved_dbid": 2296,
  "reason": "本地 CMO 版本中该 052D 场景使用 2296，经黄金脚本测试通过",
  "approved_by": "human/manual",
  "db_version": "DB3K_514"
}
```

## MCP 不可用时的 fallback

如果 MCP 客户端吞参数、连接失败或 IDE 不支持 MCP，可以直接用 sqlite3：

```python
import sqlite3
con = sqlite3.connect(r"C:\path\to\DB3K_514.db3")
con.row_factory = sqlite3.Row
rows = con.execute("SELECT ID, Name FROM DataAircraft WHERE Name LIKE ?", ("%J-15%",)).fetchall()
for row in rows:
    print(dict(row))
```

要求：

```text
只能 SELECT / WITH 查询；
不得修改数据库；
查询结果必须写入 mapping_report；
模糊查询候选必须人工或规则确认后才能 verified。
```

## mapping_report.json

每次生成 Lua 前都应输出映射报告：

```json
{
  "scenario_id": "...",
  "db_version": "DB3K_514",
  "resolved_units": [
    {
      "unit_id": "red_j15_1",
      "name": "J-15-RED-01",
      "platform_type": "J-15",
      "cmo_type": "Aircraft",
      "dbid": 2496,
      "status": "verified",
      "source": "dbid_map.json",
      "loadout_id": 9682,
      "loadout_status": "verified"
    }
  ],
  "resolved_weapons": [
    {"weapon": "YJ-83K", "weapon_dbid": 2137, "status": "verified"}
  ],
  "overrides": [],
  "unresolved": [],
  "warnings": []
}
```

## 生成器禁止行为

```text
禁止把示例 DBID 套到不同装备上；
禁止用 J-15 DBID 代替 J-16/H-6K；
禁止因为名称相似就自动 verified；
禁止把 deprecated DBID 写入 manifest；
禁止无 loadout_id 创建带武器飞机；
禁止在 mapping_report 有 unresolved 时继续输出 Lua。
```