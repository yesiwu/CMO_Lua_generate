# Optimization

`optimization/` owns deterministic candidate assembly and evaluation workflow
logic. Adaptive strategy decisions live in the flat `agents/` package, and
Campaign-level ranking/stop/baseline selection lives in `evolution/`.

Formal path:

```text
agents/StrategyProposalAgent
  -> validated candidate strategies
  -> OptimizationGenerationWorkflow
  -> candidate evaluation results
  -> Campaign ranking and champion selection
```

Do not add another CandidateSelector, ConvergenceChecker, LLM candidate
generator, or optimization loop here. Extend the existing Campaign engine and
its deterministic optimization workflow.
