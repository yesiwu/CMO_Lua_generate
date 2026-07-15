# 报错记录库 | Error Record

> AI 生成 Lua 代码时常见错误汇总。每次遇到新错误，必须先追加到本文件，再输出修复方案。

---

## 一、Missing 'LoadoutID'

**错误信息：**
```
ScenEdit_AddUnit 0 : Missing 'LoadoutID'
```

**原因：** `ScenEdit_AddUnit` 添加 Aircraft（飞机）时，`LoadoutID` 参数被省略或拼写错误。

**正确写法：**

```lua
-- ❌ 错误（均报错 Missing 'LoadoutID'）：
ScenEdit_AddUnit({side = "Blue", type = "Aircraft", ...})
ScenEdit_AddUnit({side = "Blue", type = "Aircraft", loadoutid = 332})    -- 小写 l/i
ScenEdit_AddUnit({side = "Blue", type = "Aircraft", loadout = "F-16C"})  -- 字符串类型

-- ✅ 正确：
ScenEdit_AddUnit({side = "Blue", type = "Aircraft", dbid = {{DBID}}, LoadoutID = {{LOADOUT_ID}}, ...})
```

**LoadoutID 查询步骤（MCP read_query）：**
```sql
SELECT ID FROM DataAircraftLoadouts WHERE ComponentID = {{DBID}};
```
返回的 `ID` 即为 `LoadoutID`（数值，非字符串）。

---

## 二、The requested object has been deprecated in the database

**错误信息：**
```
ScenEdit_AddUnit 0 : ,The requested object has been deprecated in the database
```

**原因：** DBID 不存在或已被官方弃用（CMO 数据库更新后某些 DBID 失效）。

**解决步骤：**
1. 确认 DBID 是通过 MCP 查询得到的，不是编造的
2. 用 `read_query` 查询 DBID 是否真实存在于数据库：
```sql
SELECT dbid, name FROM platforms WHERE dbid = {{DBID}};
```
3. 如返回空，说明该 DBID 确实不存在，重新通过 MCP 查询正确的 DBID

---

## 三、Invalid latitude/longitude value

**错误信息：**
```
ScenEdit_AddUnit 0 : Invalid latitude value
```

**原因：** 坐标参数名拼写错误或值超出范围（纬度 ±90，经度 ±180）。

**正确写法：**
```lua
-- ✅ 正确（参数名必须完全匹配）：
ScenEdit_AddUnit({latitude = 35.6762, longitude = 139.6503})

-- ❌ 错误（常见拼写错误）：
ScenEdit_AddUnit({lat = 35.6762, lon = 139.6503})      -- 参数名错误
ScenEdit_AddUnit({Latitude = 35.6762, Longitude = 139.6503})  -- 大写也可，但不是标准写法
```

---

## 四、Invalid unit type 'xxx'

**错误信息：**
```
ScenEdit_AddUnit 0 : Invalid unit type 'Air'
```

**原因：** `type` 参数使用了非标准值。

**正确 type 值（严格区分大小写）：**

| 单位类型 | 正确写法 | 错误写法 |
|---------|---------|---------|
| 飞机 | `Aircraft` | `Air`, `aircraft`, `Plane` |
| 舰艇 | `Ship` | `Naval`, `ship`, `boat` |
| 潜艇 | `Submarine` | `sub`, `Sub`, `underwater` |
| 地面设施 | `Facility` | `Ground`, `Facility`, `base` |

```lua
-- ✅ 正确：
ScenEdit_AddUnit({type = "Aircraft", ...})
ScenEdit_AddUnit({type = "Ship", ...})
ScenEdit_AddUnit({type = "Submarine", ...})
ScenEdit_AddUnit({type = "Facility", ...})
```

---

## 五、side 'xxx' does not exist

**错误信息：**
```
ScenEdit_SetUnit ... side 'xxx' does not exist
```

**原因：** 阵营未创建，或名称拼写不一致（CMO 中阵营名区分大小写）。

**解决：**
1. 先创建阵营：`ScenEdit_AddSide({name = "Blue"})`
2. 确认 `side` 参数与创建时完全一致（包括大小写和空格）

---

## 六、No unit found with DBID/Name

**错误信息：**
```
ScenEdit_GetUnit() returned nothing - no unit found
```

