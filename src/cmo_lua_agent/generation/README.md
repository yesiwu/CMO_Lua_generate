# Generation

`generation/` contains deterministic Strategy/ExecutionPlan-to-Lua machinery.
It does not call an LLM and does not own Campaign scheduling.

The formal path is:

```text
validated StrategySpec
  -> ExecutionPlanCompiler
  -> CapabilityValidator
  -> LuaGenerationService or ManualLuaTemplatePackage
  -> LuaPreflightValidator
  -> LuaGenerationResult
```

Adaptive Lua synthesis and repair live in the flat `agents/` package. Campaign
preview and execution live in `evolution/`. The retired `CandidateGenerator`,
`StrategyGenerator`, and legacy generation-local `StrategySpec` must not be
reintroduced; they formed an unused second LLM generation path.
