# Adaptive Training Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a running training workflow persistently and transparently retry transient external failures without a fixed retry cap.

**Architecture:** `TrainingRunner` records a compact transient-failure record in the existing `TrainingState.runner` mapping. `TrainingRuntime` reads the persisted `next_retry_at` timestamp before re-entering the runner and sleeps only until that time. The service status response exposes this data, while code/input failures keep their current repair or terminal paths.

**Tech Stack:** Python 3.13, dataclasses, existing JSON TrainingStore, pytest.

## Global Constraints

- Run Python commands in the `py313` Conda environment.
- Do not add retry-count caps, approval callbacks, separate audit databases, or clean-working-tree requirements.
- Preserve existing `runs/training/<workflow>` state and logs.

---

### Task 1: Persist transient retry diagnostics

**Files:**
- Modify: `src/cmo_lua_agent/training/runner.py`
- Modify: `src/cmo_lua_agent/training/store.py`
- Test: `src/cmo_lua_agent/tests/training/test_training_runner.py`

**Interfaces:**
- Produces `TrainingState.runner["retry"]` containing `kind`, `error_type`, `message`, `consecutive_failures`, and `next_retry_at`.
- Produces `TrainingStore.transition(runner=...)` for atomic persistence.

- [ ] **Step 1: Write failing runner tests**

```python
state = runner.run_once()
retry = state.runner["retry"]
assert retry["consecutive_failures"] == 1
assert retry["next_retry_at"]
```

- [ ] **Step 2: Run the focused test**

Run: `python -m pytest src/cmo_lua_agent/tests/training/test_training_runner.py -q`

- [ ] **Step 3: Implement compact retry persistence**

Use UTC timestamps and a bounded delay function (5 seconds minimum, 60 seconds maximum); do not limit the number of attempts. Clear `runner["retry"]` after the next successful state transition.

- [ ] **Step 4: Re-run focused tests**

Run: `python -m pytest src/cmo_lua_agent/tests/training/test_training_runner.py -q`

### Task 2: Honor persisted retry schedule and expose it to status callers

**Files:**
- Modify: `src/cmo_lua_agent/training/runtime.py`
- Modify: `src/cmo_lua_agent/training/service.py`
- Test: `src/cmo_lua_agent/tests/training/test_training_runtime.py`
- Test: `src/cmo_lua_agent/tests/training/test_training_service.py`

**Interfaces:**
- Consumes `state.runner["retry"]["next_retry_at"]`.
- Produces `TrainingService.inspect(...)["retry"]` when a transient failure is pending.

- [ ] **Step 1: Write failing runtime and status tests**

```python
assert service.inspect("training-001")["retry"]["consecutive_failures"] == 1
assert sleeps == [5]
```

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest src/cmo_lua_agent/tests/training/test_training_runtime.py src/cmo_lua_agent/tests/training/test_training_service.py -q`

- [ ] **Step 3: Implement scheduled retry wait**

Parse the persisted UTC value, sleep for the remaining delay, and retry the same action. If no retry record exists, retain the existing one-second worker polling interval.

- [ ] **Step 4: Re-run focused tests**

Run: `python -m pytest src/cmo_lua_agent/tests/training/test_training_runtime.py src/cmo_lua_agent/tests/training/test_training_service.py -q`

### Task 3: Verify and repeat real CMO smoke gate

**Files:**
- Test: `src/cmo_lua_agent/tests/training/`

- [ ] **Step 1: Run full regression**

Run: `python -m pytest src/cmo_lua_agent/tests -q`

- [ ] **Step 2: Commit the implementation**

```bash
git add src/cmo_lua_agent/training src/cmo_lua_agent/tests/training
git commit -m "feat: add adaptive training retry state"
```

- [ ] **Step 3: Start one real generation and inspect persisted retry state**

```powershell
python scripts/run_training_workflow.py start --input-path baseline/6v4/manual-template/6v4ScenarioIR_baseline_v3.json --objective "验证自适应训练恢复" --generation-count 1
python scripts/run_training_workflow.py status --workflow-id <returned-id>
```

- [ ] **Step 4: Record the gate outcome accurately**

Treat an unreachable provider as an external acceptance blocker; only report CMO success after the workflow enters execution and completes its generation result.
