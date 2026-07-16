"""
StrategyGenerator: converts a StrategySpec into a text prompt for the LLM.
"""
from __future__ import annotations

import logging
from typing import Any

from cmo_lua_agent.generation.strategy_spec import StrategySpec

logger = logging.getLogger(__name__)

# System-prompt template shared across all generation calls
_SYSTEM_TEMPLATE = """\
You are a Lua scripting expert for Command: Modern Operations (CMO).

Write Lua scripts that:
1. Use only the ScenEdit_* API (no io/dofile/os.execute).
2. Prefer ScenEdit_AttackContact(unitname, contact_guid, mode) with mode=0.
3. Use ScenEdit_AddUnit / ScenEdit_AddMission for programmatic unit creation.
4. Include a reload step (ScenEdit_SetUnit with new weapon DBID) before firing.
5. Use retry logic with ScenEdit_CurrentTime() instead of busy-wait loops.
6. Log all actions with print() for traceability.

Output ONLY the Lua script. No markdown, no explanations.
"""


class StrategyGenerator:
    """
    Transforms a high-level StrategySpec into a detailed prompt for the LLM.

    The actual code generation is done by `LuaGenerator` which calls the LLM
    with the prompt produced here.
    """

    def __init__(self, system_template: str = _SYSTEM_TEMPLATE) -> None:
        self.system_template = system_template

    def generate_prompt(
        self,
        spec: StrategySpec,
        examples: list[str] | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """
        Returns (system_prompt, user_prompt) suitable for an LLM chat completion.

        Parameters
        ----------
        spec : StrategySpec
            Task specification.
        examples : list[str], optional
            Example Lua scripts (in-context few-shot).
        additional_context : dict, optional
            Extra key-value pairs to inject into the prompt.
        """
        user_parts = [spec.to_prompt_context(), "", "Generate the Lua script."]

        if examples:
            user_parts.insert(1, "Examples for reference:")
            for i, ex in enumerate(examples):
                user_parts.insert(2 + i, f"-- Example {i+1}\n{ex}")

        if additional_context:
            user_parts.append("\nAdditional context:")
            for k, v in additional_context.items():
                user_parts.append(f"  {k}: {v}")

        user_prompt = "\n".join(user_parts)
        system_prompt = self.system_template

        logger.debug("[StrategyGenerator] prompt length=%d", len(user_prompt))
        return system_prompt, user_prompt
