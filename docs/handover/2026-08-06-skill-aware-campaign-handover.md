# Phase 9C Skill-Aware Campaign 交接

## 当前目标

当前工作是在 6v4 海空反舰场景中验证一条可持续迭代的正式闭环：

```text
Curated Skill
→ StrategyProposalAgent
→ 四个 Candidate StrategySpec
→ 固定 Lua 模板渲染
→ CMO 评分
→ Phase 7 批量经验
→ 后续下一代验证
```

LLM 不直接写 Lua。它通过受控 Patch 修改基线 StrategySpec；系统将完整 Candidate StrategySpec 编译为 ExecutionPlan，再由固定模板渲染可执行 Lua。



## 当前进度

### 系统架构开发
当前完成了每个阶段的独立开发 phase1 - phase 8 的开发，并且实现了 每个阶段的单独测试
并且目前能够实现 从一个 Campaign 进行候选生成，cmo推演评分，并且积累经验
这是 Phase 9C 的一次真实单代端到端验收，不是 Phase 8。
它确实从已有的固定 Lua 模板开始，但候选不是直接改 Lua：
6v4 基线 StrategySpec JSON
→ 固定 manual_baseline_template.lua
→ 基线 Lua

Curated Skill
→ StrategyProposalAgent
→ 四份 Patch
→ 四份 Candidate StrategySpec JSON
→ 同一个 manual_baseline_template.lua
→ 四份 Candidate Lua
→ CMO
→ Phase 7 经验
本次实际使用的固定模板是：
[manual_baseline_template.lua](D:\\pythonproject\\CMO_Lua_generate\\baseline\\6v4\\manual-template\\manual_baseline_template.lua)
所以模板负责不变的作战状态机、CMO 调度和评分逻辑；Baseline JSON 与四个 Candidate JSON 决定目标、弹量、延时、航空参数等受控方案差异。

### 2. 实际 Preview 已完成

## 当前阻塞与已知问题

### 代码没有提交github

### 没有基于训练workflow形成一个完整loop 
我的系统目前只打通的各自的阶段的测试，我接下来的想法是能够通过主loop去监控训练workflow  
这个训练workflow分大致三个阶段。第一阶段就是读取json和用户初始目的转lua。第二个阶段就是以这个lua为模版，进行候选lua生成，评测，积累经验。
第三个阶段，就是开启一个后台线程去启动phase8的agent去进行skill积累。因为是agent写的skill，所以到时候还要添加一个日志汇报，写成md格式的，然后描述什么时候生成的，生成了什么样的，在哪里。
主agent loop，就基于这样的训练workflow  去像codex一样一句话控制，其中一阶段和三阶段只要执行一次，二阶段可以重复执行，二阶段的问题就是怎么选择上一代冠军作为这一代baseline去优化，
我感觉 这个训练workflow，应该写成一个to dolist保存到本地。然后用户描述就是“请你读取XXjson文件，进行7代方案优化”。
为了实现这样的基于训练workflow，还需要上下文管理，会话管理，断点重塑，workflow 自动修复 就需要日志追溯。最后要写一个日志。
一次能够根据用户的一句话就训练一天这样的。

### phase8的skill积累不完善
phase 目前只能够生成skill。还应该分为相似的skill和不相似的skill，比如当前新生成了一个skill，但是以前就有类似的skill，现在需要把他们结合在一起以实现 skill进化，在同一类下，之前是1.0版本，现在就是1.1版本，生成skill的提示词和 合并进化提示词不应该是同一个东西。不同类的就按老方式进行积累。
skill进化还应该有一个验证方式，就是 从pending进化为 curated。我的系统还没有设计。但是我的phase7是会生成经验和假设经验的，假设经验会被下一次迭代进行验证。



## 下一步建议

## 必须保持的设计边界
- 测试代码应该在 conda activate py313虚拟环境下
- 不要添加太多的安全审计，比如设计什么契约，创建校验哈希值sha256，不要搞什么冻结contract，不要检查工作树干净
- 

## 容易避免的坑

- 运行真实 CMO 前必须关闭 `Command.exe` 与 `Launcher.exe`，否则 BatchRunner 会立即失败。
- 不要复用失败的 `candidate_outcome.json` 作为成功执行结果；应创建新的 attempt。
- 不要因 `score_events` 缺失否定已存在的有效官方分数；应降低因果结论和经验置信度。
- 不要让生成候选的 LLM 直接修改 Lua；Patch 必须落在受控 StrategySpec 路径内。
- 不要让 Campaign 自动触发 Phase 8 或自动批准 Skill。本轮预算已将 Phase 8 禁用。
- 所有 Python 命令必须在 `conda activate py313` 环境中执行。

## 关键入口

- 手动 Campaign CLI：`scripts/run_manual_campaign_generation.py`
- 单独 Phase 7 CLI：`scripts/run_phase7_learning.py`
- 正式策略生成协调器：`src/cmo_lua_agent/optimization/strategy_proposal_agent.py`
- AgentLoop JSON 适配器：`src/cmo_lua_agent/llm/agent_loop_json_client.py`
- 固定手工 Lua 模板：`baseline/6v4/manual-template/manual_baseline_template.lua`
- 当前 Campaign 根：`runs/evolution/skill_e2e_20260806/`
