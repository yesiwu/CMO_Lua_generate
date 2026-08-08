# Codex Training Loop Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent, result-driven Training Harness that turns one natural-language request plus a ScenarioIR file into an unattended multi-generation Campaign, recovers after restart, runs Phase 8 once at the end, and can invoke a bounded-by-progress code-repair workflow without breaking the existing manual Campaign path.

**Architecture:** Add a small `cmo_lua_agent.training` package above the existing `ProductionEvolutionCampaignService`; CampaignStore, workers, ledgers, generation artifacts, Champion selection, Rolling Baseline, and Phase 7 remain authoritative. The new TrainingStore persists only cross-generation scheduling state under `runs/training/<workflow_id>`. Existing entry points remain compatible while a new `training` chat profile exposes START/STATUS/PAUSE/RESUME/STOP tools.

**Tech Stack:** Python 3.13, dataclasses, pathlib, JSON/JSONL, existing Campaign services, pytest, Git CLI, optional Codex CLI repair backend.

## Global Constraints

- Work directly in `D:\pythonproject\CMO_Lua_generate`; do not create a Git worktree.
- Run Python commands in the `py313` Conda environment using the PowerShell activation prefix shown below.
- Preserve existing `prepare / preview / execute / inspect` behavior and existing `runs/evolution` artifacts.
- Keep runtime state lightweight: JSON, JSONL, Markdown reports, and process logs only.
- Do not add Redis, Celery, a general DAG engine, hashes beyond existing business contracts, or clean-working-tree requirements.
- Do not stop a Training Workflow because of fixed Agent, CMO, LLM, Lua, Phase 7, or Phase 8 call-count limits.
- Keep per-operation timeouts and no-progress detection as liveness controls.
- A START request authorizes every required generation action and the final Phase 8; no per-generation approval prompt is allowed on the new path.
- Existing user changes in the dirty working tree are not staged, reverted, or overwritten unless their files are explicitly part of a task below.

Use this prefix for every Python command:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
(& conda 'shell.powershell' 'hook') | Out-String | Invoke-Expression
conda activate py313
```

---

### Task 1: Protect and publicly rehydrate existing Campaigns

**Files:**
- Modify: `src/cmo_lua_agent/evolution/production_service.py`
- Modify: `src/cmo_lua_agent/evolution/control_plane.py`
- Modify: `src/cmo_lua_agent/evolution/cmo_lock.py`
- Test: `src/cmo_lua_agent/tests/evolution/test_phase9c_production_wiring.py`
- Test: `src/cmo_lua_agent/tests/evolution/test_campaign_control_plane.py`
- Test: `src/cmo_lua_agent/tests/evolution/test_knowledge_and_lock.py`

**Interfaces:**
- Produces: `ProductionEvolutionCampaignService.load_campaign(campaign_id: str) -> EvolutionCampaignService`.
- Produces: `ProductionEvolutionCampaignService.reconcile_campaign(campaign_id: str) -> dict[str, Any]`.
- Produces: `EvolutionCampaignService.load_spec(campaign_root: Path) -> EvolutionCampaignSpec`.
- Produces: `EvolutionCampaignService.reconcile_generation(campaign_id: str, generation_index: int) -> dict[str, Any]`.
- Produces: `CmoInstanceLock.clear_stale() -> bool` using the recorded owner PID.

- [ ] **Step 1: Add failing lazy-load tests**

```python
def test_production_facade_loads_persisted_campaign_after_restart(tmp_path: Path) -> None:
    first = _fixture_facade(tmp_path)
    first.prepare_campaign_request(**_prepare_args("persisted"))
    restarted = _fixture_facade(tmp_path)
    assert restarted.load_campaign("persisted").inspect_campaign("persisted")["campaign_id"] == "persisted"
```

- [ ] **Step 2: Run the focused tests and confirm `campaign_service_not_loaded`**

```powershell
python -m pytest src/cmo_lua_agent/tests/evolution/test_phase9c_production_wiring.py -q
```

- [ ] **Step 3: Implement public loading and make facade methods lazy**

```python
def load_campaign(self, campaign_id: str) -> EvolutionCampaignService:
    root = self._campaigns_root / campaign_id
    spec = EvolutionCampaignService.load_spec(root)
    package = self._package_loader.load(spec.scenario_ref)
    service = self._build_core(spec, package)
    self._services[campaign_id] = service
    return service
