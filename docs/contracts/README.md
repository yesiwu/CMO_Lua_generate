# docs/contracts

记录 Scenario JSON、Scenario IR、Resolved Manifest、ValidationIssue 和 ToolResult 的稳定格式。文档必须区分语法解析、结构校验、语义校验、数据库校验和运行时结果，注明字段类型、错误升级规则和版本号。任何 generator warning 升级为 error 都要更新这里。当前状态：计划实现，待冻结 scenario-json-v1。
