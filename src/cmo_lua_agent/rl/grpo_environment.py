"""
GRPOEnvironment: the RL environment for Group Relative Policy Optimisation.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Optional

from cmo_lua_agent.evaluation.combat_metrics import CombatMetrics
from cmo_lua_agent.evaluation.combat_result_parser import CombatResultParser
from cmo_lua_agent.evaluation.reward import RewardComputer

logger = logging.getLogger(__name__)


class GRPOEnvironment:
    """
    GRPO environment: given a task spec, generates a Lua script and returns reward.

    One "episode" = generate script → execute in CMO → compute reward.

    Parameters
    ----------
    cmo_executable : Path | str
    scenario_path : Path | str
    output_dir : Path | str
        Base directory for per-episode outputs.
    reward_config : RewardConfig, optional
        Passed to RewardComputer.
    """

    def __init__(
        self,
        cmo_executable: Path | str,
        scenario_path: Path | str,
        output_dir: Path | str,
        reward_config: Optional[Any] = None,
    ) -> None:
        self.cmo_executable = Path(cmo_executable)
        self.scenario_path = Path(scenario_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reward_computer = RewardComputer(reward_config)
        self.parser = CombatResultParser()
        self._episode_count = 0

    def reset(self) -> str:
        """Return the episode_id for the next episode."""
        self._episode_id = uuid.uuid4().hex[:8]
        self._episode_dir = self.output_dir / f"grpo_ep_{self._episode_id}"
        self._episode_dir.mkdir(parents=True, exist_ok=True)
        self._episode_count += 1
        return self._episode_id

    def step(self, lua_script: str) -> tuple[CombatMetrics, float, bool]:
        """
        Execute one GRPO step.

        Parameters
        ----------
        lua_script : str
            The candidate Lua script.

        Returns
        -------
        tuple[CombatMetrics, float, bool]
            (metrics, reward, done)
            done is always True (one script = one episode).
        """
        # Write script
        script_path = self._episode_dir / f"candidate_{self._episode_count}.lua"
        script_path.write_text(lua_script, encoding="utf-8")

        # Execute via CMO
        from cmo_lua_agent.execution.cmo_runner import CmoRunner

        runner = CmoRunner(self.cmo_executable, self.scenario_path)
        result = runner.run(script_path)

        # Parse results
        db_path = self._episode_dir / "events.db"
        if result.sqlite_path and Path(result.sqlite_path).exists():
            db_path = Path(result.sqlite_path)

        metrics = self.parser.parse(
            db_path,
            run_id=self._episode_id,
            script_name=script_path.name,
        )
        reward = self.reward_computer.compute(metrics)

        logger.info(
            "[GRPO] ep=%s script=%s reward=%.4f hits=%d kills=%d",
            self._episode_id,
            script_path.name,
            reward,
            metrics.total_hits(),
            metrics.total_kills(),
        )

        return metrics, reward, True

    @property
    def episode_dir(self) -> Path:
        return self._episode_dir