```

`preview_generation` and `execute_generation` must still bind the Rolling Baseline for the requested generation; inspect/control methods may use the base package because they only read persisted truth.

- [ ] **Step 4: Add deterministic worker reconciliation tests**

Test both branches: a persisted `running` worker with a complete `generation-result.json` becomes `completed`; an incomplete worker becomes `reconciliation_required` and a later execute receives a fresh phase-level operation while retaining completed candidate slots.

- [ ] **Step 5: Implement reconciliation and stale-lock cleanup**

`reconcile_generation` reads WorkerState, operation ledger, candidate artifacts, and generation-result. It never marks a generation complete from Training state alone. A stale `.cmo-instance.lock` is removable only when its recorded PID is not alive; a live PID remains locked.

- [ ] **Step 6: Run old-flow regression tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/evolution/test_campaign_control_plane.py src/cmo_lua_agent/tests/evolution/test_phase9c_production_wiring.py src/cmo_lua_agent/tests/evolution/test_knowledge_and_lock.py src/cmo_lua_agent/tests/evolution/test_manual_campaign_generation_cli.py -q
```

- [ ] **Step 7: Commit only Task 1 files**

```powershell
git add src/cmo_lua_agent/evolution/production_service.py src/cmo_lua_agent/evolution/control_plane.py src/cmo_lua_agent/evolution/cmo_lock.py src/cmo_lua_agent/tests/evolution/test_phase9c_production_wiring.py src/cmo_lua_agent/tests/evolution/test_campaign_control_plane.py src/cmo_lua_agent/tests/evolution/test_knowledge_and_lock.py
git commit -m "feat: rehydrate persisted evolution campaigns"
```

### Task 2: Add TrainingRequest, TrainingState, and TrainingStore

**Files:**
- Create: `src/cmo_lua_agent/training/__init__.py`
- Create: `src/cmo_lua_agent/training/models.py`
- Create: `src/cmo_lua_agent/training/store.py`
- Test: `src/cmo_lua_agent/tests/training/test_training_store.py`

**Interfaces:**
- Produces: `TrainingRequest`, `TrainingState`, `TrainingStatus`, `TrainingStage`, `TrainingAction`, `Phase8Progress`.
- Produces: `TrainingStore.create(request)`, `load_request()`, `load_state()`, `transition(...)`, `append_event(...)`, `write_summary(...)`, `write_todo(...)`, and `lock()`.

- [ ] **Step 1: Write state serialization and transition tests**

```python
def test_training_store_creates_minimal_resumable_files(tmp_path: Path) -> None:
    store = TrainingStore(tmp_path, "training-001")
    store.create(_request("training-001", generations=3))
    assert store.load_state().status is TrainingStatus.CREATED
    assert (store.root / "request.json").is_file()
    assert (store.root / "journal.jsonl").read_text(encoding="utf-8").count("\n") == 1
```

- [ ] **Step 2: Run the new test and confirm the package is missing**

```powershell
python -m pytest src/cmo_lua_agent/tests/training/test_training_store.py -q
```

- [ ] **Step 3: Implement immutable request and scheduler-only state models**

```python
@dataclass(frozen=True, slots=True)
class TrainingRequest:
    schema_version: str
    workflow_id: str
    session_id: str | None
    input_path: str
    objective: str
    generation_mode: str
    generation_count: int | None
    auto_code_repair: bool
    phase8_mode: str
    authorized_by_request: bool
    created_at: str
```

`TrainingState` contains workflow/campaign IDs, revision, status, stage, action, current generation, completed generations, active worker/failure, last good commit, runner metadata, Phase 8 progress, and timestamps. It contains no Candidate score or CMO result copy.

- [ ] **Step 4: Implement atomic JSON, append-only journal, derived summary/TODO, and exclusive workflow lock**

Use a sibling `.tmp` followed by `os.replace`. The lock uses `O_CREAT | O_EXCL`, records PID and instance ID, and may clear only a dead owner.

