"""The sole formal coordinator for constrained Phase 6 strategy proposals.

production_service.py    [agent_loop_json_client.py])提供 限制使用工具

[optimization/strategy_proposal_agent.py]本身没有大段 LLM Prompt，它只是协调器。
实际提示词分散在三个位置：
四个候选方案意图的 Prompt
[candidate_intent_planner.py (line 130)]
_SYSTEM = You are CandidateIntentPlanner...
它的动态上下文在：
candidate_intent_planner.py (line 45)
包含目标、Bootstrap Skill、经验卡、角色约束、Tactical Context 等。
"""

from __future__ import annotations

from dataclasses import replace

from cmo_lua_agent.contract.strategy_validator import StrategyValidator
from cmo_lua_agent.optimization.candidate_intent_planner import CandidateIntentPlanner, IntentJsonClient
from cmo_lua_agent.optimization.candidate_patch_generator import CandidatePatchGenerator
from cmo_lua_agent.optimization.candidate_intent_conformance import (
    CandidateIntentConformanceValidator,
    check_candidate_role_feasibility,
)
from cmo_lua_agent.optimization.phase6_models import StrategyCandidate, StrategyProposalContext
from cmo_lua_agent.optimization.proposal_context_builder import ProposalTacticalContextBuilder
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

    def __init__(self, client: IntentJsonClient, *, intent_client: IntentJsonClient | None = None) -> None:
        self._planner = CandidateIntentPlanner(intent_client or client)
        self._generator = CandidatePatchGenerator(client)
        self._last_usage = StrategyProposalUsage()
        self._last_audit: dict[str, object] = {}
        self._last_tactical_context: dict[str, object] | None = None

    @property
    def last_usage(self) -> StrategyProposalUsage:
        return self._last_usage

    @property
    def total_client_calls(self) -> int:
        return self._last_usage.total_calls

    @property
    def last_audit(self) -> dict[str, object]:
        return dict(self._last_audit)

    @property
    def last_tactical_context(self) -> dict[str, object] | None:
        return None if self._last_tactical_context is None else dict(self._last_tactical_context)

    def propose(self, context: StrategyProposalContext) -> tuple[StrategyCandidate, ...]:
        intent_calls = patch_calls = repair_calls = 0
        self._last_tactical_context = None
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
                # Role feasibility is advisory. A constrained catalog must not turn
                # a hard-valid, executable candidate into a terminal preview error.
                tactical = ProposalTacticalContextBuilder().build(
                    scenario=context.scenario,
                    baseline=context.baseline,
                    patch_catalog=catalog,
                    role_specs=role_specs,
                    accepted_candidates=(),
                )
                self._last_tactical_context = tactical.to_dict()
                context = replace(context, proposal_tactical_context=self._last_tactical_context)
                audit["proposal_context_checksum"] = tactical.checksum
                audit["baseline_operation_count"] = len(tactical.baseline_operations)
                audit["patchable_path_count"] = len(catalog)
                audit["failure_profile_available"] = bool(tactical.failure_profile["available"])
            intents = self._planner.plan(context, role_specs=role_specs)
            intent_calls += self._planner.last_call_count
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
                    failed_attempts = error.diagnostics.get("candidate_patch_attempts")
                    cast_attempts = audit["patch_attempts"]
                    assert isinstance(cast_attempts, list)
                    if isinstance(failed_attempts, list):
                        cast_attempts.extend(failed_attempts)
                    else:
                        failed_initial = error.diagnostics.get("initial_patch_failure")
                        if isinstance(failed_initial, dict):
                            cast_attempts.append(failed_initial)
                    raise
                patch_calls += used_patch
                repair_calls += used_repair
                cast_attempts = audit["patch_attempts"]
                assert isinstance(cast_attempts, list)
                cast_attempts.extend(candidate_audit)
                if any(item.strategy_checksum == candidate.strategy_checksum for item in accepted):
                    raise ProposalContractError("duplicate_accepted_strategy")
                dimensions = semantic_dimensions(candidate.intended_difference)
                accepted.append(_accepted_summary(candidate, dimensions))
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
    def _validate_candidate(*, intent, strategy, changed_paths, context, catalog, validator: StrategyValidator):
        conformance = CandidateIntentConformanceValidator().validate(
            intent=intent,
            changed_paths=tuple(changed_paths),
            catalog=catalog,
        )
        report = validator.validate(strategy, context.scenario)
        if not report.valid:
            violations = tuple(_validation_violation(issue, strategy) for issue in report.errors)
            raise StrategyValidationProposalError(violations=violations, changed_paths=tuple(changed_paths))
        return conformance

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
                intent=intent,
                catalog=catalog,
                accepted=accepted,
                tactical_context=self._patch_tactical_context(context, catalog, accepted),
                error=prior_error,
            )
            attempts = audit["candidate_repair"]["patch_attempts"]  # type: ignore[index]
            attempts.append(_patch_audit(intent.candidate_id, "targeted_repair", patch, prior_error))  # type: ignore[union-attr]
            assembled = assembler.assemble(patch)
            self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, catalog=catalog, validator=validator)
        except ProposalContractError as initial_error:
            try:
                repair_calls += 1
                patch = self._generator.generate(
                    intent=intent,
                    catalog=catalog,
                    accepted=accepted,
                    tactical_context=self._patch_tactical_context(context, catalog, accepted),
                    error=initial_error,
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
            attempts = error.diagnostics.get("candidate_patch_attempts", [])
            self._last_audit = {"candidate_generation": {"candidate_id": intent.candidate_id, "patch_attempts": attempts}, "usage": {"intent_calls": 0, "patch_calls": patch_calls, "repair_calls": repair_calls}}
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
        patch = None
        try:
            patch = self._generator.generate(
                intent=intent,
                catalog=catalog,
                accepted=accepted,
                tactical_context=self._patch_tactical_context(context, catalog, accepted),
            )
            attempts.append(_patch_audit(intent.candidate_id, "initial", patch))
            assembled = assembler.assemble(patch)
            conformance = self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, catalog=catalog, validator=validator)
            if conformance.repair_recommended:
                raise ProposalContractError(
                    "candidate_role_quality_weak",
                    diagnostics={"conformance_report": conformance.to_dict()},
                )
        except ProposalContractError as initial_error:
            context_audit = _patch_context(intent, patch) if patch is not None else {}
            initial_error.diagnostics.update(context_audit)
            initial_failure = _patch_failure_audit(
                intent.candidate_id, "initial_failed", initial_error, patch=patch
            )
            attempts.append(initial_failure)
            if initial_error.code in {
                "proposal_json_invalid",
                "patch_path_not_executable",
            }:
                raise CandidateProposalError(candidate_id=intent.candidate_id, stage="patch_generation", cause=initial_error) from initial_error
            repair_context = initial_error
            for repair_index in range(3):
                try:
                    patch = self._generator.generate(
                        intent=intent,
                        catalog=catalog,
                        accepted=accepted,
                        tactical_context=self._patch_tactical_context(context, catalog, accepted),
                        error=repair_context,
                    )
                    attempts.append(_patch_audit(intent.candidate_id, f"repair_{repair_index + 1}", patch, repair_context))
                    assembled = assembler.assemble(patch)
                    self._validate_candidate(intent=intent, strategy=assembled.strategy, changed_paths=assembled.changed_paths, context=context, catalog=catalog, validator=validator)
                except ProposalContractError as repair_error:
                    repair_error.diagnostics["initial_patch_failure"] = initial_failure
                    repair_error.diagnostics["candidate_patch_attempts"] = attempts
                    if repair_index == 2:
                        raise CandidateProposalError(
                            candidate_id=intent.candidate_id,
                            stage="patch_repair",
                            cause=repair_error,
                        ) from repair_error
                    repair_context = repair_error
                    continue
                return StrategyCandidate(intent.candidate_id, assembled.strategy, patch.proposal_summary, assembled.changed_paths), 1, repair_index + 1, attempts
        return StrategyCandidate(intent.candidate_id, assembled.strategy, patch.proposal_summary, assembled.changed_paths), 1, 0, attempts

    @staticmethod
    def _patch_tactical_context(
        context: StrategyProposalContext,
        catalog,
        accepted: tuple[AcceptedCandidateSummary, ...],
    ) -> dict[str, object] | None:
        if context.generation_context is None:
            return context.proposal_tactical_context
        tactical = ProposalTacticalContextBuilder().build(
            scenario=context.scenario,
            baseline=context.baseline,
            patch_catalog=catalog,
            role_specs=candidate_role_specs(context.generation_context),
            accepted_candidates=accepted,
        )
        return tactical.to_dict()


