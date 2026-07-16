"""
ExperienceRetriever: retrieves relevant historical experiences for few-shot prompting.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from cmo_lua_agent.memory.experience_store import ExperienceStore

logger = logging.getLogger(__name__)


class ExperienceRetriever:
    """
    Retrieves the most relevant historical Lua scripts for a given task,
    to be used as few-shot examples in the LLM prompt.

    Parameters
    ----------
    store : ExperienceStore
        Source of historical experiences.
    max_examples : int
        Maximum examples to return per retrieval.
    min_reward : float
        Only consider experiences with reward >= this.
    """

    def __init__(
        self,
        store: ExperienceStore,
        max_examples: int = 3,
        min_reward: float = 0.0,
    ) -> None:
        self.store = store
        self.max_examples = max_examples
        self.min_reward = min_reward

    def retrieve(
        self,
        task_description: str,
        mission_type: str = "",
        side: str = "",
    ) -> list[dict[str, Any]]:
        """
        Find the most relevant historical experiences.

        Strategy:
        1. If mission_type + side are known, use best_for_mission.
        2. Otherwise fall back to keyword search on task_description.

        Parameters
        ----------
        task_description : str
            Free-text description of the current task.
        mission_type : str, optional
        side : str, optional

        Returns
        -------
        list[dict]  -- each dict has keys: task_description, lua_script, reward
        """
        results: list[dict[str, Any]] = []

        # Priority 1: mission + side lookup
        if mission_type and side:
            results = list(
                self.store.best_for_mission(
                    mission_type, side, top_k=self.max_examples
                )
            )
            if results:
                logger.debug(
                    "[retriever] mission+side hit: %s/%s → %d examples",
                    mission_type,
                    side,
                    len(results),
                )

        # Priority 2: keyword search
        if len(results) < self.max_examples:
            keyword_results = list(
                self.store.search(
                    task_description,
                    top_k=self.max_examples,
                    min_reward=self.min_reward,
                )
            )
            for r in keyword_results:
                if r not in results:
                    results.append(r)
            results = results[: self.max_examples]

        logger.info(
            "[retriever] retrieved %d examples for task: %.40s",
            len(results),
            task_description[:40],
        )
        return results

    def format_for_prompt(
        self,
        experiences: list[dict[str, Any]],
        include_reward: bool = True,
    ) -> str:
        """
        Format retrieved experiences as a string for LLM prompt injection.

        Parameters
        ----------
        experiences : list[dict]
            Output from retrieve().
        include_reward : bool
            If True, prepend reward as a comment so the LLM sees the outcome.

        Returns
        -------
        str
            Multi-line string suitable for prepending to the user prompt.
        """
        if not experiences:
            return ""

        parts = ["-- Few-shot examples from previous runs:"]
        for i, exp in enumerate(experiences, 1):
            if include_reward:
                parts.append(f"-- Example {i} (reward={exp.get('reward', 0):.2f})")
            else:
                parts.append(f"-- Example {i}")
            parts.append(exp.get("lua_script", ""))
            parts.append("")

        return "\n".join(parts)
