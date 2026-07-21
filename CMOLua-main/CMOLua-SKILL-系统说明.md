# CMOLua-main 系统说明

## 1. 项目定位

`CMOLua-main` 是面向 **Command: Modern Operations（CMO）** 的 Lua 作战脚本技能包。它的目标不是单纯把任意 JSON 翻译成 Lua，而是把以下能力组合起来：

1. 让 AI 按 CMO Lua API、数据类型和作战规则生成代码。
2. 通过 MCP 连接 CMO 数据库，查询真实的 `DBID`、装备信息和关联数据。
3. 将结构化作战方案 JSON 稳定地渲染成可粘贴到 CMO Lua Console 的 `all.lua`。
4. 提供模板、参考文档、案例和错误排查资料。
5. 在 Windows 上通过 GUI 自动启动 CMO、打开 Lua Console、粘贴并执行脚本。

因此，项目包含两条相关但可以独立使用的链路：

```text
AI 对话链路：自然语言 -> SKILL.md 规则 -> MCP 查询 DBID -> AI 生成 Lua

确定性生成链路：作战方案 JSON -> tools/json_to_lua.py -> all.lua

可选执行链路：Lua 文件 -> auto_clicker -> CMO GUI -> Lua Console 执行
```

## 2. 重要边界

### 2.1 `SKILL.md` 不是 Python 入口

`SKILL.md` 是给 Cursor、Trae、VS Code + Continue、Claude Desktop 等 AI 客户端读取的行为规范。它规定：

- 生成代码前必须查阅 CMO Lua API 和数据类型文档。
- 不得凭空编造单位 `DBID`、武器 `DBID`、`LoadoutID`、`GUID` 或阵营名。
- 涉及装备数据时必须优先调用 MCP 查询。
- 多脚本场景应先形成 manifest，再生成建军、清弹、装弹和攻击脚本。
- 输出前必须做字段、命名、数量、弹药和幂等性检查。

它本身不会执行 Python，也不会直接把 JSON 写成文件。

### 2.2 `json_to_lua.py` 不会自动调用 MCP

`tools/json_to_lua.py` 是一个本地、同步、确定性的 Python 生成器，只读取 JSON 并生成 Lua 文本。它使用 JSON 中已有的 `dbid`、`loadoutId` 和 `weaponDbid`；如果武器 DBID 没有写入 JSON，只对少量武器使用内置兜底表。

所以生产流程应当是：

```text
先由 AI/MCP 确认装备数据
    -> 写入并校验 JSON
    -> 运行 json_to_lua.py
    -> 审阅 Lua
    -> 在 CMO 中执行
```

直接运行生成器不能替代 DBID 查询，也不能保证 JSON 中的 ID 在当前 CMO 数据库版本中有效。

### 2.3 `auto_clicker` 是 GUI 自动化，不是 BatchRunner

`auto_clicker` 使用 `pyautogui` 和 `pyperclip` 操作屏幕坐标。它依赖固定的 CMO 安装路径、窗口布局、分辨率和按钮位置，适合个人 Windows 桌面测试，不适合无人值守服务或跨机器部署。

## 3. 目录结构

```text
CMOLua-main/
├── SKILL.md                    AI 行为规范，核心入口
├── README.md / README_en.md    快速开始和英文说明
├── CONTEXT.md                  项目上下文和使用约束
├── tools/
│   └── json_to_lua.py          JSON -> all.lua 确定性生成器
├── mcp/
│   ├── server.py               MCP stdio 服务端
│   ├── query.py                MCP 查询实现/缓存/校验
│   ├── requirements.txt        MCP 依赖
│   └── db/                     CMO DB3K_*.db3 数据库放置目录
├── auto_clicker/               CMO GUI 启动、粘贴、点击执行
├── scripts/
│   ├── install.ps1             安装到 Cursor skill 目录并生成 MCP 配置
│   ├── start-mcp.ps1           启动 MCP 的辅助脚本
│   ├── check-deps.ps1          依赖检查
│   └── validate-structure.ps1  目录结构检查
├── json/                       示例作战方案 JSON 和示例 Lua
├── templates/                  基础、任务、航母、齐射等 Lua 模板
├── references/                 API、数据类型、DBID 参考文档
├── examples/                   官方和贡献案例，每个案例含说明、分析和 Lua
├── errors/                     常见 CMO/Lua 错误排查资料
├── assets/                     prompt、技能配置和模板索引
├── outputs/                    生成结果和调试产物
└── _archive/                   历史版本备份
```

