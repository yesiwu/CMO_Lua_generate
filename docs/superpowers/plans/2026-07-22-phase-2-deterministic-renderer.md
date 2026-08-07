# Phase 2 Deterministic Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile the verified 6v4 baseline into a deterministic ExecutionPlan and Lua script without changing the existing JSON-to-Lua or Chat paths.

**Architecture:** The compiler consumes the existing Phase 1 ScenarioDefinition and StrategySpec. A capability validator validates the compiled plan against a narrow, versioned naval-air runtime. The renderer composes registered Plan Primitives and internal Runtime Helpers into Lua; only the Golden service drives this parallel chain.

**Tech Stack:** Python 3.13 dataclasses, existing ValidationResult, pytest, CMO BatchRunner through CmoRunner.

## Global Constraints

- Only the verified 6v4 naval-air anti-surface baseline is supported.
- No Phase 3 telemetry, scoring, candidate optimization, Agent integration, Skill work, Auto-mode changes, or Chat default-path changes.
- Plan Primitive and Runtime Helper are separate concepts.
- Same ScenarioDefinition, StrategySpec, and Runtime version must yield byte-identical Plan and Lua.
- Actual CMO execution remains manually approved and is required for Phase 2 final acceptance.

---

### Task 1: Immutable execution-plan models and Golden provenance

**Files:**
- Create: `src/cmo_lua_agent/generation/runtime_models.py`
- Modify: `src/cmo_lua_agent/contract/strategy_models.py`
- Create: `baseline/6v4/golden_manifest.json`
- Test: `src/cmo_lua_agent/tests/generation/test_runtime_models.py`

- [ ] Write tests for deep-frozen parameters, canonical JSON Pointer paths, stable checksums, and Golden Manifest validation.
- [ ] Run the test module and confirm imports fail because Phase 2 models do not exist.
- [ ] Implement the smallest immutable models and Phase 1 scenario-definition deserializer.
- [ ] Re-run the test module.

### Task 2: Compiler and capability validation

**Files:**
- Create: `src/cmo_lua_agent/generation/execution_plan_compiler.py`
- Create: `src/cmo_lua_agent/generation/capability_validator.py`
- Test: `src/cmo_lua_agent/tests/generation/test_execution_plan_compiler.py`
- Test: `src/cmo_lua_agent/tests/generation/test_capability_validator.py`

- [ ] Write failing tests for 6v4 operation lowering, dependency ordering, unknown facts, unsupported capabilities, missing Primitive registration, schema mismatch, missing dependency, and dependency cycles.
- [ ] Implement a narrow compiler for ship attacks and J-15 sorties.
- [ ] Implement validation against the registered runtime surface.
- [ ] Run both modules.

### Task 3: Runtime primitives and deterministic renderer

**Files:**
- Create: `src/cmo_lua_agent/generation/runtime_primitives.py`
- Create: `src/cmo_lua_agent/generation/lua_renderer.py`
- Test: `src/cmo_lua_agent/tests/generation/test_runtime_primitives.py`
- Test: `src/cmo_lua_agent/tests/generation/test_lua_renderer.py`

- [ ] Write failing tests proving Helpers never appear as Operations, names are deterministic, output has version metadata and a source map, and each supported Primitive renders the baseline behavior.
- [ ] Implement only the narrow 6v4 naval-air Primitive registry and its internal Lua Helpers.
- [ ] Implement canonical topological rendering and stable Lua serialization.
- [ ] Run the Renderer tests.

### Task 4: Golden service and verification assets

**Files:**
- Create: `src/cmo_lua_agent/generation/golden_baseline_service.py`
- Modify: `src/cmo_lua_agent/generation/__init__.py`
- Create: `baseline/6v4/scenario_definition.json`
- Create: `baseline/6v4/expected_execution_plan.json`
- Create: `baseline/6v4/rendered_baseline.lua`
- Test: `src/cmo_lua_agent/tests/generation/test_golden_baseline_service.py`

- [ ] Write a failing Golden test that loads verified sources, validates checksums, and compares canonical Plan and Lua artifacts.
- [ ] Implement the computation-only Golden service; it must not call CMOLua-main or mutate ScenarioWorkflow.
- [ ] Generate reviewed Golden artifacts through the service and re-run the Golden test.

### Task 5: Diagnostics and real CMO Golden execution

**Files:**
- Modify: `pytest.ini`
- Create: `src/cmo_lua_agent/tests/execution/test_phase2_golden_cmo.py`

- [ ] Write a separately marked integration test that executes the rendered Golden Lua with CmoRunner only when `CMO_GOLDEN=1`.
- [ ] Verify the rendered Lua with the existing LuaPreflightValidator.
- [ ] Run the full normal test suite.
- [ ] Run the real Golden CMO test with manual approval and record the resulting run identifier in the Golden Manifest only after success.
