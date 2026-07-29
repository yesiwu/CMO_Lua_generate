"""The sole formal coordinator for constrained Phase 6 strategy proposals."""

from __future__ import annotations

from cmo_lua_agent.contract.strategy_validator import StrategyValidator
from cmo_lua_agent.optimization.candidate_intent_planner import CandidateIntentPlanner, IntentJsonClient
from cmo_lua_agent.optimization.candidate_patch_generator import CandidatePatchGenerator
from cmo_lua_agent.optimization.candidate_set_validator import _dimension
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate, StrategyProposalContext
from cmo_lua_agent.optimization.proposal_models import AcceptedCandidateSummary, CandidateProposalError, ProposalContractError, StrategyProposalUsage, StrategyValidationProposalError
from cmo_lua_agent.optimization.strategy_patch import StrategyPatchAssembler, build_patchable_leaf_catalog


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
        try:
            intent_calls += 1
            intents = self._planner.plan(context)
            audit: dict[str, object] = {
                "intents": [
                    {"candidate_id": item.candidate_id, "role": item.role, "objective": item.objective,
                     "strategy_dimensions": list(item.strategy_dimensions)}
                    for item in intents
                ],
                "accepted_candidates": [],
                "patch_attempts": [],
            }
            catalog = build_patchable_leaf_catalog(
                baseline=context.baseline,
                scenario=context.scenario,
                allowed_paths=context.allowed_strategy_paths,
            )
            assembler = StrategyPatchAssembler(baseline=context.baseline, catalog=catalog)
            validator = StrategyValidator()
            accepted: list[AcceptedCandidateSummary] = []
            candidates: list[StrategyCandidate] = []
            for intent in intents:
                try:
                    patch_calls += 1
                    patch = self._generator.generate(intent=intent, catalog=catalog, accepted=tuple(accepted))
                    cast_attempts = audit["patch_attempts"]
                    assert isinstance(cast_attempts, list)
                    cast_attempts.append(_patch_audit(intent.candidate_id, "initial", patch))
                    assembled = assembler.assemble(patch)
                    self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, validator=validator)
                except ProposalContractError as initial_error:
                    try:
                        repair_calls += 1
                        patch = self._generator.generate(intent=intent, catalog=catalog, accepted=tuple(accepted), error=initial_error)
                        cast_attempts = audit["patch_attempts"]
                        assert isinstance(cast_attempts, list)
                        cast_attempts.append(_patch_audit(intent.candidate_id, "repair", patch, initial_error))
                        assembled = assembler.assemble(patch)
                        self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, validator=validator)
                    except ProposalContractError as repair_error:
                        raise CandidateProposalError(
                            candidate_id=intent.candidate_id,
                            stage="patch_repair",
                            cause=repair_error,
                        ) from repair_error
                candidate = StrategyCandidate(intent.candidate_id, assembled.strategy, patch.proposal_summary, assembled.changed_paths)
                if any(item.strategy_checksum == candidate.strategy_checksum for item in accepted):
                    raise ProposalContractError("duplicate_accepted_strategy")
                dimensions = tuple(sorted({_dimension(path) for path in assembled.changed_paths}))
                accepted.append(AcceptedCandidateSummary(candidate.candidate_id, candidate.strategy_checksum, assembled.changed_paths, dimensions))
                cast_accepted = audit["accepted_candidates"]
                assert isinstance(cast_accepted, list)
                cast_accepted.append({"candidate_id": candidate.candidate_id, "strategy_checksum": candidate.strategy_checksum,
                                      "changed_paths": list(assembled.changed_paths), "strategy_dimensions": list(dimensions)})
                candidates.append(candidate)
            return tuple(candidates)
        finally:
            self._last_usage = StrategyProposalUsage(intent_calls, patch_calls, repair_calls)
            if "audit" in locals():
                audit["usage"] = {"intent_calls": intent_calls, "patch_calls": patch_calls, "repair_calls": repair_calls}
                self._last_audit = audit

    @staticmethod
    def _validate_candidate(*, intent, strategy, changed_paths, context, validator: StrategyValidator) -> None:
        if not intent.min_changes <= len(changed_paths) <= intent.max_changes:
            raise ProposalContractError("actual_change_count_out_of_bounds")
        dimensions = {_dimension(path) for path in changed_paths}
        if not dimensions.issubset(set(intent.strategy_dimensions)):
            raise ProposalContractError("actual_dimension_not_intended")
        if not set(intent.required_dimensions).issubset(dimensions):
            raise ProposalContractError("repair_failure_profile_not_applied")
        report = validator.validate(strategy, context.scenario)
        if not report.valid:
            violations = tuple(_validation_violation(issue, strategy) for issue in report.errors)
            raise StrategyValidationProposalError(violations=violations, changed_paths=tuple(changed_paths))


def _patch_audit(candidate_id, phase, patch, prior_error=None) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "phase": phase,
        "changes": [{"path": change.path, "value": change.value} for change in patch.changes],
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
