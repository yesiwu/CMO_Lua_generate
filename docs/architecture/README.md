# docs/architecture

记录系统分层、依赖方向、Chat/Run/Optimize 模式和 CMOLua 集成边界。每份文档必须说明当前实现状态，禁止把规划目录当成可用模块。架构图应以 `CLI/Tools -> Orchestration -> Contract/Generation/Execution -> Artifacts` 为主方向，避免 contract 反向依赖终端。当前状态：已实现根索引，细分决策文档计划补充。
