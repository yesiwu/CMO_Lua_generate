# inputs

保存用户输入、标准场景样例和待校验 JSON。输入是 Workflow 的事实来源，生成器不得在运行时静默覆盖它。建议按 `scenario-json-v1/` 和日期组织，文件名避免包含秘密。进入 contract 前必须经过 JSON loader；输入错误应产生结构化 ValidationReport。当前状态：目录已建立，现有样例仍分散在 `Lua/`、`json_data/` 和 CMOLua-main/json。
