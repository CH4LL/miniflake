from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="miniflake", alias="APP_NAME")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    health_version: str = Field(default="0.1.0", alias="HEALTH_VERSION")

    snowflake_account: str = Field(alias="SNOWFLAKE_ACCOUNT")
    snowflake_user: str = Field(alias="SNOWFLAKE_USER")
    snowflake_role: str = Field(alias="SNOWFLAKE_ROLE")
    snowflake_warehouse: str = Field(alias="SNOWFLAKE_WAREHOUSE")
    snowflake_database: str = Field(alias="SNOWFLAKE_DATABASE")
    snowflake_schema: str = Field(default="PUBLIC", alias="SNOWFLAKE_SCHEMA")
    snowflake_private_key_path: str | None = Field(default=None, alias="SNOWFLAKE_PRIVATE_KEY_PATH")
    snowflake_private_key: str | None = Field(default=None, alias="SNOWFLAKE_PRIVATE_KEY")
    snowflake_private_key_passphrase: str | None = Field(
        default=None, alias="SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"
    )

    snowflake_statement_timeout_seconds: int = Field(
        default=60, alias="SNOWFLAKE_STATEMENT_TIMEOUT_SECONDS"
    )
    snowflake_query_tag: str = Field(default="miniflake", alias="SNOWFLAKE_QUERY_TAG")
    snowflake_max_rows: int = Field(default=1000, alias="SNOWFLAKE_MAX_ROWS")
    snowflake_retry_attempts: int = Field(default=3, alias="SNOWFLAKE_RETRY_ATTEMPTS")
    snowflake_retry_backoff_seconds: float = Field(
        default=0.5, alias="SNOWFLAKE_RETRY_BACKOFF_SECONDS"
    )
    repository_search_limit: int = Field(default=25, alias="REPOSITORY_SEARCH_LIMIT")
    acs_vintages: list[int] = Field(default=[2019, 2020], alias="ACS_VINTAGES")
    nation_geo_id: str = Field(default="US", alias="NATION_GEO_ID")
    acs_wide_table_template: str = Field(
        default="{vintage}_CBG_{series_prefix}", alias="ACS_WIDE_TABLE_TEMPLATE"
    )
    metadata_field_descriptions_template: str = Field(
        default="{vintage}_METADATA_CBG_FIELD_DESCRIPTIONS",
        alias="METADATA_FIELD_DESCRIPTIONS_TEMPLATE",
    )
    metadata_fips_codes_template: str = Field(
        default="{vintage}_METADATA_CBG_FIPS_CODES",
        alias="METADATA_FIPS_CODES_TEMPLATE",
    )
    metadata_geographic_data_template: str = Field(
        default="{vintage}_METADATA_CBG_GEOGRAPHIC_DATA",
        alias="METADATA_GEOGRAPHIC_DATA_TEMPLATE",
    )
    fixtures_dir: str = Field(default="fixtures", alias="FIXTURES_DIR")
    variable_catalog_spec_path: str = Field(
        default="fixtures/variable_catalog_spec.yaml",
        alias="VARIABLE_CATALOG_SPEC_PATH",
    )
    state_fips_names_path: str = Field(
        default="fixtures/state_fips_names.json",
        alias="STATE_FIPS_NAMES_PATH",
    )
    tool_max_variable_candidates: int = Field(default=5, alias="TOOL_MAX_VARIABLE_CANDIDATES")
    tool_max_geography_candidates: int = Field(default=5, alias="TOOL_MAX_GEOGRAPHY_CANDIDATES")
    tool_rank_limit_max: int = Field(default=25, alias="TOOL_RANK_LIMIT_MAX")
    tool_compare_max_geographies: int = Field(default=5, alias="TOOL_COMPARE_MAX_GEOGRAPHIES")
    tool_suggestion_limit: int = Field(default=5, alias="TOOL_SUGGESTION_LIMIT")
    disabled_tools: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="DISABLED_TOOLS"
    )

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5", alias="ANTHROPIC_MODEL")
    anthropic_classifier_model: str = Field(
        default="claude-haiku-4-5", alias="ANTHROPIC_CLASSIFIER_MODEL"
    )
    anthropic_max_tokens: int = Field(default=4096, alias="ANTHROPIC_MAX_TOKENS")
    anthropic_effort: str = Field(default="low", alias="ANTHROPIC_EFFORT")
    anthropic_thinking: str = Field(default="adaptive", alias="ANTHROPIC_THINKING")
    anthropic_timeout_seconds: float = Field(default=30.0, alias="ANTHROPIC_TIMEOUT_SECONDS")
    agent_max_iterations: int = Field(default=8, alias="AGENT_MAX_ITERATIONS")
    agent_budget_seconds: float = Field(default=45.0, alias="AGENT_BUDGET_SECONDS")
    agent_min_seconds_per_llm_call: float = Field(
        default=5.0, alias="AGENT_MIN_SECONDS_PER_LLM_CALL"
    )
    agent_llm_retry_enabled: bool = Field(default=True, alias="AGENT_LLM_RETRY_ENABLED")

    response_budget_seconds: float = Field(default=60.0, alias="RESPONSE_BUDGET_SECONDS")
    api_timeout_margin_seconds: float = Field(default=2.0, alias="API_TIMEOUT_MARGIN_SECONDS")
    conversation_ttl_seconds: int = Field(default=3600, alias="CONVERSATION_TTL_SECONDS")
    conversation_max_turns: int = Field(default=20, alias="CONVERSATION_MAX_TURNS")
    conversation_history_window_turns: int = Field(
        default=10, alias="CONVERSATION_HISTORY_WINDOW_TURNS"
    )
    conversation_max_conversations: int = Field(
        default=1000, alias="CONVERSATION_MAX_CONVERSATIONS"
    )
    max_message_chars: int = Field(default=4000, alias="MAX_MESSAGE_CHARS")
    session_cookie_name: str = Field(default="miniflake_session", alias="SESSION_COOKIE_NAME")
    session_cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")
    session_cookie_samesite: str = Field(default="lax", alias="SESSION_COOKIE_SAMESITE")

    @property
    def api_request_timeout_seconds(self) -> float:
        return max(
            self.response_budget_seconds - self.api_timeout_margin_seconds,
            self.agent_min_seconds_per_llm_call,
        )

    def acs_wide_table_name(self, vintage: int, series_prefix: str) -> str:
        return self.acs_wide_table_template.format(vintage=vintage, series_prefix=series_prefix)

    def metadata_field_descriptions_table(self, vintage: int) -> str:
        return self.metadata_field_descriptions_template.format(vintage=vintage)

    def metadata_fips_codes_table(self, vintage: int) -> str:
        return self.metadata_fips_codes_template.format(vintage=vintage)

    def metadata_geographic_data_table(self, vintage: int) -> str:
        return self.metadata_geographic_data_template.format(vintage=vintage)

    def fixtures_path(self) -> Path:
        return Path(self.fixtures_dir)

    def variable_catalog_spec_file(self) -> Path:
        return Path(self.variable_catalog_spec_path)

    def state_fips_names_file(self) -> Path:
        return Path(self.state_fips_names_path)

    @field_validator("acs_vintages", mode="before")
    @classmethod
    def parse_acs_vintages(cls, value: object) -> object:
        if isinstance(value, str):
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        return value

    @field_validator("disabled_tools", mode="before")
    @classmethod
    def parse_disabled_tools(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def validate_private_key_source(self) -> Self:
        has_path = bool(self.snowflake_private_key_path)
        has_pem = bool(self.snowflake_private_key)
        if has_path and has_pem:
            raise ValueError(
                "Provide only one of snowflake_private_key_path or snowflake_private_key"
            )
        if not has_path and not has_pem:
            raise ValueError("snowflake_private_key is required")
        return self

    def load_private_key_bytes(self) -> bytes:
        if self.snowflake_private_key:
            return self.snowflake_private_key.encode("utf-8")
        if self.snowflake_private_key_path:
            return Path(self.snowflake_private_key_path).read_bytes()
        raise ValueError("snowflake_private_key is required")


@lru_cache
def get_settings() -> Settings:
    return Settings()
