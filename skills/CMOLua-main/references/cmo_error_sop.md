# CMO Lua 报错排查 SOP v3.0

> 适用范围：CMO 控制台报错、脚本能执行但仿真没动静、延时事件不触发、生成 Lua 未通过静态校验时使用。本文件用于修复，不建议在普通生成阶段长期加载。

## 测试者需要提供的信息

修复前尽量收集：

```text
1. CMO 控制台第一条错误；
2. 已打印的 _errnum_ 和 _errmsg_；
3. 报错前后 20 行日志；
4. 出错对应的 generated.lua 函数或代码块；
5. 场景是否为空白新场景，还是已经运行过同名单位/事件；
6. Time Trigger 应触发时，仿真是否已经按“播放”推进时间。
```

## 总体决策树

```text
脚本完全不运行
  -> Lua 语法错误？
  -> 是否把 Markdown 代码围栏也粘进 CMO？
  -> 是否用了非 Lua 操作符？例如字符串拼接必须是 .. 不是 +

脚本运行但没有单位
  -> 阵营是否创建成功？
  -> AddSide 是否传了 table？
  -> AddUnit type 是否非法？
  -> DBID 是否过期/错误？
  -> 坐标是否非法？

单位存在但没有 contact
  -> 红方 awareness 是否 OMNI？
  -> 蓝方目标 autodetectable 是否 true？
  -> 创建后是否推进了仿真时间？
  -> 目标 name 是否与 main 创建时完全一致？

有 contact 但不发射
  -> AttackContact 是否传了 contact GUID，而不是 unit GUID？
  -> mode 是否写成数字 1，而不是字符串 "1"？
  -> weapon DBID 是否错误或未装弹？
  -> 攻击方挂架/挂载是否兼容该武器？

事件已注册但不触发
  -> 游戏是否暂停？是否按播放推进？
  -> Time 字段是否用了 .NET ticks，而不是 Unix 秒？
  -> Event/Action/Trigger 是否重名冲突？
  -> 事件脚本是否引用了 local 函数或 upvalue？

发射了但行为异常
  -> 是否对移动目标用了 BOL？
  -> 是否没有把 quantity 拆成逐枚事件？
  -> 飞机是否还没起飞/没到射程？
  -> RTB 是否漏了 base/homebase？
```

## 常见症状表

| 症状 | 最可能原因 | 修复 |
|---|---|---|
| `side 'xxx' does not exist` | AddSide 失败或 side 字符串错误 | 使用 `ScenEdit_AddSide({name=...})`，再 `VP_GetSide` 诊断 |
| `Invalid unit type` | `Air`、`Ground`、小写或未知类型 | 改为 `Aircraft`、`Ship`、`Submarine`、`Facility`、`Satellite` |
| `Invalid latitude/longitude` | 坐标是占位字符串、空值或越界 | 生成前校验数字坐标 |
| `Missing LoadoutID` | Aircraft 没有 loadout | 查 loadout_id，Lua 使用本地实测字段名 |
| `_errmsg_: Invalid GUID` | 把 unit GUID 传给 AttackContact | 用 `VP_GetSide().contacts` 找 contact GUID |
| AttackContact 返回 nil | `mode=1` 数字、武器错、无挂架、contact 错 | 使用 `mode="1"`，核验武器和装弹 |
| contact count = 0 | 目标未 autodetectable 或红方不是 OMNI | 创建时、创建后、发射前三次设置 autodetectable；红方 OMNI |
| 脚本运行但延时不发射 | Time Trigger 未创建或游戏暂停 | 检查触发器日志，按播放推进 |
| Event 不调用函数 | 函数定义成 `local` | 改成全局函数 |
| 返航失败/盘旋 | 只设置 base 或只设置 homebase | RTB 同时设置 `homebase` 和 `base` |
| 重跑报 Event already exists | 事件名不唯一 | Event/Trigger/Action 加当前时间戳 |
| 装弹后数量为 0 | mount 不兼容或清弹把挂架删了 | 清弹只能 `remove=true`，不删 mount |

## 必须检查的日志

生成 Lua 中应该有这些日志。如果没有，先补日志再排查：

```lua
print("[CMO] side check: red=" .. tostring(redSide ~= nil) .. " blue=" .. tostring(blueSide ~= nil))
print("[CMO] create unit name=" .. tostring(u.name) .. " ok=" .. tostring(ok) .. " errmsg=" .. tostring(_errmsg_))
print("[CMO] contact count=" .. tostring(contactCount))
print("[CMO] AttackContact return=" .. tostring(r))
print("[CMO] _errnum_=" .. tostring(_errnum_) .. " _errmsg_=" .. tostring(_errmsg_))
print("[CMO] scheduled trigger=" .. trName .. " fireTime=" .. fireTime)
```

## 修复原则

```text
优先做最小补丁，不要整份重写；
优先修 manifest 和映射，不要靠 Lua 里硬补；
若 DBID/LoadoutID 错，回到 dbid_map/MCP；
若单位名错，回到 manifest.name；
若事件不触发，检查 Time ticks 和 local 函数；
若无 contact，检查 autodetectable、OMNI、settle delay；
若打击数量不对，检查 AMMO 与 STRIKE 账本；
修复后更新 cmo_error_sop 或 core_rules 中对应规则。
```

## 静态扫描建议

修复前可用简单静态扫描拦截：

```text
[ ] 是否出现 ```lua 或 ``` Markdown 围栏
[ ] 是否出现 pcall(ScenEdit_XXX, ...)
[ ] 是否出现 ScenEdit_AddSide("红方")
[ ] 是否出现 mode=1 或 mode = 1
[ ] 是否出现 s[1]/s[2]/s[3] 访问 STRIKE
[ ] 是否出现 local function fireAt
[ ] 是否出现 Time = ScenEdit_CurrentTime() + delay
[ ] 是否出现 Red/Blue 作为 side
[ ] 是否出现 JSON 中不存在的单位名
[ ] 是否存在未验证 DBID / LoadoutID
```