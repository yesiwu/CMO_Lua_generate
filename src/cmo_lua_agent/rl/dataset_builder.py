"""
DatasetBuilder: builds SFT / GRPO datasets from TrajectoryStore.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterator, Optional

from cmo_lua_agent.rl.trajectory_store import TrajectoryStore
from cmo_lua_agent.rl.trajectory import Trajectory

logger = logging.getLogger(__name__)


class DatasetEntry:
    """A single (instruction, lua_script, reward) training example."""

    __slots__ = ("instruction", "lua_script", "reward", "run_id", "iteration")

    def __init__(
        self,
        instruction: str,
        lua_script: str,
        reward: float,
        run_id: str = "",
        iteration: int = 0,
    ) -> None:
        self.instruction = instruction
        self.lua_script = lua_script
        self.reward = reward
        self.run_id = run_id
        self.iteration = iteration

    def to_dict(self) -> dict[str, Any]:
        return {
            "instruction": self.instruction,
            "lua_script": self.lua_script,
            "reward": self.reward,
            "run_id": self.run_id,
            "iteration": self.iteration,
        }


class TrajectoryDataset:
    """In-memory dataset backed by a list of DatasetEntry."""

    def __init__(self, entries: list[DatasetEntry] | None = None) -> None:
        self.entries: list[DatasetEntry] = entries or []

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[DatasetEntry]:
        return iter(self.entries)

    def save(self, path: Path | str) -> None:
        """Write as JSON Lines (one JSON object per line)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for entry in self.entries:
                fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        logger.info("[TrajectoryDataset] Saved %d entries to %s", len(self.entries), path)

    @classmethod
    def load(cls, path: Path | str) -> "TrajectoryDataset":
        """Load from JSON Lines."""
        path = Path(path)
        entries = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                entries.append(
                    DatasetEntry(
                        instruction=d.get("instruction", ""),
                        lua_script=d.get("lua_script", ""),
                        reward=d.get("reward", 0.0),
                        run_id=d.get("run_id", ""),
                        iteration=d.get("iteration", 0),
                    )
                )
        logger.info("[TrajectoryDataset] Loaded %d entries from %s", len(entries), path)
        return cls(entries)


class DatasetBuilder:
    """
    Converts TrajectoryStore → TrajectoryDataset.

    The dataset can be used directly for SFT or processed further for GRPO.
    """

    def build(
        self,
        store: TrajectoryStore,
        min_reward: float = -0.5,
        filter_repeated: bool = True,
    ) -> TrajectoryDataset:
        """
        Parameters
        ----------
        store : TrajectoryStore
            Source trajectories.
        min_reward : float
            Drop examples below this reward.
        filter_repeated : bool
            Deduplicate identical scripts.

        Returns
        -------
        TrajectoryDataset
        """
        seen_scripts: set[str] = set()
        entries: list[DatasetEntry] = []

        for traj in store.trajectories():
            for step in traj.steps:
                if step.reward < min_reward:
                    continue

                if filter_repeated:
                    import hashlib

                    key = hashlib.md5(step.lua_script.encode()).hexdigest()
                    if key in seen_scripts:
                        continue
                    seen_scripts.add(key)

                # Instruction is reconstructed from combat_metrics if available
                instruction = self._build_instruction(step.combat_metrics)

                entries.append(
                    DatasetEntry(
                        instruction=instruction,
                        lua_script=step.lua_script,
                        reward=step.reward,
                        run_id=traj.run_id,
                        iteration=step.iteration,
                    )
                )

        logger.info(
            "[DatasetBuilder] Built dataset with %d entries (filtered from store)",
            len(entries),
        )
        return TrajectoryDataset(entries)

    @staticmethod
    def _build_instruction(combat_metrics: dict[str, Any]) -> str:
        """Reconstruct the task instruction from metrics metadata."""
        mission = combat_metrics.get("mission_type", "TOT")
        side = combat_metrics.get("side", "Blue")
        objectives = combat_metrics.get("objectives", [])
        if isinstance(objectives, list):
            obj_str = "; ".join(objectives)
        else:
            obj_str = str(objectives)
        return f"Generate a {mission} Lua script for {side} side. Objectives: {obj_str}"
