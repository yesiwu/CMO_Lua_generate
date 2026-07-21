"""Workflow coordination with one filesystem ownership boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cmo_lua_agent.artifacts import (
    ArtifactPersistenceError,
    RunArtifactStore,
)
from cmo_lua_agent.contract import (
    ResolvedScenarioManifest,
    ScenarioContract,
)
from cmo_lua_agent.generation import (
    LuaGenerationResult,
    LuaGenerationService,
)
from cmo_lua_agent.orchestration.workflow_state import (
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
    WorkflowTransitionError,
)


@dataclass(slots=True)
class WorkflowContext:
    """Coordinate generation while delegating all writes to the store."""

    store: RunArtifactStore
    state: WorkflowState

    def __post_init__(self) -> None:
        if not isinstance(self.store, RunArtifactStore):
            raise TypeError("store must be a RunArtifactStore")
        if not isinstance(self.state, WorkflowState):
            raise TypeError("state must be a WorkflowState")
        if self.store.run_id != self.state.run_id:
            raise ValueError(
                "store and state must use the same run_id"
            )

    @classmethod
    def create(
        cls,
        runs_root: Path,
        *,
        run_id: str | None = None,
    ) -> "WorkflowContext":
        store = RunArtifactStore.create(
            runs_root,
            run_id=run_id,
        )
        context = cls(
            store=store,
            state=WorkflowState.initial(store.paths),
        )
        context._persist_state()
        return context

    def advance(self, stage: WorkflowStage) -> WorkflowState:
        """Enter one workflow stage and atomically persist the state."""

        next_state = self.state.advance(stage)
        self.state = next_state
        self._persist_state()
        return self.state

    def save_manifest(
        self,
        manifest: ResolvedScenarioManifest,
    ) -> Path:
        if not isinstance(manifest, ResolvedScenarioManifest):
            raise TypeError(
                "manifest must be a ResolvedScenarioManifest"
            )

        self.state = self.state.advance(WorkflowStage.MANIFEST)
        self._persist_state()
        return self.store.save_manifest(manifest)

    def generate_lua(
        self,
        service: LuaGenerationService,
        *,
        manifest: ResolvedScenarioManifest,
        contract: ScenarioContract,
    ) -> LuaGenerationResult:
        if not isinstance(manifest, ResolvedScenarioManifest):
            raise TypeError(
                "manifest must be a ResolvedScenarioManifest"
            )
        if not isinstance(contract, ScenarioContract):
            raise TypeError(
                "contract must be a ScenarioContract"
            )
        if (
            self.state.status is not WorkflowStatus.RUNNING
            or self.state.stage is not WorkflowStage.MANIFEST
        ):
            raise WorkflowTransitionError(
                "Lua generation requires a saved manifest"
            )

        try:
            self.state = self.state.advance(
                WorkflowStage.GENERATION
            )
            self._persist_state()

            result = service.generate(
                manifest=manifest,
                contract=contract,
                manifest_path=self.store.paths.resolved_manifest,
                output_path=self.store.paths.original_lua,
            )
            if not isinstance(result, LuaGenerationResult):
                raise TypeError(
                    "generation service must return LuaGenerationResult"
                )

            self.store.save_validation(
                "lua_preflight",
                result.preflight,
            )
            candidate = _require_candidate_text(result)
            if result.success:
                self.store.save_original_lua(candidate)
            else:
                self.store.save_rejected_lua(candidate)

            return result
        except Exception as exc:
            code = (
                "artifact_persistence_failed"
                if isinstance(exc, ArtifactPersistenceError)
                else "generation_failed"
            )
            self._mark_failed_best_effort(
                code,
                str(exc) or type(exc).__name__,
            )
            raise

    def complete(self) -> WorkflowState:
        if not self.store.paths.original_lua.is_file():
            raise WorkflowTransitionError(
                "workflow cannot complete without accepted Lua"
            )
        if self.store.paths.rejected_lua.exists():
            raise WorkflowTransitionError(
                "workflow cannot complete from a rejected Lua candidate"
            )
        self.state = self.state.complete()
        self._persist_state()
        return self.state

    def fail(
        self,
        code: str,
        message: str,
    ) -> WorkflowState:
        self.state = self.state.fail(code, message)
        self._persist_state()
        return self.state

    def needs_user_input(
        self,
        code: str,
        message: str,
    ) -> WorkflowState:
        """Persist an auditable stop that must be resumed with user input."""
        self.state = self.state.needs_user_input(code, message)
        self._persist_state()
        return self.state

    def _persist_state(self) -> Path:
        return self.store.save_final_result(self.state)

    def _mark_failed_best_effort(
        self,
        code: str,
        message: str,
    ) -> None:
        try:
            self.state = self.state.fail(
                code,
                message or type(message).__name__,
            )
        except (WorkflowTransitionError, TypeError, ValueError):
            return

        try:
            self._persist_state()
        except ArtifactPersistenceError:
            # Preserve the original generation or persistence exception.
            pass


def _require_candidate_text(
    result: LuaGenerationResult,
) -> str:
    if result.lua_text is None or not result.lua_text.strip():
        raise ValueError(
            "generation result must contain a non-blank Lua candidate"
        )
    return result.lua_text
