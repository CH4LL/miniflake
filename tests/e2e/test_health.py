from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from tests.conftest import make_settings_env


def test_health_returns_200_and_documented_body(apply_env) -> None:
    get_settings.cache_clear()
    apply_env(make_settings_env())
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "test-miniflake"
    assert body["version"] == "0.1.0-test"
    assert body["environment"] == "test"
