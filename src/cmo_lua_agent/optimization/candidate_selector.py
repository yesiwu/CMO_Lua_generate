"""
CandidateSelector: selects the next Lua script to try based on history & diversity.
"""
from __future__ import annotations

import hashlib
import logging
import random
from typing import Optional

from cmo_lua_agent.orchestration.workflow_context import WorkflowContext
from cmo_lua_agent.orchestration.optimization_state import OptimizationState
from cmo_lua_agent.generation.strategy_spec import StrategySpec
from cmo_lua_agent.generation.candidate_generator import CandidateGenerator

logger = logging.getLogger(__name__)


class CandidateSelector:
    """
    Wraps CandidateGenerator and adds experience-guided selection:

    - If no history: generate from the StrategySpec directly.
    - If there is history: sample a previously-seen good script as a template
      (mutation / crossover) and call the generator on that.
    """

    def __init__(
        self,
        candidate_generator: Optional[CandidateGenerator] = None,
        diversity_threshold: float = 0.7,
        use_template_prob: float = 0.5,
    ) -> None:
        """
        Parameters
        ----------
        candidate_generator : CandidateGenerator
            The underlying LLM-based generator.
        diversity_threshold : float
            Scripts with hash similarity above this threshold are considered
            "too similar" to the best known script.
        use_template_prob : float
            Probability of using a template script vs. generating from scratch.
        """
        self.candidate_generator = candidate_generator
        self.diversity_threshold = diversity_threshold
        self.use_template_prob = use_template_prob

    def select(
        self,
        state: OptimizationState,
        ctx: WorkflowContext,
        spec: Optional[StrategySpec] = None,
    ) -> str:
        """
        Return the next Lua script candidate.

        Parameters
        ----------
        state : OptimizationState
            Current optimisation state (history, best script, etc.).
        ctx : WorkflowContext
            Workflow context (LLM client, etc.).
        spec : StrategySpec, optional
            Task spec.  Required when no history exists.

        Returns
        -------
        str
            Lua script source.
        """
        if self.candidate_generator is None:
            raise RuntimeError("CandidateSelector requires a CandidateGenerator")

        # No history → generate from spec
        if not state.history:
            if spec is None:
                raise ValueError("spec required on first iteration")
            candidates = self.candidate_generator.generate(spec)
            return candidates[0]

        # Decide: use template or generate fresh?
        use_template = random.random() < self.use_template_prob

        if use_template and state.best_script:
            template = state.best_script
            additional_context = {"template_hint": "mutate_from_best"}
        else:
            template = ""
            additional_context = None

        # Build a spec if not provided
        if spec is None:
            spec = StrategySpec()

        candidates = self.candidate_generator.generate(
            spec,
            additional_context=additional_context,
        )
        script = candidates[0]

        # Diversity guard: reject too-similar scripts
        if self._too_similar(script, state):
            logger.info("[selector] Script too similar to best, adding noise")
            script = self._inject_diversity(script)

        return script

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _too_similar(self, script: str, state: OptimizationState) -> bool:
        if not state.best_script:
            return False
        a = set(script.split())
        b = set(state.best_script.split())
        if not a or not b:
            return False
        overlap = len(a & b) / max(len(a), len(b))
        return overlap >= self.diversity_threshold

    @staticmethod
    def _inject_diversity(script: str) -> str:
        """Inject a small random variation to force differentiation."""
        lines = script.splitlines()
        if len(lines) < 3:
            return script
        # Flip a random numeric constant
        import random, re

        def replacer(m: re.Match) -> str:
            val = int(m.group(1))
            delta = random.choice([-1, 1]) * random.randint(1, 5)
            return f"{max(0, val + delta)}"

        modified = re.sub(r"\b(\d{1,4})\b", replacer, script)
        return modified