**原因：** 查询条件（DBID 或 name）对应的单位不存在。

**解决：** 用 MCP `query_dbid` 重新确认 DBID，或用 `read_query` 验证数据库中存在该单位。

---

## 七、GUID 格式错误

**错误信息：**
```
Invalid GUID format
```

**原因：** GUID 必须是标准 UUID 格式（36 字符，8-4-4-4-12）。

**正确写法：**
```lua
-- ✅ 正确：
ScenEdit_GetUnit({guid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"})

-- ❌ 错误（常见 AI 编造）：
ScenEdit_GetUnit({guid = "12345"})
ScenEdit_GetUnit({guid = "unit-001"})
```

---

## 八、参数名大小写混用

**常见错误参数名对照表：**

| 正确参数名 | AI 常误写为 |
|-----------|------------|
| `LoadoutID` | `loadoutid`, `loadout_id`, `loadoutID`, `Loadout` |
| `latitude` | `Lat`, `LAT`, `lat` |
| `longitude` | `Lon`, `LON`, `lon` |
| `altitude` | `Alt`, `ALT`, `alt` |
| `guid` | `GUID`, `Guid` |
| `dbid` | `DBID`, `Dbid` |
| `side` | `Side`, `SIDE` |
| `name` | `Name`, `NAME` |
| `type` | `Type`, `TYPE` |

---

## 九、Facility（地面设施）不需要 LoadoutID

**重要例外：** `type = "Facility"`（机场、雷达站等）**不需要** `LoadoutID`，添加时省略此参数即可。

```lua
-- ✅ Facility 正确写法（不需要 LoadoutID）：
ScenEdit_AddUnit({
    side = "Blue",
    type = "Facility",
    dbid = 35,  -- 跑道 DBID
    name = "Runway",
    latitude = 35.6762,
    longitude = 139.6503
})

-- ❌ Aircraft 必须有 LoadoutID：
ScenEdit_AddUnit({
    side = "Blue",
    type = "Aircraft",
    dbid = 3785,
    LoadoutID = 332,
    ...
})
```

---

## 十、altitude 默认单位是米，不是英尺

**常见错误**：
```lua
-- ❌ 误以为默认是英尺，导致飞机高度极低无法起飞
ScenEdit_AddUnit({..., altitude = 500})  -- 实际只有 500 米

-- ✅ 默认米，如果要英尺必须加 FT 后缀
ScenEdit_AddUnit({..., altitude = 5000})     -- 5000 米
ScenEdit_AddUnit({..., altitude = "5000 FT"}) -- 5000 英尺 ≈ 1524 米
```

---

## 十一、loadoutid（小写）与 LoadoutID（大写）

CMO Lua API 中两均可，但 `ScenEdit_AddUnit` 中推荐使用 `LoadoutID`（大写 I）。

```lua
-- ✅ 均可
ScenEdit_AddUnit({..., LoadoutID = 332})    -- 大写（推荐）
ScenEdit_AddUnit({..., loadoutid = 332})    -- 小写（也有效）

-- ❌ 字符串类型会报错
ScenEdit_AddUnit({..., LoadoutID = "332"})  -- 必须是数值
```

---

## 十二、单位不存在导致 nil 后继续调用属性报错

**错误信息**：
```
attempt to index a nil value
```

**原因**：`ScenEdit_GetUnit` 返回 nil 后继续访问 `.name` 等属性。

**正确写法**：
```lua
local unit = ScenEdit_GetUnit({name = "NotExist"})
if unit then
    print(unit.name)  -- 只在 unit 存在时访问
else
    print("单位不存在")
end
```

---

## 十三、ScenEdit_KillUnit vs ScenEdit_DeleteUnit 区别

| 函数 | 是否触发事件 | 适用场景 |
|------|-------------|---------|
| `ScenEdit_KillUnit` | ✅ 触发（Event 系统感知） | 模拟被击毁 |
| `ScenEdit_DeleteUnit` | ❌ 不触发 | 清理测试单位 |

---

## 十四、ScenEdit_GetUnit 返回 nil 而非报错

**错误表现**：`ScenEdit_GetUnit` 找不到单位时返回 nil，不会抛出错误。

