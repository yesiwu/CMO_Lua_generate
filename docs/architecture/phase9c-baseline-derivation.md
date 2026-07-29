# Phase 9C Baseline Derivation

`json_data/6v4ScenarioIR.json` is the only production input for the 6v4
Baseline. `BaselineStrategyBuilder` deterministically derives the
`ScenarioDefinition` and `StrategySpec` for every production Campaign.

`baseline/6v4/generated/` contains Golden and audit outputs only. Production
loaders do not treat those artifacts as inputs.

`baseline/6v4/legacy/` contains the pre-ScenarioIR manual Baseline for
historical Phase 2, Phase 3.2, and Phase 6 reproduction. It is read-only and
not production eligible. A new Campaign must reject an explicit request to use
the legacy Baseline rather than falling back to it.

The real Baseline CMO Golden remains pending deployment of the updated
BatchRunner.
