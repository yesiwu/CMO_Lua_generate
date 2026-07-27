"""Stable machine-readable errors shared by Phase 7 and Phase 8."""

from __future__ import annotations


class SkillEvolutionError(ValueError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def fail(error_code: str, message: str) -> SkillEvolutionError:
    return SkillEvolutionError(error_code, message)
