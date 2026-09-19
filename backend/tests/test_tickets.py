import json

import pytest
from fastapi.testclient import TestClient
from src.config.settings import get_settings
from tests.conftest import TEST_PASSWORD, TEST_USERNAME

STAFF_QUESTION = "VPN 连不上，需要人工帮忙"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


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


def _finish_auto_reply(
    client: TestClient, token: str, conversation_id: int, message_id: int
) -> None:
    with client.stream(
        "GET",
        f"/api/conversations/{conversation_id}/assistant-stream",
        params={"after_user_message_id": message_id},
        headers=_auth(token),
    ) as response:
        assert response.status_code == 200
        b"".join(response.iter_bytes())


def _ask(client: TestClient, token: str, conversation_id: int, content: str) -> dict:
    sent = _send(client, token, conversation_id, content)
    assert sent.status_code == 200, sent.text
    data = sent.json()["data"]
    if data["stream"]:
        _finish_auto_reply(client, token, conversation_id, data["user_message"]["id"])
    return data


def _transfer(client: TestClient, token: str, conversation_id: int):
    return client.post(
        f"/api/conversations/{conversation_id}/transfer",
        headers=_auth(token),
        json={},
    )


def _recv_event(ws) -> dict:
    while True:
        raw = ws.receive()
        text = raw.get("text")
        if text == "ping":
            continue
        if text:
            return json.loads(text)
        raise AssertionError(f"unexpected websocket frame: {raw}")


def _recv_until(ws, names: set[str], limit: int = 12) -> list[dict]:
    events: list[dict] = []
    seen: set[str] = set()
    for _ in range(limit):
        event = _recv_event(ws)
        events.append(event)
        name = event.get("event")
        if isinstance(name, str):
            seen.add(name)
        if names.issubset(seen):
            return events
    raise AssertionError(f"missing {names - seen} in {events}")


def test_tickets_require_auth(client: TestClient):
    response = client.get("/api/tickets")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


def test_transfer_creates_pending_and_pushes_ws(client: TestClient):
    token = _login(client)
    conversation = _create_conversation(client, token)
    asked = _ask(client, token, conversation["id"], STAFF_QUESTION)
    assert asked["stream"] is True

    with client.websocket_connect(f"/ws?access_token={token}") as ws:
        transferred = _transfer(client, token, conversation["id"])
        assert transferred.status_code == 200, transferred.text
        data = transferred.json()["data"]
        assert set(data) == {"handoff_state", "wait_message"}
        assert data["handoff_state"] == "waiting"
        assert "ticket_id" not in data
        assert "ticket_status" not in data
        wait = data["wait_message"]
        assert wait["role"] == "system"
        assert wait["content"] == get_settings().wait_human_text
        assert wait["source"] is None

        events = _recv_until(ws, {"ticket.created", "handoff.changed", "message.created"})
        created = next(item for item in events if item["event"] == "ticket.created")
        changed = next(item for item in events if item["event"] == "handoff.changed")
        message_event = next(item for item in events if item["event"] == "message.created")
        assert created["conversation_id"] == conversation["id"]
        assert created["title"] == STAFF_QUESTION[:30]
        assert created["preview"] == STAFF_QUESTION[:30]
        assert changed == {
            "event": "handoff.changed",
            "conversation_id": conversation["id"],
            "handoff_state": "waiting",
        }
        assert message_event["conversation_id"] == conversation["id"]
        assert message_event["message"]["content"] == get_settings().wait_human_text
        assert message_event["message"]["source"] is None

        listed = client.get(
            "/api/tickets",
            headers=_auth(token),
            params={"status": "pending"},
        )
        assert listed.status_code == 200
        items = listed.json()["data"]
        assert len(items) == 1
        assert items[0]["id"] == created["ticket_id"]
        assert items[0]["status"] == "pending"
        assert items[0]["conversation_id"] == conversation["id"]

        detail = client.get(
            f"/api/conversations/{conversation['id']}", headers=_auth(token)
        ).json()["data"]
        assert detail["handoff_state"] == "waiting"
        assert "ticket_status" not in detail

        duplicate = _transfer(client, token, conversation["id"])
        assert duplicate.status_code == 409
        body = duplicate.json()
        assert body["error_code"] == "CONFLICT"
        assert body["error"] == "当前已在等待或由人工处理"


