"""
GRPOTrainer: Group Relative Policy Optimisation loop.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from cmo_lua_agent.rl.grpo_environment import GRPOEnvironment
from cmo_lua_agent.rl.trajectory_store import TrajectoryStore
from cmo_lua_agent.rl.trajectory import Trajectory, TrajectoryStep
from cmo_lua_agent.rl.dataset_builder import DatasetBuilder

logger = logging.getLogger(__name__)


class GRPOTrainer:
    """
    Implements a simplified GRPO loop:

    For each task, generate G candidate scripts in parallel,
    evaluate them all, pick the top-K, and use them to update
    the candidate selector's implicit policy (stored as experience).

    Parameters
    ----------
    llm_client : Any
        Chat completion client.
    environment : GRPOEnvironment
        The RL environment.
    output_dir : Path | str
        Checkpoint + log output directory.
    group_size : int
        Number of candidates per GRPO group (G in the paper).
    top_k : int
        Number of top candidates to keep per group (K in the paper).
    epochs : int
        Number of GRPO iterations.
    """

    def __init__(
        self,
        llm_client: Any,
        environment: GRPOEnvironment,
        output_dir: Path | str,
        group_size: int = 4,
        top_k: int = 2,
        epochs: int = 5,
    ) -> None:
        self.llm_client = llm_client
        self.env = environment
        self.output_dir = Path(output_dir)
        self.group_size = group_size
        self.top_k = top_k
        self.epochs = epochs
        self.trajectory_store = TrajectoryStore()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def train(self, dataset_path: Path | str) -> Path:
        """
        Run the GRPO loop.

        Parameters
        ----------
        dataset_path : Path | str
            Training dataset (from DatasetBuilder).

        Returns
        -------
        Path
            Checkpoint directory (best policy snapshot).
        """
        from cmo_lua_agent.rl.dataset_builder import TrajectoryDataset

        dataset = TrajectoryDataset.load(dataset_path)

        for epoch in range(self.epochs):
            logger.info("[GRPO] Epoch %d / %d", epoch + 1, self.epochs)

            # Build group from dataset (cycle through entries)
            entries = list(dataset)
            if not entries:
                logger.warning("[GRPO] Empty dataset, skipping epoch")
                continue

            # One GRPO group per entry for simplicity
            episode_id = self.env.reset()
            traj = Trajectory(run_id=episode_id)

            for entry_idx in range(min(len(entries), self.group_size)):
                entry = entries[entry_idx % len(entries)]
                # Generate candidates (beam)
                candidates = self._generate_candidates(entry.instruction, self.group_size)

                best_reward = -1.0
                best_script = ""
                best_metrics = None

                # Evaluate all candidates
                for cand in candidates:
                    metrics, reward, _ = self.env.step(cand)
                    if reward > best_reward:
                        best_reward = reward
                        best_script = cand
                        best_metrics = metrics

                step = TrajectoryStep(
                    iteration=entry_idx,
                    lua_script=best_script,
                    script_path=str(self.env.episode_dir / f"candidate_{entry_idx}.lua"),
                    reward=best_reward,
                    combat_metrics=best_metrics.to_dict() if best_metrics else {},
                )
                traj.add_step(step)

            self.trajectory_store.add(traj)

        # Save experience
        exp_path = self.output_dir / "grpo_experience.jsonl"
        self.trajectory_store.save(exp_path)

        marker = self.output_dir / "grpo_complete.txt"
        marker.write_text(f"epochs={self.epochs}\ngroup_size={self.group_size}\n")
        return self.output_dir

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _generate_candidates(self, instruction: str, n: int) -> list[str]:
        """Call LLM to generate n candidate Lua scripts."""
        system_prompt = (
            "You are a Lua scripting expert for Command: Modern Operations.\n"
            "Output ONLY the Lua script. No markdown, no explanations."
        )
        user_prompt = (
            f"Task: {instruction}\n\n"
            f"Generate a Lua script that accomplishes this task. "
            f"Use ScenEdit_AttackContact with mode=0. "
            f"Include reload step before firing."
        )
        candidates = []
        for _ in range(n):
            response = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
            )
            text = response.get("content", "")
            candidates.append(self._strip_markdown(text))
        return candidates

    @staticmethod
    def _strip_markdown(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            _, _, rest = text.partition("\n")
            if rest.endswith("```"):
                rest = rest[:-3]
            return rest.strip()
        return text