`outputs/` 中已有的大量脚本是历史生成结果，不是生成器运行时必需的输入。新结果建议放在单独的运行目录，避免覆盖历史产物。

## 4. JSON -> Lua 主流程

### 4.1 命令行入口

在项目根目录执行：

```powershell
python CMOLua-main/tools/json_to_lua.py `
  CMOLua-main/json/red_blue_5v3_liaoning1.json `
  CMOLua-main/outputs/lua/generated/all.lua
```

也可以不指定输出文件，让 Lua 写到标准输出：

```powershell
python CMOLua-main/tools/json_to_lua.py CMOLua-main/json/A1场景.json
```

作为 Python 库使用：

```python
from tools.json_to_lua import generate_cmo_lua

lua_text = generate_cmo_lua("CMOLua-main/json/A1场景.json")
with open("all.lua", "w", encoding="utf-8") as f:
    f.write(lua_text)
```

从仓库根目录以库方式导入时，应确保 `CMOLua-main` 在 `PYTHONPATH` 中，或在 `CMOLua-main` 目录内执行。

### 4.2 生成器的内部阶段

`generate_cmo_lua()` 的实际流程如下：

1. 用 UTF-8 读取 JSON。
2. 校验 `sides.red`、`sides.blue`、单位 DBID、舰载机母舰和 `strikePlan` 引用。
3. 建立单位索引，把 JSON 的单位 ID 转换成 CMO 使用的单位名称。
4. 按 `aircraft`、`carrier`、`ship` 分类单位。
5. 汇总武器 DBID，优先使用 JSON 显式值，其次使用少量内置兜底值。
6. 从 `weaponLoad` 生成清弹和装弹清单。
7. 从 `strikePlan` 展开舰艇和舰载机打击组合，并按数量拆分发射任务。
8. 计算舰艇和航空兵器的中线/接近点，生成航路和返航信息。
9. 按固定顺序拼接 Lua：`header -> manifest -> main -> clear -> reload -> globals -> attack-ship -> attack-air -> footer`。
10. 返回完整 Lua 文本，CLI 再决定写文件还是输出到 stdout。

### 4.3 输出脚本的五个作战段

| 段 | 作用 |
|---|---|
| `main` | 创建红蓝阵营、设置姿态/条令、创建舰艇、目标和舰载机 |
| `clear` | 遍历指定舰艇的挂载，移除已有待发武器，减少重复执行影响 |
| `reload` | 按 JSON 中的 `weaponLoad` 为舰艇或舰载机装弹 |
| `attack-ship` | 使用全局 `fireAt` 和时间触发器安排舰艇逐枚发射 |
| `attack-air` | 设置舰载机起飞、航路、攻击和返航任务 |

脚本末尾会打印提示，说明脚本只负责预约动作，仍需要在 CMO 中推进仿真时间才能触发真实时间到达（TOT）事件。

## 5. JSON 输入格式

最小结构如下：

```json
{
  "scenario": {
    "id": "demo",
    "name": "示例想定",
    "time": "2026-07-08 08:00:00",
    "timeZone": "UTC+8"
  },
  "sides": {
    "red": {
      "name": "红方",
      "units": []
    },
    "blue": {
      "name": "蓝方",
      "units": []
    }
  },
  "strikePlan": []
}
```

### 5.1 场景字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `scenario.id` | string | 想定稳定标识 |
| `scenario.name` | string | 输出注释和日志中的想定名称 |
| `scenario.time` | string | 场景起始时间，主要用于元数据和审计 |
| `scenario.timeZone` | string | 时区说明 |
| `scenario.summary` | string | 人类可读的场景摘要 |
| `settle.ship` | number | 舰艇接敌/发现沉降等待秒数，默认 30 |
| `settle.air` | number | 舰载机起飞和接敌等待秒数，默认 150 |

### 5.2 单位字段

每个 `sides.<red|blue>.units[]` 元素通常包含：

```json
{
  "id": "red_052d_1",
  "name": "Red-052D-1",
  "dbid": 4936,
  "type": "052D",
  "latitude": 21.1437,
  "longitude": 123.451,
  "heading": 115,
  "speed": 20,
  "weaponLoad": []
}
```

