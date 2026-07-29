"""Phase 9C production composition and its explicitly isolated test variant."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from cmo_lua_agent.evolution.champion_selection import ChampionSelectionPolicy
from cmo_lua_agent.evolution.campaign_store import CampaignStore
from cmo_lua_agent.evolution.control_plane import EvolutionCampaignService
from cmo_lua_agent.evolution.controlled_input_package import (
    ControlledCampaignInputPackageLoader,
)
from cmo_lua_agent.evolution.formal_candidate_evaluator import FormalCandidateEvaluator
from cmo_lua_agent.evolution.models import (
    CampaignBudget,
    CampaignExecutionMode,
    EvolutionCampaignSpec,
)
from cmo_lua_agent.evolution.novelty import CandidateNoveltyValidator
from cmo_lua_agent.evolution.production_executor import ProductionGenerationExecutor
from cmo_lua_agent.evolution.production_knowledge import (
    ProductionKnowledgeSnapshotProvider,
)
from cmo_lua_agent.evolution.production_preview_builder import ProductionPreviewBuilder
from cmo_lua_agent.evolution.production_phase_adapters import (
    ProductionPhase7Adapter,
    ProductionPhase8Adapter,
)
from cmo_lua_agent.evolution.stop_policy import StopPolicy
from cmo_lua_agent.llm.json_client import ClaudeJsonClient
from cmo_lua_agent.optimization.strategy_proposal_agent import StrategyProposalAgent


@dataclass(frozen=True, slots=True)
class ProductionDependencyOverrides:
    """Dependencies available only to the fixture-safe test factory."""

    test_mode: bool
    artifact_provenance: str
    package_loader: object | None = None
    proposal_agent: object | None = None
    candidate_evaluator: object | None = None
    phase7_adapter: object | None = None
    phase8_adapter: object | None = None
    champion_policy: object | None = None
    stop_policy: object | None = None
    synchronous_fake_workers: bool = True
    knowledge_snapshot_provider: object | None = None


class _UnavailableAdapter:
    def __init__(self, phase: str) -> None:
        self._phase = phase

    def run(self, **_: object) -> dict[str, object]:
        raise RuntimeError(f"{self._phase}_production_adapter_not_configured")


class _FixtureChampionPolicy:
    """Test-only scorer that never upgrades fixture evidence to formal evidence."""

    def select(self, *, rolling_baseline, candidates):
        ranked = [
            item
            for item in candidates
            if item.execution_success
            and item.scoreable
            and item.semantic_valid
            and item.official_score is not None
        ]
        best = max(
            ranked,
            key=lambda item: (item.official_score, item.candidate_id),
            default=rolling_baseline,
        )
        return SimpleNamespace(
            best_candidate_id=best.candidate_id,
            selected_champion_id=best.candidate_id,
            selected_score=best.official_score,
            improved=best.candidate_id != rolling_baseline.candidate_id,
            exclusion_reasons={},
        )


class ProductionEvolutionCampaignService:
    """Facade that creates one immutable, package-bound core service per campaign."""

    def __init__(
        self,
        *,
        project_root: Path,
        package_loader: object,
        proposal_agent: object,
        candidate_evaluator: object,
        phase7_adapter: object,
        phase8_adapter: object,
        champion_policy: object | None,
        stop_policy: object,
        synchronous_fake_workers: bool,
        artifact_provenance: str,
        knowledge_snapshot_provider: object | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self._campaigns_root = self.project_root / "runs" / "evolution"
        self._package_loader = package_loader
        self._proposal_agent = proposal_agent
        self._candidate_evaluator = candidate_evaluator
        self._phase7 = phase7_adapter
        self._phase8 = phase8_adapter
        self._champion = champion_policy
        self._stop = stop_policy
        self._synchronous = synchronous_fake_workers
        self.artifact_provenance = artifact_provenance
        self._knowledge = knowledge_snapshot_provider
        self._services: dict[str, EvolutionCampaignService] = {}

    def prepare_campaign_request(
        self,
        *,
        campaign_id: str,
        input_package_id: str,
        generation_objective: str,
        budget: dict[str, object],
        minimum_improvement_delta: int,
        no_improvement_patience: int,
    ) -> dict[str, Any]:
        package = self._package_loader.load(input_package_id)
        runtime_preflight = (
            self._candidate_evaluator.preflight()
            if hasattr(self._candidate_evaluator, "preflight")
            else {"status": "test_fixture"}
        )
        campaign_budget = CampaignBudget(**budget)
        spec = EvolutionCampaignSpec(
            campaign_id=campaign_id,
            scenario_id=package.scenario.scenario_id,
            scenario_ref=input_package_id,
            scenario_checksum=package.checksums["scenario"],
            initial_strategy_ref="baseline/6v4/baseline_strategy.json",
            runtime_contract_checksum=package.checksums["runtime"],
            renderer_contract_checksum=package.checksums["renderer"],
            score_contract_checksum=package.checksums["score_spec_compiled"],
            semantic_contract_checksum=package.package_checksum,
            code_revision=package.git_commit,
            allowed_strategy_paths=package.allowed_strategy_paths,
            generation_objective=generation_objective,
            budget=campaign_budget,
            execution_mode=(
                CampaignExecutionMode.FAKE_FIXTURE
                if self.artifact_provenance == "test_fixture"
                else CampaignExecutionMode.PRODUCTION_CMO
            ),
            minimum_improvement_delta=minimum_improvement_delta,
            no_improvement_patience=no_improvement_patience,
        )
        service = self._build_core(spec, package)
        self._services[campaign_id] = service
        result = service.prepare_campaign(spec)
        CampaignStore(self._campaigns_root / campaign_id).write_input_package_manifest(
            {
                "package_id": package.package_id,
                "package_checksum": package.package_checksum,
                "git_commit": package.git_commit,
                "working_tree_dirty": package.working_tree_dirty,
                "diff_checksum": package.diff_checksum,
                "artifact_provenance": self.artifact_provenance,
                "scenario_asset": package.scenario_asset.to_dict(),
                "runtime_preflight": runtime_preflight,
            }
        )
        return result

    def _build_core(self, spec: EvolutionCampaignSpec, package: object) -> EvolutionCampaignService:
        root_for = lambda campaign_id: self._campaigns_root / campaign_id
        preview = ProductionPreviewBuilder(
            package=package,
            proposal_agent=self._proposal_agent,
            novelty_validator=CandidateNoveltyValidator(),
            campaign_root_provider=root_for,
            knowledge_snapshot_provider=self._knowledge,
        )
        executor = ProductionGenerationExecutor(
            package=package,
            candidate_evaluator=self._candidate_evaluator,
            phase7_adapter=self._phase7,
            phase8_adapter=self._phase8,
            champion_policy=(
                self._champion
                or ChampionSelectionPolicy(
                    minimum_improvement_delta=spec.minimum_improvement_delta
                )
            ),
            stop_policy=self._stop,
            artifact_provenance=self.artifact_provenance,
        )
        return EvolutionCampaignService(
            campaigns_root=self._campaigns_root,
            preview_builder=preview,
            generation_executor=executor,
            synchronous_fake_workers=self._synchronous,
        )

    def _service(self, campaign_id: str) -> EvolutionCampaignService:
        service = self._services.get(campaign_id)
        if service is None:
            raise ValueError("campaign_service_not_loaded")
        return service

    def preview_generation(self, **kwargs: Any):
        return self._service(str(kwargs["campaign_id"])).preview_generation(**kwargs)

    def repair_preview_candidate(self, **kwargs: Any):
        return self._service(str(kwargs["campaign_id"])).repair_preview_candidate(**kwargs)

    def execute_generation(self, **kwargs: Any):
        return self._service(str(kwargs["campaign_id"])).execute_generation(**kwargs)

    def inspect_campaign(self, campaign_id: str):
        return self._service(campaign_id).inspect_campaign(campaign_id)

    def inspect_generation(self, campaign_id: str, generation_index: int):
        return self._service(campaign_id).inspect_generation(campaign_id, generation_index)

    def pause_campaign(self, campaign_id: str):
        return self._service(campaign_id).pause_campaign(campaign_id)

    def resume_campaign(self, campaign_id: str):
        return self._service(campaign_id).resume_campaign(campaign_id)

    def stop_campaign(self, campaign_id: str):
        return self._service(campaign_id).stop_campaign(campaign_id)

    def persist_permission_grant(self, receipt: object, context: dict[str, Any]) -> str:
        campaign_id = str(context["arguments"]["campaign_id"])
        return self._service(campaign_id).persist_permission_grant(receipt, context)


def create_production_evolution_campaign_service(
    *,
    project_root: Path,
    app_config: Any,
    llm_client: Any,
) -> ProductionEvolutionCampaignService:
    """Create the sole production service. It intentionally accepts no overrides."""

    json_client = ClaudeJsonClient(llm_client)
    phase7 = ProductionPhase7Adapter(
        project_root=project_root,
        json_client=json_client,
    )
    phase8 = ProductionPhase8Adapter(
        project_root=project_root,
        json_client=json_client,
        experience_store=phase7.experience_store,
    )
    return ProductionEvolutionCampaignService(
        project_root=project_root,
        package_loader=ControlledCampaignInputPackageLoader(
            project_root=project_root,
            # Phase 9C-1 freezes the current revision and dirty fingerprint
            # into the input package instead of rejecting an otherwise
            # traceable operator worktree before a preview.
            require_clean_worktree=False,
        ),
        proposal_agent=StrategyProposalAgent(json_client),
        candidate_evaluator=FormalCandidateEvaluator(
            json_client=json_client,
            cmo_runner_path=Path(r"C:\CMO\CmoBatchRunner\CmoBatchRunner.exe"),
            cmo_executable_path=Path(r"C:\CMO\Command\bin\Debug\Command.exe"),
        ),
        phase7_adapter=phase7,
        phase8_adapter=phase8,
        champion_policy=None,
        stop_policy=StopPolicy(),
        synchronous_fake_workers=False,
        artifact_provenance="formal_renderer",
        knowledge_snapshot_provider=ProductionKnowledgeSnapshotProvider(
            project_root=project_root,
            experience_store=phase7.experience_store,
        ),
    )


def create_test_evolution_campaign_service(
    *,
    project_root: Path,
    overrides: ProductionDependencyOverrides,
) -> ProductionEvolutionCampaignService:
    if not overrides.test_mode or overrides.artifact_provenance != "test_fixture":
        raise ValueError("test_dependency_overrides_required")
    if overrides.package_loader is None or overrides.proposal_agent is None:
        raise ValueError("test_dependency_overrides_incomplete")
    return ProductionEvolutionCampaignService(
        project_root=project_root,
        package_loader=overrides.package_loader,
        proposal_agent=overrides.proposal_agent,
        candidate_evaluator=overrides.candidate_evaluator or (lambda **_: {}),
        phase7_adapter=overrides.phase7_adapter or _UnavailableAdapter("phase7"),
        phase8_adapter=overrides.phase8_adapter or _UnavailableAdapter("phase8"),
        champion_policy=overrides.champion_policy or _FixtureChampionPolicy(),
        stop_policy=overrides.stop_policy or StopPolicy(),
        synchronous_fake_workers=overrides.synchronous_fake_workers,
        artifact_provenance="test_fixture",
        knowledge_snapshot_provider=overrides.knowledge_snapshot_provider,
    )