def test_accept_reply_close_state_machine_and_ws(client: TestClient, monkeypatch):
    token = _login(client)
    conversation = _create_conversation(client, token)
    _ask(client, token, conversation["id"], STAFF_QUESTION)
    transferred = _transfer(client, token, conversation["id"])
    assert transferred.status_code == 200
    ticket_id = client.get("/api/tickets", headers=_auth(token)).json()["data"][0]["id"]

    pending_reply = client.post(
        f"/api/tickets/{ticket_id}/messages",
        headers=_auth(token),
        json={"content": "还不能回"},
    )
    assert pending_reply.status_code == 409
    assert pending_reply.json()["error"] == "不能回复"

    with client.websocket_connect(f"/ws?access_token={token}") as ws:
        accepted = client.post(
            f"/api/tickets/{ticket_id}/accept",
            headers=_auth(token),
            json={},
        )
        assert accepted.status_code == 200
        accept_data = accepted.json()["data"]
        assert accept_data["id"] == ticket_id
        assert accept_data["status"] == "processing"
        assert accept_data["accepted_at"]
        events = _recv_until(ws, {"ticket.accepted", "handoff.changed"})
        assert any(
            item["event"] == "ticket.accepted"
            and item["ticket_id"] == ticket_id
            and item["conversation_id"] == conversation["id"]
            for item in events
        )
        assert any(
            item["event"] == "handoff.changed" and item["handoff_state"] == "in_progress"
            for item in events
        )

        again = client.post(
            f"/api/tickets/{ticket_id}/accept",
            headers=_auth(token),
            json={},
        )
        assert again.status_code == 409
        assert again.json()["error"] == "无法接入"

        replied = client.post(
            f"/api/tickets/{ticket_id}/messages",
            headers=_auth(token),
            json={"content": "请先重启客户端"},
        )
        assert replied.status_code == 200
        agent_message = replied.json()["data"]["agent_message"]
        assert agent_message["role"] == "agent"
        assert agent_message["source"] is None
        assert agent_message["content"] == "请先重启客户端"
        created = _recv_until(ws, {"message.created"})[-1]
        assert created["event"] == "message.created"
        assert created["conversation_id"] == conversation["id"]
        assert created["message"]["role"] == "agent"
        assert created["message"]["source"] is None

        async def should_not_call_llm(*args, **kwargs):
            raise AssertionError("人工未关闭时不得调用 FAQ/闲聊/AI")

        monkeypatch.setattr("src.services.qa.chat_json", should_not_call_llm)
        monkeypatch.setattr("src.services.qa.chat_stream", should_not_call_llm)
        monkeypatch.setattr("src.services.qa.embed_texts", should_not_call_llm)

        staff = _send(client, token, conversation["id"], "还是不行")
        assert staff.status_code == 200
        staff_data = staff.json()["data"]
        assert staff_data["stream"] is False
        assert staff_data["handoff_state"] == "in_progress"
        assert staff_data["assistant_message"] is None
        user_pushed = _recv_until(ws, {"message.created"})[-1]
        assert user_pushed["message"]["role"] == "user"
        assert user_pushed["message"]["content"] == "还是不行"
        assert user_pushed["message"]["source"] is None

        closed = client.post(
            f"/api/tickets/{ticket_id}/close",
            headers=_auth(token),
            json={},
        )
        assert closed.status_code == 200
        close_data = closed.json()["data"]
        assert close_data["status"] == "closed"
        assert close_data["closed_at"]
        close_events = _recv_until(ws, {"ticket.closed", "handoff.changed"})
        assert any(item["event"] == "ticket.closed" for item in close_events)
        assert any(
            item["event"] == "handoff.changed" and item["handoff_state"] == "none"
            for item in close_events
        )

        after_close = client.post(
            f"/api/tickets/{ticket_id}/messages",
            headers=_auth(token),
            json={"content": "关了不能再回"},
        )
        assert after_close.status_code == 409
        assert after_close.json()["error"] == "不能回复"

        close_again = client.post(
            f"/api/tickets/{ticket_id}/close",
            headers=_auth(token),
            json={},
        )
        assert close_again.status_code == 409
        assert close_again.json()["error"] == "已关闭"

    detail = client.get(
        f"/api/conversations/{conversation['id']}", headers=_auth(token)
    ).json()["data"]
    assert detail["handoff_state"] == "none"
    assert "ticket_status" not in detail

    resumed = _send(client, token, conversation["id"], "关闭后继续问系统")
    assert resumed.status_code == 200
    assert resumed.json()["data"]["stream"] is True
    assert resumed.json()["data"]["handoff_state"] == "none"

    again_transfer = _transfer(client, token, conversation["id"])
    assert again_transfer.status_code == 200
    listed = client.get("/api/tickets", headers=_auth(token)).json()["data"]
    open_tickets = [item for item in listed if item["status"] != "closed"]
    assert len(open_tickets) == 1
    assert open_tickets[0]["id"] != ticket_id


def test_unaccepted_ticket_stays_pending(client: TestClient):
    token = _login(client)
    conversation = _create_conversation(client, token)
    _ask(client, token, conversation["id"], STAFF_QUESTION)
    transferred = _transfer(client, token, conversation["id"])
    assert transferred.status_code == 200
    listed = client.get(
        "/api/tickets",
        headers=_auth(token),
        params={"status": "pending"},
    ).json()["data"]
    assert listed[0]["status"] == "pending"
    processing = client.get(
        "/api/tickets",
        headers=_auth(token),
        params={"status": "processing"},
    ).json()["data"]
    assert processing == []
    conversation_detail = client.get(
        f"/api/conversations/{conversation['id']}", headers=_auth(token)
    ).json()["data"]
    assert conversation_detail["handoff_state"] == "waiting"


def test_ticket_detail_and_invalid_status(client: TestClient):
    token = _login(client)
    conversation = _create_conversation(client, token)
    _ask(client, token, conversation["id"], STAFF_QUESTION)
    _transfer(client, token, conversation["id"])
    ticket = client.get("/api/tickets", headers=_auth(token)).json()["data"][0]
    detail = client.get(f"/api/tickets/{ticket['id']}", headers=_auth(token))
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["id"] == ticket["id"]
    assert data["status"] == "pending"
    assert any(item["role"] == "system" for item in data["messages"])
    assert data["accepted_at"] is None
    assert data["closed_at"] is None

    missing = client.get("/api/tickets/99999", headers=_auth(token))
    assert missing.status_code == 404
    bad_status = client.get(
        "/api/tickets",
        headers=_auth(token),
        params={"status": "waiting"},
    )
    assert bad_status.status_code == 400
    assert bad_status.json()["error_code"] == "VALIDATION_ERROR"


def test_ws_rejects_bad_token(client: TestClient):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?access_token=not-a-valid-token") as ws:
            ws.receive_text()
