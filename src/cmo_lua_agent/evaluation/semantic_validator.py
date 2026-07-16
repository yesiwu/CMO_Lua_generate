"""
SemanticValidator: checks Lua scripts for correctness beyond syntax.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from cmo_lua_agent.generation.lua_generator import LuaGenerator

logger = logging.getLogger(__name__)

# Patterns that indicate common mistakes
_FORBIDDEN_PATTERNS = [
    (r"\bio\.open\b", "Forbidden: io.open is disabled in the Lua sandbox"),
    (r"\bio\.execute\b", "Forbidden: io.execute is disabled"),
    (r"\bdofile\b", "Forbidden: dofile is disabled"),
    (r"\bos\.execute\b", "Forbidden: os.execute is disabled"),
    (r"\bload\(", "Forbidden: raw load() is disabled"),
    (r"\brequire\s*\(", "Forbidden: require() is disabled"),
    (r"\bpackage\.", "Forbidden: package table access is restricted"),
]

_REQUIRED_PATTERNS = [
    (r"ScenEdit_AttackContact", "Missing: ScenEdit_AttackContact call"),
    (r"ScenEdit_SetUnit", "Warning: ScenEdit_SetUnit not found (reload step?)"),
]


class ValidationResult:
    """Result of a semantic validation pass."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def summary(self) -> str:
        parts = []
        if self.errors:
            parts.append(f"ERRORS ({len(self.errors)}): " + "; ".join(self.errors))
        if self.warnings:
            parts.append(f"WARNINGS ({len(self.warnings)}): " + "; ".join(self.warnings))
        if not parts:
            parts.append("OK")
        return " | ".join(parts)


class SemanticValidator:
    """
    Static-analysis checks on generated Lua code.

    Does NOT require running the script — uses regex + heuristic analysis.
    """

    def validate(self, lua_script: str) -> ValidationResult:
        """
        Check a Lua script for forbidden patterns and missing required calls.

        Parameters
        ----------
        lua_script : str

        Returns
        -------
        ValidationResult
        """
        result = ValidationResult()

        for pattern, message in _FORBIDDEN_PATTERNS:
            if re.search(pattern, lua_script):
                result.add_error(message)

        for pattern, message in _REQUIRED_PATTERNS:
            if not re.search(pattern, lua_script):
                result.add_warning(message)

        # Additional structural checks
        if "function" in lua_script and not re.search(r"\bend\b", lua_script):
            result.add_warning("Function declared but 'end' not found")

        # Check for obvious empty scripts
        stripped = lua_script.strip()
        if len(stripped) < 50:
            result.add_warning("Script seems unusually short")

        logger.debug("[SemanticValidator] %s", result.summary())
        return result
