"""The sole formal coordinator for constrained Phase 6 strategy proposals."""

from __future__ import annotations

from cmo_lua_agent.contract.strategy_validator import StrategyValidator
from cmo_lua_agent.optimization.candidate_intent_planner import CandidateIntentPlanner, IntentJsonClient
from cmo_lua_agent.optimization.candidate_patch_generator import CandidatePatchGenerator
from cmo_lua_agent.optimization.candidate_set_validator import _dimension
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate, StrategyProposalContext
from cmo_lua_agent.optimization.proposal_models import AcceptedCandidateSummary, ProposalContractError, StrategyProposalUsage
from cmo_lua_agent.optimization.strategy_patch import StrategyPatchAssembler, build_patchable_leaf_catalog


class StrategyProposalAgent:
    """Coordinates exactly one intent call and bounded per-candidate patch calls."""

    def __init__(self, client: IntentJsonClient) -> None:
        self._planner = CandidateIntentPlanner(client)
        self._generator = CandidatePatchGenerator(client)
        self._last_usage = StrategyProposalUsage()

    @property
    def last_usage(self) -> StrategyProposalUsage:
        return self._last_usage

    @property
    def total_client_calls(self) -> int:
        return self._last_usage.total_calls

    def propose(self, context: StrategyProposalContext) -> tuple[StrategyCandidate, ...]:
        intent_calls = patch_calls = repair_calls = 0
        try:
            intent_calls += 1
            intents = self._planner.plan(context)
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
                    assembled = assembler.assemble(patch)
                    self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, validator=validator)
                except ProposalContractError as initial_error:
                    repair_calls += 1
                    patch = self._generator.generate(intent=intent, catalog=catalog, accepted=tuple(accepted), error=initial_error)
                    assembled = assembler.assemble(patch)
                    self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, validator=validator)
                candidate = StrategyCandidate(intent.candidate_id, assembled.strategy, patch.proposal_summary, assembled.changed_paths)
                if any(item.strategy_checksum == candidate.strategy_checksum for item in accepted):
                    raise ProposalContractError("duplicate_accepted_strategy")
                dimensions = tuple(sorted({_dimension(path) for path in assembled.changed_paths}))
                accepted.append(AcceptedCandidateSummary(candidate.candidate_id, candidate.strategy_checksum, assembled.changed_paths, dimensions))
                candidates.append(candidate)
            return tuple(candidates)
        finally:
            self._last_usage = StrategyProposalUsage(intent_calls, patch_calls, repair_calls)

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
            raise ProposalContractError("assembled_strategy_invalid")