- [ ] **Step 5: Run the TrainingStore tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/training/test_training_store.py -q
```

- [ ] **Step 6: Commit Task 2**

```powershell
git add src/cmo_lua_agent/training src/cmo_lua_agent/tests/training/test_training_store.py
git commit -m "feat: persist training workflow state"
```

### Task 3: Resolve arbitrary compatible ScenarioIR files

**Files:**
- Create: `src/cmo_lua_agent/training/input_resolver.py`
- Modify: `src/cmo_lua_agent/evolution/controlled_input_package.py`
- Modify: `src/cmo_lua_agent/evolution/production_service.py`
- Test: `src/cmo_lua_agent/tests/training/test_input_resolver.py`
- Test: `src/cmo_lua_agent/tests/evolution/test_phase9c_assets_and_jobs.py`

**Interfaces:**
- Produces: `ResolvedScenarioInput(reference: str, absolute_path: Path, scenario_id: str)`.
- Produces: `ScenarioInputResolver(project_root).resolve(path: str | Path) -> ResolvedScenarioInput`.
- Extends: `ControlledCampaignInputPackageLoader.load(reference)` so the legacy package ID remains valid and a validated project-relative or absolute JSON path is also valid.

- [ ] **Step 1: Write failing resolver tests using a copy of the manual-template ScenarioIR**

Assert path normalization, JSON-object validation, BaselineStrategyBuilder validation, missing path error, and loader use of the supplied JSON rather than `json_data/6v4ScenarioIR.json`.

- [ ] **Step 2: Run focused tests and observe `unknown_campaign_input_package`**

```powershell
python -m pytest src/cmo_lua_agent/tests/training/test_input_resolver.py -q
```

- [ ] **Step 3: Implement resolver and backward-compatible loader extension**

The fixed ID `red_blue_6v4_liaoning_v1` keeps its current source path. A file reference is resolved without copying the user file, validated through `BaselineStrategyBuilder`, and persisted in `EvolutionCampaignSpec.scenario_ref` so restart can reload it.

- [ ] **Step 4: Make `initial_strategy_ref` reflect the resolved ScenarioIR**

Use the package’s persisted scenario reference instead of the current hard-coded `json_data/6v4ScenarioIR.json#derived-baseline` when the new path is used.

- [ ] **Step 5: Run input and legacy package tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/training/test_input_resolver.py src/cmo_lua_agent/tests/evolution/test_phase9c_assets_and_jobs.py src/cmo_lua_agent/tests/evolution/test_legacy_baseline_migration.py -q
```

- [ ] **Step 6: Commit Task 3**

```powershell
git add src/cmo_lua_agent/training/input_resolver.py src/cmo_lua_agent/evolution/controlled_input_package.py src/cmo_lua_agent/evolution/production_service.py src/cmo_lua_agent/tests/training/test_input_resolver.py src/cmo_lua_agent/tests/evolution/test_phase9c_assets_and_jobs.py
git commit -m "feat: resolve training ScenarioIR inputs"
```

### Task 4: Add Training execution policy without count budgets or per-generation Phase 8

**Files:**
- Modify: `src/cmo_lua_agent/evolution/models.py`
- Modify: `src/cmo_lua_agent/evolution/control_plane.py`
- Modify: `src/cmo_lua_agent/evolution/campaign_store.py`
- Modify: `src/cmo_lua_agent/evolution/production_executor.py`
- Modify: `src/cmo_lua_agent/evolution/production_service.py`
- Test: `src/cmo_lua_agent/tests/evolution/test_campaign_models.py`
- Test: `src/cmo_lua_agent/tests/evolution/test_phase9c_control_transaction.py`
- Test: `src/cmo_lua_agent/tests/evolution/test_phase9c_frozen_preview.py`

**Interfaces:**
- Adds: `CampaignBudget.enforce_count_limits: bool = True`.
- Adds: `EvolutionCampaignSpec.phase8_mode: str = "per_generation"`.
- Adds: `ProductionEvolutionCampaignService.prepare_training_campaign(...)` that builds an internal compatibility budget with `enforce_count_limits=False` and `phase8_mode="after_all_generations"`.

- [ ] **Step 1: Write tests proving old budget enforcement remains and Training mode skips it**

```python
def test_training_budget_does_not_exhaust_cmo_or_llm_counts() -> None:
    budget = _budget(enforce_count_limits=False, max_cmo_runs=1, max_llm_total_calls=1)
    assert budget.can_reserve_generation(available_cmo_runs=0)
```

Also assert legacy mode still raises the existing budget errors.

- [ ] **Step 2: Write executor tests for Phase 7 every generation and Phase 8 never per generation in Training mode**

The expected generation result is `phase7.status == "completed"` and `phase8 == {"status": "not_run", "reason": "deferred_to_training_phase8"}`.

- [ ] **Step 3: Implement the policy flag through model serialization and every count gate**

All current comparisons against CMO/LLM count ceilings must be conditional on `enforce_count_limits`. Per-candidate and per-generation timeouts remain active. Existing JSON without the new field deserializes with `True`.

- [ ] **Step 4: Implement internal Training authorization**

Training execution calls `execute_generation` directly; it does not create a terminal PermissionHook receipt. Existing campaign tools retain their current approval declarations and schemas.

- [ ] **Step 5: Run budget, executor, and old tool tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/evolution/test_campaign_models.py src/cmo_lua_agent/tests/evolution/test_campaign_control_plane.py src/cmo_lua_agent/tests/evolution/test_phase9c_control_transaction.py src/cmo_lua_agent/tests/evolution/test_phase9c_frozen_preview.py src/cmo_lua_agent/tests/tools/test_campaign_tool_profile.py -q
```

