# Agent-Centric Architecture Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize real LLM/Codex decision makers in a flat `agents/` package and leave one clear, recoverable production training chain.

**Architecture:** Preserve TrainingRunner as the outer scheduler and the production Campaign control plane as the generation engine. Move only adaptive decision components into `agents/`; keep parsing, validation, execution, storage, and Git deterministic. Retire conflicting orchestrators and replace private script access with public runtime methods.

**Tech Stack:** Python 3.13, dataclasses, pytest, subprocess, persistent JSON/JSONL stores.

## Global Constraints

- Work directly in the current workspace; do not create a worktree.
- Keep `agents/` flat with no child directories.
- Preserve empty directories.
- Preserve standard ScenarioWorkflow, Campaign, and Training flows.
- Run every Python command in Conda environment `py313`.
- Write a failing regression test before each production behavior change.

---

### Task 1: Characterize and reconnect candidate repair

**Files:**
- Modify: `src/cmo_lua_agent/tests/evolution/test_phase9c_production_wiring.py`
- Modify: `src/cmo_lua_agent/evolution/formal_candidate_evaluator.py`

**Interfaces:**
- Consumes: `context.spec.budget.max_repair_attempts_per_candidate`.
- Produces: `CandidateRequest.max_repairs` equal to the persisted Campaign value.

- [ ] Add a test that captures the CandidateRequest passed to CandidateEvaluationWorkflow and expects the Campaign repair allowance.
- [ ] Run the test and confirm it fails because production currently passes zero.
- [ ] Replace the hard-coded zero with the Campaign budget value.
- [ ] Run the focused evolution test and related candidate tests.

### Task 2: Move strategy LLM decision classes into flat agents

**Files:**
- Create: `src/cmo_lua_agent/agents/strategy_proposal_agent.py`
- Create: `src/cmo_lua_agent/agents/strategy_intent_agent.py`
- Create: `src/cmo_lua_agent/agents/strategy_patch_agent.py`
- Modify: all production and test imports of the old optimization modules.
- Delete: the three replaced `optimization/` modules.
- Modify: `src/cmo_lua_agent/agents/__init__.py`

**Interfaces:**
- Preserve existing public class names and call signatures.
- Production imports must resolve only to `cmo_lua_agent.agents.*`.

- [ ] Add an architecture test asserting the classes live in `agents` and old implementation modules are absent.
- [ ] Run it and confirm failure against the old layout.
- [ ] Move implementations and update imports without changing behavior.
- [ ] Run strategy proposal, preview, and production wiring tests.

### Task 3: Introduce a visible SystemRepairAgent boundary

**Files:**
- Create: `src/cmo_lua_agent/agents/system_repair_agent.py`
- Modify: `src/cmo_lua_agent/training/repair.py`
- Modify: `src/cmo_lua_agent/tests/training/test_code_repair.py`

**Interfaces:**
- `SystemRepairAgent.repair(prompt: str) -> str` owns the Codex backend invocation.
- `CodeRepairCoordinator` owns snapshots, tests, restores, reports, and Git commits.

- [ ] Add a test injecting SystemRepairAgent-compatible behavior through the coordinator.
- [ ] Run it and confirm the boundary is missing.
- [ ] Implement the Agent and delegate repair generation from the coordinator.
- [ ] Run code-repair and TrainingRunner tests.

### Task 4: Remove conflicting legacy orchestrators and broken dead modules

**Files:**
- Delete: `src/cmo_lua_agent/evolution/workflow.py`
- Delete: `src/cmo_lua_agent/evolution/cli.py`
- Delete: `scripts/run_phase9_evolution.py`
- Delete: `src/cmo_lua_agent/optimization/candidate_selector.py`
- Delete: `src/cmo_lua_agent/optimization/convergence.py`
- Delete: `src/cmo_lua_agent/evaluation/semantic_validator.py`
- Modify/delete: tests that exclusively specify retired behavior.

**Interfaces:**
- Production retains only TrainingRunner plus CampaignEngine orchestration.

- [ ] Add an architecture test that rejects imports/references to retired orchestrators from production entry points.
- [ ] Confirm it fails before cleanup.
- [ ] Remove retired files and stale exports/references.
- [ ] Run evolution, optimization, evaluation, and import-smoke tests.

### Task 5: Replace private Campaign script coupling

**Files:**
- Modify: `src/cmo_lua_agent/evolution/production_service.py`
- Modify: `scripts/run_manual_campaign_generation.py`
- Modify: `scripts/run_simplified_generation.py`
- Modify: `src/cmo_lua_agent/tests/evolution/test_manual_campaign_generation_cli.py`

**Interfaces:**
- Public Runtime methods load persisted Campaigns, wait for a generation operation, and return inspection data.
- Scripts may not access Runtime or Engine underscore-prefixed fields.

- [ ] Add a source-level CLI test rejecting `_package_loader`, `_services`, `_build_core`, and `._load` usage.
- [ ] Confirm the test fails.
- [ ] Add the smallest public Runtime methods and migrate both scripts.
- [ ] Run CLI and Campaign control-plane tests.

### Task 6: Preserve old TrainingRequest state

**Files:**
- Modify: `src/cmo_lua_agent/tests/training/test_training_store.py`
- Modify: `src/cmo_lua_agent/training/store.py`

**Interfaces:**
- `TrainingStore.load_request()` accepts pre-`execution_mode` schema 1.0 records and defaults them to `PRODUCTION_CMO`.

- [ ] Add a test loading a legacy request without `execution_mode`.
- [ ] Confirm it fails with a constructor error.
- [ ] Normalize the missing field during load without rewriting historical files.
- [ ] Run TrainingStore, runtime, service, and acceptance tests.

### Task 7: Document the single chain and verify the repository

**Files:**
- Create: `src/cmo_lua_agent/agents/README.md`
- Modify: `docs/architecture/current-state.md`
- Modify: `DIRECTORY_GUIDE.md`

**Interfaces:**
- Documentation names one formal training chain and lists every active Agent.

- [ ] Update the Agent catalog and architecture chain.
- [ ] Run focused suites for training, evolution, orchestration, main, and tools.
- [ ] Run the full source test suite in `py313`.
- [ ] Import every non-test module and require zero failures.
- [ ] Run `git diff --check` and inspect the final diff for unrelated changes.