def _patch_audit(candidate_id, phase, patch, prior_error=None) -> dict[str, object]:
    context = _patch_context(None, patch)
    return {
        "candidate_id": candidate_id,
        "phase": phase,
        "changes": [{"path": change.path, "value": change.value} for change in patch.changes],
        "actual_change_count": context["actual_change_count"],
        "changed_paths": context["changed_paths"],
        "actual_dimensions": context["actual_dimensions"],
        "actual_operation_count": context["actual_operation_count"],
        "error_code": None,
        "proposal_summary": patch.proposal_summary,
        "prior_error_code": None if prior_error is None else prior_error.code,
    }


def _patch_failure_audit(
    candidate_id: str,
    phase: str,
    error: ProposalContractError,
    *,
    patch=None,
) -> dict[str, object]:
    diagnostics = error.diagnostics
    context = _patch_context(None, patch) if patch is not None else {}
    audit: dict[str, object] = {
        "candidate_id": candidate_id,
        "phase": phase,
        "error_code": error.code,
        "actual_change_count": diagnostics.get("actual_change_count", context.get("actual_change_count")),
        "proposed_paths": list(diagnostics.get("proposed_paths", context.get("changed_paths", ()))),
    }
    if context:
        previous_patch = context["previous_patch"]
        assert isinstance(previous_patch, dict)
        audit.update({
            "changes": previous_patch["changes"],
            "changed_paths": diagnostics.get("changed_paths", context["changed_paths"]),
            "actual_dimensions": diagnostics.get("actual_dimensions", context["actual_dimensions"]),
            "actual_operation_count": diagnostics.get("actual_operation_count", context["actual_operation_count"]),
        })
    return audit


