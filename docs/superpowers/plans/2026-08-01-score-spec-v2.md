# Score Spec v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Add an isolated v2 6v4 scoring contract for cumulative ship damage without changing v1 outcomes or candidate-generation behavior.

**Architecture:** v2 adds a separate ScoreSpec and native Lua instrumentation. Ship damage produces one cumulative award per crossed threshold; destruction only finalizes the remaining value. Process and AAR data remain diagnostic and never modify the CMO side score.

**Tech Stack:** Python 3.13, pytest, existing score compiler, CMO Lua, external CmoBatchRunner summary contract.

## Global Constraints

- Preserve \`baseline/6v4/scenario_score_spec.json\` and v1 artifacts byte-for-byte.
- Do not modify StrategySpec, Patch catalog, candidate quality, ExecutionPlan, or manual-template combat logic.
- No mission points for contact, range entry, accepted attack orders, missile firing, or individual missile hits.
- v1 and v2 results never share a leaderboard or campaign generation.
- Do not start a v2 CMO campaign until BatchRunner produces a valid score-event chain: \`initial + sum(delta) == final\`.

---

## File Structure

- \`baseline/6v4/scenario_score_spec_v2.json\`: immutable v2 source contract.
- \`src/cmo_lua_agent/scoring/models.py\`: typed threshold metadata.
- \`src/cmo_lua_agent/scoring/native_score_compiler.py\`: deterministic v2 compiler support.
- \`src/cmo_lua_agent/generation/system_instrumentation.py\`: idempotent threshold Lua and destruction finalization.
- \`src/cmo_lua_agent/evaluation/phase3_evaluation.py\`: strict v2 score-event validation.
- \`src/cmo_lua_agent/tests/scoring/test_native_score_compiler.py\`: contract/compiler regressions.
- \`src/cmo_lua_agent/tests/generation/test_system_instrumentation.py\`: Lua instrumentation regressions.
- \`src/cmo_lua_agent/tests/evaluation/test_phase3_evaluation.py\`: summary-chain regressions.
- \`baseline/6v4/scored/v2/score-spec-v2-golden-manifest.json\`: v2-only Golden artifact.
- \`docs/architecture/current-state.md\`: activation status.

### Task 1: Define and Parse ScoreSpec v2

**Files:**
- Create: \`baseline/6v4/scenario_score_spec_v2.json\`
- Modify: \`src/cmo_lua_agent/scoring/models.py\`
- Test: \`src/cmo_lua_agent/tests/scoring/test_native_score_compiler.py\`

**Consumes:** existing ScoreSpec parsing.

**Produces:** \`damage_thresholds: tuple[tuple[int, int], ...]\` on a score rule.

- [ ] **Step 1: Write the failing test**

\`\`\`python
def test_v2_score_spec_declares_cumulative_ship_damage_rules() -> None:
    spec = load_score_spec(Path("baseline/6v4/scenario_score_spec_v2.json"))
    cvn = spec.rule_for("mission_score/blue_cvn70")
    assert cvn.damage_thresholds == ((25, 50), (50, 100), (75, 150), (100, 200))
    assert spec.rule_for("mission_score/red_j15_1").damage_thresholds == ()
\`\`\`

- [ ] **Step 2: Verify RED**

Run: \`python -m pytest src/cmo_lua_agent/tests/scoring/test_native_score_compiler.py::test_v2_score_spec_declares_cumulative_ship_damage_rules -q\`

Expected: FAIL because threshold parsing is absent.

- [ ] **Step 3: Implement the minimum source contract and parser**

Use cumulative awards at 25%, 50%, 75%, and 100%. Values must be strictly ascending in threshold, signed consistently with the unit side, and finish at the unit total value. Set:

\`\`\`json
{"unit_id":"blue_cvn70","damage_thresholds":[[25,50],[50,100],[75,150],[100,200]]}
{"unit_id":"blue_cg59","damage_thresholds":[[25,25],[50,50],[75,75],[100,100]]}
{"unit_id":"blue_ddg113_1","damage_thresholds":[[25,19],[50,38],[75,56],[100,75]]}
\`\`\`

Use equivalent values for \`blue_ddg113_2\`, then negative cumulative values for red ships. J-15 stays destruction-only at \`-20\`.

- [ ] **Step 4: Verify GREEN**

Run: \`python -m pytest src/cmo_lua_agent/tests/scoring/test_native_score_compiler.py -q\`

Expected: PASS, including v1 tests.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add baseline/6v4/scenario_score_spec_v2.json src/cmo_lua_agent/scoring/models.py src/cmo_lua_agent/tests/scoring/test_native_score_compiler.py
git commit -m "feat: define v2 cumulative damage score contract"
\`\`\`

### Task 2: Compile and Render Idempotent v2 Mission-Score Lua

**Files:**
- Modify: \`src/cmo_lua_agent/scoring/native_score_compiler.py\`
- Modify: \`src/cmo_lua_agent/generation/system_instrumentation.py\`
- Test: \`src/cmo_lua_agent/tests/scoring/test_native_score_compiler.py\`
- Test: \`src/cmo_lua_agent/tests/generation/test_system_instrumentation.py\`

**Consumes:** parsed threshold rules from Task 1.

**Produces:** v2 Lua which awards threshold deltas once and finalizes destruction without double scoring.

- [ ] **Step 1: Write the failing tests**

\`\`\`python
def test_v2_lua_awards_only_threshold_delta() -> None:
    lua = render_instrumentation(v2_compilation)
    assert "mission_score_damage_poll" in lua
    assert "desired_award - prior_award" in lua
    assert "damage_threshold_percent" in lua

def test_v2_lua_has_no_process_score_rules() -> None:
    lua = render_instrumentation(v2_compilation)
    assert "UnitDetected" not in lua
    assert "weapon_released" not in lua
\`\`\`

- [ ] **Step 2: Verify RED**

Run: \`python -m pytest src/cmo_lua_agent/tests/generation/test_system_instrumentation.py -q\`

Expected: FAIL because the v2 damage monitor does not exist.

- [ ] **Step 3: Implement the monitor**

For v2 rules only, register a five-second \`RegularTime\` Lua entry. It reads a ship damage percentage, selects the highest crossed threshold, loads prior cumulative award from a namespaced KeyValue, applies only \`desired_award - prior_award\`, persists the new cumulative award, and emits \`rule_id\`, \`unit_id\`, \`damage_threshold_percent\`, \`delta\`, \`cumulative_unit_award\`, and \`event_sequence\`.

\`UnitDestroyed\` uses the same state and only applies the delta necessary to reach the 100% cumulative award. Missing-unit lookup cannot infer destruction. Do not emit mission score for contacts, weapon release, range, hit, coordination, or return events.

- [ ] **Step 4: Verify GREEN**

Run: \`python -m pytest src/cmo_lua_agent/tests/generation/test_system_instrumentation.py src/cmo_lua_agent/tests/scoring/test_native_score_compiler.py -q\`

Expected: PASS.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add src/cmo_lua_agent/scoring/native_score_compiler.py src/cmo_lua_agent/generation/system_instrumentation.py src/cmo_lua_agent/tests/scoring/test_native_score_compiler.py src/cmo_lua_agent/tests/generation/test_system_instrumentation.py
git commit -m "feat: render idempotent v2 damage score instrumentation"
\`\`\`

### Task 3: Make Phase 3 Reject Malformed v2 Evidence

**Files:**
- Modify: \`src/cmo_lua_agent/evaluation/phase3_evaluation.py\`
- Test: \`src/cmo_lua_agent/tests/evaluation/test_phase3_evaluation.py\`

**Consumes:** \`execution-summary.json\` and compiled v2 score rules.

**Produces:** scoreable v2 outcomes only when official final score and all threshold events reconcile.

- [ ] **Step 1: Write the failing tests**

\`\`\`python
def test_v2_event_chain_accepts_cumulative_damage_score(tmp_path: Path) -> None:
    result = evaluate_summary(tmp_path, summary_with_v2_events())
    assert result.native_snapshot.final_score == 100
    assert result.score_events[0].rule_id == "mission_score/blue_cg59"

def test_v2_duplicate_threshold_is_unscoreable(tmp_path: Path) -> None:
    result = evaluate_summary(tmp_path, summary_with_duplicate_v2_threshold())
    assert result.native_snapshot.scoreable is False
\`\`\`

- [ ] **Step 2: Verify RED**

Run: \`python -m pytest src/cmo_lua_agent/tests/evaluation/test_phase3_evaluation.py -q\`

Expected: FAIL because threshold metadata is not enforced.

- [ ] **Step 3: Implement strict event parsing**

Require v2 event fields \`rule_id\`, \`unit_id\`, \`delta\`, \`score_after\`, \`event_sequence\`, \`damage_threshold_percent\`, and \`cumulative_unit_award\`. Reject duplicated \`(rule_id, threshold)\`, non-monotonic cumulative awards, invalid thresholds, or any chain not equal to \`official_score.final - initial\`. Preserve v1 parsing unchanged.

Process metrics remain diagnostic and cannot enter \`RewardBreakdown\` or \`native_score\`.

- [ ] **Step 4: Verify GREEN**

Run: \`python -m pytest src/cmo_lua_agent/tests/evaluation/test_phase3_evaluation.py -q\`

Expected: PASS.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add src/cmo_lua_agent/evaluation/phase3_evaluation.py src/cmo_lua_agent/tests/evaluation/test_phase3_evaluation.py
git commit -m "feat: validate v2 official score event chains"
\`\`\`

### Task 4: Establish v2 Golden Isolation and Activation Gate

**Files:**
- Create: \`baseline/6v4/scored/v2/score-spec-v2-golden-manifest.json\`
- Modify: \`src/cmo_lua_agent/tests/scoring/test_6v4_score_baseline.py\`
- Modify: \`docs/architecture/current-state.md\`

**Consumes:** v2 compiler and instrumentation.

**Produces:** stable v2 Golden artifacts without changing v1, plus explicit real-CMO activation criteria.

- [ ] **Step 1: Write the failing Golden test**

\`\`\`python
def test_v2_golden_is_stable_and_does_not_change_v1_artifacts() -> None:
    v1_before = Path("baseline/6v4/native_score_fragment.lua").read_bytes()
    result = build_v2_score_golden()
    assert result.manifest["score_spec_schema_version"] == "2.0.0"
    assert Path("baseline/6v4/native_score_fragment.lua").read_bytes() == v1_before
\`\`\`

- [ ] **Step 2: Verify RED**

Run: \`python -m pytest src/cmo_lua_agent/tests/scoring/test_6v4_score_baseline.py -q\`

Expected: FAIL because no v2 Golden output exists.

- [ ] **Step 3: Implement v2 Golden generation**

Write only below \`baseline/6v4/scored/v2/\`. Record ScoreSpec checksum, compiled Lua checksum, generation version, and \`comparison_eligible=false\` against v1 results.

- [ ] **Step 4: Update current-state documentation**

Record that v2 engineering exists, v1 history remains immutable, process/AAR metrics do not rank candidates, and real v2 CMO use is blocked until BatchRunner emits a complete official score-event chain.

- [ ] **Step 5: Verify full regression**

\`\`\`powershell
python -m compileall src\cmo_lua_agent
python -m pytest src\cmo_lua_agent\tests\scoring -q
python -m pytest src\cmo_lua_agent\tests\evaluation -q
python -m pytest src\cmo_lua_agent\tests\generation -q
python -m pytest src\cmo_lua_agent\tests -q
git diff --check
\`\`\`

Expected: PASS. No CMO or LLM call occurs.

- [ ] **Step 6: Commit**

\`\`\`powershell
git add baseline/6v4/scored/v2 src/cmo_lua_agent/tests/scoring/test_6v4_score_baseline.py docs/architecture/current-state.md
git commit -m "test: establish v2 cumulative damage score golden"
\`\`\`

## External Acceptance Gate

Deploy matching external CmoBatchRunner extraction, then run one explicitly approved v2 CMO slot. It must produce \`official_score.status=VALID\`, a complete event chain, unique threshold events, and \`initial + sum(delta) == final\`. Until that passes, do not create a v2 Campaign or compare v2 against v1.

