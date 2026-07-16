"""
Optimisation workflow: iterates script generation → execution → evaluation,
updating a reward signal to guide candidate selection.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from cmo_lua_agent.orchestration.workflow_state import WorkflowState, WorkflowPhase
from cmo_lua_agent.orchestration.workflow_context import WorkflowContext
from cmo_lua_agent.orchestration.execution_policy import ExecutionPolicy
from cmo_lua_agent.optimization.candidate_selector import CandidateSelector
from cmo_lua_agent.optimization.convergence import ConvergenceChecker
from cmo_lua_agent.optimization.experience_distiller import ExperienceDistiller
from cmo_lua_agent.optimization.optimization_state import OptimizationState
from cmo_lua_agent.evaluation.reward import RewardComputer
from cmo_lua_agent.rl.trajectory import Trajectory, TrajectoryStep
from cmo_lua_agent.rl.trajectory_store import TrajectoryStore
from cmo_lua_agent.rl.dataset_builder import DatasetBuilder

logger = logging.getLogger(__name__)


class OptimizationWorkflow:
    """
    Drives the inner loop:

        generate → execute → score → update candidate selector → converge?
    """

    def __init__(
        self,
        context: WorkflowContext,
        policy: Optional[ExecutionPolicy] = None,
    ) -> None:
        self.ctx = context
        self.policy = policy or ExecutionPolicy()
        self.state = OptimizationState()
        self.trajectory_store = TrajectoryStore()
        self.candidate_selector = CandidateSelector()
        self.convergence = ConvergenceChecker()
        self.distiller = ExperienceDistiller()
        self.reward_computer = RewardComputer()
        self.dataset_builder = DatasetBuilder()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self) -> WorkflowState:
        """Run optimisation until convergence or max iterations reached."""
        ws = WorkflowState(
            workflow_name="optimization",
            run_id=self.state.run_id,
            max_iterations=self.policy.max_iterations_per_workflow,
        )

        while not ws.cancelled:
            ws.phase = WorkflowPhase.GENERATING
            # 1. Generate next candidate using selector
            candidate = self.candidate_selector.select(self.state, self.ctx)
            ws.iteration = self.state.iteration

            # 2. Write script to temp path
            script_path = self._write_script(candidate)
            ws.lua_script = candidate
            ws.script_path = str(script_path)

            # 3. Execute
            ws.phase = WorkflowPhase.EXECUTING
            exec_ok, combat_metrics = self._execute(script_path)
            ws.execution_ok = exec_ok
            ws.combat_metrics = combat_metrics

            if not exec_ok:
                self._record_failure(ws, script_path)
                if not ws.next_iteration():
                    break
                continue

            # 4. Score
            ws.phase = WorkflowPhase.EVALUATING
            reward = self.reward_computer.compute(combat_metrics)
            ws.reward = reward
            logger.info("[opt] iter=%d reward=%.4f", ws.iteration, reward)

            # 5. Record trajectory
            step = TrajectoryStep(
                iteration=ws.iteration,
                lua_script=candidate,
                script_path=str(script_path),
                reward=reward,
                combat_metrics=combat_metrics,
            )
            traj = Trajectory(run_id=self.state.run_id, steps=[step])
            self.trajectory_store.add(traj)
            self.state.last_reward = reward

            # 6. Update selector
            self.candidate_selector.update(self.state, candidate, reward)

            # 7. Convergence check
            if self.convergence.is_converged(self.state):
                logger.info("[opt] Converged at iter %d", ws.iteration)
                ws.mark_done(success=True)
                break

            # 8. Next iteration?
            if not ws.next_iteration():
                ws.mark_done(success=False, error="max iterations reached")
                break

        return ws

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _write_script(self, lua: str) -> Path:
        path = self.ctx.output_dir / f"opt_{self.state.iteration:03d}.lua"
        path.parent.mkdirp(parents=True, exist_ok=True)
        path.write_text(lua, encoding="utf-8")
        return path

    def _execute(self, script_path: Path):
        # Defer to CMO executor (import lazily to avoid circular deps)
        from cmo_lua_agent.execution.cmo_runner import CmoRunner

        runner = CmoRunner(self.ctx.cmo_executable, self.ctx.scenario_path)
        result = runner.run(script_path)
        ok = result.success
        metrics = result.combat_metrics or {}
        return ok, metrics

    def _record_failure(self, ws: WorkflowState, script_path: Path) -> None:
        ws.reward = 0.0
        ws.combat_metrics = {}
        step = TrajectoryStep(
            iteration=ws.iteration,
            lua_script=ws.lua_script or "",
            script_path=str(script_path),
            reward=0.0,
            combat_metrics={},
        )
        self.trajectory_store.add(Trajectory(run_id=self.state.run_id, steps=[step]))

    def export_dataset(self, path: Path) -> None:
        """Export replay buffer as an SFT/GRPO dataset."""
        self.dataset_builder.build(self.trajectory_store).save(path)
