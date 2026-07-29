"""Load the controlled 6v4 campaign input from ScenarioIR."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.contract.strategy_models import BaselineStrategy, ScenarioDefinition
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.generation.scored_lua_assembly import SCORED_RENDERER_VERSION
from cmo_lua_agent.scoring.baseline import compile_score_baseline


@dataclass(frozen=True, slots=True)
class CampaignInputBundle:
    """The deterministic input bundle for the controlled 6v4 campaign."""

    project_root: Path
    baseline_root: Path
    scenario_ir_path: Path
    baseline_derivation_source_path: Path
    job_config_path: Path
    bootstrap_skill_path: Path
    scenario: ScenarioDefinition
    baseline: BaselineStrategy
    runtime: LuaRuntimeProfile
    score_compilation: Any
    checksums: dict[str, str]


class CampaignInputLoader:
    """Load the production 6v4 input without consulting legacy assets."""

    def load_6v4(
        self,
        *,
        project_root: Path,
        job_config_path: Path,
        baseline_source_path: Path | None = None,
    ) -> CampaignInputBundle:
        root = Path(project_root).resolve()
        baseline_root = root / "baseline" / "6v4"
        if baseline_source_path is not None:
            requested = Path(baseline_source_path).resolve()
            legacy_root = baseline_root / "legacy"
            if requested.is_relative_to(legacy_root):
                raise ValueError("legacy_baseline_not_production_eligible")
            raise ValueError("baseline_source_override_not_allowed")
        scenario_ir_path = root / "json_data" / "6v4ScenarioIR.json"
        bootstrap_path = (
            root
            / "src"
            / "cmo_lua_agent"
            / "skills"
            / "bootstrap"
            / "cmo_naval_air_strategy_proposal_v1.md"
        )
        job_config_path = Path(job_config_path).resolve()
        for path in (scenario_ir_path, bootstrap_path, job_config_path):
            if not path.is_file() or not path.is_relative_to(root):
                raise ValueError("campaign_input_path_invalid")

        scenario_ir = self._load_json(scenario_ir_path)
        derived = BaselineStrategyBuilder().build(scenario_ir)
        scenario = derived.scenario
        baseline = BaselineStrategy(
            strategy=derived.strategy,
            source_lua="json_data/6v4ScenarioIR.json",
            verified=True,
        )
        compilation = compile_score_baseline(
            baseline_root, scenario=scenario
        ).compilation
        runtime = LuaRuntimeProfile("cmo_naval_air_anti_surface_scored", "2.0.0")
        checksums = {
            "scenario_ir": self._sha(scenario_ir_path),
            "scenario_definition_derived": derived.manifest.scenario_definition_checksum,
            "baseline_strategy_derived": derived.manifest.baseline_strategy_checksum,
            "baseline_derivation_mapping": derived.manifest.mapping_checksum,
            "bootstrap": self._sha(bootstrap_path),
            "job_config": self._sha(job_config_path),
            "score_fragment": compilation.fragment_checksum,
            "score_spec": compilation.score_spec_checksum,
            "runtime": f"{runtime.runtime_id}:{runtime.runtime_version}",
            "renderer": SCORED_RENDERER_VERSION,
        }
        return CampaignInputBundle(
            project_root=root,
            baseline_root=baseline_root,
            scenario_ir_path=scenario_ir_path,
            baseline_derivation_source_path=scenario_ir_path,
            job_config_path=job_config_path,
            bootstrap_skill_path=bootstrap_path,
            scenario=scenario,
            baseline=baseline,
            runtime=runtime,
            score_compilation=compilation,
            checksums=checksums,
        )

    @staticmethod
    def _sha(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("scenario_ir_invalid")
        return value