| 字段 | 说明 |
|---|---|
| `id` | JSON 内部引用 ID，供 `strikePlan` 使用 |
| `name` | CMO 中创建的单位名；必须全局一致 |
| `dbid` | CMO 平台 DBID，必须从真实数据库查询 |
| `type` | 用于判断舰艇、航母或舰载机 |
| `latitude` / `longitude` | 创建位置；应为数字 |
| `heading` / `speed` | 初始航向和速度 |
| `proficiency` | 熟练度，缺省时生成器使用 `Veteran` |
| `weaponLoad` | 需要装载的武器清单 |
| `aircraftCarried` | 航母携带的舰载机 ID 列表 |
| `base` | 舰载机对应航母的 JSON `id` |
| `loadoutId` | 舰载机挂载方案 ID |

舰载机可以使用字符串坐标（例如“随航母起飞”）作为业务描述，但生成器会把非数字坐标转换为 `0`，因此真正运行前应确认脚本是否需要由 CMO 自动定位或改为有效坐标。

### 5.3 武器装载字段

```json
{
  "weapon": "YJ-18",
  "weaponDbid": 2868,
  "loaded": 16,
  "fired": 8,
  "targets": ["blue_cvn70"]
}
```

- `loaded` 决定生成器请求装入的数量。
- `fired` 用于表达作战意图；实际发射数量还要由 `strikePlan` 决定。
- `weaponDbid` 应优先显式写入。
- `targets` 是可追踪性信息，真正的打击关系以 `strikePlan` 为准。

### 5.4 `strikePlan` 字段

单射手写法：

```json
{
  "shooter": "red_052d_1",
  "weapon": "YJ-18",
  "weaponDbid": 2868,
  "loaded": 16,
  "fired": 8,
  "targets": ["blue_cvn70"]
}
```

多射手编组写法：

```json
{
  "id": "red_055_group",
  "shooters": ["red_055_1", "red_055_2"],
  "weapon": "YJ-18",
  "loaded": 16,
  "fired": 13,
  "targets": ["blue_ddg113_1", "blue_ddg113_2"]
}
```

生成器会把 `shooters` 和 `targets` 配对，必要时把总数量拆分到多条发射任务。目标 ID 必须能够在红蓝双方的 `units` 中找到，否则只会产生警告，后续 Lua 可能找不到目标。

## 6. MCP 数据库服务

### 6.1 服务端

入口是 `mcp/server.py`，通过 stdio 提供 MCP 服务，服务名为 `HKBQ_SqlDB`。数据库路径读取顺序为：

1. 环境变量 `SQLITE_DB_PATH`。
2. 默认的 `mcp/db/DB3K_504.db3`。

服务使用 SQLite 只读查询逻辑，包含短期缓存、表名白名单和多语句拦截。`read_query` 只允许 `SELECT` 或 `WITH` 查询，并自动限制结果行数。

### 6.2 提供的工具

| 工具 | 用途 |
|---|---|
| `query_dbid(query, limit=50)` | 按关键词搜索飞机、舰艇、潜艇、设施 |
| `get_dbid_by_name(name)` | 按名称查找一个最匹配的 DBID |
| `get_dbid_by_country(country, category, limit)` | 按国家和类别筛选装备 |
| `read_query(sql, params, row_limit)` | 执行受限的 SELECT 查询 |
| `list_tables()` | 列出 SQLite 表 |
| `describe_table(table_name)` | 查看表结构，并校验表名 |

关键查询示例：

```sql
SELECT ID, Name FROM DataShip WHERE Name LIKE '%Aegis%' LIMIT 20
```

```sql
SELECT ID, Name FROM DataAircraftLoadouts WHERE ComponentID = 2496 LIMIT 20
```

### 6.3 安装数据库和依赖

```powershell
python -m pip install -r CMOLua-main/mcp/requirements.txt
Copy-Item `
  "D:\游戏目录\Command Modern Operations\DB\DB3K_504.db3" `
  "CMOLua-main\mcp\db\DB3K_504.db3"
```

数据库版本必须和当前 CMO 安装匹配。版本不匹配时，DBID 可能存在但含义或 LoadoutID 不一致。

手动启动 MCP：

```powershell
$env:SQLITE_DB_PATH = "D:\pythonproject\CMO_Lua_generate\CMOLua-main\mcp\db\DB3K_504.db3"
python CMOLua-main/mcp/server.py
```

MCP 是 stdio 服务，启动后不会像 HTTP 服务一样监听端口；应由 IDE 的 MCP 客户端启动和管理它。

## 7. Skill 接入 IDE

### 7.1 使用安装脚本

