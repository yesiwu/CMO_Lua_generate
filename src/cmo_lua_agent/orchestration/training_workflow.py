"""
Training workflow: fine-tunes a model (SFT or GRPO) on accumulated trajectories.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from cmo_lua_agent.orchestration.workflow_state import WorkflowState, WorkflowPhase
from cmo_lua_agent.orchestration.workflow_context import WorkflowContext
from cmo_lua_agent.rl.trajectory_store import TrajectoryStore
from cmo_lua_agent.rl.dataset_builder import DatasetBuilder
from cmo_lua_agent.rl.sft_trainer import SFTTrainer
from cmo_lua_agent.rl.grpo_trainer import GRPOTrainer
from cmo_lua_agent.rl.grpo_environment import GRPOEnvironment

logger = logging.getLogger(__name__)


class TrainingWorkflow:
    """
    Supports two training modes:

    - **SFT**: Supervised Fine-Tuning on (prompt, lua_script) pairs.
    - **GRPO**: Group Relative Policy Optimisation using accumulated trajectories.

    Parameters
    ----------
    mode : str
        "sft" or "grpo"
    trajectory_store : TrajectoryStore
        Source of training examples.
    """

    def __init__(
        self,
        context: WorkflowContext,
        trajectory_store: TrajectoryStore,
        mode: str = "sft",
    ) -> None:
        self.ctx = context
        self.trajectory_store = trajectory_store
        self.mode = mode.lower()
        self.state = WorkflowState(
            workflow_name=f"training_{mode}",
            run_id="",
            phase=WorkflowPhase.INIT,
        )
        self._trainer: Optional[SFTTrainer | GRPOTrainer] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> WorkflowState:
        """Execute the training run end-to-end."""
        self.state.phase = WorkflowPhase.INIT

        # 1. Build dataset from trajectories
        dataset = DatasetBuilder().build(self.trajectory_store)
        logger.info("[train] Dataset size: %d samples", len(dataset))

        if len(dataset) == 0:
            self.state.mark_done(success=False, error="no training samples")
            return self.state

        # 2. Save dataset to disk
        dataset_path = self.ctx.output_dir / "train_dataset.jsonl"
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        dataset.save(dataset_path)
        self.state.script_path = str(dataset_path)

        # 3. Train
        self.state.phase = WorkflowPhase.GENERATING
        if self.mode == "sft":
            self._train_sft(dataset_path)
        elif self.mode == "grpo":
            self._train_grpo(dataset_path)
        else:
            self.state.mark_done(success=False, error=f"Unknown mode: {self.mode}")
            return self.state

        self.state.execution_ok = True
        self.state.mark_done(success=True)
        return self.state

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------
    def _train_sft(self, dataset_path: Path) -> None:
        trainer = SFTTrainer(
            llm_client=self.ctx.llm_client,
            output_dir=self.ctx.output_dir / "sft_checkpoints",
        )
        self._trainer = trainer
        checkpoint = trainer.train(dataset_path)
        logger.info("[train] SFT checkpoint: %s", checkpoint)
        self.state.lua_script = str(checkpoint)

    def _train_grpo(self, dataset_path: Path) -> None:
        env = GRPOEnvironment(
            cmo_executable=self.ctx.cmo_executable,
            scenario_path=self.ctx.scenario_path,
            output_dir=self.ctx.output_dir / "grpo_runs",
        )
        trainer = GRPOTrainer(
            llm_client=self.ctx.llm_client,
            environment=env,
            output_dir=self.ctx.output_dir / "grpo_checkpoints",
        )
        self._trainer = trainer
        checkpoint = trainer.train(dataset_path)
        logger.info("[train] GRPO checkpoint: %s", checkpoint)
        self.state.lua_script = str(checkpoint)
