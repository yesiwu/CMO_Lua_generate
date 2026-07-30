"""The sole formal coordinator for constrained Phase 6 strategy proposals."""

from __future__ import annotations

from cmo_lua_agent.contract.strategy_validator import StrategyValidator
from cmo_lua_agent.optimization.candidate_intent_planner import CandidateIntentPlanner, IntentJsonClient
from cmo_lua_agent.optimization.candidate_patch_generator import CandidatePatchGenerator
from cmo_lua_agent.optimization.candidate_intent_conformance import (
    CandidateIntentConformanceValidator,
    check_candidate_role_feasibility,
)
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate, StrategyProposalContext
from cmo_lua_agent.optimization.proposal_models import (
    AcceptedCandidateSummary,
    CandidateIntent,
    CandidateProposalError,
    ProposalContractError,
    StrategyProposalUsage,
    StrategyValidationProposalError,
    candidate_role_specs,
)
from cmo_lua_agent.optimization.strategy_patch import StrategyPatchAssembler, build_patchable_leaf_catalog
from cmo_lua_agent.optimization.strategy_dimensions import semantic_dimensions


class StrategyProposalAgent:
    """Coordinates exactly one intent call and bounded per-candidate patch calls."""

    def __init__(self, client: IntentJsonClient) -> None:
        self._planner = CandidateIntentPlanner(client)
        self._generator = CandidatePatchGenerator(client)
        self._last_usage = StrategyProposalUsage()
        self._last_audit: dict[str, object] = {}

    @property
    def last_usage(self) -> StrategyProposalUsage:
        return self._last_usage

    @property
    def total_client_calls(self) -> int:
        return self._last_usage.total_calls

    @property
    def last_audit(self) -> dict[str, object]:
        return dict(self._last_audit)

    def propose(self, context: StrategyProposalContext) -> tuple[StrategyCandidate, ...]:
        intent_calls = patch_calls = repair_calls = 0
        audit: dict[str, object] = {"intents": [], "accepted_candidates": [], "patch_attempts": []}
        try:
            catalog = build_patchable_leaf_catalog(
                baseline=context.baseline,
                scenario=context.scenario,
                allowed_paths=context.allowed_strategy_paths,
            )
            role_specs = (
                candidate_role_specs(context.generation_context)
                if context.generation_context is not None
                else None
            )
            if role_specs is not None:
                feasibility = tuple(
                    check_candidate_role_feasibility(
                        candidate_id=spec.candidate_id,
                        role_spec=spec,
                        patch_catalog=catalog,
                    )
                    for spec in role_specs
                )
                audit["role_feasibility"] = [item.to_dict() for item in feasibility]
                # Report the most constrained role first. This gives the operator the
                # useful blocker when a catalog cannot support coordinated exploration.
                failed = next(
                    (item for item in reversed(feasibility) if not item.feasible), None
                )
                if failed is not None:
                    raise ProposalContractError(
                        "candidate_role_not_feasible", diagnostics=failed.to_dict()
                    )
            intent_calls += 1
            intents = self._planner.plan(context, role_specs=role_specs)
            audit["intents"] = [
                    {"candidate_id": item.candidate_id, "role": item.role, "objective": item.objective,
                     "strategy_dimensions": list(item.strategy_dimensions),
                     "min_changes": item.min_changes, "max_changes": item.max_changes,
                     "min_operations": item.min_operations, "min_dimensions": item.min_dimensions,
                     "require_surface": item.require_surface, "require_sortie": item.require_sortie,
                     "max_operations": item.max_operations, "max_dimensions": item.max_dimensions,
                     "failure_profile_mode": item.failure_profile_mode,
                     "failure_profile_available": item.failure_profile_mode == "required",
                     "failure_operation_ids": list(item.failure_operation_ids),
                     "failure_semantic_dimensions": list(item.failure_semantic_dimensions),
                     "failure_profile_source_checksum": item.failure_profile_source_checksum,
                     "required_dimensions": list(item.required_dimensions)}
                    for item in intents
                ]
            assembler = StrategyPatchAssembler(baseline=context.baseline, catalog=catalog)
            validator = StrategyValidator()
            accepted: list[AcceptedCandidateSummary] = []
            candidates: list[StrategyCandidate] = []
            for intent in intents:
                try:
                    candidate, used_patch, used_repair, candidate_audit = self._generate_candidate(
                        context=context,
                        intent=intent,
                        accepted=tuple(accepted),
                        catalog=catalog,
                        assembler=assembler,
                        validator=validator,
                    )
                except CandidateProposalError as error:
                    patch_calls += 1
                    if error.stage == "patch_repair":
                        repair_calls += 1
                    raise
                patch_calls += used_patch
                repair_calls += used_repair
                cast_attempts = audit["patch_attempts"]
                assert isinstance(cast_attempts, list)
                cast_attempts.extend(candidate_audit)
                if any(item.strategy_checksum == candidate.strategy_checksum for item in accepted):
                    raise ProposalContractError("duplicate_accepted_strategy")
                dimensions = semantic_dimensions(candidate.intended_difference)
                accepted.append(AcceptedCandidateSummary(candidate.candidate_id, candidate.strategy_checksum, candidate.intended_difference, dimensions))
                cast_accepted = audit["accepted_candidates"]
                assert isinstance(cast_accepted, list)
                cast_accepted.append({"candidate_id": candidate.candidate_id, "strategy_checksum": candidate.strategy_checksum,
                                      "changed_paths": list(candidate.intended_difference), "strategy_dimensions": list(dimensions)})
                candidates.append(candidate)
            return tuple(candidates)
        finally:
            self._last_usage = StrategyProposalUsage(intent_calls, patch_calls, repair_calls)
            audit["usage"] = {"intent_calls": intent_calls, "patch_calls": patch_calls, "repair_calls": repair_calls}
            self._last_audit = audit

    @staticmethod
    def _validate_candidate(*, intent, strategy, changed_paths, context, catalog, validator: StrategyValidator) -> None:
        CandidateIntentConformanceValidator().validate(
            intent=intent,
            changed_paths=tuple(changed_paths),
            catalog=catalog,
        )
        report = validator.validate(strategy, context.scenario)
        if not report.valid:
            violations = tuple(_validation_violation(issue, strategy) for issue in report.errors)
            raise StrategyValidationProposalError(violations=violations, changed_paths=tuple(changed_paths))

    def repair_candidate(
        self,
        context: StrategyProposalContext,
        *,
        intent: CandidateIntent,
        accepted: tuple[AcceptedCandidateSummary, ...],
        prior_error: ProposalContractError,
    ) -> StrategyCandidate:
        """Regenerate only one named candidate; never invokes the intent planner."""
        patch_calls = repair_calls = 0
        catalog = build_patchable_leaf_catalog(
            baseline=context.baseline,
            scenario=context.scenario,
            allowed_paths=context.allowed_strategy_paths,
        )
        assembler = StrategyPatchAssembler(baseline=context.baseline, catalog=catalog)
        validator = StrategyValidator()
        audit: dict[str, object] = {"candidate_repair": {"candidate_id": intent.candidate_id, "patch_attempts": []}}
        try:
            patch_calls += 1
            patch = self._generator.generate(
                intent=intent, catalog=catalog, accepted=accepted, error=prior_error
            )
            attempts = audit["candidate_repair"]["patch_attempts"]  # type: ignore[index]
            attempts.append(_patch_audit(intent.candidate_id, "targeted_repair", patch, prior_error))  # type: ignore[union-attr]
            assembled = assembler.assemble(patch)
            self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, catalog=catalog, validator=validator)
        except ProposalContractError as initial_error:
            try:
                repair_calls += 1
                patch = self._generator.generate(
                    intent=intent, catalog=catalog, accepted=accepted, error=initial_error
                )
                attempts = audit["candidate_repair"]["patch_attempts"]  # type: ignore[index]
                attempts.append(_patch_audit(intent.candidate_id, "targeted_local_repair", patch, initial_error))  # type: ignore[union-attr]
                assembled = assembler.assemble(patch)
                self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, catalog=catalog, validator=validator)
            except ProposalContractError as repair_error:
                raise CandidateProposalError(candidate_id=intent.candidate_id, stage="targeted_patch_repair", cause=repair_error) from repair_error
        finally:
            self._last_usage = StrategyProposalUsage(0, patch_calls, repair_calls)
            audit["usage"] = {"intent_calls": 0, "patch_calls": patch_calls, "repair_calls": repair_calls}
            self._last_audit = audit
        return StrategyCandidate(intent.candidate_id, assembled.strategy, patch.proposal_summary, assembled.changed_paths)

    def generate_candidate(
        self,
        context: StrategyProposalContext,
        *,
        intent: CandidateIntent,
        accepted: tuple[AcceptedCandidateSummary, ...],
    ) -> StrategyCandidate:
        """Generate one new candidate without invoking the intent planner."""
        catalog = build_patchable_leaf_catalog(
            baseline=context.baseline,
            scenario=context.scenario,
            allowed_paths=context.allowed_strategy_paths,
        )
        assembler = StrategyPatchAssembler(baseline=context.baseline, catalog=catalog)
        try:
            candidate, patch_calls, repair_calls, audit = self._generate_candidate(
                context=context,
                intent=intent,
                accepted=accepted,
                catalog=catalog,
                assembler=assembler,
                validator=StrategyValidator(),
            )
        except CandidateProposalError as error:
            patch_calls = 1
            repair_calls = 1 if error.stage == "patch_repair" else 0
            self._last_usage = StrategyProposalUsage(0, patch_calls, repair_calls)
            self._last_audit = {"candidate_generation": {"candidate_id": intent.candidate_id, "patch_attempts": []}, "usage": {"intent_calls": 0, "patch_calls": patch_calls, "repair_calls": repair_calls}}
            raise
        self._last_usage = StrategyProposalUsage(0, patch_calls, repair_calls)
        self._last_audit = {"candidate_generation": {"candidate_id": intent.candidate_id, "patch_attempts": audit}, "usage": {"intent_calls": 0, "patch_calls": patch_calls, "repair_calls": repair_calls}}
        return candidate

    def _generate_candidate(
        self,
        *,
        context: StrategyProposalContext,
        intent: CandidateIntent,
        accepted: tuple[AcceptedCandidateSummary, ...],
        catalog,
        assembler,
        validator: StrategyValidator,
    ) -> tuple[StrategyCandidate, int, int, list[dict[str, object]]]:
        attempts: list[dict[str, object]] = []
        try:
            patch = self._generator.generate(intent=intent, catalog=catalog, accepted=accepted)
            attempts.append(_patch_audit(intent.candidate_id, "initial", patch))
            assembled = assembler.assemble(patch)
            self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, catalog=catalog, validator=validator)
        except ProposalContractError as initial_error:
            if initial_error.code in {
                "proposal_json_invalid",
                "patch_path_not_executable",
            }:
                raise CandidateProposalError(candidate_id=intent.candidate_id, stage="patch_generation", cause=initial_error) from initial_error
            try:
                patch = self._generator.generate(intent=intent, catalog=catalog, accepted=accepted, error=initial_error)
                attempts.append(_patch_audit(intent.candidate_id, "repair", patch, initial_error))
                assembled = assembler.assemble(patch)
                self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, catalog=catalog, validator=validator)
            except ProposalContractError as repair_error:
                raise CandidateProposalError(candidate_id=intent.candidate_id, stage="patch_repair", cause=repair_error) from repair_error
            return StrategyCandidate(intent.candidate_id, assembled.strategy, patch.proposal_summary, assembled.changed_paths), 1, 1, attempts
        return StrategyCandidate(intent.candidate_id, assembled.strategy, patch.proposal_summary, assembled.changed_paths), 1, 0, attempts


