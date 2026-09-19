import asyncio
import sqlite3
import time
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pycore.core.config import ConfigManager
from src.config.settings import AppSettings, get_settings
from src.db.session import get_db_context, init_db, reset_engine
from src.repositories.document import DocumentRepository
from src.services.ingest import INTERRUPTED_MESSAGE, fail_interrupted_ingests
from tests.conftest import TEST_PASSWORD, TEST_USERNAME

VPN_TEXT = (
    "VPN 提示认证失败时，请先检查账号是否锁定，再重试导入配置文件。\n\n"
    "公司网络异常时不要把现象当成权限不足。"
)
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
READY_CHUNK_SQL = (
    "select count(*) from chunks c "
    "join documents d on c.document_id=d.id where d.status='ready'"
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _wait_document(client: TestClient, token: str, document_id: int, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/documents/{document_id}", headers=_auth(token))
        assert response.status_code == 200
        last = response.json()["data"]
        if last["status"] in {"ready", "failed"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"document {document_id} not finished: {last}")


def _sqlite(db_path: Path, sql: str):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchone()
    finally:
        conn.close()


def _docx_bytes(text: str) -> bytes:
    from docx import Document as DocxDocument

    document = DocxDocument()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def api(client: TestClient, tmp_path: Path, monkeypatch) -> TestClient:
    settings = get_settings()
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(settings, "upload_dir", str(upload_dir))
    monkeypatch.setattr(settings, "llm_api_key", "")
    return client


def test_documents_require_auth(api: TestClient):
    response = api.post(
        "/api/documents",
        files={"file": ("vpn.txt", VPN_TEXT.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


def test_upload_supported_formats_return_queued(api: TestClient):
    token = _login(api)
    samples = [
        ("vpn.txt", VPN_TEXT.encode("utf-8"), "text/plain"),
        ("vpn.md", VPN_TEXT.encode("utf-8"), "text/markdown"),
        ("vpn.markdown", VPN_TEXT.encode("utf-8"), "text/markdown"),
        ("vpn.docx", _docx_bytes(VPN_TEXT), DOCX_MIME),
        ("blank.pdf", _pdf_bytes(), "application/pdf"),
    ]
    for filename, payload, mime in samples:
        response = api.post(
            "/api/documents",
            headers=_auth(token),
            files={"file": (filename, payload, mime)},
        )
        assert response.status_code == 200, filename
        data = response.json()["data"]
        assert data["status"] == "queued"
        assert data["stage"] == "queued"
        assert data["progress_percent"] == 0
        assert data["chunk_count"] == 0
        assert data["faq_count"] == 0
        _wait_document(api, token, data["id"])


def test_reject_unsupported_formats_without_row(api: TestClient, tmp_path: Path):
    token = _login(api)
    db_path = tmp_path / "test.db"
    before = _sqlite(db_path, "select count(*) from documents")[0]
    for filename in ("sheet.xlsx", "legacy.doc"):
        response = api.post(
            "/api/documents",
            headers=_auth(token),
            files={"file": (filename, b"not-a-real-file", "application/octet-stream")},
        )
        assert response.status_code == 400, filename
        body = response.json()
        assert body["error_code"] == "VALIDATION_ERROR"
        assert body["error"] == "不支持该格式，请上传 PDF、Word（.docx）、Markdown 或 txt"
    after = _sqlite(db_path, "select count(*) from documents")[0]
    assert after == before


def test_reject_oversize_without_row(api: TestClient, tmp_path: Path, monkeypatch):
    token = _login(api)
    monkeypatch.setattr(get_settings(), "upload_max_bytes", 8)
    db_path = tmp_path / "test.db"
    before = _sqlite(db_path, "select count(*) from documents")[0]
    response = api.post(
        "/api/documents",
        headers=_auth(token),
        files={"file": ("vpn.txt", b"0123456789", "text/plain")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "文件过大" in body["error"]
    after = _sqlite(db_path, "select count(*) from documents")[0]
    assert after == before


def test_empty_document_failed_not_retrievable(api: TestClient, tmp_path: Path):
    token = _login(api)
    response = api.post(
        "/api/documents",
        headers=_auth(token),
        files={"file": ("empty.txt", b"   \n\n", "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "queued"
    document_id = response.json()["data"]["id"]
    detail = _wait_document(api, token, document_id)
    assert detail["status"] == "failed"
    assert "无法提取正文" in (detail["error_message"] or "")
    assert detail["chunks"] == []
    assert detail["faqs"] == []
    assert detail["chunk_count"] == 0
    assert detail["faq_count"] == 0

    listing = api.get("/api/documents?status=failed", headers=_auth(token))
    assert listing.status_code == 200
    ids = [item["id"] for item in listing.json()["data"]]
    assert document_id in ids
    failed_item = next(item for item in listing.json()["data"] if item["id"] == document_id)
    assert failed_item["status"] == "failed"
    assert "无法提取正文" in (failed_item["error_message"] or "")

    chunks, faqs, ready_chunks = (
        _sqlite(tmp_path / "test.db", "select count(*) from chunks")[0],
        _sqlite(tmp_path / "test.db", "select count(*) from faqs")[0],
        _sqlite(tmp_path / "test.db", READY_CHUNK_SQL)[0],
    )
    assert chunks == 0
    assert faqs == 0
    assert ready_chunks == 0
    assert not list((tmp_path / "uploads").glob("*empty.txt"))


def test_ready_document_has_chunks_tags_and_faq(api: TestClient, tmp_path: Path):
    token = _login(api)
    response = api.post(
        "/api/documents",
        headers=_auth(token),
        files={"file": ("vpn-auth.md", VPN_TEXT.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 200
    queued = response.json()["data"]
    assert queued["status"] == "queued"
    document_id = queued["id"]
    detail = _wait_document(api, token, document_id)
    assert detail["status"] == "ready"
    assert detail["stage"] == "ready"
    assert detail["progress_percent"] == 100
    assert detail["chunk_count"] >= 1
    assert detail["faq_count"] >= 1
    assert "network" in detail["object_types"]
    assert "troubleshooting" in detail["request_types"]
    assert detail["chunks"]
    assert detail["faqs"]
    assert detail["chunks"][0]["content"]
    stored = list((tmp_path / "uploads").glob("*vpn-auth.md"))
    assert stored and stored[0].is_file()

    ready_chunks = _sqlite(tmp_path / "test.db", READY_CHUNK_SQL)[0]
    assert ready_chunks >= 1


def test_ws_pushes_document_events(api: TestClient):
    token = _login(api)
    with api.websocket_connect(f"/ws?access_token={token}") as ws:
        response = api.post(
            "/api/documents",
            headers=_auth(token),
            files={"file": ("vpn-ws.md", VPN_TEXT.encode("utf-8"), "text/markdown")},
        )
        assert response.status_code == 200
        document_id = response.json()["data"]["id"]
        events = []
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            message = ws.receive_json()
            events.append(message)
            if message.get("event") in {"document.ready", "document.failed"}:
                break
        names = [item.get("event") for item in events]
        assert "document.progress" in names
        assert "document.ready" in names
        assert any(item.get("document_id") == document_id for item in events)
        percents = [
            item.get("progress_percent")
            for item in events
            if item.get("event") == "document.progress"
        ]
        assert percents == sorted(p for p in percents if p is not None)


def test_ws_rejects_bad_token(api: TestClient):
    with pytest.raises(Exception):
        with api.websocket_connect("/ws?access_token=not-a-valid-token") as ws:
            ws.receive_text()


def test_interrupt_marks_failed_and_deletes_file(tmp_path: Path):
    ConfigManager.reset()
    reset_engine()
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    leftover = upload_dir / "queued.txt"
    leftover.write_text("partial", encoding="utf-8")
    ConfigManager[AppSettings]().load_from_dict(
        AppSettings,
        {
            "secret_key": "test-local-jwt-secret-32bytes-min",
            "database_path": str(tmp_path / "interrupt.db"),
            "upload_dir": str(upload_dir),
            "internal_username": TEST_USERNAME,
            "internal_password": TEST_PASSWORD,
        },
    )

    async def scenario() -> None:
        await init_db()
        async with get_db_context() as session:
            repo = DocumentRepository(session)
            document = await repo.create(
                filename="queued.txt",
                content_type="txt",
                storage_path=str(leftover),
            )
            document_id = document.id
        await fail_interrupted_ingests()
        async with get_db_context() as session:
            repo = DocumentRepository(session)
            document = await repo.get_by_id(document_id)
            assert document is not None
            assert document.status == "failed"
            assert document.stage == "failed"
            assert document.error_message == INTERRUPTED_MESSAGE
            assert document.storage_path is None
            assert await repo.list_chunks(document_id) == []
            assert await repo.list_faqs(document_id) == []
            assert await repo.list_retrievable_chunks() == []

    try:
        asyncio.run(scenario())
        assert not leftover.exists()
    finally:
        reset_engine()
        ConfigManager.reset()
