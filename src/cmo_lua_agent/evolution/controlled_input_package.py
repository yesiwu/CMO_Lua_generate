"""Load and freeze the controlled 6v4 Phase 9C input package."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import subprocess
from typing import Any

from cmo_lua_agent.contract.baseline_strategy_builder import BaselineStrategyBuilder
from cmo_lua_agent.contract.strategy_models import BaselineStrategy
from cmo_lua_agent.evolution.baseline_failure_profile import (
    BaselineFailureProfileBuilder,
)
from cmo_lua_agent.evolution.production_assets import ControlledScenarioAssetRegistry
from cmo_lua_agent.evolution.production_models import (
    ControlledScenarioAsset,
    canonical_checksum,
)
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
from cmo_lua_agent.generation.manual_lua_template import ManualLuaTemplatePackage
from cmo_lua_agent.generation.scored_lua_assembly import SCORED_RENDERER_VERSION
from cmo_lua_agent.optimization.bootstrap_skill_loader import BootstrapSkillLoader
from cmo_lua_agent.scoring.baseline import compile_score_baseline


@dataclass(frozen=True, slots=True)
class ControlledCampaignInputPackage:
    package_id: str
    scenario: Any
    baseline: Any
    native_score_compilation: Any
    runtime: LuaRuntimeProfile
    renderer_version: str
    bootstrap: Any
    scenario_asset: ControlledScenarioAsset
    baseline_failure_profile: Any | None
    allowed_strategy_paths: tuple[str, ...]
    diversity_dimensions: tuple[str, ...]
    checksums: dict[str, str]
    git_commit: str
    working_tree_dirty: bool
    diff_checksum: str | None
    package_checksum: str
    scenario_ir_checksum: str = ""
    baseline_derivation_manifest: Any | None = None
    manual_template_root: Path | None = None
    scenario_ir_path: Path | None = None


class ControlledCampaignInputPackageLoader:
    """加载并固定 Campaign 所需的场景、基线与运行契约输入包。

