"""
项目配置加载与校验模块。

该模块负责从环境变量、.env 文件或配置文件中读取系统配置，
例如：
- LLM API Key；
- LLM Base URL；
- 模型名称；
- 最大输出 Token 数；
- 请求超时时间；
- CMO 执行命令；
- Skill 目录；
- 运行产物目录；
- 最大修复次数。

其他模块应通过本模块获取配置，避免在代码中直接写死路径、
模型名称、密钥或超时时间。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class LlmConfig:
    api_key: str
    base_url: str | None
    model_id: str
    max_tokens: int
    timeout_seconds: float
    max_retries: int


@dataclass(frozen=True)
class AppConfig:
    llm: LlmConfig


def _require_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(
            f"缺少环境变量 {name}，请检查项目根目录下的 .env 文件"
        )

    return value.strip()


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)

    if value is None:
        return None

    value = value.strip()
    return value or None


def load_config() -> AppConfig:
    load_dotenv(override=False)

    llm_config = LlmConfig(
        api_key=_require_env("ANTHROPIC_API_KEY"),
        base_url=_optional_env("ANTHROPIC_BASE_URL"),
        model_id=_require_env("MODEL_ID"),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "8000")),
        timeout_seconds=float(
            os.getenv("LLM_TIMEOUT_SECONDS", "120")
        ),
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
    )

    return AppConfig(llm=llm_config)