- [ ] **Step 6: Commit Task 4**

```powershell
git add src/cmo_lua_agent/evolution/models.py src/cmo_lua_agent/evolution/control_plane.py src/cmo_lua_agent/evolution/campaign_store.py src/cmo_lua_agent/evolution/production_executor.py src/cmo_lua_agent/evolution/production_service.py src/cmo_lua_agent/tests/evolution
git commit -m "feat: add unbounded training campaign policy"
```

### Task 5: Implement single- and multi-generation TrainingRunner

**Files:**
- Create: `src/cmo_lua_agent/training/runner.py`
- Create: `src/cmo_lua_agent/training/runtime.py`
- Test: `src/cmo_lua_agent/tests/training/test_training_runner.py`
- Test: `src/cmo_lua_agent/tests/training/test_training_runner_integration.py`

**Interfaces:**
- Consumes: `TrainingStore`, `ScenarioInputResolver`, `ProductionEvolutionCampaignService`.
- Produces: `TrainingRunner.run() -> TrainingState`, `run_once() -> TrainingState`, and `reconcile() -> TrainingState`.
- Produces: `CampaignDriver` protocol with `prepare`, `preview`, `execute`, `inspect_generation`, `pause`, `resume`, `stop`, and `reconcile` methods so fake integration tests do not start CMO.

- [ ] **Step 1: Write a failing one-generation state-machine test**

```python
def test_runner_completes_one_generation_without_user_approval(tmp_path: Path) -> None:
    driver = FakeCampaignDriver()
    state = TrainingRunner(_store(tmp_path, generations=1), driver).run()
    assert state.completed_generations == (0,)
    assert driver.calls == ["prepare", "preview:0", "execute:0", "inspect:0"]
```

- [ ] **Step 2: Implement one-action-at-a-time deterministic transitions**

`run_once` derives its next action from request/state plus Campaign truth, persists state before and after each external action, and treats an already completed artifact as idempotent success.

- [ ] **Step 3: Write and pass fake three-generation integration**

Assert order `prepare → preview/execute/inspect × 3`, all three completed generations, no approval callback, and no per-generation Phase 8 call.

- [ ] **Step 4: Implement worker polling with operation timeout and progress events**

Polling reads persisted WorkerState. Timeout creates a TRANSIENT failure record; it does not decrement a retry budget or mark a generation successful.

- [ ] **Step 5: Add PAUSE/RESUME/STOP safe-boundary tests**

Pause prevents scheduling the next action after the active Campaign call returns. Resume reconciles before scheduling. Stop records STOPPED and calls Campaign stop once.

- [ ] **Step 6: Run TrainingRunner and old Campaign tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/training/test_training_runner.py src/cmo_lua_agent/tests/training/test_training_runner_integration.py src/cmo_lua_agent/tests/evolution/test_campaign_control_plane.py -q
```

- [ ] **Step 7: Commit Task 5**

```powershell
git add src/cmo_lua_agent/training/runner.py src/cmo_lua_agent/training/runtime.py src/cmo_lua_agent/tests/training/test_training_runner.py src/cmo_lua_agent/tests/training/test_training_runner_integration.py
git commit -m "feat: run persistent multi-generation training"
```

### Task 6: Add restart reconciliation and process supervision

**Files:**
- Create: `src/cmo_lua_agent/training/process.py`
- Modify: `src/cmo_lua_agent/training/runner.py`
- Modify: `src/cmo_lua_agent/training/runtime.py`
- Test: `src/cmo_lua_agent/tests/training/test_training_recovery.py`
- Test: `src/cmo_lua_agent/tests/training/test_training_process.py`

**Interfaces:**
- Produces: `TrainingProcessManager.start(workflow_id)`, `is_running(workflow_id)`, and `restart(workflow_id)`.
- Produces CLI module invocation: `python -m cmo_lua_agent.training.runtime run --project-root ... --workflow-id ...`.

- [ ] **Step 1: Write crash-injection tests at PREPARE, PREVIEW, EXECUTE, completed Worker, summary, and Phase 8 boundaries**

Each test persists the fake driver truth, constructs a new Runner instance, calls `reconcile`, and asserts the completed external action is not repeated.

- [ ] **Step 2: Implement reconciliation from Campaign truth**

Training state is a projection: when it conflicts with CampaignStore or generation artifacts, Campaign truth wins and a `reconciled` journal event records the change.

- [ ] **Step 3: Implement hidden process launch and workflow PID metadata**

Use `subprocess.Popen` with the active Python executable, redirected `runner.log`, `stdin=DEVNULL`, and Windows `CREATE_NO_WINDOW` when available. Tests inject a fake launcher.

- [ ] **Step 4: Run recovery tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/training/test_training_recovery.py src/cmo_lua_agent/tests/training/test_training_process.py -q
```

