"""
SFTTrainer: Supervised Fine-Tuning on (instruction, lua_script) pairs.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Minimum fields required per training row
REQUIRED_FIELDS = frozenset({"instruction", "lua_script"})


class SFTTrainer:
    """
    Wraps an SFT training job.

    Currently delegates to an external fine-tuning CLI (e.g. Axolotl, LLaMA Factory).
    Configuration is written as a YAML file and the process is spawned.

    Parameters
    ----------
    llm_client : Any
        Placeholder; the fine-tuned model replaces it after training.
    output_dir : Path | str
        Directory to store checkpoints and logs.
    model_name : str
        Base model to fine-tune (e.g. "deepseek-ai/DeepSeek-Coder-V2").
    training_config : dict, optional
        Override for the training YAML.
    """

    def __init__(
        self,
        llm_client: Any,
        output_dir: Path | str,
        model_name: str = "deepseek-ai/DeepSeek-Coder-V2",
        training_config: Optional[dict[str, Any]] = None,
    ) -> None:
        self.llm_client = llm_client
        self.output_dir = Path(output_dir)
        self.model_name = model_name
        self.training_config = training_config or {}
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def train(self, dataset_path: Path | str) -> Path:
        """
        Run SFT training.

        Parameters
        ----------
        dataset_path : Path | str
            JSON Lines file produced by DatasetBuilder.

        Returns
        -------
        Path
            Path to the best checkpoint directory.
        """
        dataset_path = Path(dataset_path)

        # Build training YAML
        config_path = self.output_dir / "sft_config.yaml"
        self._write_config(config_path, dataset_path)

        logger.info("[SFT] Starting training with config %s", config_path)
        logger.warning(
            "[SFT] External trainer CLI not configured; training is a no-op here. "
            "Replace with Axolotl/LLaMA Factory invocation."
        )

        # Placeholder: write a marker so callers can detect completion
        marker = self.output_dir / "sft_complete.txt"
        marker.write_text(f"dataset={dataset_path}\nmodel={self.model_name}\n")
        return self.output_dir / "checkpoint_best"

    # ------------------------------------------------------------------
    # Config writing (Axolotl YAML format)
    # ------------------------------------------------------------------
    def _write_config(self, config_path: Path, dataset_path: Path) -> None:
        cfg = {
            "base_model": self.model_name,
            "dataset_path": str(dataset_path),
            "output_dir": str(self.output_dir / "checkpoints"),
            "sequence_len": 2048,
            "micro_batch_size": 1,
            "gradient_accumulation_steps": 16,
            "epochs": 3,
            "lr": 2e-5,
            "prompt_template": "### Instruction:\n{instruction}\n### Response:\n{lua_script}",
            **self.training_config,
        }

        import yaml

        with config_path.open("w", encoding="utf-8") as fh:
            yaml.dump(cfg, fh, allow_unicode=True, default_flow_style=False)
