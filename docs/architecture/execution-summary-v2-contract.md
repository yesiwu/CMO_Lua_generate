# Execution Summary v2 Contract

`execution-summary.json` is the only authoritative machine interface for a
formal CMO native score. It is written by CmoBatchRunner after the BatchRunner
has completed its result artifacts. Python consumers validate this document;
they never infer a score from SQLite, CSV, display names, unit losses, or a
minimum/intermediate score.

## Official score

`official_score` uses a stable score-side identity:

```json
{
  "stable_side_id": "red",
  "cmo_side_id": "red",
  "display_name": "红方",
  "initial": 0,
  "final": 35,
  "delta": 35,
  "status": "VALID",
  "score_event_chain_status": "VALID"
}
```

`display_name` is presentation-only. A missing or mismatched exact CMO side
identifier is `UNSCORABLE`; there is no display-name fallback.

For a valid score, `initial + sum(score_events[].delta) == final`. Each event
has a stable `native_score/...` rule ID and its original CMO rule name. A
nonzero final score without a complete event chain is unscorable.

## Runtime execution evidence

The optional `runtime_execution` object is a separate execution-fidelity
contract. It does not alter the official native score.

```json
{
  "simulation_start_time": "2026-07-29T00:00:00.0000000Z",
  "simulation_end_time": "2026-07-29T00:03:01.0000000Z",
  "simulation_elapsed_seconds": 181,
  "stop_reason": "ScenarioEnded",
  "last_runtime_event_time": "2026-07-29T00:03:00.0000000Z",
  "last_scheduled_operation_time": "2026-07-29T00:03:00.0000000Z",
  "scheduled_operation_count": 5,
  "started_operation_count": 5,
  "completed_operation_count": 5,
  "pending_operation_count": 0,
  "lua_bootstrap_seen": true,
  "score_fragment_registered": true,
  "execution_fidelity": "complete"
}
```

BatchRunner derives these values only from controlled Renderer markers and the
CMO simulation clock. When a marker is absent, an operation remains pending;
it is never treated as complete. `execution_fidelity` is `partial` when any
planned tactical operation is pending, simulation ends before its scheduled
time, bootstrap evidence is absent, or native score registration is absent.

The Phase 3 consumer maps `complete` to the downstream evidence value
`verified` and preserves `partial` as `partial`. This fidelity evidence is not
a fallback score source.