ProductionEvolutionCampaignService 在 prepare/load 时调用它；加载结果供 Preview 与
Executor 共用，避免各阶段各自读取不同版本的外部输入。
    """
    PACKAGE_ID = "red_blue_6v4_liaoning_v1"
    ASSET_ID = "red_blue_6v4_liaoning_scen_v1"
    _ALLOWED_PATHS = (
        "/attacks/0/target_ids/0",
        "/attacks/0/delay_seconds",
        "/attacks/0/fire_quantity",
        "/attacks/1/target_ids/0",
        "/attacks/1/delay_seconds",
        "/attacks/1/fire_quantity",
        "/attacks/2/target_ids/0",
        "/attacks/2/delay_seconds",
        "/attacks/2/fire_quantity",
        "/attacks/3/fire_quantity",
        "/attacks/4/target_ids/0",
        "/attacks/4/fire_quantity",
        "/sorties/0/route/0/latitude",
        "/sorties/0/route/0/longitude",
        "/sorties/1/route/0/latitude",
        "/sorties/1/route/0/longitude",
        "/sorties/1/target_id",
        "/sorties/0/air_tactics/launch_delay_seconds",
        "/sorties/0/air_tactics/ingress_altitude_m",
        "/sorties/0/air_tactics/popup_altitude_m",
        "/sorties/0/air_tactics/popup_range_nm",
        "/sorties/0/air_tactics/attack_range_nm",
        "/sorties/1/air_tactics/launch_delay_seconds",
        "/sorties/1/air_tactics/ingress_altitude_m",
        "/sorties/1/air_tactics/popup_altitude_m",
        "/sorties/1/air_tactics/popup_range_nm",
        "/sorties/1/air_tactics/attack_range_nm",
    )

    def __init__(
        self,
        *,
        project_root: Path,
        registry_path: Path | None = None,
        verification_root: Path | None = None,
        baseline_result_root: Path | None = None,
    ) -> None:
        self.root = Path(project_root).resolve()
        self.registry_path = (
            Path(registry_path).resolve()
            if registry_path is not None
            else self.root / "config" / "cmo-assets.local.json"
        )
        self.verification_root = (
            Path(verification_root).resolve()
            if verification_root is not None
            else self.root / "data" / "asset-verifications"
        )
        self.baseline_result_root = (
            Path(baseline_result_root).resolve()
            if baseline_result_root is not None
            else None
        )

    def load(self, package_id: str) -> ControlledCampaignInputPackage:
        scenario_ir_path = self._scenario_ir_path(package_id)
        baseline_root = self.root / "baseline" / "6v4"
        paths = {
            "scenario_ir": scenario_ir_path,
            "objectives": baseline_root / "scenario_objectives.json",
            "role_catalog": baseline_root / "unit_role_catalog.json",
            "score_profile": baseline_root / "score_profile.json",
            "score_spec": baseline_root / "scenario_score_spec.json",
            "score_fragment": baseline_root / "native_score_fragment.lua",
        }
        if not all(path.is_file() for path in paths.values()):
            raise ValueError("controlled_input_package_incomplete")
        commit, dirty, diff_checksum = self._git_state()
        scenario_ir = self._load_json(paths["scenario_ir"])
        derived = BaselineStrategyBuilder().build(scenario_ir)
        scenario = derived.scenario
        template_root = baseline_root / "manual-template"
        if not (template_root / "manual_baseline_template.json").is_file():
            raise ValueError("manual_template_renderer_required")
        manual_template = ManualLuaTemplatePackage.load(template_root)
        baseline = BaselineStrategy(
            strategy=derived.strategy,
            source_lua="baseline/6v4/manual-template/manual_baseline_template.lua",
            verified=True,
        )
        # Score-rule unit names must come from the same ScenarioIR-derived
        # definition that the renderer and CMO job execute.
        score = compile_score_baseline(
            baseline_root,
            scenario=scenario,
        ).compilation
        runtime = LuaRuntimeProfile("cmo_naval_air_anti_surface_scored", "2.0.0")
        bootstrap = BootstrapSkillLoader(self.root).load(
            "src/cmo_lua_agent/skills/bootstrap/cmo_naval_air_strategy_proposal_v1.md"
        )
        asset = ControlledScenarioAssetRegistry(
            registry_path=self.registry_path,
            verification_root=self.verification_root,
        ).load_verified(self.ASSET_ID)
        failure_profile = (
            BaselineFailureProfileBuilder().build(self.baseline_result_root)
            if self.baseline_result_root is not None
            else None
        )
        checksums = {
            name: self._sha(path) for name, path in paths.items()
        }
        checksums.update({
            "scenario_ir": derived.manifest.scenario_ir_checksum,
            "scenario_definition_derived": derived.manifest.scenario_definition_checksum,
            "baseline_strategy_derived": derived.manifest.baseline_strategy_checksum,
            "baseline_derivation_mapping": derived.manifest.mapping_checksum,
            "score_spec_compiled": score.score_spec_checksum,
            "score_fragment_compiled": score.fragment_checksum,
            "runtime": canonical_checksum(runtime.to_dict()),
            "renderer": canonical_checksum(SCORED_RENDERER_VERSION),
            "bootstrap": bootstrap.checksum,
            "scenario_asset": asset.sha256,
        })
        allowed_paths = self._ALLOWED_PATHS
        mapped_paths = {
            slot.strategy_path
            for slot in manual_template.slots.values()
            if slot.strategy_path is not None
        }
        allowed_paths = tuple(path for path in self._ALLOWED_PATHS if path in mapped_paths)
        if not allowed_paths:
            raise ValueError("manual_template_no_executable_strategy_paths")
        checksums["manual_template"] = self._sha(template_root / "manual_baseline_template.lua")
        checksums["manual_template_mapping"] = self._sha(template_root / "manual_baseline_template.json")
        identity = {
            "package_id": package_id,
            "checksums": checksums,
            "git_commit": commit,
            "working_tree_dirty": dirty,
            "diff_checksum": diff_checksum,
            "allowed_strategy_paths": list(allowed_paths),
        }
        return ControlledCampaignInputPackage(
            package_id=package_id,
            scenario=scenario,
            baseline=baseline,
            native_score_compilation=score,
            runtime=runtime,
            renderer_version=SCORED_RENDERER_VERSION,
            bootstrap=bootstrap,
            scenario_asset=asset,
            baseline_failure_profile=failure_profile,
            allowed_strategy_paths=allowed_paths,
            diversity_dimensions=(
                "target_assignment",
                "attack_timing",
                "fire_quantity",
                "air_route",
            ),
            checksums=checksums,
            git_commit=commit,
            working_tree_dirty=dirty,
            diff_checksum=diff_checksum,
            package_checksum=canonical_checksum(identity),
            scenario_ir_checksum=derived.manifest.scenario_ir_checksum,
            baseline_derivation_manifest=derived.manifest.to_dict(),
            manual_template_root=template_root,
            scenario_ir_path=scenario_ir_path,
        )

    def _scenario_ir_path(self, package_id: str) -> Path:
        if package_id == self.PACKAGE_ID:
            return self.root / "json_data" / "6v4ScenarioIR.json"
        candidate = Path(package_id)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        candidate = candidate.resolve()
        if not candidate.is_file() or candidate.suffix.lower() != ".json":
            raise ValueError("unknown_campaign_input_package")
        return candidate

    def _git_state(self) -> tuple[str, bool, str | None]:
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            diff = subprocess.run(
                ["git", "diff", "--binary", "HEAD"],
                cwd=self.root,
                check=True,
                capture_output=True,
            ).stdout
            status = subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=self.root,
                check=True,
                capture_output=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError("git_revision_unavailable") from exc
        dirty = bool(diff or status)
        fingerprint = b"diff\0" + diff + b"\0status\0" + status
        return commit, dirty, sha256(fingerprint).hexdigest() if dirty else None

    @staticmethod
    def _sha(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        import json

        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("scenario_ir_invalid")
        return value
