# Score Spec v2 Design

## Goal

Add an auditable v2 scoring contract for the 6v4 campaign without changing v1
history, existing campaigns, candidate generation, or CMO execution flow.

The official mission score must continue to represent battlefield outcome. Process
signals and AAR-derived measurements remain diagnostic data and cannot change the
official score or choose a champion.

## Preconditions

The current BatchRunner output must first provide a complete, internally
consistent `score_events` chain in `execution-summary.json`. A v2 run is
unscoreable when:

```text
initial + sum(score_events.delta) != final
```

No v2 campaign, leaderboard, or historical-result migration is part of this
work until that condition is verified against a real CMO result.

## Contract Versioning

- Keep `baseline/6v4/scenario_score_spec.json` as immutable v1.
- Add a new v2 ScoreSpec and compilation artifact with independent checksums.
- v1 and v2 outcomes must never be placed in the same leaderboard or compared as
  a single optimization generation.

## Mission Score

Mission score uses each platform's fixed total value. Enemy damage increases the
red score; red damage decreases it. A platform can never contribute more than its
absolute total value over its whole lifecycle.

| Platform | Total score |
| --- | ---: |
| Blue CVN-70 | +200 |
| Blue CG-59 | +100 |
| Each Blue DDG-113 | +75 |
| Red Liaoning | -200 |
| Red 055 Nanchang | -100 |
| Each Red 052D | -75 |
| Each Red J-15 | -20 on destruction only |

For ships, v2 applies cumulative awards at 25%, 50%, 75%, and 100% damage. The
award at a threshold is the difference between the desired cumulative value and
the already-issued value. `UnitDestroyed` finalizes the amount necessary to
reach the 100% cumulative value; it cannot duplicate earlier damage awards.

The first implementation uses deterministic threshold crossings rather than
per-second proportional score updates. It persists issued thresholds per unit so
that polling, retries, and CMO event replay cannot award a threshold twice.

## Process And AAR Data

The following are retained as facts outside the official score:

- contact acquired;
- attack range reached;
- attack order accepted;
- confirmed weapon release;
- aircraft return after weapon release;
- multi-platform release timing;
- weapon release/hit counts, damage value, and time-to-first-damage.

They may populate `process_metrics` and AAR data in execution artifacts. They
must not add official points, serve as a primary rank key, or reward firing a
weapon without an attributable effect.

## Explicit Exclusions

- No points for launching missiles, obtaining a contact, entering an area, or an
  accepted attack command.
- No direct score for individual missile hits.
- No continuous five-second `ScenEdit_SetScore` calculation in the first v2
  release.
- No change to StrategySpec, Candidate Patch catalog, ExecutionPlan, candidate
  quality gates, or the active manual Lua baseline.
- No change to v1 artifacts, historical outcomes, or current campaign results.

## Implementation Boundaries

The implementation will touch only the score contract/compiler, score Lua
instrumentation, BatchRunner summary extraction, Phase 3 contract validation,
and focused Golden/regression tests. Candidate proposals remain unchanged.

Each emitted score event must contain a stable rule ID, source unit ID, damage
threshold or destruction-finalization marker, delta, cumulative unit award, and
event sequence. Phase 3 remains a verifier and reader of those fields.

## Verification

1. Unit tests prove threshold differences and idempotency.
2. Golden tests compile stable v2 Lua and manifests without touching v1.
3. Phase 3 rejects missing, duplicated, or inconsistent v2 score events.
4. A later, explicitly approved real CMO single-slot run verifies that the
   official score and the event chain agree.

CMO effectiveness validation is not part of the implementation change itself.
