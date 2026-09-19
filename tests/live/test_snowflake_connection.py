import os

import pytest

from app.config import Settings, get_settings
from app.data.connection import connect_snowflake

pytestmark = pytest.mark.live

RUN_LIVE = os.environ.get("RUN_LIVE_TESTS") == "1"


@pytest.fixture(autouse=True)
def _skip_unless_live() -> None:
    if not RUN_LIVE:
        pytest.skip("Set RUN_LIVE_TESTS=1 to run live Snowflake tests")


def test_connection_opens() -> None:
    get_settings.cache_clear()
    settings = Settings()
    connection = connect_snowflake(settings)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
        cursor.close()
    finally:
        connection.close()


def test_current_role_is_readonly() -> None:
    get_settings.cache_clear()
    settings = Settings()
    connection = connect_snowflake(settings)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT CURRENT_ROLE()")
        role = cursor.fetchone()[0]
        assert role.upper() == settings.snowflake_role.upper()
        cursor.close()
    finally:
        connection.close()


def test_safegraph_database_visible() -> None:
    get_settings.cache_clear()
    settings = Settings()
    connection = connect_snowflake(settings)
    try:
        cursor = connection.cursor()
        cursor.execute(f"SHOW DATABASES LIKE '{settings.snowflake_database}'")
        rows = cursor.fetchall()
        assert len(rows) >= 1
        cursor.close()
    finally:
        connection.close()