- [ ] **Step 5: Commit Task 6**

```powershell
git add src/cmo_lua_agent/training/process.py src/cmo_lua_agent/training/runner.py src/cmo_lua_agent/training/runtime.py src/cmo_lua_agent/tests/training/test_training_recovery.py src/cmo_lua_agent/tests/training/test_training_process.py
git commit -m "feat: recover and supervise training runners"
```

### Task 7: Freeze Workflow Experience inputs and run Phase 8 once

**Files:**
- Modify: `src/cmo_lua_agent/learning/skill_evolution/workflow.py`
- Modify: `src/cmo_lua_agent/evolution/production_phase_adapters.py`
- Create: `src/cmo_lua_agent/training/phase8.py`
- Create: `src/cmo_lua_agent/training/reporting.py`
- Modify: `src/cmo_lua_agent/training/runner.py`
- Test: `src/cmo_lua_agent/tests/training/test_training_phase8.py`
- Test: `src/cmo_lua_agent/tests/learning/test_phase8_skill_evolution_workflow.py`

**Interfaces:**
- Extends: `SkillEvolutionWorkflow.run(..., experience_ids: Collection[str] | None = None)`; `None` preserves old all-record behavior.
- Produces: `TrainingPhase8Coordinator.freeze_inputs()` and `run()`.
- Produces: `TrainingReportWriter.write_training_report()` and `write_skill_report()`.

- [ ] **Step 1: Write filtered Phase 8 input tests**

Create records from two Workflow optimization ID prefixes, pass only one Workflow’s IDs, and assert aggregation-manifest contains only the selected records. Assert the legacy call with no filter still reads all records.

- [ ] **Step 2: Implement optional Experience ID filtering**

Unknown requested IDs raise `phase8_experience_missing`; excluded records remain excluded. The final manifest lists ID plus original record path and is reused on restart.

- [ ] **Step 3: Implement final coordinator and idempotent Phase 8 state**

After the last generation, collect `phase7.experience_ids` from official generation results, atomically write `phase8/experience-input.json`, then run exactly one `phase8_run_id=<workflow_id>_phase8`. Existing completed result is reused.

- [ ] **Step 4: Implement deterministic reports**

`training-report.md` contains request, generation statuses, Champion/score summaries by artifact reference, failures, repairs, Phase 8 result, and final status. `skill-generation-report.md` lists the frozen Experience IDs and pending skill packages.

- [ ] **Step 5: Run Phase 8 tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/training/test_training_phase8.py src/cmo_lua_agent/tests/learning/test_phase8_skill_evolution_workflow.py -q
```

- [ ] **Step 6: Commit Task 7**

```powershell
git add src/cmo_lua_agent/learning/skill_evolution/workflow.py src/cmo_lua_agent/evolution/production_phase_adapters.py src/cmo_lua_agent/training/phase8.py src/cmo_lua_agent/training/reporting.py src/cmo_lua_agent/training/runner.py src/cmo_lua_agent/tests/training/test_training_phase8.py src/cmo_lua_agent/tests/learning/test_phase8_skill_evolution_workflow.py
git commit -m "feat: aggregate training experience in final phase 8"
```

### Task 8: Expose START/STATUS/PAUSE/RESUME/STOP to the Main Agent

**Files:**
- Create: `src/cmo_lua_agent/tools/training_tools.py`
- Modify: `src/cmo_lua_agent/tools/tool_base/factory.py`
- Modify: `src/cmo_lua_agent/main.py`
- Test: `src/cmo_lua_agent/tests/tools/test_training_tool_profile.py`
- Modify: `src/cmo_lua_agent/tests/test_main.py`

**Interfaces:**
- Produces tools: `start_training`, `inspect_training`, `control_training`.
- Adds chat profile: `training`.
- START schema requires `input_path`, `objective`, `generation_count`; workflow ID and campaign ID are generated deterministically enough for collision-free local use.

- [ ] **Step 1: Write failing profile and tool tests**

Assert exactly the three high-level tools are exposed, none has `requires_approval=True`, START persists request before launch, STATUS performs no LLM work, and control accepts only pause/resume/stop.

- [ ] **Step 2: Implement `TrainingService` orchestration facade**

Add `src/cmo_lua_agent/training/service.py` with `start`, `inspect`, and `control`. `start` validates input and request, writes state, records the Git baseline, launches the Runner, and returns immediately.

- [ ] **Step 3: Register the training profile and update the system prompt**

The prompt tells the Agent to call START directly when path, objective, and generation count are present; never ask for input package ID, budget-file, Skill authorization, CMO authorization, per-generation confirmation, or final Phase 8 confirmation.

- [ ] **Step 4: Run profile and main assembly tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/tools/test_training_tool_profile.py src/cmo_lua_agent/tests/test_main.py -q
```

