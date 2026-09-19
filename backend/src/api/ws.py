"""实时通道（API-018）。鉴权用查询参数 access_token，禁止把 Token 写入日志。"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pycore.core import get_logger

from src.config.settings import get_settings
from src.db.session import get_db_context
from src.services.auth import AuthService

logger = get_logger()

ws_router = APIRouter()


class DocumentHub:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        self._connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self._connections.pop(user_id, None)

    async def broadcast_user(self, user_id: int, payload: dict) -> None:
        text = json.dumps(payload, ensure_ascii=False)
        for websocket in list(self._connections.get(user_id, ())):
            try:
                await websocket.send_text(text)
            except Exception:
                self.disconnect(user_id, websocket)

    async def broadcast_all(self, payload: dict) -> None:
        for user_id in list(self._connections):
            await self.broadcast_user(user_id, payload)


hub = DocumentHub()


async def _user_id_from_token(token: str | None) -> int | None:
    if not token:
        return None
    async with get_db_context() as session:
        service = AuthService(session)
        user_id = service.decode_access_token(token)
        if user_id is None:
            return None
        user = await service.get_user_by_id(user_id)
        if user is None:
            return None
        return user.id


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("access_token")
    user_id = await _user_id_from_token(token)
    if user_id is None:
        logger.info("WebSocket 鉴权失败，关闭连接")
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await hub.connect(user_id, websocket)
    heartbeat = asyncio.create_task(_heartbeat(websocket))
    try:
        while True:
            message = await websocket.receive_text()
            if message == "pong":
                continue
    except WebSocketDisconnect:
        logger.info("WebSocket 已断开", user_id=user_id)
    except Exception:
        logger.exception("WebSocket 连接异常")
    finally:
        heartbeat.cancel()
        hub.disconnect(user_id, websocket)


async def _heartbeat(websocket: WebSocket) -> None:
    interval = get_settings().ws_heartbeat_seconds
    try:
        while True:
            await asyncio.sleep(interval)
            await websocket.send_text("ping")
    except Exception:
        return


async def publish_document_progress(
    user_id: int,
    document_id: int,
    status: str,
    stage: str,
    progress_percent: int,
) -> None:
    await hub.broadcast_user(
        user_id,
        {
            "event": "document.progress",
            "document_id": document_id,
            "status": status,
            "stage": stage,
            "progress_percent": progress_percent,
        },
    )


async def publish_document_ready(user_id: int, document_id: int) -> None:
    await hub.broadcast_user(
        user_id,
        {"event": "document.ready", "document_id": document_id},
    )


async def publish_document_failed(user_id: int, document_id: int, error_message: str) -> None:
    await hub.broadcast_user(
        user_id,
        {
            "event": "document.failed",
            "document_id": document_id,
            "error_message": error_message,
        },
    )


async def publish_events(events: list[dict]) -> None:
    for payload in events:
        await hub.broadcast_all(payload)
