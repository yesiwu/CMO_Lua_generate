# Training Inspect Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resume a persisted running workflow when a status query finds that its background Runner has exited.

**Architecture:** `TrainingService.inspect()` reads the persisted state and asks the existing `TrainingProcessManager` whether the stored process is alive. Only an explicit `False` for a `RUNNING` workflow launches one replacement Runner. Managers that do not expose liveness keep their current inspection-only behavior.

**Tech Stack:** Python 3.13, existing `TrainingStore`, `TrainingProcessManager`, pytest.

## Global Constraints

- Run Python commands in the `py313` Conda environment.
- Work directly in the existing workspace, as explicitly requested by the user.
- Do not add a daemon, polling service, approval callback, or execution budget.
- Preserve existing `runs/training/<workflow>` state and logs.

---

### Task 1: Relaunch a known-dead running workflow during inspection

**Files:**

- Modify: `src/cmo_lua_agent/training/service.py`
- Test: `src/cmo_lua_agent/tests/training/test_training_service.py`

**Interfaces:**

- Consumes: optional `process_manager.is_running(workflow_id) -> bool`.
- Produces: `TrainingService.inspect(workflow_id)["runner_pid"]`, set only when this inspection launched a replacement process.

- [ ] **Step 1: Write the failing test**

```python
TrainingStore(tmp_path, "training-001").transition(status=TrainingStatus.RUNNING)
status = service.inspect("training-001")
assert launches == ["training-001", "training-001"]
assert status["runner_pid"] == 2
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python -m pytest src/cmo_lua_agent/tests/training/test_training_service.py -q`

Expected: the second launch and `runner_pid` are absent.

- [ ] **Step 3: Implement the minimal inspection recovery**

```python
process_running = self._process_is_running(workflow_id)
replacement_pid = None
if state.status is TrainingStatus.RUNNING and process_running is False:
    replacement_pid = self._processes.start(workflow_id)
```

Make `_process_is_running()` return `None` when the manager has no callable `is_running`; this preserves legacy/fake manager behavior.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest src/cmo_lua_agent/tests/training/test_training_service.py -q`

Expected: PASS.

- [ ] **Step 5: Run full regression and commit**

Run: `python -m pytest -q`

Commit only the two files:

```bash
git commit --only src/cmo_lua_agent/training/service.py src/cmo_lua_agent/tests/training/test_training_service.py -m "fix: recover dead training runner during status query"
```
