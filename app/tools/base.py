from __future__ import annotations

from pathlib import Path
from typing import Protocol

import yaml
from pydantic import BaseModel, ConfigDict

from app.data.models import Geography
from app.data.repository import CensusRepository
from app.data.search_utils import match_rank
from app.tools.results import ToolResult

DESCRIPTIONS_PATH = Path(__file__).resolve().parent / "descriptions.yaml"


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Tool(Protocol):
    name: str
    description: str
    input_model: type[BaseModel]

    def run(self, repository: CensusRepository, input: BaseModel) -> ToolResult: ...


def load_tool_descriptions(path: Path | None = None) -> dict[str, str]:
    descriptions_path = path or DESCRIPTIONS_PATH
    raw = yaml.safe_load(descriptions_path.read_text(encoding="utf-8"))
    notes = raw.pop("notes", {})
    descriptions = {key: str(value).strip() for key, value in raw.items()}
    if isinstance(notes, dict) and "measurement_period" in notes:
        descriptions["_measurement_period_note"] = str(notes["measurement_period"]).strip()
    return descriptions


def measurement_period_note() -> str:
    return load_tool_descriptions()["_measurement_period_note"]


def relaxed_geography_suggestions(
    repository: CensusRepository,
    query: str,
    *,
    limit: int,
) -> list[str]:
    candidates: dict[str, tuple[int, str]] = {}
    search_terms = _relaxed_search_terms(query)
    for term in search_terms:
        result = repository.search_geographies(term, None, limit=limit)
        for geography in result.rows:
            rank = match_rank(geography.name, term)
            existing = candidates.get(geography.name)
            if existing is None or rank < existing[0]:
                candidates[geography.name] = (rank, geography.name)
    ranked = sorted(candidates.values(), key=lambda item: (item[0], item[1].lower()))
    return [name for _, name in ranked[:limit]]


def relaxed_variable_suggestions(
    repository: CensusRepository,
    query: str,
    *,
    limit: int,
) -> list[str]:
    candidates: dict[str, tuple[int, str]] = {}
    for term in _relaxed_search_terms(query):
        result = repository.search_variables(term, None, limit=limit)
        for variable in result.rows:
            rank = min(
                match_rank(variable.field_id, term),
                match_rank(variable.name, term),
            )
            suggestion = f"{variable.name} ({variable.field_id})"
            existing = candidates.get(suggestion)
            if existing is None or rank < existing[0]:
                candidates[suggestion] = (rank, suggestion)
    ranked = sorted(candidates.values(), key=lambda item: (item[0], item[1].lower()))
    return [name for _, name in ranked[:limit]]


def geography_candidate_models(geographies: list[Geography]) -> list[BaseModel]:
    return [geography.model_copy() for geography in geographies]


def _relaxed_search_terms(query: str) -> list[str]:
    stripped = query.strip()
    terms = [stripped]
    if len(stripped) > 3:
        terms.append(stripped[:3])
    for token in stripped.split():
        if len(token) >= 3:
            terms.append(token)
    deduped: list[str] = []
    for term in terms:
        if term and term not in deduped:
            deduped.append(term)
    return deduped