- [ ] **Step 5: Commit Task 8**

```powershell
git add src/cmo_lua_agent/training/service.py src/cmo_lua_agent/tools/training_tools.py src/cmo_lua_agent/tools/tool_base/factory.py src/cmo_lua_agent/main.py src/cmo_lua_agent/tests/tools/test_training_tool_profile.py src/cmo_lua_agent/tests/test_main.py
git commit -m "feat: expose training harness agent tools"
```

### Task 9: Make AgentLoop result-driven with progress-based loop protection

**Files:**
- Modify: `src/cmo_lua_agent/orchestration/agent_loop.py`
- Modify: `src/cmo_lua_agent/llm/agent_loop_json_client.py`
- Modify: `src/cmo_lua_agent/orchestration/ui_state.py`
- Modify: `src/cmo_lua_agent/cli/terminal_display.py`
- Modify: `src/cmo_lua_agent/main.py`
- Modify: `src/cmo_lua_agent/tests/test_agent_loop.py`
- Modify: `src/cmo_lua_agent/tests/test_agent_loop_guards.py`
- Modify: `src/cmo_lua_agent/tests/llm/test_agent_loop_json_client.py`

**Interfaces:**
- Changes: `AgentLoop(..., max_turns: int | None = None)`; `None` is the production default and means no count termination.
- Adds progress signature over tool name, normalized arguments, result/error, and history revision.

- [ ] **Step 1: Replace the turn-budget test with a result-driven test**

Feed more than twelve productive tool rounds followed by final text; assert completion and no NEEDS_INPUT event caused by turn count.

- [ ] **Step 2: Add no-progress signature tests**

Three identical failed calls with identical state revision must stop with a diagnostic result. A changed argument, changed result, or new artifact revision resets the no-progress streak.

- [ ] **Step 3: Replace the bounded `for` loop with `while True`**

Keep the monotonically increasing turn counter for display/statistics. Remove fixed-turn failure text and omit `/max` from UI when max is `None`.

- [ ] **Step 4: Preserve the bounded JSON sub-agent adapter only as an opt-in compatibility parameter**

`AgentLoopJsonClient(max_turns=None)` uses the same result-driven default. Tests that explicitly pass an integer retain the old compatibility behavior until their callers are migrated.