**正确写法**：
```lua
-- ❌ 错误：直接访问 nil 对象的属性
local unit = ScenEdit_GetUnit({guid='not-exist'})
unit.heading = 90  -- 报错: attempt to index nil

-- ✅ 正确：nil 检查
local unit = ScenEdit_GetUnit({guid='not-exist'})
if unit then
    unit.heading = 90
else
    print("单位不存在")
end

-- ✅ 推荐：使用 pcall 包装
local ok, unit = pcall(ScenEdit_GetUnit, {guid='not-exist'})
if ok and unit then
    unit.heading = 90
end
```

---

## 十五、事件脚本中的换行符必须是 \r\n

**错误表现**：事件中的 Lua 脚本换行不正确。

**正确写法**：
```lua
-- ❌ 错误：使用 \n
ScenEdit_SetAction({
    mode = 'add',
    type = 'LuaScript',
    ScriptText = 'if true then\nprint("test")\nend'
})

-- ✅ 正确：使用 \r\n
ScenEdit_SetAction({
    mode = 'add',
    type = 'LuaScript',
    ScriptText = 'if true then\r\nprint("test")\r\nend'
})
```

---

## 十六、Contact GUID 与 Unit GUID 的区别

**错误表现**：混淆 Contact 和 Unit 的 GUID。

**正确做法**：
```lua
-- ❌ 错误：直接使用 Contact 的 GUID 查询 Unit
local contact = ScenEdit_GetContact({guid='contact-guid'})
local unit = ScenEdit_GetUnit({guid=contact.guid})  -- 可能失败

-- ✅ 正确：使用 actualunitid 获取真实 Unit GUID
local contact = ScenEdit_GetContact({guid='contact-guid'})
if contact and contact.actualunitid then
    local unit = ScenEdit_GetUnit({guid=contact.actualunitid})
end
```

---

## 十七、KeyStore 只能存储字符串

**错误表现**：直接存储数字导致问题。

**正确写法**：
```lua
-- ❌ 错误：存储数字
ScenEdit_SetKeyValue('counter', 5)  -- 可能失败或存储不正确

-- ✅ 正确：转换为字符串
ScenEdit_SetKeyValue('counter', tostring(5))

-- 读取时转换回数字
local count = tonumber(ScenEdit_GetKeyValue('counter')) or 0
```

---

## 十八、事件脚本是沙盒环境

**错误表现**：事件脚本中无法访问外部变量。

```lua
-- ❌ 错误：在事件脚本中使用外部变量
local externalVar = 100
ScenEdit_SetAction({
    mode = 'add',
    type = 'LuaScript',
    ScriptText = 'ScenEdit_SetScore("Blue", externalVar, "msg")'  -- externalVar 未定义
})

-- ✅ 正确：使用 KeyStore 在事件间共享状态
ScenEdit_SetKeyValue('score_value', tostring(100))
ScenEdit_SetAction({
    mode = 'add',
    type = 'LuaScript',
    ScriptText = 'local v = tonumber(ScenEdit_GetKeyValue("score_value")); ScenEdit_SetScore("Blue", v, "msg")'
})

---

## 十九、ScenEdit_SetSidePosture 使用说明

**正确写法：**

```lua
-- Set posture: H=Hostile, F=Friendly, N=Neutral, U=Unfriendly
ScenEdit_SetSidePosture('Red', 'Blue', 'H')

-- ✅ 更安全：用 pcall 包装防止阵营已存在时重复调用报错
pcall(ScenEdit_SetSidePosture, 'Red', 'Blue', 'H')
```

**阵营态度枚举值：**

| 值 | 含义 |
|----|------|
| `'H'` | Hostile（敌对） |
| `'F'` | Friendly（友好） |
| `'N'` | Neutral（中立） |
| `'U'` | Unfriendly（不友好） |

## 二十、Tool_Range 函数参数必须是显式坐标表格

**错误信息：**
```
Tool_Range 0 : ,No points have been set
```

**原因：** `Tool_Range` 函数不支持直接传入单位对象（unit wrapper），必须传入包含 `latitude` 和 `longitude` 的显式坐标表格。

**错误写法：**
```lua
-- ❌ 错误：直接传入单位对象
local range = Tool_Range(unitA, unitB)
local range = Tool_Range(red_055, blue_cvn)
```

**正确写法：**
```lua
-- ✅ 正确：传入显式坐标表格
local range = Tool_Range(
    {latitude = unitA.latitude, longitude = unitA.longitude},
    {latitude = unitB.latitude, longitude = unitB.longitude}
)

