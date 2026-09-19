from collections.abc import AsyncIterator

from fastapi import Depends, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pycore.api import APIRouter, error_response, paginated_response, success_response
from pycore.api.routes import handle_errors
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.api.ws import publish_events
from src.db.models import User
from src.db.session import get_db
from src.repositories.conversation import ConversationConflictError
from src.services.qa import (
    MessageCreate,
    QaNotFoundError,
    QaService,
    stream_assistant_reply,
)
from src.services.ticket import EmptyBody, TicketConflictError, TicketNotFoundError, TicketService

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _error(error: str, error_code: str, status_code: int) -> JSONResponse:
    resp, code = error_response(
        error=error, error_code=error_code, status_code=status_code
    )
    return JSONResponse(status_code=code, content=jsonable_encoder(resp))


def _not_found(message: str = "会话不存在") -> JSONResponse:
    return _error(message, "NOT_FOUND", status.HTTP_404_NOT_FOUND)


@router.post("")
@handle_errors
async def create_conversation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user
    detail = await QaService(db).create_conversation()
    return success_response(data=detail.model_dump(), message="ok")


@router.get("")
@handle_errors
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user
    items, total = await QaService(db).list_conversations(page=page, page_size=page_size)
    return paginated_response(
        data=[item.model_dump() for item in items],
        page=page,
        page_size=page_size,
        total_items=total,
    )


@router.get("/{conversation_id}")
@handle_errors
async def get_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user
    try:
        detail = await QaService(db).get_conversation(conversation_id)
    except QaNotFoundError as exc:
        return _not_found(exc.message)
    return success_response(data=detail.model_dump(), message="ok")


@router.post("/{conversation_id}/messages")
@handle_errors
async def send_message(
    conversation_id: int,
    body: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user
    try:
        result = await QaService(db).send_user_message(conversation_id, body.content)
    except QaNotFoundError as exc:
        return _not_found(exc.message)
    except ConversationConflictError as exc:
        return _error(str(exc), "CONFLICT", status.HTTP_409_CONFLICT)
    if not result.stream:
        await db.commit()
        await publish_events(
            [
                {
                    "event": "message.created",
                    "conversation_id": conversation_id,
                    "message": result.user_message.model_dump(),
                }
            ]
        )
    return success_response(data=result.model_dump(), message="ok")


@router.post("/{conversation_id}/transfer")
@handle_errors
async def transfer_conversation(
    conversation_id: int,
    body: EmptyBody | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user, body
    try:
        payload, events = await TicketService(db).transfer(conversation_id)
    except TicketNotFoundError as exc:
        return _not_found(exc.message)
    except TicketConflictError as exc:
        return _error(str(exc), "CONFLICT", status.HTTP_409_CONFLICT)
    await db.commit()
    await publish_events(events)
    return success_response(data=payload.model_dump(), message="ok")


@router.get("/{conversation_id}/assistant-stream")
@handle_errors
async def assistant_stream(
    conversation_id: int,
    after_user_message_id: int = Query(...),
    user: User = Depends(get_current_user),
):
    del user
    generator = stream_assistant_reply(conversation_id, after_user_message_id)
    try:
        first = await anext(generator)
    except QaNotFoundError as exc:
        return _error(exc.message, "NOT_FOUND", status.HTTP_404_NOT_FOUND)
    except ConversationConflictError as exc:
        return _error(str(exc), "CONFLICT", status.HTTP_409_CONFLICT)
    except StopAsyncIteration:
        return _error("无法继续回复", "NOT_FOUND", status.HTTP_404_NOT_FOUND)

    async def with_first() -> AsyncIterator[str]:
        yield first
        async for chunk in generator:
            yield chunk

    return StreamingResponse(
        with_first(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