- [ ] **Step 5: Run AgentLoop and terminal tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/test_agent_loop.py src/cmo_lua_agent/tests/test_agent_loop_guards.py src/cmo_lua_agent/tests/llm/test_agent_loop_json_client.py src/cmo_lua_agent/tests/cli -q
```

- [ ] **Step 6: Commit Task 9**

```powershell
git add src/cmo_lua_agent/orchestration/agent_loop.py src/cmo_lua_agent/llm/agent_loop_json_client.py src/cmo_lua_agent/orchestration/ui_state.py src/cmo_lua_agent/cli/terminal_display.py src/cmo_lua_agent/main.py src/cmo_lua_agent/tests
git commit -m "feat: make agent loop result driven"
```

### Task 10: Upgrade ChatSessionStore and add context compaction

**Files:**
- Modify: `src/cmo_lua_agent/orchestration/chat_session_store.py`
- Create: `src/cmo_lua_agent/orchestration/context_manager.py`
- Modify: `src/cmo_lua_agent/cli/chat.py`
- Test: `src/cmo_lua_agent/tests/orchestration/test_chat_session_store.py`
- Create: `src/cmo_lua_agent/tests/orchestration/test_context_manager.py`
- Modify: `src/cmo_lua_agent/tests/cli/test_chat_sessions.py`

**Interfaces:**
- Migrates lazily from `sessions/<session_id>.json` to `sessions/<session_id>/session.json`, `messages.jsonl`, `summary.json`, and `tool-results/`.
- Produces: `ContextManager.build(session, training_state=None, training_summary=None, repair_context=None) -> list[dict[str, Any]]`.

- [ ] **Step 1: Preserve and extend the existing uncommitted session tests**

Add tests for old JSON lazy migration, append-only messages, active workflow metadata, large tool-result externalization, and lossless full-history reload.

- [ ] **Step 2: Implement directory sessions with atomic metadata and JSONL messages**

Old files remain readable. First mutation writes the new directory form; it does not delete the old file until the new representation is fully written.

- [ ] **Step 3: Implement size-driven ContextManager**

The active request contains system rules, current user message, session goal/workflow ID, Training state/summary, rolling summary, recent relevant messages, and pinned Repair context. It externalizes or omits re-readable tool bodies before summarizing completed history; it never truncates by a fixed turn count.

- [ ] **Step 4: Wire context building without changing persisted full history**

`run_chat` continues saving all messages. Only the list passed to `AgentLoop.run` is compacted, then new messages are merged back by stable position/ID.

- [ ] **Step 5: Run session and chat tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/orchestration/test_chat_session_store.py src/cmo_lua_agent/tests/orchestration/test_context_manager.py src/cmo_lua_agent/tests/cli/test_chat_sessions.py src/cmo_lua_agent/tests/test_main.py -q
```

- [ ] **Step 6: Commit Task 10 including the existing session work**

```powershell
git add src/cmo_lua_agent/orchestration/chat_session_store.py src/cmo_lua_agent/orchestration/context_manager.py src/cmo_lua_agent/cli/chat.py src/cmo_lua_agent/main.py src/cmo_lua_agent/tests/orchestration src/cmo_lua_agent/tests/cli/test_chat_sessions.py src/cmo_lua_agent/tests/test_main.py
git commit -m "feat: persist and compact agent sessions"
```

### Task 11: Classify failures and invoke automatic code repair

**Files:**
- Create: `src/cmo_lua_agent/training/failures.py`
- Create: `src/cmo_lua_agent/training/repair.py`
- Modify: `src/cmo_lua_agent/training/runner.py`
- Modify: `src/cmo_lua_agent/training/service.py`
- Test: `src/cmo_lua_agent/tests/training/test_failure_classification.py`
- Test: `src/cmo_lua_agent/tests/training/test_code_repair.py`

**Interfaces:**
- Produces: `FailureKind` values TRANSIENT, BUSINESS, INPUT, CODE, UNKNOWN.
- Produces: `FailureClassifier.classify(exception, artifacts) -> FailureRecord`.
- Produces: `CodeRepairCoordinator.repair(record) -> RepairResult` with injected command runner, test runner, and Git client.

- [ ] **Step 1: Write deterministic classification tests**

Network/timeout errors map to TRANSIENT, known Candidate outcomes to BUSINESS, missing/invalid ScenarioIR to INPUT, Python traceback/import/state-machine failures to CODE, and ambiguous text to UNKNOWN.

- [ ] **Step 2: Write a temporary-Git integration test for successful repair**

The fake repair command changes one Python file and adds a regression test. The coordinator requires the targeted test to fail before repair and pass afterward, runs impacted tests and `git diff --check`, commits, pushes through an injected fake remote, updates `last_good_commit`, and requests a Replacement Runner.

- [ ] **Step 3: Write no-progress rollback tests**

Two repair observations with the same error signature, hypothesis, diff, and test result constitute no progress. The coordinator restores tracked code to the recorded baseline commit, retains `runs/training`, writes `code-repair-report.md`, and returns FAILED. There is no fixed repair-attempt counter.

- [ ] **Step 4: Implement the Codex CLI backend behind an injectable protocol**

The production command uses the installed `codex` executable in non-interactive execution mode with the project root and a prompt containing only FailureRecord, relevant file paths, test command, and required modification-log format. Tests never invoke the real CLI.

- [ ] **Step 5: Implement Git baseline/commit/push rules**

