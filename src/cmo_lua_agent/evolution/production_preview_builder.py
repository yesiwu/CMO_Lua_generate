"""Formal Phase 9C preview assembly; the only proposal LLM stage."""

from __future__ import annotations

import json
import os
from pathlib import Path

from cmo_lua_agent.evolution.control_plane import GenerationPreviewPayload
from cmo_lua_agent.evolution.production_models import (
    FrozenCandidateSet,
    canonical_checksum,
)
from cmo_lua_agent.optimization.candidate_set_validator import CandidateSetValidator
from cmo_lua_agent.optimization.phase6_models import StrategyProposalContext


class ProductionPreviewBuilder:
    def __init__(
        self,
        *,
        package,
        proposal_agent,
        novelty_validator,
        campaign_root_provider,
        generation_context_builder=None,
        knowledge_snapshot_provider=None,
    ) -> None:
        self._package = package
        self._proposal_agent = proposal_agent
        self._novelty = novelty_validator
        self._root_for = campaign_root_provider
        self._context_builder = generation_context_builder
        self._knowledge = knowledge_snapshot_provider
        self.proposal_calls = 0

    def build(self, *, spec, generation_index: int, preview_revision: int) -> GenerationPreviewPayload:
        root = Path(self._root_for(spec.campaign_id)).resolve()
        preview_root = (
            root
            / "previews"
            / f"generation_{generation_index:03d}"
            / f"revision_{preview_revision:03d}"
        )
        frozen_path = preview_root / "frozen-candidate-set.json"
        diff_path = preview_root / "strategy-diff.json"
        snapshot_path = preview_root / "knowledge-snapshot.json"
        if frozen_path.is_file() and diff_path.is_file() and snapshot_path.is_file():
            frozen = FrozenCandidateSet.from_dict(
                json.loads(frozen_path.read_text(encoding="utf-8"))
            )
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            diffs = json.loads(diff_path.read_text(encoding="utf-8"))
            return self._payload(frozen, snapshot, diffs, frozen_path, diff_path, 0)
        preview_root.mkdir(parents=True, exist_ok=False)
        context_value = (
            dict(self._context_builder(generation_index))
            if self._context_builder is not None
            else self._default_generation_context(generation_index)
        )
        if self._knowledge is None:
            snapshot_body = {
                "campaign_id": spec.campaign_id,
                "generation_index": generation_index,
                "bootstrap_checksum": self._package.bootstrap.checksum,
                "active_skills": [],
                "experience_cards": [],
                "contract": self._package.checksums,
                "parent_strategy_checksum": canonical_checksum(
                    self._package.baseline.strategy.to_dict()
                ),
            }
            snapshot = {
                **snapshot_body,
                "checksum": canonical_checksum(snapshot_body),
            }
        else:
            snapshot = self._knowledge.freeze(
                path=snapshot_path,
                spec=spec,
                package=self._package,
                generation_index=generation_index,
            )
        context = StrategyProposalContext(
            scenario=self._package.scenario,
            baseline=self._package.baseline.strategy,
            user_objective=spec.generation_objective,
            allowed_strategy_paths=self._package.allowed_strategy_paths,
            diversity_dimensions=self._package.diversity_dimensions,
            runtime_id=self._package.runtime.runtime_id,
            runtime_version=self._package.runtime.runtime_version,
            bootstrap=self._package.bootstrap,
            retrieved_experience_cards=tuple(
                dict(item) for item in snapshot.get("experience_cards", ())
            ),
            active_curated_skill=(
                dict(snapshot["active_skills"][0])
                if snapshot.get("active_skills")
                else None
            ),
            generation_context=context_value,
        )
        try:
            candidates = self._proposal_agent.propose(context)
        except Exception as error:
            trace = getattr(self._proposal_agent, "last_audit", {})
            if trace:
                self._atomic_json(preview_root / "proposal-trace.json", trace)
            self._atomic_json(
                preview_root / "proposal-failure.json",
                self.failure_audit(error=error, proposal_agent=self._proposal_agent),
            )
            raise
        finally:
            usage = getattr(self._proposal_agent, "last_usage", None)
            self.proposal_calls = int(getattr(usage, "total_calls", 0))
        trace = getattr(self._proposal_agent, "last_audit", {})
        if trace:
            self._atomic_json(preview_root / "proposal-trace.json", trace)
        try:
            candidate_set = CandidateSetValidator().validate(
                scenario=self._package.scenario,
                baseline=self._package.baseline.strategy,
                candidates=candidates,
                allowed_paths=self._package.allowed_strategy_paths,
                diversity_dimensions=self._package.diversity_dimensions,
            )
            if not candidate_set.diversity_report.valid:
                raise ValueError("candidate_set_invalid")
            self._novelty.validate(
                baseline=self._package.baseline.strategy,
                candidates=candidates,
                generation_context=context_value,
            )
        except Exception as error:
            self._atomic_json(
                preview_root / "proposal-failure.json",
                self.failure_audit(error=error, proposal_agent=self._proposal_agent),
            )
            raise
        frozen = FrozenCandidateSet.create(
            campaign_id=spec.campaign_id,
            generation_index=generation_index,
            preview_revision=preview_revision,
            baseline=self._package.baseline.strategy.to_dict(),
            candidates=tuple(candidate.to_dict() for candidate in candidates),
            source_proposal_operation_id=f"g{generation_index:03d}:strategy_proposal:r{preview_revision:03d}",
        )
        diffs = [
            {
                "candidate_id": candidate.candidate_id,
                "changed_paths": list(
                    candidate_set.diversity_report.candidate_diffs[candidate.candidate_id]
                ),
            }
            for candidate in candidates
        ]
        if not snapshot_path.is_file():
            self._atomic_json(snapshot_path, snapshot)
        self._atomic_json(frozen_path, frozen.to_dict())
        self._atomic_json(diff_path, diffs)
        return self._payload(frozen, snapshot, diffs, frozen_path, diff_path, self.proposal_calls)

    def _default_generation_context(self, generation_index: int) -> dict[str, object]:
        profile = getattr(self._package, "baseline_failure_profile", None)
        repair_role = "repair" if profile is not None else "conservative_risk_reduction"
        return {
            "generation_index": generation_index,
            "candidate_roles": {
                "candidate_00": "exploit",
                "candidate_01": repair_role,
                "candidate_02": "explore",
                "candidate_03": "conservative_control",
            },
            "allowed_strategy_paths": list(self._package.allowed_strategy_paths),
            "history_fingerprints": [],
            "previous_generation_failures": (
                list(profile.failure_indicators) if profile is not None else []
            ),
            "conservative_max_changed_leaves": 1,
        }

    @staticmethod
    def _payload(frozen, snapshot, diffs, frozen_path, diff_path, calls):
        return GenerationPreviewPayload(
            knowledge_snapshot_checksum=snapshot["checksum"],
            candidate_set_checksum=frozen.candidate_set_checksum,
            strategy_diffs=tuple(diffs),
            proposal_llm_calls=calls,
            baseline_checksum=frozen.baseline_checksum,
            frozen_candidate_set_ref=str(frozen_path),
            strategy_diff_ref=str(diff_path),
        )

    @staticmethod
    def failure_audit(*, error: Exception, proposal_agent) -> dict[str, object]:
        error_code = getattr(error, "code", None) or str(error) or type(error).__name__
        if error_code.startswith("novelty_"):
            stage = "novelty_validation"
        elif error_code == "candidate_set_invalid":
            stage = "candidate_set_validation"
        else:
            stage = getattr(error, "stage", "intent_or_patch")
        return {
            "candidate_id": getattr(error, "candidate_id", None),
            "error_code": error_code,
            "failure_stage": stage,
            "message": str(error),
            "proposal_llm_calls": int(
                getattr(getattr(proposal_agent, "last_usage", None), "total_calls", 0)
            ),
            "validator_violations": list(getattr(error, "violations", ())),
            "changed_paths": list(getattr(error, "changed_paths", ())),
        }

    @staticmethod
    def _atomic_json(path: Path, value: object) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
