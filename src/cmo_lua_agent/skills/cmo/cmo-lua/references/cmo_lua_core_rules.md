# CMO Lua 核心红线规则 v3.0

> 适用范围：所有由 AI/生成器产出的 Command: Modern Operations Lua 脚本。该文件只保留强制红线，供 LLM 生成代码前加载。更详细的模板、DBID 查询、舰载机流程和报错排查请加载对应 Skill 文件。

## 核心原则

CMO Lua 生成不是自由写代码，而是“数据驱动的脚本编译”。事实来自 JSON/ScenarioIR/Manifest，装备数据来自 CMO 数据库或已验证映射，Lua 只负责把这些事实转换为 CMO API 调用。

## 30 条红线

1. 禁止编造 DBID、Weapon DBID、LoadoutID、GUID。所有数值必须来自 MCP/CMO 数据库、只读 SQLite 查询，或带来源记录的 verified cache。
2. 原始 JSON 中的 DBID 不能默认可信。若与本地数据库或已验证脚本冲突，必须生成 override 记录并说明原因。
3. 生成 Lua 前必须先生成 manifest。Lua 只能引用 manifest 中的单位、武器、装弹、打击任务，不得直接从原始 JSON 随机取字段。
4. 单位 `id` 是内部稳定键；Lua 中的 `name` 必须来自 manifest 的 `units[*].name`。多脚本中不得擅自加前缀、后缀或翻译单位名。
5. 阵营名必须来自当前输入数据的权威字段，优先级为：`sides.red.name/sides.blue.name`、`participants`、`ScenarioIR.sides`、用户显式 override。不得自行把 `红方/蓝方` 改成 `Red/Blue`，也不得简化其他阵营名。
6. CMO 单位类型只能使用本地版本已验证的合法值，例如 `Aircraft`、`Ship`、`Submarine`、`Facility`、`Satellite`。禁止写 `Air`、`Ground`、`ship` 等不确定类型。
7. 坐标必须是十进制数字。纬度范围 `[-90, 90]`，经度范围 `[-180, 180]`。如果 JSON 写“随航母”“起飞后设定”等占位符，不得直接传入 `ScenEdit_AddUnit`。
8. `ScenEdit_AddSide` 必须传 table：`ScenEdit_AddSide({name="红方", color="255,0,0"})`。禁止 `ScenEdit_AddSide("红方")`。
9. 所有 `ScenEdit_*` 调用必须使用匿名函数包装：`pcall(function() ScenEdit_XXX(...) end)`。禁止 `pcall(ScenEdit_XXX, args)`。
10. 需要返回值时必须这样写：`local ok, u = pcall(function() return ScenEdit_GetUnit({...}) end)`。
11. 红方全知必须显式使用 `ScenEdit_SetSideOptions({side="红方", awareness="OMNI"})`，不能用 EMCON 或 Doctrine 伪装。
12. 红蓝双方 Doctrine 的 WCS 必须显式设置。默认建议空中、水面、水下、陆地均为 Free：`"0"`。
13. 蓝方目标创建时必须 `autodetectable=true`，创建后再遍历确认，发射前在 `fireAt` 中再次设置。
14. `ScenEdit_AttackContact` 必须攻击 contact GUID，不是目标 unit GUID。
15. contact 获取优先使用 `VP_GetSide({Side=_SIDE_RED}).contacts`，先用 `actualunitid/actualUnitID/actualunitguid/actualUnitGuid` 匹配目标 GUID，再用名称兜底。
16. 指定武器打击时使用 `mode="1"`，且 `mode` 必须是字符串，不得写数字 `1`。
17. 自动选弹时使用 `mode="0"`，只允许在平台挂载已验证但具体 weapon DBID 决定交给 CMO 时使用。
18. 真延时打击必须使用 Time Trigger + LuaScript Action + Event。禁止同步 `for` 循环假装延时。
19. 齐射必须把 `quantity=N` 拆成 N 个事件，每个事件调用 `fireAt(..., qty=1)`。
20. 被事件脚本调用的函数必须是全局函数，例如 `fireAt`、`scheduleOne`、`totTicks`。这些函数不能加 `local`。
21. 事件脚本运行在沙箱环境，不能依赖外部 upvalue。需要跨事件使用的数据必须是全局常量或 KeyStore 字符串。
22. Event、Trigger、Action 名称必须包含 `ScenEdit_CurrentTime()` 或其他唯一后缀，保证脚本可重跑。
23. 每个事件脚本执行后必须清理自己的 Event、Action、Trigger，避免重复触发或命名冲突。
24. 清弹只能用 `ScenEdit_AddReloadsToUnit({..., remove=true})`，且要先快照 mount weapons。禁止用 `DumpAmmo`、`remove_weapon`、删 mount 作为清弹手段。
25. 装弹统一使用 `ScenEdit_AddReloadsToUnit`。不要用飞机 loadout API 给舰艇 VLS 或舰艇挂架补弹。
26. Aircraft 创建必须有已验证 `loadout_id`，除非明确走“裸机 fallback”并记录 warning。
27. 舰载机创建时必须设置 `base=<航母/基地名>`。返航必须同时设置 `homebase` 和 `base`，必要时再设置返航 course。
28. 生成的 Lua 必须打印足够诊断信息：阵营创建、单位创建、装弹结果、contact 查询、AttackContact 返回、`_errnum_`、`_errmsg_`、事件触发时间。
29. 黄金脚本只能提供结构和 API 用法，不是新场景的事实来源。禁止把黄金脚本中的单位、坐标、目标和打击方案照搬到当前 JSON。
30. 静态校验失败时不得进入 CMO 运行。必须先修 manifest、DBID 映射或生成器模板。

## 命名层级规范

| 层级 | 字段风格 | 示例 |
|---|---|---|
| 原始 JSON | 保持源文件风格 | `loadoutId`、`weaponDbid`、`sides.red.name` |
| Manifest | snake_case | `loadout_id`、`weapon_dbid`、`dbid_verified` |
| Lua API | 以本地 CMO 实测为准 | 推荐使用已验证的 `loadoutid`，若目标版本要求 `LoadoutID`，在适配器层统一转换 |

## 推荐加载方式

生成普通 Lua 时加载：

```text
cmo_lua_core_rules.md
cmo_manifest_spec.md
cmo_templates_attack.md
cmo_dbid_mcp_policy.md
```

仅当 manifest 中存在舰载机或航母/基地起降时加载：

```text
cmo_aircraft_carrier_ops.md
```

仅当 CMO 执行报错或需要修复时加载：

```text
cmo_error_sop.md
```