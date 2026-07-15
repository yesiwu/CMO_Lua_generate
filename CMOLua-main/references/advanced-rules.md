# CMO Lua 高级规则参考

> 本文档补充 `.cursorrules` 和 `SKILL.md` 中的高级用法，包括工具函数、事件系统、错误处理等。

---

## 一、工具函数（Tool_*）

### 距离计算
```lua
-- 计算两点间距离（返回海里）
local nm = Tool_Range(
    {latitude = 38.5, longitude = -72.0},
    {latitude = 40.0, longitude = -70.0}
)
```

### 方位计算
```lua
-- 计算方位角（返回度数，0-360）
local deg = Tool_Bearing(
    {latitude = 38.5, longitude = -72.0},
    {latitude = 40.0, longitude = -70.0}
)
```

### 视距检查
```lua
-- 检查两点间是否可视（考虑地球曲率和地形）
local los = Tool_LOS(
    {latitude = lat1, longitude = lon1, altitude = alt1},
    {latitude = lat2, longitude = lon2, altitude = alt2}
)
```

### 获取地面高程
```lua
-- 获取某点地面高程（米）
local elev = World_GetElevation({latitude = 38.5, longitude = -72.0})
```

### 场景时间
```lua
-- 获取当前场景时间（Unix 时间戳，单位秒）
local t = ScenEdit_CurrentTime()

-- 时间偏移：60分钟后触发
local triggerTime = ScenEdit_CurrentTime() + (60 * 60)
```

---

## 二、事件系统（TCA 模式）

### 基本结构
```
Event (事件)
  └── Trigger (触发器) - 什么条件触发
  └── Condition (条件) - 额外检查（可选）
  └── Action (动作) - 触发后执行什么
```

### 创建事件示例

```lua
-- 1. 创建事件
local event = ScenEdit_SetEvent('单位损失警报', {
    mode = 'add',
    IsRepeatable = true,
    IsActive = true
})

-- 2. 添加触发器（单位被摧毁）
ScenEdit_SetTrigger({
    mode = 'add',
    type = 'UnitDestroyed',
    side = 'Blue'
})
ScenEdit_SetEventTrigger(event.guid, {mode = 'add', name = 'UnitDestroyed'})

-- 3. 添加动作（发送消息）
ScenEdit_SetAction({
    mode = 'add',
    type = 'LuaScript',
    ScriptText = 'local u = ScenEdit_UnitX(); ScenEdit_SpecialMessage("Blue", "单位损失: " .. u.name)'
})
ScenEdit_SetEventAction(event.guid, {mode = 'add', name = 'LuaScript'})
```

### 触发器类型

| 类型 | 说明 |
|------|------|
| `ScenLoaded` | 场景加载时 |
| `Time` | 指定时间触发 |
| `RegularTime` | 定时重复触发 |
| `UnitDestroyed` | 单位被摧毁 |
| `UnitDamaged` | 单位受损 |
| `WeaponDetonation` | 武器引爆 |
| `Contact` | 发现接触 |

### 事件上下文变量

```lua
-- 在事件脚本中可用的变量
ScenEdit_UnitX()   -- 触发事件的单位（如被摧毁的单位）
ScenEdit_UnitY()   -- 另一个相关单位（如探测者）
ScenEdit_UnitC()   -- Contact 对象（接触事件）

-- 示例：单位被摧毁时记录日志
ScenEdit_SetAction({
    mode = 'add',
    type = 'LuaScript',
    ScriptText = [[
        local unit = ScenEdit_UnitX()
        if unit then
            local msg = "单位被摧毁: " .. unit.name .. " (阵营: " .. unit.side .. ")"
            ScenEdit_SpecialMessage("Blue", msg)
        end
    ]]
})
```

---

## 三、KeyStore 持久化存储

### 基本操作
```lua
-- 存储（只接受字符串！）
ScenEdit_SetKeyValue('key_name', tostring(value))
ScenEdit_SetKeyValue('unit_guid', unit.guid)
ScenEdit_SetKeyValue('is_active', 'true')

-- 读取
local value = ScenEdit_GetKeyValue('key_name')  -- 返回字符串或空字符串
local num = tonumber(ScenEdit_GetKeyValue('counter')) or 0
```

### 计数器示例
```lua
-- 场景加载时初始化
if ScenEdit_GetKeyValue('init_done') == '' then
    ScenEdit_SetKeyValue('strike_count', '0')
    ScenEdit_SetKeyValue('init_done', 'true')
end

-- 打击事件中增加计数
local count = tonumber(ScenEdit_GetKeyValue('strike_count')) or 0
count = count + 1
ScenEdit_SetKeyValue('strike_count', tostring(count))
ScenEdit_SpecialMessage('Red', '打击次数: ' .. tostring(count))
```

---

## 四、错误处理最佳实践

### pcall 包装
```lua
-- 安全调用 ScenEdit_GetUnit
local function safeGetUnit(guid)
    local ok, unit = pcall(ScenEdit_GetUnit, {guid = guid})
    if ok and unit then
        return unit
    end
    return nil
end

-- 使用
local unit = safeGetUnit('some-guid')
if unit then
    print('找到单位: ' .. unit.name)
else
    print('单位不存在')
end
```

### 批量操作容错
```lua
-- 遍历阵营单位时安全处理
local ok, side = pcall(VP_GetSide, {Side = 'Blue'})
if ok and side and side.units then
    for _, u in ipairs(side.units) do
        local unitOk, unit = pcall(ScenEdit_GetUnit, {guid = u.guid})
        if unitOk and unit then
            -- 处理单位
            print(unit.name)
        end
    end
end
```

