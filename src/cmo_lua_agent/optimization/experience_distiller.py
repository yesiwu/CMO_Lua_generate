"""
ExperienceDistiller: extracts high-quality (lua_script, reward) pairs from history.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

from cmo_lua_agent.rl.trajectory_store import TrajectoryStore
from cmo_lua_agent.rl.trajectory import Trajectory

logger = logging.getLogger(__name__)


class DistilledExperience:
    """A curated (script, reward, count) triple."""

    __slots__ = ("lua_script", "reward", "count", "rank")

    def __init__(self, lua_script: str, reward: float, count: int = 1) -> None:
        self.lua_script = lua_script
        self.reward = reward
        self.count = count
        self.rank: int = 0

    @property
    def quality(self) -> float:
        """
        Quality score balancing reward and coverage.
        reward * log(1 + count) favours repeated high-reward scripts.
        """
        import math

        return self.reward * math.log(1 + self.count)


class ExperienceDistiller:
    """
    Extracts, deduplicates, and ranks experiences from a TrajectoryStore.

    Output is suitable for:
    - SFT dataset building
    - GRPO reward normalisation
    - CandidateSelector template selection
    """

    def __init__(self, min_reward: float = -0.5) -> None:
        """
        Parameters
        ----------
        min_reward : float
            Only include experiences with reward >= this threshold.
        """
        self.min_reward = min_reward

    def distill(
        self, store: TrajectoryStore, top_k: Optional[int] = None
    ) -> list[DistilledExperience]:
        """
        Process all trajectories and return ranked experiences.

        Parameters
        ----------
        store : TrajectoryStore
            Source trajectories.
        top_k : int, optional
            Return only the top-k experiences (by quality).

        Returns
        -------
        list[DistilledExperience]
            Sorted by quality descending.
        """
        # Aggregate by script content (deduplicate)
        script_map: dict[str, tuple[float, int]] = {}

        for traj in store.trajectories():
            for step in traj.steps:
                if step.reward < self.min_reward:
                    continue
                key = self._hash_script(step.lua_script)
                if key in script_map:
                    prev_reward, cnt = script_map[key]
                    script_map[key] = (max(prev_reward, step.reward), cnt + 1)
                else:
                    script_map[key] = (step.reward, 1)

        experiences = [
            DistilledExperience(lua_script=step.lua_script, reward=reward, count=cnt)
            for step, (reward, cnt) in (
                (self._find_step(store, key), vals)
                for key, vals in script_map.items()
            )
        ]

        # Rank by quality
        experiences.sort(key=lambda e: e.quality, reverse=True)
        for i, e in enumerate(experiences):
            e.rank = i + 1

        logger.info(
            "[distiller] %d unique scripts, %d above threshold",
            len(experiences),
            sum(1 for e in experiences if e.reward >= 0),
        )

        if top_k is not None:
            experiences = experiences[:top_k]

        return experiences

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    @staticmethod
    def _hash_script(script: str) -> str:
        return hashlib.md5(script.encode("utf-8")).hexdigest()

    @staticmethod
    def _find_step(store: TrajectoryStore, key: str) -> "Trajectory.Step":
        """Find the step matching the script hash (first occurrence)."""
        for traj in store.trajectories():
            for step in traj.steps:
                if ExperienceDistiller._hash_script(step.lua_script) == key:
                    return step
        # Fallback (shouldn't happen)
        from cmo_lua_agent.rl.trajectory import TrajectoryStep

        return TrajectoryStep(iteration=0, lua_script="", script_path="", reward=0.0, combat_metrics={})