在 PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File CMOLua-main/scripts/install.ps1
```

脚本会：

1. 复制项目到 `%USERPROFILE%\.cursor\skills\cmo-hkbq-skill`。
2. 生成或备份 Cursor 的 MCP 配置。
3. 将 `SQLITE_DB_PATH` 指向目标目录下的 DB3K 数据库。
4. 检查 `SKILL.md`、MCP 服务端、参考文档和模板目录。

安装脚本中的默认命名是 Cursor skill；其他 IDE 需要按其 MCP 配置格式手动接入。

### 7.2 手动 MCP 配置

```json
{
  "mcpServers": {
    "HKBQ_SqlDB": {
      "command": "python",
      "args": ["D:\\pythonproject\\CMO_Lua_generate\\CMOLua-main\\mcp\\server.py"],
      "env": {
        "SQLITE_DB_PATH": "D:\\pythonproject\\CMO_Lua_generate\\CMOLua-main\\mcp\\db\\DB3K_504.db3"
      }
    }
  }
}
```

安装依赖的 Python 必须和 IDE 实际启动 MCP 使用的 Python 是同一个环境。出现 `No module named fastmcp` 时，优先检查解释器路径，而不是重复修改 Lua 代码。

## 8. GUI 自动执行器

### 8.1 入口和流程

`CMOLua-main/main.py` 只做一件事：调用 `auto_clicker.workflow.main()`。执行流程为：

1. 检查管理员权限。
2. 弹出文件选择器选择 Lua 文件。
3. 启动 `Command.exe`。
4. 等待 CMO 启动。
5. 按 `auto_clicker/config.py` 中的坐标点击确认、菜单、Lua Console。
6. 将 Lua 文件内容复制到剪贴板并粘贴。
7. 点击执行和关闭窗口。

默认 CMO 路径和坐标写死在 `auto_clicker/config.py`：

- `DEFAULT_EXE_PATH`：示例中的 `E:\game\...\Command.exe`。
- `pre_paste_steps`：启动确认、进入菜单、打开 Lua Console。
- `post_paste_steps`：执行 Lua、关闭窗口。

如果机器分辨率、窗口位置或 CMO 版本不同，需要修改这些配置；坐标自动化不具备可靠的控件识别能力。

### 8.2 启动方式

```powershell
python CMOLua-main/main.py
```

此命令不会读取 JSON，也不会调用 `json_to_lua.py`。通常应先生成并审阅 Lua，再把 Lua 文件交给自动执行器。

## 9. 推荐的完整使用流程

### 方案 A：AI + MCP 生成

1. 安装 Skill 并配置 MCP。
2. 复制与 CMO 版本匹配的 DB3K 数据库。
3. 在 IDE 中加载 `SKILL.md`。
4. 用英文关键词查询装备和 LoadoutID。
5. 根据真实查询结果生成 manifest 和 Lua 文件。
6. 审阅单位名、阵营、数量、弹药和时间触发器。
7. 在 CMO 中执行，并推进仿真时间验证结果。

### 方案 B：JSON 确定性生成

1. 准备符合本文 JSON 结构的作战方案。
2. 通过 MCP 或其他可信来源核对所有 DBID/LoadoutID。
3. 将核对后的 ID 写入 JSON。
4. 运行 `tools/json_to_lua.py`。
5. 检查 stderr 中的 `[warn]`，修复单位引用和舰载机母舰问题。
6. 用 Lua 静态检查工具或 CMO Console 做语法验证。
7. 先执行 `main`、`clear`、`reload`，确认单位和弹药状态，再推进仿真时间测试攻击。

### 方案 C：接入现有 CMO Agent

在已有 Agent 中，建议把它拆成三个明确工具：

```text
generate_lua(json_path, output_path)
    -> 调用 tools/json_to_lua.py

query_cmo_db(query/tool arguments)
    -> 调用 mcp/server.py 或 MCP 客户端

execute_lua(lua_path)
    -> 调用现有 CMO BatchRunner 或 GUI 执行器