---

## 五、Wrapper 对象属性

### Unit 常用属性
```lua
unit.guid        -- 全局唯一标识
unit.name        -- 名称
unit.side        -- 阵营
unit.type        -- 类型 (Ship, Aircraft 等)
unit.latitude    -- 纬度
unit.longitude   -- 经度
unit.altitude    -- 高度
unit.heading     -- 航向
unit.speed       -- 速度
unit.fuel        -- 燃油百分比
unit.damage      -- 损伤程度
unit.mission     -- 当前任务
unit.base        -- 所属基地
unit.proficiency -- 熟练度
```

### Side 常用属性
```lua
side.name        -- 阵营名
side.units       -- 单位数组
side.contacts    -- 接触数组
side.missions    -- 任务数组
side.rps         -- 参考点数组
side.guid        -- 阵营 GUID
```

### Mission 常用属性
```lua
mission.name        -- 任务名
mission.side        -- 所属阵营
mission.type        -- 任务类型
mission.isactive    -- 是否激活
mission.unitlist    -- 分配的单位列表
mission.targetlist  -- 目标列表
```

---

## 六、高级用法示例

### 巡逻任务完整设置
```lua
-- 1. 创建巡逻区域参考点
ScenEdit_AddReferencePoint({
    side = 'Blue', name = 'PATROL-1', latitude = 35.0, longitude = 127.0
})
ScenEdit_AddReferencePoint({
    side = 'Blue', name = 'PATROL-2', latitude = 35.1, longitude = 128.0
})
ScenEdit_AddReferencePoint({
    side = 'Blue', name = 'PATROL-3', latitude = 35.2, longitude = 127.5
})
ScenEdit_AddReferencePoint({
    side = 'Blue', name = 'PATROL-4', latitude = 35.1, longitude = 126.5
})

-- 2. 创建巡逻任务
ScenEdit_AddMission('Blue', '海空巡逻', 'patrol', {type = 'naval'})

-- 3. 配置巡逻区域
ScenEdit_SetMission('Blue', '海空巡逻', {
    patrolzone = {'PATROL-1', 'PATROL-2', 'PATROL-3', 'PATROL-4'},
    onethirdrule = true,
    flightsize = 2,
    minaircraftreq = 1
})

-- 4. 分配单位到任务
ScenEdit_AssignUnitToMission('unit-guid-1', '海空巡逻')
ScenEdit_AssignUnitToMission('unit-guid-2', '海空巡逻')
```

### 打击任务完整设置
```lua
-- 1. 创建打击任务
ScenEdit_AddMission('Red', '反舰打击', 'strike', {type = 'naval'})

-- 2. 设置目标
ScenEdit_SetMission('Red', '反舰打击', {
    targetside = 'Blue'
})

-- 3. 分配执行单位
ScenEdit_AssignUnitToMission('bomber-guid', '反舰打击')
```

### EMCON 控制
```lua
-- 阵营级 EMCON
ScenEdit_SetEMCON('Side', 'Blue', 'Radar=Passive;Sonar=Active;OECM=Passive')

-- 单机 EMCON
ScenEdit_SetEMCON('Unit', 'unit-guid', 'Radar=Active')
```

### 条令设置
```lua
-- 阵营级条令
ScenEdit_SetDoctrine({side = 'Blue'}, {
    weapon_control_status_air = 0,      -- 对空：自由
    weapon_control_status_surface = 0,  -- 对水面：自由
    weapon_control_status_subsurface = 1, -- 对水下：严格
    ignore_plotted_course = 'no',
    use_nuclear_weapons = 'no'
})

-- 单机条令覆盖
ScenEdit_SetDoctrine({guid = 'unit-guid'}, {
    weapon_control_status_air = 2  -- 对空：禁止
})
```

---

## 七、代码风格规范

### 命名规范
```lua
-- 常量：大写下划线
local MAX_UNITS = 20
local DEGREES_TO_RADIANS = 0.0174533

-- 函数：驼峰或下划线
function calculateDistance(p1, p2)
function calculate_distance(p1, p2)

-- 变量：小写下划线
local unit_guid = 'abc-123'
local is_active = true
```

### 注释规范
```lua
-- === 区块分隔注释 ===
-- --- 子区块 ---
-- 普通注释

-- 示例：
-- === 单位创建 ===
local unit = ScenEdit_AddUnit({...})

-- --- 持久化 GUID ---
ScenEdit_SetKeyValue('UNIT_GUID', unit.guid)
```

### 调试输出
```lua
-- 玩家可见消息（推荐）
ScenEdit_SpecialMessage('Blue', '任务已完成')

-- 控制台调试（仅开发时使用）
print('Debug: unit created')
```

---

## 八、常见陷阱速查

| 陷阱 | 避免方法 |
|------|----------|
| `VP_GetSide().units` 可能为空 | 使用 `if side.units and #side.units > 0 then` |
| `ScenEdit_SetMission` 覆盖整个巡逻区 | 每次设置时提供完整参考点列表 |
| 定时触发器基于场景时间 | 使用 `ScenEdit_CurrentTime() + offset` |
| Aircraft 忘记 LoadoutID | 始终通过 MCP 查询 `DataAircraftLoadouts` |
| 事件脚本中的 `\n` | 改用 `\r\n` |
| Contact GUID 直接当 Unit GUID 用 | 使用 `contact.actualunitid` |
| 事件脚本无法访问外部变量 | 使用 KeyStore 存储和读取 |
