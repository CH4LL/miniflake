# S2: Tool layer

Status: see [roadmap.md](../roadmap.md). Estimate: 2 h. Depends on S1.

## Goal

Typed tools that the LLM can call, each mapping to one or two repository methods and returning a result whose shape makes ambiguity, absence and unavailability explicit. The tool layer is where "this cannot be answered from the data" becomes a value rather than a hallucination opportunity.

## Scope

1. Tool contract: input model, result model, `run` function, LLM-facing description.
2. Six tools: `find_geography`, `find_variable`, `get_value`, `rank_geographies`, `get_trend`, `compare`.
3. `ToolRegistry` producing JSON Schema tool definitions and dispatching calls by name.
4. Outcome types shared by all tools.
5. Tool descriptions authored for the LLM, stored alongside each tool.

## Out of scope

Calling the LLM, prompt composition, natural-language answer text.

## Tool contract (`app/tools/base.py`)

```python
class Tool(Protocol):
    name: str
    description: str
    input_model: type[BaseModel]

    def run(self, repository: CensusRepository, input: BaseModel) -> ToolResult: ...
```

`ToolResult` is a discriminated union:

- `Success(data: BaseModel, provenance: list[Provenance])`
- `Ambiguous(candidates: list[BaseModel], hint: str)`: more than one plausible match; `hint` tells the model how to disambiguate (e.g. ask for the state).
- `NotFound(what: str, suggestions: list[str])`: nothing matched; `suggestions` are close alternatives from the catalog.
- `PeriodUnavailable(requested: str, available: list[str])`: the geography and variable exist but not for the requested date or period.
- `UnsupportedRequest(reason: str)`: the request is well-formed but the dataset cannot express it (e.g. median or rate at state/county level, tract or street level, a variable outside the curated catalog).
- `ToolError(message: str, retryable: bool)`: repository failure.

Every variant serializes to JSON for the LLM with a `kind` discriminator.

## Tools

### find_geography

Input: `query: str`, `level: GeoLevel | None`, `within_state: str | None`.
Behaviour: search the repository; a single exact match at the requested level is `Success`; multiple matches with different parents is `Ambiguous` listing name, level and state for each; no match is `NotFound` with the closest names.

### find_variable

Input: `query: str`, `topic: str | None`.
Behaviour: search the curated catalog; return `Success` with up to a configured number of candidates ranked by match quality when they belong to the same series, `Ambiguous` when candidates span different series, `NotFound` with topic suggestions otherwise.

### get_value

Input: `field_id: str`, `geo_id: str`, `vintage: int | None`.
Behaviour: resolve the variable's `aggregation_kind` and the geography level. Count fields at rolled-up geography use repository SUM rollup; median/rate fields at rolled-up geography return `UnsupportedRequest` explaining block-group-only availability. Block-group reads are direct. Return `Success` with value, vintage, `aggregation_method` and geography name. If the vintage is not available, return `PeriodUnavailable` with the available vintages.

### rank_geographies

Input: `field_id: str`, `level: GeoLevel`, `within_geo_id: str | None`, `vintage: int | None`, `order: "asc" | "desc"`, `limit: int`.
Behaviour: rank at the given level, optionally within a parent. Only `count` fields are supported at rolled-up levels; median/rate fields return `UnsupportedRequest`. Return `Success` with an ordered list of (geography, value).

### get_trend

Input: `field_id: str`, `geo_id: str`, `start_year: int | None`, `end_year: int | None`.
Behaviour: return the time series via `get_time_series` (level-aware rollup in the repository). Include a note that all vintages are ACS 5-year estimates with overlapping measurement windows across consecutive vintages.

### compare

Input: `field_id: str`, `geo_ids: list[str]` (2 to a configured maximum), `vintage: int | None`.
Behaviour: fetch observations for all geographies at a common vintage. If a common vintage does not exist, return `PeriodUnavailable` listing vintages per geography. Return `Success` with values and the absolute and relative difference between the first two entries.

## Registry (`app/tools/registry.py`)

- `register(tool)`; duplicate names raise at startup.
- `schemas()` returns the list of tool definitions in the provider-neutral shape `{name, description, input_schema}` derived from the pydantic model with `additionalProperties: false`.
- `dispatch(name, raw_input, repository)` validates input against the model, runs the tool, catches `RepositoryError` into `ToolError`, and catches validation errors into `UnsupportedRequest` with the validation message, so the LLM can self-correct.
- `default_registry(settings)` registers the six tools; tools can be disabled by configuration to support the cut policy.

## Provenance

Each `Success` carries the list of `Provenance` objects from every repository call it made. The composer in S3 renders these; tools must not drop or merge them.

## Acceptance criteria

- Given the fake repository, when `find_geography("Texas", level=State)` runs, then the result is `Success` with the Texas geography.
- Given `find_geography("Orange County")`, then the result is `Ambiguous` with candidates in more than one state and a hint mentioning the state.
- Given `find_geography("Atlantis")`, then the result is `NotFound` naming the query, with suggestions when the relaxed search finds near matches.
- Given `get_value` for a valid variable and geography with a year outside the fixture range, then the result is `PeriodUnavailable` listing the available years.
- Given `get_value` with no vintage, then the result uses the latest vintage and provenance names it.
- Given `get_value` for a median field at county level, then the result is `UnsupportedRequest`.
- Given `get_value` for a median field at block group level, then the result is `Success` with `aggregation_method: direct`.
- Given `rank_geographies` for a count field at level `County` within a state, then the results all have that state as parent and are ordered as requested.
- Given `rank_geographies` for a median field at any rolled-up level, then the result is `UnsupportedRequest`.
- Given `compare` with geographies that share no date, then the result is `PeriodUnavailable`.
- Given `compare` with one geo id, then dispatch returns `UnsupportedRequest` describing the minimum.
- Given a repository that raises `RepositoryError`, when any tool is dispatched, then the result is `ToolError` and nothing propagates.
- Given the registry, when `schemas()` is called, then every schema is valid JSON Schema, has `additionalProperties: false`, and the names are unique.
- Given a tool disabled in configuration, then it is absent from `schemas()` and dispatching it returns `UnsupportedRequest`.

## Tests to write first

1. `tests/unit/tools/test_results.py`: serialization of each `ToolResult` variant including the `kind` discriminator.
2. `tests/unit/tools/test_registry.py`: schema generation, duplicate registration, dispatch validation, error wrapping, disabled tools.
3. `tests/component/tools/test_find_geography.py`, `test_find_variable.py`, `test_get_value.py`, `test_rank_geographies.py`, `test_get_trend.py`, `test_compare.py`: each covering `Success` and every applicable outcome against `FakeCensusRepository`.

## Files

- `app/tools/__init__.py`, `base.py`, `results.py`, `registry.py`, `descriptions.yaml`
- `app/tools/find_geography.py`, `find_variable.py`, `get_value.py`, `rank_geographies.py`, `get_trend.py`, `compare.py`
- tests listed above

## Documentation updates at stage end

- `ARCHITECTURE.md`: tool list and outcome types.
- `docs/EXTENDING.md`: "add a tool" section written against the real contract.
- `CHANGELOG.md`, `docs/roadmap.md`.