-- 或者使用具体数值
local range = Tool_Range(
    {latitude = 20.0, longitude = 115.0},
    {latitude = 18.0, longitude = 117.0}
)
```

**同样适用于其他工具函数：**
```lua
-- Tool_Bearing 也需要显式坐标
local bearing = Tool_Bearing(
    {latitude = unitA.latitude, longitude = unitA.longitude},
    {latitude = unitB.latitude, longitude = unitB.longitude}
)

-- Tool_LOS 也需要显式坐标
local los = Tool_LOS(
    {latitude = unitA.latitude, longitude = unitA.longitude},
    {latitude = unitB.latitude, longitude = unitB.longitude}
)
```

> 参考资料：`references/lua-api/tool-functions.md`

> 参考资料：`references/lua-api/index.md` — 阵营操作（side-functions.md）

---

## 二十一、Event/Trigger/Action 已存在（重跑脚本）

**错误信息**：
```
ScenEdit_SetEvent X 0 : Event 'TOT_1_2' already exists
```

**原因：** 重跑脚本时，旧的 Event/Trigger/Action 没清理。

**解决（红线 #11 幂等性）**：

```lua
-- ✅ 命名包含时间戳（推荐）
local function scheduleOne(..., tag)
    tag = tag .. "_" .. tostring(ScenEdit_CurrentTime())
    local evName = "Event " .. tag
    ...
end

-- ✅ 或者每次脚本开头清理
for _, ev in ipairs(ScenEdit_GetEvents() or {}) do
    pcall(ScenEdit_SetEvent, ev.name, {mode='remove'})
end
```

---

## 二十二、mount_guid 不匹配（装弹失败）

**错误信息**：
```
ScenEdit_AddReloadsToUnit 0 : mount 'xxxx' not found
```

或静默失败：`ScenEdit_AddReloadsToUnit` 返回 nil 但不报错。

**原因：** `mount_guid` 拼写错误，或者该武器和 mount 类型不兼容（如往防空垂发系统装填反舰弹）。

**解决：**
```lua
-- ✅ 不指定 mount_guid，让 API 自动分配（最稳）
pcall(ScenEdit_AddReloadsToUnit, {
    side = "红方",
    unitname = "055-1",
    wpn_dbid = 2868,
    number = 16,
    -- 省略 mount_guid
})

-- ⚠ 如果必须指定，先查清 mount 类型
local u = ScenEdit_GetUnit({side="红方", name="055-1"})
for _, m in ipairs(u.mounts or {}) do
    print(("mount_guid=%s type=%s"):format(m.mount_guid, m.mount_type))
end
```

---

## 二十三、VLS 格口数超出（装弹自动截断）

**症状：** `ScenEdit_AddReloadsToUnit` 调用"成功"返回 `true`，但 `dumpAmmo` 显示装上的弹数小于请求的 `number`。

**原因：** CMO 把超出 VLS 物理容量的部分**静默丢弃**，不报错。

**解决（红线 §E 弹药自检）：**
```lua
-- 装弹后必须 dumpAmmo 自检
pcall(ScenEdit_AddReloadsToUnit, {...})
-- 立刻验证
for _, m in ipairs(u.mounts or {}) do
    for _, w in ipairs(m.mount_weapons or {}) do
        if w.wpn_dbid == 2868 then
            local cur = tonumber(w.wpn_current) or 0
            if cur < requestedQty then
                warn(("实际装弹 %d < 请求 %d"):format(cur, requestedQty))
            end
        end
    end
end
```

> 详细规范见 `SKILL.md §6 manifest 标准模板` 的 `§E checkAmmoBalance()`。

---

## 二十四、get_dbid_by_country 对中文国家名返回空

**症状：** `get_dbid_by_country(country="中国")` 返回 0 条结果。

**原因：** CMO 数据库 `OperatorCountry` 字段存的是英文（"China"），中文搜索匹配不到。

**解决：**
```python
# ❌ 错
get_dbid_by_country(country="中国")

# ✅ 对（先查中文映射）
CN_COUNTRY_MAP = {"中国": "China", "美国": "USA", "俄罗斯": "Russia", "日本": "Japan"}
get_dbid_by_country(country=CN_COUNTRY_MAP["中国"])
```

---


