"""Validate execution plans against the registered Phase 2 runtime.## CapabilityGap  能力缺口 ，描述RuntimeProfile 不支持的cmo  lua语法"""

from __future__ import annotations

from dataclasses import dataclass

from cmo_lua_agent.generation.runtime_models import ExecutionPlan, LuaRuntimeProfile
from cmo_lua_agent.generation.runtime_primitives import RuntimePrimitiveRegistry


@dataclass(frozen=True, slots=True)
class CapabilityValidationIssue:
    code: str
    operation_id: str | None
    message: str


@dataclass(frozen=True, slots=True)
class CapabilityValidationResult:
    issues: tuple[CapabilityValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues


class CapabilityValidator:
    def __init__(self, registry: RuntimePrimitiveRegistry) -> None:
        self._registry = registry

    def validate(
        self,
        *,
        plan: ExecutionPlan,
        runtime: LuaRuntimeProfile,
    ) -> CapabilityValidationResult:
        issues: list[CapabilityValidationIssue] = []

        if plan.runtime_id != runtime.runtime_id or plan.runtime_version != runtime.runtime_version:
            issues.append(
                CapabilityValidationIssue(
                    code="runtime_version_mismatch",
                    operation_id=None,
                    message=(
                        f"plan runtime {plan.runtime_id}@{plan.runtime_version} "
                        f"does not match profile {runtime.runtime_id}@{runtime.runtime_version}"
                    ),
                )
            )

        operation_ids = {operation.operation_id for operation in plan.operations}
        for operation in plan.operations:
            primitive = self._registry.get(operation.primitive_type)
            if primitive is None:
                issues.append(
                    CapabilityValidationIssue(
                        code="unknown_primitive",
                        operation_id=operation.operation_id,
                        message=f"unknown primitive: {operation.primitive_type}",
                    )
                )
                continue

            if primitive.runtime_id != runtime.runtime_id or primitive.runtime_version != runtime.runtime_version:
                issues.append(
                    CapabilityValidationIssue(
                        code="runtime_version_mismatch",
                        operation_id=operation.operation_id,
                        message=f"primitive {operation.primitive_type} is not registered for this runtime",
                    )
                )

            parameter_error = primitive.validate_parameters(operation.parameters)
            if parameter_error is not None:
                issues.append(
                    CapabilityValidationIssue(
                        code="invalid_parameters",
                        operation_id=operation.operation_id,
                        message=parameter_error,
                    )
                )

            for dependency in operation.depends_on:
                if dependency not in operation_ids:
                    issues.append(
                        CapabilityValidationIssue(
                            code="missing_dependency",
                            operation_id=operation.operation_id,
                            message=f"missing dependency: {dependency}",
                        )
                    )

        if self._has_cycle(plan):
            issues.append(
                CapabilityValidationIssue(
                    code="cyclic_dependency",
                    operation_id=None,
                    message="execution plan dependencies contain a cycle",
                )
            )

        return CapabilityValidationResult(issues=tuple(issues))

    def _has_cycle(self, plan: ExecutionPlan) -> bool:
        dependencies = {
            operation.operation_id: tuple(operation.depends_on)
            for operation in plan.operations
        }
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(operation_id: str) -> bool:
            if operation_id in visited:
                return False
            if operation_id in visiting:
                return True
            visiting.add(operation_id)
            for dependency in dependencies.get(operation_id, ()):
                if dependency in dependencies and visit(dependency):
                    return True
            visiting.remove(operation_id)
            visited.add(operation_id)
            return False

        return any(visit(operation_id) for operation_id in dependencies)
