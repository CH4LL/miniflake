from app.data.fake_repository import FakeCensusRepository
from app.tools.find_variable import FindVariableInput, FindVariableTool
from app.tools.results import Ambiguous, NotFound, Success


def _tool() -> FindVariableTool:
    from app.config import Settings

    settings = Settings(
        SNOWFLAKE_ACCOUNT="TEST",
        SNOWFLAKE_USER="TEST",
        SNOWFLAKE_ROLE="TEST",
        SNOWFLAKE_WAREHOUSE="TEST",
        SNOWFLAKE_DATABASE="TEST",
        SNOWFLAKE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        _env_file=None,
    )
    return FindVariableTool(settings, "search variables")


def test_find_total_population_success() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(repository, FindVariableInput(query="total population"))
    assert isinstance(result, Success)
    assert result.data.candidates
    assert result.data.candidates[0].field_id == "B01003e1"


def test_find_income_ambiguous() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(repository, FindVariableInput(query="income"))
    assert isinstance(result, Ambiguous)
    series_ids = {candidate.series_id for candidate in result.candidates}
    assert len(series_ids) > 1


def test_find_population_phrase_with_filler_words_succeeds() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(repository, FindVariableInput(query="how many people live"))
    assert isinstance(result, Success)
    assert result.data.candidates[0].field_id == "B01003e1"


def test_find_educated_resolves_via_alias() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(repository, FindVariableInput(query="how educated"))
    assert isinstance(result, Success)
    assert result.data.candidates[0].series_id == "B15003"


def test_find_unknown_variable_not_found() -> None:
    repository = FakeCensusRepository()
    result = _tool().run(repository, FindVariableInput(query="average iq"))
    assert isinstance(result, NotFound)
    assert result.what == "average iq"
