from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
