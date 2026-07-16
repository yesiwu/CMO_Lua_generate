"""
CandidateGenerator: produces one or more Lua script candidates per generation call.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from cmo_lua_agent.generation.strategy_spec import StrategySpec
from cmo_lua_agent.generation.strategy_generator import StrategyGenerator

logger = logging.getLogger(__name__)


class CandidateGenerator:
    """
    Wraps LLM + prompt construction to produce Lua candidates.

    Supports both single-shot and beam / diverse-candidate generation.

    Parameters
    ----------
    strategy_generator : StrategyGenerator
        Builds the prompt from a StrategySpec.
    llm_client : Any
        Chat-completion client (DeepSeek / OpenAI compatible).
    beam_width : int
        Number of candidates to generate in parallel (default 1).
    temperature : float
        LLM sampling temperature.
    """

    def __init__(
        self,
        strategy_generator: StrategyGenerator,
        llm_client: Any,
        beam_width: int = 1,
        temperature: float = 0.7,
    ) -> None:
        self.strategy_generator = strategy_generator
        self.llm_client = llm_client
        self.beam_width = beam_width
        self.temperature = temperature

    def generate(
        self,
        spec: StrategySpec,
        examples: list[str] | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        Generate one or more Lua script candidates.

        Returns
        -------
        list[str]
            List of Lua script strings (length = beam_width).
        """
        system_prompt, user_prompt = self.strategy_generator.generate_prompt(
            spec, examples=examples, additional_context=additional_context
        )

        if self.beam_width == 1:
            response = self._call_llm(system_prompt, user_prompt, self.temperature)
            return [self._strip_markdown(response)]

        # Beam search: generate multiple candidates
        candidates = []
        for i in range(self.beam_width):
            temp = self.temperature + i * 0.1  # slight temperature variation
            response = self._call_llm(system_prompt, user_prompt, temp)
            candidates.append(self._strip_markdown(response))

        return candidates

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _call_llm(
        self, system_prompt: str, user_prompt: str, temperature: float
    ) -> str:
        response = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return response.get("content", "")

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove ```lua … ``` wrappers if present."""
        text = text.strip()
        if text.startswith("```"):
            _, _, rest = text.partition("\n")
            if rest.endswith("```"):
                rest = rest[:-3]
            return rest.strip()
        return text