START records and pushes the current commit without requiring a clean tree. Repair commits stage only files reported by the repair result; `runs/`, CMO artifacts, temporary files, and unrelated dirty files are excluded. Push failure is recorded and retried as TRANSIENT; it is not reported as success.

- [ ] **Step 6: Wire Runner failure handling and Replacement Runner handoff**

TRANSIENT waits/retries after state reconciliation, BUSINESS uses existing candidate repair/resume behavior, INPUT enters WAITING_USER, CODE enters REPAIRING, UNKNOWN is diagnosed and only becomes CODE with failing-test evidence.

- [ ] **Step 7: Run repair tests**

```powershell
python -m pytest src/cmo_lua_agent/tests/training/test_failure_classification.py src/cmo_lua_agent/tests/training/test_code_repair.py -q
```

- [ ] **Step 8: Commit Task 11**

```powershell
git add src/cmo_lua_agent/training/failures.py src/cmo_lua_agent/training/repair.py src/cmo_lua_agent/training/runner.py src/cmo_lua_agent/training/service.py src/cmo_lua_agent/tests/training/test_failure_classification.py src/cmo_lua_agent/tests/training/test_code_repair.py
git commit -m "feat: repair training code failures automatically"
```

### Task 12: End-to-end acceptance and Legacy quarantine

**Files:**
- Create: `scripts/run_training_workflow.py`
- Modify: `src/cmo_lua_agent/evolution/auto_campaign_tools.py`
- Modify: `src/cmo_lua_agent/evolution/campaign_orchestrator.py`
- Create: `src/cmo_lua_agent/tests/training/test_training_acceptance.py`
- Modify: `docs/plans/2026-08-08-codex-training-loop-harness-design.md`

**Interfaces:**
- Produces CLI commands: `start`, `run`, `status`, `pause`, `resume`, `stop`.
- Marks legacy modules in docstrings and prevents new production imports; does not delete them until reference and behavior checks pass.

- [ ] **Step 1: Add fake three-generation acceptance**

Invoke the CLI/service with a ScenarioIR path and objective, assert automatic prepare/preview/execute, query progress mid-run, restart, complete three generations, freeze Workflow Experience IDs, run Phase 8 once, and emit all reports.

- [ ] **Step 2: Add old manual single-generation characterization**

Run the existing manual CLI with fake dependencies and assert its budget-file, preview, confirm-CMO, inspect, per-generation Phase 8 semantics, and artifact layout remain unchanged.

- [ ] **Step 3: Mark legacy code without deleting live references**

Add module deprecation comments and an `rg`-based test or documented check. Delete a legacy module only if `rg` shows no production import and its unique behavior is covered by the new Harness; otherwise leave it quarantined for a later commit.

- [ ] **Step 4: Run the complete suite in py313**

```powershell
python -m pytest -q
git diff --check
```

- [ ] **Step 5: Run non-CMO CLI smoke tests**

```powershell
python scripts/run_training_workflow.py --help
python -m cmo_lua_agent.main chat --help
python scripts/run_manual_campaign_generation.py --help
```

- [ ] **Step 6: Run real smoke gates in order when CMO is available**

1. Existing manual single generation.
2. New Harness one generation.
3. New Harness two generations.
4. Kill/restart Runner and resume.
5. New Harness seven generations.

Record commands and artifact paths in `training-report.md`. A missing CMO runtime is reported as an unexecuted external acceptance gate, never as a passing test.

- [ ] **Step 7: Commit Task 12**

```powershell
git add scripts/run_training_workflow.py src/cmo_lua_agent/evolution/auto_campaign_tools.py src/cmo_lua_agent/evolution/campaign_orchestrator.py src/cmo_lua_agent/tests/training/test_training_acceptance.py docs/plans/2026-08-08-codex-training-loop-harness-design.md
git commit -m "feat: complete codex training loop harness"
```

## Final Verification

- [ ] `python -m pytest -q` reports zero failures in the activated `py313` environment.
- [ ] `git diff --check` reports no whitespace errors.
- [ ] `rg -n "max_turns=12|max_turns = 12" src/cmo_lua_agent` finds no production AgentLoop cap.
- [ ] Training profile tools contain no `requires_approval=True`.
- [ ] Fake three-generation acceptance records exactly one final Phase 8.
- [ ] Existing manual Campaign tests remain green.
- [ ] Restart tests prove Campaign artifacts override stale Training state.
- [ ] Repair integration proves regression failure, repair pass, isolated commit/push, Replacement Runner, and no-progress rollback.
- [ ] Git status is reviewed so unrelated user changes remain untouched.