```

不要让 Agent 直接把自然语言拼接成 Lua 并绕过 JSON、MCP 和校验；这样会重新引入硬编码 DBID、单位名不一致和弹药数量失真的问题。

## 10. 校验与审阅清单

### JSON 生成前

- [ ] `sides.red` 和 `sides.blue` 都存在。
- [ ] 每个单位的 `id` 唯一，所有 `strikePlan` 引用都能找到。
- [ ] `name` 在 CMO 中可唯一识别，并在所有脚本中保持一致。
- [ ] 平台 `dbid` 已通过当前 CMO 数据库确认。
- [ ] 舰载机的 `base` 指向航母 ID，`loadoutId` 已确认。
- [ ] 武器 `weaponDbid` 已写入，不能依赖少量兜底表。
- [ ] 经纬度、航向、速度等数值字段不是描述性字符串。
- [ ] `loaded` 足以覆盖 `strikePlan` 的实际发射数量。

### Lua 执行前

- [ ] 检查生成器输出的 `[warn]`。
- [ ] 检查 Lua 中的阵营名、单位名、目标名和 DBID。
- [ ] 确认 `fireAt`、`scheduleLua` 等事件回调在 CMO 沙箱中可见。
- [ ] 先验证创建单位和装弹，再验证攻击调度。
- [ ] 确认 CMO 已加载正确想定、数据库版本和 Lua Console。
- [ ] 记录 CMO Console 日志和结果目录，便于定位 `LuaFailed`、`NotStarted` 或空引用错误。

## 11. 常见问题

### 找不到 `fastmcp`

MCP 使用的 Python 环境没有安装依赖，或 IDE 使用的 Python 和安装依赖的 Python 不一致。用同一个解释器执行：

```powershell
python -m pip install -r CMOLua-main/mcp/requirements.txt
python -c "import fastmcp; print(fastmcp.__file__)"
```

### MCP 能启动但查不到 DBID

检查 `SQLITE_DB_PATH`、数据库文件是否存在、数据库版本是否和 CMO 匹配。再用 `list_tables()` 和 `describe_table()` 确认表结构。

### 生成器报 `JSON 缺少 sides.red / sides.blue`

输入不是 `json_to_lua.py` 期望的作战方案格式。需要把其他格式先转换为本文的 `scenario + sides + strikePlan` 结构。

### 生成器只打印警告但脚本仍运行失败

当前 `_validate()` 的大部分检查是非致命警告。它不会替你验证所有 DBID、LoadoutID 或 CMO 运行时对象。生产接入时应在生成前增加严格 schema 校验，并把关键数据缺失升级为错误。

### CMO 中找不到单位或目标

通常是单位名不一致、阵营名不一致、创建失败后仍继续执行攻击，或脚本运行在错误的想定中。先查看 `main` 阶段的日志，再检查 `getUnit()` 返回值。

### 舰载机无法起飞或攻击

检查 `base` 是否解析成航母名称、`loadoutId` 是否有效、舰载机是否真的创建成功，以及接触沉降等待时间是否足够。生成器对非数字坐标会使用 `0`，这类输入需要特别审阅。

### GUI 自动执行点击错位

修改 `auto_clicker/config.py` 的 CMO 路径和点击坐标，确保窗口分辨率、缩放比例和启动后的对话框与配置一致。更可靠的生产执行方式是使用 BatchRunner 或显式 CMO 执行接口，而不是屏幕坐标点击。

## 12. 与当前 CMO Agent 的接入建议

在 `D:\pythonproject\CMO_Lua_generate` 的 Agent 中接入时，推荐保留以下边界：

```text
用户/LLM
  -> 结构化 scenario JSON
  -> JSON 校验与 ID 校验
  -> json_to_lua.py 生成 original.lua
  -> RunArtifactStore 保存输入、生成物和日志
  -> CMO BatchRunner 执行
  -> 读取 runner.log / cmo_output.txt
  -> 返回成功、失败、结果目录和可读摘要
```

其中：

- `CMOLua-main` 负责领域知识、JSON 转 Lua 和数据库查询。
- 当前 Agent 负责审批、进度显示、工作区权限、BatchRunner 进程管理和结果读取。
- 两边都不应重复维护一份 DBID 兜底表；真实数据库查询应是唯一来源。
- 每次运行都应保存原始 JSON、生成的 Lua、执行日志和结果目录，保证可复现。

## 13. 结论

`CMOLua-main` 最适合被当作一个 **CMO Lua 领域技能 + 数据查询服务 + 确定性代码生成器** 使用，而不是一个独立的通用 Lua 编译器。最稳妥的集成顺序是：

```text
安装 Skill/MCP
  -> 用 MCP 确认 DBID/LoadoutID
  -> 形成规范 JSON
  -> 运行 json_to_lua.py
  -> 做 Lua/数据审阅
  -> 交给 BatchRunner 或 CMO 执行
  -> 读取日志和结果
```

这样可以把“知识生成”“数据查询”“脚本生成”和“仿真执行”分开，既保留 AI 的作战方案理解能力，也避免因硬编码数据或 GUI 坐标导致运行结果不可复现。
