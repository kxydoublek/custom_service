from pathlib import Path

from pycore.core.config import ConfigManager
from src.config.settings import AppSettings
from src.db.session import resolve_sqlite_path

TEST_USERNAME = "it-admin"
TEST_PASSWORD = "test-local-password"


def test_login_success(client):
    response = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str) and data["access_token"]
    assert data["user"]["username"] == TEST_USERNAME
    assert isinstance(data["user"]["id"], int)


def test_login_wrong_password(client):
    response = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": "not-the-password"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == "UNAUTHORIZED"
    assert body["error"] == "账号或密码不正确"
    assert body["data"] is None


def test_login_unknown_user_same_message(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "not-a-user", "password": "whatever"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "UNAUTHORIZED"
    assert body["error"] == "账号或密码不正确"


def test_login_missing_fields(client):
    response = client.post("/api/auth/login", json={})
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["error"] == "请输入用户名和密码"


def test_me_requires_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "UNAUTHORIZED"


def test_me_rejects_bad_token(client):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "UNAUTHORIZED"


def test_me_with_valid_token(client):
    login = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    token = login.json()["data"]["access_token"]
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["username"] == TEST_USERNAME
    assert isinstance(data["id"], int)


def test_logout_without_token(client):
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["data"]["logged_out"] is True


def test_logout_with_token(client):
    login = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    token = login.json()["data"]["access_token"]
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["logged_out"] is True


def test_sqlite_relative_path_resolves_under_backend(tmp_path: Path):
    resolved = resolve_sqlite_path("data/Customer_Service.db")
    assert resolved.is_absolute()
    assert resolved.name == "Customer_Service.db"
    assert resolved.parent.name == "data"
    assert resolved.parent.parent.name == "backend"
    assert resolved.parent.is_dir()


def test_config_load_ignores_process_env(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SECRET_KEY=file-secret\n"
        "INTERNAL_USERNAME=it-admin\n"
        "INTERNAL_PASSWORD=file-password\n"
        "DATABASE_PATH=data/Customer_Service.db\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("INTERNAL_PASSWORD", "from-process-env")
    monkeypatch.setenv("SECRET_KEY", "from-process-env")
    ConfigManager.reset()
    manager = ConfigManager[AppSettings]()
    manager.load(AppSettings, env_file, use_env=False)
    assert manager.settings.internal_password == "file-password"
    assert manager.settings.secret_key == "file-secret"
    ConfigManager.reset()
