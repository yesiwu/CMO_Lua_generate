# Simplified Experience and Skill Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow related naval-air experiences and curated Skills to accumulate across `.scen` files and environment versions, while retaining only executable-artifact checks as hard execution gates.

**Architecture:** Experience aggregation and retrieval use tactical key, mission type, capability dimensions, conditions, and evidence quality. Environment and scenario identity remain provenance and ranking metadata. Curated Skills use one task-scope directory, with legacy cohort paths read only for backward compatibility. Campaign git state is audit metadata only.

**Tech Stack:** Python 3.13, pytest, JSON/JSONL file stores.

## Global Constraints

- Run Python commands in the `py313` Conda environment.
- Do not run CMO or DeepSeek.
- Do not delete unrelated dirty worktree changes.
- Keep StrategySpec, ExecutionPlan, Lua, CMO Results, and official-score validation as hard business checks.

---

### Task 1: Define scenario-agnostic promotion behavior

**Files:**
- Modify: `src/cmo_lua_agent/learning/skill_evolution/promotion.py`
- Modify: `src/cmo_lua_agent/learning/skill_evolution/validation.py`
- Test: `src/cmo_lua_agent/tests/learning/test_phase8_skill_evolution_workflow.py`

- [x] Add tests proving similar mission/key evidence from distinct `.scen` assets aggregates together and can qualify without a scenario-count requirement.
- [x] Replace environment/scenario promotion gates with: two independent optimization rounds, two support votes, support greater than contradict votes, mean evidence quality at least `0.50`, and scoreable/semantic-valid support evidence.
- [x] Keep scenario and environment metadata in aggregates for explanation only.

### Task 2: Make Skills task-scoped rather than cohort-scoped

**Files:**
- Modify: `src/cmo_lua_agent/learning/skill_evolution/active_loader.py`
- Modify: `src/cmo_lua_agent/learning/skill_evolution/assets.py`
- Test: `src/cmo_lua_agent/tests/learning/test_phase8_active_skill_loader.py`
- Test: `src/cmo_lua_agent/tests/learning/test_phase8_skill_assets.py`

- [x] Add tests proving a curated Skill can load for the same mission with changed environment metadata.
- [x] Write new Pending/Curated packages under `data/skills/<state>/<skill_id>/...`, with no cohort directory.
- [x] Retain read-only fallback loading from old cohort paths so existing assets remain inspectable.
- [x] Keep package checksum tamper detection as a hard asset-integrity rule.

### Task 3: Remove worktree cleanliness from Campaign configuration

**Files:**
- Modify: `src/cmo_lua_agent/evolution/controlled_input_package.py`
- Modify: `src/cmo_lua_agent/evolution/production_service.py`
- Test: `src/cmo_lua_agent/tests/evolution/test_legacy_baseline_migration.py`

- [x] Add a test proving a dirty worktree is recorded and cannot reject controlled package creation.
- [x] Remove the public `require_clean_worktree` option and its rejection branch.
- [x] Preserve git revision, dirty flag, and optional diff digest solely as audit fields.

### Task 4: Regressions and documentation

**Files:**
- Modify: `docs/architecture/current-state.md`
- Test: `src/cmo_lua_agent/tests/learning/`
- Test: `src/cmo_lua_agent/tests/evolution/`

- [x] Document mission/capability-first experience reuse and non-blocking scenario/environment metadata.
- [x] Run targeted learning and evolution tests, the full test suite, `compileall`, and `git diff --check`.
