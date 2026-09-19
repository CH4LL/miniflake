from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

from app.config import Settings
from app.data.catalog import load_variable_catalog_spec
from app.data.models import GeoLevel
from app.tools.registry import ToolRegistry

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"
TEMPLATES_PATH = PROMPTS_DIR / "templates.yaml"


def load_templates(path: Path | None = None) -> dict[str, str]:
    templates_path = path or TEMPLATES_PATH
    raw = yaml.safe_load(templates_path.read_text(encoding="utf-8"))
    return {key: str(value).strip() for key, value in raw.items()}


def build_system_prompt(
    registry: ToolRegistry,
    settings: Settings,
    *,
    context_facts: list[str],
) -> str:
    catalog = load_variable_catalog_spec(settings.variable_catalog_spec_file())
    topics = sorted({series.topic for series in catalog.series})
    template = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    environment = Environment(undefined=StrictUndefined, autoescape=False)
    return environment.from_string(template).render(
        tools=registry.schemas(),
        geography_levels=[level.value for level in GeoLevel],
        topics=topics,
        vintages=settings.acs_vintages,
        context_facts=context_facts,
    )
