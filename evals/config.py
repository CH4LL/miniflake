from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_PATH = Path(__file__).resolve().parent / "eval_config.yaml"


class EvalSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EVAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    latency_budget_seconds: float = Field(default=60.0, alias="LATENCY_BUDGET_SECONDS")
    http_timeout_seconds: float = Field(default=70.0, alias="HTTP_TIMEOUT_SECONDS")
    retry_count: int = Field(default=1, alias="RETRY_COUNT")
    default_tolerance_pct: float = Field(default=1.0, alias="DEFAULT_TOLERANCE_PCT")
    default_target_url: str = Field(
        default="https://miniflake-eowbm7u4ua-uk.a.run.app",
        alias="DEFAULT_TARGET_URL",
    )
    agent_input_price_per_million: float = Field(default=3.0, alias="AGENT_INPUT_PRICE_PER_MILLION")
    agent_output_price_per_million: float = Field(
        default=15.0, alias="AGENT_OUTPUT_PRICE_PER_MILLION"
    )
    classifier_input_price_per_million: float = Field(
        default=0.8, alias="CLASSIFIER_INPUT_PRICE_PER_MILLION"
    )
    classifier_output_price_per_million: float = Field(
        default=4.0, alias="CLASSIFIER_OUTPUT_PRICE_PER_MILLION"
    )


def _load_yaml_defaults() -> dict[str, object]:
    if not CONFIG_PATH.exists():
        return {}
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


@lru_cache
def get_eval_settings() -> EvalSettings:
    defaults = _load_yaml_defaults()
    return EvalSettings(**defaults)
