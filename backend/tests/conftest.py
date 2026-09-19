from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pycore.core.config import ConfigManager
from src.config.settings import AppSettings
from src.db.session import reset_engine

TEST_USERNAME = "it-admin"
TEST_PASSWORD = "test-local-password"


def _test_settings(db_path: Path) -> dict:
    return {
        "secret_key": "test-local-jwt-secret-32bytes-min",
        "database_path": str(db_path),
        "internal_username": TEST_USERNAME,
        "internal_password": TEST_PASSWORD,
        "jwt_expire_hours": 12,
        "debug": False,
        "cors_origins": [
            "http://localhost:5199",
            "http://127.0.0.1:5199",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
        ],
    }


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    ConfigManager.reset()
    reset_engine()
    ConfigManager[AppSettings]().load_from_dict(
        AppSettings,
        _test_settings(tmp_path / "test.db"),
    )

    from src.main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    reset_engine()
    ConfigManager.reset()