def _patch_audit(candidate_id, phase, patch, prior_error=None) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "phase": phase,
        "changes": [{"path": change.path, "value": change.value} for change in patch.changes],
        "proposal_summary": patch.proposal_summary,
        "prior_error_code": None if prior_error is None else prior_error.code,
    }


def _validation_violation(issue, strategy) -> dict[str, object]:
    value = _strategy_value(strategy.to_dict(), issue.path)
    constraints = {
        "strategy.total_ammo_exceeded": "total fire quantity plus reserve must not exceed shooter weapon inventory",
        "strategy.ammo_exceeded": "fire quantity plus reserve must not exceed weapon inventory",
        "strategy.friendly_target": "target side must differ from attacker side",
        "strategy.route_coordinate_invalid": "latitude must be [-90, 90] and longitude must be [-180, 180]",
    }
    return {"code": issue.code, "path": issue.path, "actual_value": value,
            "constraint_summary": constraints.get(issue.code, issue.message)}


def _strategy_value(payload, path):
    if not path.startswith("$. ") and not path.startswith("$"):
        return None
    tokens = path[2:].replace("][", ".").replace("[", ".").replace("]", "").split(".")
    current = payload
    try:
        for token in tokens:
            if not token:
                continue
            current = current[int(token)] if isinstance(current, list) else current[token]
    except (IndexError, KeyError, ValueError, TypeError):
        return None
    return current
