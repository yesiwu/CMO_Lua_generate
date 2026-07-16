"""
Workflow context: shared state & services available across all workflows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path

from cmo_lua_agent.execution.models import JobConfig
from cmo_lua_agent.memory.experience_store import ExperienceStore


@dataclass
class WorkflowContext:
    """Immutable-ish context container for workflow execution."""

    # Project / environment
    project_root: Path
    cmo_executable: Path
    scenario_path: Path

    # Output
    output_dir: Path

    # Optional overrides
    llm_client: Optional[Any] = None          # LLM client (DeepSeek / OpenAI)
    experience_store: Optional[ExperienceStore] = None

    # Job-level config (set per-run)
    job_config: Optional[JobConfig] = None

    # Scratch space for passing data between steps
    scratch: dict[str, Any] = field(default_factory=dict)

    def scratch_set(self, key: str, value: Any) -> None:
        self.scratch[key] = value

    def scratch_get(self, key: str, default: Any = None) -> Any:
        return self.scratch.get(key, default)
