from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
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