def _patch_context(intent, patch) -> dict[str, object]:
    changed_paths = tuple(change.path for change in patch.changes)
    dimensions = semantic_dimensions(changed_paths)
    operations = tuple(sorted({
        "/".join(path.strip("/").split("/")[:2])
        for path in changed_paths
        if len(path.strip("/").split("/")) >= 2
    }))
    context: dict[str, object] = {
        "previous_patch": {
            "proposal_summary": patch.proposal_summary,
            "changes": [{"path": change.path, "value": change.value} for change in patch.changes],
        },
        "actual_change_count": len(changed_paths),
        "changed_paths": list(changed_paths),
        "actual_dimensions": list(dimensions),
        "actual_operation_count": len(operations),
    }
    if intent is not None:
        context["minimum_dimension_count"] = intent.minimum_distinct_dimensions
        context["required_change_range"] = {
            "minimum": intent.min_changes,
            "maximum": intent.max_changes,
        }
        context["required_operation_range"] = {
            "minimum": intent.min_operations,
            "maximum": intent.max_operations,
        }
        context["required_dimension_range"] = {
            "minimum": intent.minimum_distinct_dimensions,
            "maximum": intent.max_dimensions,
        }
    return context


def _accepted_summary(candidate: StrategyCandidate, dimensions: tuple[str, ...]) -> AcceptedCandidateSummary:
    """Keep only accepted coverage facts for later Patch prompts."""
    operation_keys = tuple(sorted({
        "/".join(path.strip("/").split("/")[:2])
        for path in candidate.intended_difference
        if len(path.strip("/").split("/")) >= 2
    }))
    attacks = {f"attacks/{index}": attack.target_ids[0] for index, attack in enumerate(candidate.strategy_spec.attacks)}
    sorties = {f"sorties/{index}": sortie.target_id for index, sortie in enumerate(candidate.strategy_spec.sorties)}
    target_summary = tuple(
        sorted((attacks | sorties)[operation]
               for operation in operation_keys
               if operation in attacks or operation in sorties)
    )
    return AcceptedCandidateSummary(
        candidate.candidate_id,
        candidate.strategy_checksum,
        candidate.intended_difference,
        dimensions,
        operation_keys,
        target_summary,
    )


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
