from __future__ import annotations

from pydantic import BaseModel

from app.config import Settings
from app.data.catalog import load_state_fips_names
from app.data.models import GeoLevel
from app.data.repository import CensusRepository
from app.tools.base import (
    ToolInput,
    geography_candidate_models,
    relaxed_geography_suggestions,
)
from app.tools.results import Ambiguous, NotFound, Success, ToolResult


class FindGeographyInput(ToolInput):
    query: str
    level: GeoLevel | None = None
    within_state: str | None = None


class FindGeographyTool:
    name = "find_geography"
    input_model = FindGeographyInput

    def __init__(self, settings: Settings, description: str) -> None:
        self.description = description
        self._settings = settings
        self._state_fips = {
            state["abbreviation"].upper(): state["fips"]
            for state in load_state_fips_names(settings.state_fips_names_file())
        }
        self._state_names = {
            state["name"].lower(): state["fips"]
            for state in load_state_fips_names(settings.state_fips_names_file())
        }

    def run(self, repository: CensusRepository, input: BaseModel) -> ToolResult:
        payload = FindGeographyInput.model_validate(input)
        lowered_query = payload.query.lower()
        if any(
            marker in lowered_query
            for marker in ("city of", "metro area", "metropolitan area", "cbsa", "census tract")
        ):
            return NotFound(
                what=payload.query,
                suggestions=[
                    "Use state, county, or block-group geographies supported by this dataset."
                ],
            )
        result = repository.search_geographies(
            payload.query,
            payload.level,
            self._settings.repository_search_limit,
        )
        provenance = [result.provenance]
        rows = list(result.rows)
        if payload.within_state:
            state = self._resolve_state(payload.within_state)
            if state is None:
                return NotFound(
                    what=payload.within_state,
                    suggestions=sorted(self._state_names.keys())[
                        : self._settings.tool_suggestion_limit
                    ],
                )
            rows = [
                geography
                for geography in rows
                if (geography.level == GeoLevel.STATE and geography.geo_id == state["fips"])
                or (
                    geography.parent_geo_id is not None
                    and geography.parent_geo_id.startswith(state["fips"])
                )
                or (
                    geography.state_abbreviation is not None
                    and geography.state_abbreviation.upper() == state["abbreviation"]
                )
            ]
        if not rows:
            return NotFound(
                what=payload.query,
                suggestions=relaxed_geography_suggestions(
                    repository,
                    payload.query,
                    limit=self._settings.tool_suggestion_limit,
                ),
            )
        exact_matches = [
            geography for geography in rows if geography.name.lower() == payload.query.lower()
        ]
        if len(exact_matches) == 1:
            return Success(data=exact_matches[0], provenance=provenance)
        if len(rows) == 1:
            return Success(data=rows[0], provenance=provenance)
        hint = _ambiguity_hint(rows)
        return Ambiguous(candidates=geography_candidate_models(rows), hint=hint)

    def _resolve_state(self, value: str) -> dict[str, str] | None:
        normalized = value.strip()
        upper = normalized.upper()
        if upper in self._state_fips:
            return {
                "fips": self._state_fips[upper],
                "abbreviation": upper,
            }
        lower = normalized.lower()
        if lower in self._state_names:
            fips = self._state_names[lower]
            return {"fips": fips, "abbreviation": self._abbreviation_for_fips(fips)}
        return None

    def _abbreviation_for_fips(self, fips: str) -> str:
        for abbreviation, state_fips in self._state_fips.items():
            if state_fips == fips:
                return abbreviation
        return fips


def _ambiguity_hint(geographies: list) -> str:
    states = {geo.state_abbreviation for geo in geographies if geo.state_abbreviation}
    levels = {geo.level.value for geo in geographies}
    if len(states) > 1:
        return "Multiple matches in different states; ask which state is intended."
    if len(levels) > 1:
        return "Multiple matches at different geography levels; ask which level is intended."
    return "Multiple matches found; ask the user to clarify."
