# Runtime Entry Points and Ownership

Updated: 2026-08-12

## Main chat entry

`python -m cmo_lua_agent.main chat` uses profile `all` and is the only normal
conversation entry. It assembles one `AgentLoop` with common workspace/scenario
tools plus Training and Campaign high-level tools. The optional `standard`,
`training`, and `campaign` profiles only isolate toolsets for debugging; they
append a short scope rule to the same `MAIN_SYSTEM_PROMPT` and are not separate
agents.

Each plain `chat` launch creates a new empty chat session. Historical transcripts
remain on disk and can be selected explicitly with `chat --resume`,
`chat --session <session-id>`, or the in-chat `:use <session-id>` command. This
keeps a new task free from stale conversational assumptions while preserving
Training/Campaign recovery through their independent persistent state.

Repository questions follow `search_workspace -> read_file`; dot-prefixed paths
are never exposed to the main Agent. Complete chat history remains persisted.
`ContextManager` leaves requests unchanged below 80% of the configured one-million
token window and only then compacts a request copy toward 60%.

This document is the routing map for new development. A lifecycle has one
production entry point; lower layers must not create a parallel scheduler.

## Persistent training (recommended user entry)

```text
TrainingService.start
  -> TrainingProcessManager.start
  -> training.runtime.run_workflow
  -> TrainingRunner
  -> ProductionCampaignDriver
  -> ProductionEvolutionCampaignService (public Campaign facade)
  -> EvolutionCampaignService (persistent state/control engine)
  -> ProductionGenerationExecutor
  -> Phase 6 evaluation
  -> Phase 7 learning after each completed generation
  -> Phase 8 aggregation once, after all generations
  -> final Training report
```

Ownership is deliberately split by responsibility:

- `TrainingService`: create, inspect, pause, resume, and stop a long-running user request.
- `TrainingRunner`: persisted scheduler state and retry/resume decisions.
- `ProductionCampaignDriver`: the only adapter from scheduler actions to the Campaign facade.
- `ProductionEvolutionCampaignService`: the public production Campaign API.
- `EvolutionCampaignService`: internal durable Campaign transitions and worker control.
- `ProductionGenerationExecutor`: execute one frozen generation through Phase 6/7.
- `CodeRepairCoordinator`: protect changes, verify/restore edits, and record repairs.
- `CodeRepairAgent`: the self-developed LLM tool loop used by that coordinator;
  it does not invoke a local Codex CLI.

There is no per-request model-turn limit in this chain. Progress is bounded by
the requested generation count, persisted state, explicit stop/pause, or a
terminal unrecoverable failure—not by an AgentLoop turn counter.

## Campaign operator entry

Chat Campaign tools and manual Campaign scripts call only public methods on
`ProductionEvolutionCampaignService`. They must not access `_services`,
`_package_loader`, `_build_core`, CampaignStore internals, or run a second
orchestration loop.

## Agent boundary

All adaptive LLM/Codex decision classes live directly in
`src/cmo_lua_agent/agents/`. Deterministic code stays in the owning package:

- `training/`: durable scheduler and repair transaction
- `evolution/`: Campaign control, preview, execution, and generation lifecycle
- `optimization/`: deterministic optimization assembly/evaluation
- `learning/` and `skills/`: Phase 7/8 evidence and skill lifecycle
- `execution/`: CMO process execution
- `llm/`: provider clients and transport, never workflow policy

## Retired paths

The former `evolution/workflow.py`, parser-only `evolution/cli.py`,
`scripts/run_phase9_evolution.py`, and broken unused selector/convergence/
semantic-validator modules are removed. Do not recreate them. Extend the
persistent Training chain or public Campaign facade instead.

## Compatibility promises

- Existing Campaign state and Training state remain readable.
- Historical Training requests without `execution_mode` load as
  `PRODUCTION_CMO` without rewriting the artifact.
- Empty directories are retained as requested; their presence does not make
  them an approved code entry point.
