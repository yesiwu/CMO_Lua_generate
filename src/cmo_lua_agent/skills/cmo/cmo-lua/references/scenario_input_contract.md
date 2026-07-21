# 场景 JSON、契约与校验

`generate_cmo_lua` 的输入是工作区内一个 UTF-8 编码、顶层为对象的 `.json` 场景文件。
它不是“自然语言直接生成 Lua”的入口。场景意图、单位、阵营、任务、弹药与目标关系必须
先以 JSON 表达，并通过本项目的验证与数据库解析。

## 固定阶段

```text
JSON 文件
  → Schema 校验
  → 语义校验和规范化
  → Scenario IR 构建与校验
  → CMO 数据库解析
  → Scenario Contract / Resolved Manifest
  → JSON-to-Lua 生成
  → Lua preflight
```

每个阶段的输出只供下一阶段消费，不得回写原始输入。数据库解析后才得到可供生成器使用的
已确认装备、DBID、挂载或其他 CMO 数据。模型不得在 JSON、Lua 或对话中猜测 DBID、
LoadoutID、GUID，也不得用缩写改写 JSON 中的阵营或单位名称。

## 失败处理

生成工具返回 `failed_stage` 时，优先读取 `issues` 的 `code`、`path` 与 `message`。
常见处理方式如下：

- `schema`：修复字段类型、缺失字段、列表/对象结构或 JSON 格式；
- `semantic`：修复单位、阵营、射手、目标、武器和任务之间的业务关系；
- `ir`：检查规范化后 ID、名称和引用是否一致；
- `database`：修正无法解析或不兼容的 CMO 装备描述，不要补造编号；
- `manifest`：修正已解析资源之间的组合约束；
- `generation`：查看 Lua preflight 报告和 `rejected.lua`，而不是直接执行它。

## 生成后的约束

成功的 `original.lua` 是本次 Manifest 的产物。若要改变场景意图，应修改 JSON 后重新运行，
而不是只编辑 Lua 并把它当成新的场景来源。允许为调试执行已有 Lua，但须在结果说明中明确
它是否来自当前 JSON 运行。

需要 CMO Lua API、真实延时 TOT、载机、攻击或数据库关联表细节时，再加载相应的
`cmo_*.md` 参考文件；这些领域规则补充本项目工作流，不能取代前述校验阶段。
