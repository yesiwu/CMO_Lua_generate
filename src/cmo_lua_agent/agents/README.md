# Agents

This package is intentionally flat. Do not create role subdirectories.

An `agent` is a component that asks an LLM or Codex to make an adaptive
decision. Deterministic orchestration, validation, persistence, CMO execution,
and artifact writing stay in their domain packages. This boundary gives future
changes one obvious place to start without turning `agents/` into a second
workflow layer.

## Current agents

| File | Adaptive responsibility | Called by |
| --- | --- | --- |
| `strategy_intent_agent.py` | Plan bounded candidate intent | `StrategyProposalAgent` |
| `strategy_patch_agent.py` | Propose scalar strategy patches | `StrategyProposalAgent` |
| `strategy_proposal_agent.py` | Coordinate the bounded strategy decision | production preview builder |
| `lua_synthesis_agent.py` | Produce constrained Lua synthesis output | candidate generation/evaluation |
| `lua_repair_agent.py` | Repair candidate Lua after model or CMO/preflight evidence | formal candidate evaluator |
| `comparative_learning_agent.py` | Compare completed generation evidence | Phase 7 adapter |
| `skill_author_agent.py` | Draft a skill from qualified evidence | Phase 8 workflow |
| `system_repair_agent.py` | Ask Codex to modify Python source for a classified system bug | training repair coordinator |

Support files such as `repair_models.py`, `structured_strategy_client.py`,
`strategy_change_guard.py`, and `artifact_writer.py` define contracts or
deterministic helpers. They remain here only because they are private support
for the flat agents; they must not start workflows or CMO processes.

## Extension rule

1. Add or change adaptive LLM behavior in `agents/`.
2. Keep prompts and structured output validation beside that agent.
3. Invoke the agent from exactly one domain workflow.
4. Keep retries, state transitions, Git/test rollback, Campaign execution, and
   persisted artifacts in their existing domain owners.
5. Do not add another orchestrator or a second CLI for the same lifecycle.

For the complete production call chain, see
`docs/architecture/runtime-entrypoints.md`.
