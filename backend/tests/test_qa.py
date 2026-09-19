import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from src.config.settings import get_settings
from src.db.session import resolve_sqlite_path
from tests.conftest import TEST_PASSWORD, TEST_USERNAME

FAQ_QUESTION = "VPN 提示认证失败怎么办？"
FAQ_ANSWER = "请先检查账号是否锁定，再重试导入配置文件。"
SOFTWARE_CHUNK = "Outlook 崩溃时请先重启客户端并清理缓存。"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _db_path() -> Path:
    return resolve_sqlite_path(get_settings().database_path)


def _connect():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_ready_document(*, faq: tuple[str, str] | None = None, chunk: dict | None = None) -> None:
    settings = get_settings()
    embedding = json.dumps([0.0] * settings.llm_embed_dimensions)
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO documents (filename, content_type, status, stage, progress_percent, "
            "char_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("kb.txt", "txt", "ready", "ready", 100, 20, _now(), _now()),
        )
        document_id = cur.lastrowid
        if faq is not None:
            conn.execute(
                "INSERT INTO faqs (document_id, question, answer, embedding) VALUES (?, ?, ?, ?)",
                (document_id, faq[0], faq[1], embedding),
            )
        if chunk is not None:
            conn.execute(
                "INSERT INTO chunks (document_id, ordinal, content, object_types, request_types, "
                "entities, embedding) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    document_id,
                    0,
                    chunk["content"],
                    json.dumps(chunk["object_types"]),
                    json.dumps(chunk["request_types"]),
                    json.dumps([]),
                    embedding,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _insert_ticket(conversation_id: int, status: str = "pending") -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO tickets (conversation_id, status, created_at) VALUES (?, ?, ?)",
            (conversation_id, status, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def _create_conversation(client: TestClient, token: str) -> dict:
    response = client.post("/api/conversations", headers=_auth(token), json={})
    assert response.status_code == 200
    return response.json()["data"]


def _send(client: TestClient, token: str, conversation_id: int, content: str):
    return client.post(
        f"/api/conversations/{conversation_id}/messages",
        headers=_auth(token),
        json={"content": content},
    )


def _parse_sse(payload: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    event_name = None
    for line in payload.splitlines():
        if line.startswith("event:"):
            event_name = line[len("event:") :].strip()
        elif line.startswith("data:") and event_name:
            events.append((event_name, json.loads(line[len("data:") :].strip())))
            event_name = None
    return events


def _read_stream(
    client: TestClient, token: str, conversation_id: int, message_id: int
) -> list[tuple[str, dict]]:
    with client.stream(
        "GET",
        f"/api/conversations/{conversation_id}/assistant-stream",
        params={"after_user_message_id": message_id},
        headers=_auth(token),
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_bytes()).decode("utf-8")
    return _parse_sse(body)


def _ask_and_stream(client: TestClient, token: str, conversation_id: int, content: str):
    sent = _send(client, token, conversation_id, content)
    assert sent.status_code == 200, sent.text
    data = sent.json()["data"]
    assert data["assistant_message"] is None
    events = _read_stream(client, token, conversation_id, data["user_message"]["id"])
    return data, events


def test_conversations_require_auth(client: TestClient):
    response = client.post("/api/conversations", json={})
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


def test_create_conversation_and_history_without_ticket_status(client: TestClient):
    token = _login(client)
    created = _create_conversation(client, token)
    assert created["title"] == "新会话"
    assert created["messages"] == []
    assert created["handoff_state"] == "none"
    assert "ticket_status" not in created

    listed = client.get("/api/conversations", headers=_auth(token))
    assert listed.status_code == 200
    body = listed.json()
    assert body["success"] is True
    item = body["data"][0]
    assert set(item) == {"id", "title", "updated_at", "preview"}
    assert "ticket_status" not in item


def test_empty_message_rejected(client: TestClient):
    token = _login(client)
    conversation = _create_conversation(client, token)
    response = _send(client, token, conversation["id"], "   ")
    assert response.status_code == 400
    assert response.json()["error"] == "请输入要发送的内容"


def test_faq_exact_match_skips_classification(client: TestClient, monkeypatch):
    _seed_ready_document(faq=(FAQ_QUESTION, FAQ_ANSWER))
    token = _login(client)
    conversation = _create_conversation(client, token)
    classify_calls: list[str] = []

    async def fail_if_classify(messages, *, temperature, purpose):
        classify_calls.append(purpose)
        raise AssertionError("FAQ 原文全等不应走分类")

    monkeypatch.setattr("src.services.qa.chat_json", fail_if_classify)

    sent, events = _ask_and_stream(
        client,
        token,
        conversation["id"],
        "ＶＰＮ提示认证失败怎么办？",
    )
    assert sent["stream"] is True
    assert [name for name, _ in events][0] == "meta"
    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert "delta" in names
    assert names[-1] == "done"
    assert events[0][1]["source"] == "faq"
    collected = "".join(item[1]["text"] for item in events if item[0] == "delta")
    assert collected == FAQ_ANSWER
    done_message = events[-1][1]["assistant_message"]
    assert done_message["source"] == "faq"
    assert done_message["content"] == FAQ_ANSWER
    assert classify_calls == []

    detail = client.get(
        f"/api/conversations/{conversation['id']}", headers=_auth(token)
    ).json()["data"]
    assert detail["messages"][-1]["content"] == FAQ_ANSWER
    assert detail["messages"][-1]["source"] == "faq"
    assert "ticket_status" not in detail


def test_out_of_scope_three_paths_same_text(client: TestClient):
    settings = get_settings()
    token = _login(client)
    conversation = _create_conversation(client, token)
    questions = [
        "那个东西坏了，信息不足该怎么处理",
        "帮我查工单进度和申请进度",
        "今天天气怎么样，超出范围了吗",
    ]
    texts = []
    for question in questions:
        sent, events = _ask_and_stream(client, token, conversation["id"], question)
        assert sent["stream"] is True
        assert events[0][0] == "meta"
        assert events[0][1]["source"] == "knowledge_qa"
        collected = "".join(item[1]["text"] for item in events if item[0] == "delta")
        texts.append(collected)
        assert events[-1][0] == "done"
        assert events[-1][1]["assistant_message"]["source"] == "knowledge_qa"
        assert "clarification_question" not in json.dumps(events, ensure_ascii=False)
        assert "工单号是多少" not in collected
    assert texts[0] == texts[1] == texts[2] == settings.out_of_scope_text


def test_empty_recall_returns_no_knowledge_text(client: TestClient):
    _seed_ready_document(
        chunk={
            "content": SOFTWARE_CHUNK,
            "object_types": ["software"],
            "request_types": ["troubleshooting"],
        }
    )
    settings = get_settings()
    token = _login(client)
    conversation = _create_conversation(client, token)
    _, events = _ask_and_stream(client, token, conversation["id"], "显示器黑屏怎么办")
    collected = "".join(item[1]["text"] for item in events if item[0] == "delta")
    assert events[0][1]["source"] == "knowledge_qa"
    assert collected == settings.no_knowledge_text
    assert SOFTWARE_CHUNK not in collected


def test_empty_tags_do_not_recall_all_chunks(client: TestClient):
    _seed_ready_document(
        chunk={
            "content": SOFTWARE_CHUNK,
            "object_types": ["software"],
            "request_types": ["troubleshooting"],
        }
    )
    settings = get_settings()
    token = _login(client)
    conversation = _create_conversation(client, token)
    _, events = _ask_and_stream(client, token, conversation["id"], "这个问题无标签")
    collected = "".join(item[1]["text"] for item in events if item[0] == "delta")
    assert collected == settings.out_of_scope_text
    assert SOFTWARE_CHUNK not in collected


def test_handoff_stops_auto_reply(client: TestClient, monkeypatch):
    token = _login(client)
    conversation = _create_conversation(client, token)
    _insert_ticket(conversation["id"], "pending")

    async def should_not_classify(*args, **kwargs):
        raise AssertionError("转人工未关闭时不得调用分类/闲聊/知识问答")

    monkeypatch.setattr("src.services.qa.chat_json", should_not_classify)
    monkeypatch.setattr("src.services.qa.chat_stream", should_not_classify)
    monkeypatch.setattr("src.services.qa.embed_texts", should_not_classify)

    sent = _send(client, token, conversation["id"], "人工处理中继续提问")
    assert sent.status_code == 200
    data = sent.json()["data"]
    assert data["stream"] is False
    assert data["handoff_state"] == "waiting"
    assert data["assistant_message"] is None

    detail = client.get(
        f"/api/conversations/{conversation['id']}", headers=_auth(token)
    ).json()["data"]
    assert detail["handoff_state"] == "waiting"
    assert all(item["role"] != "assistant" for item in detail["messages"])
    assert "ticket_status" not in detail


def test_generation_lock_second_send_conflict(client: TestClient):
    token = _login(client)
    conversation = _create_conversation(client, token)
    first = _send(client, token, conversation["id"], "你好")
    assert first.status_code == 200
    assert first.json()["data"]["stream"] is True
    second = _send(client, token, conversation["id"], "谢谢")
    assert second.status_code == 409
    body = second.json()
    assert body["error_code"] == "CONFLICT"
    assert body["error"] == "请等待当前回复结束"


def test_classification_json_failure_falls_back(client: TestClient):
    settings = get_settings()
    token = _login(client)
    conversation = _create_conversation(client, token)
    sent, events = _ask_and_stream(
        client, token, conversation["id"], "请处理【分类失败】这个问题"
    )
    assert sent["stream"] is True
    collected = "".join(item[1]["text"] for item in events if item[0] == "delta")
    assert events[0][1]["source"] == "knowledge_qa"
    assert collected == settings.out_of_scope_text


def test_small_talk_source_and_sse_order(client: TestClient):
    token = _login(client)
    conversation = _create_conversation(client, token)
    _, events = _ask_and_stream(client, token, conversation["id"], "你好，在吗")
    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert "delta" in names
    assert names.index("delta") < names.index("done")
    assert events[0][1]["source"] == "small_talk"
    collected = "".join(item[1]["text"] for item in events if item[0] == "delta")
    assert collected
    assert events[-1][1]["assistant_message"]["source"] == "small_talk"
