from fastapi import Depends, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pycore.api import APIRouter, error_response, paginated_response, success_response
from pycore.api.routes import handle_errors
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.api.ws import publish_events
from src.db.models import User
from src.db.session import get_db
from src.services.ticket import (
    EmptyBody,
    TicketConflictError,
    TicketMessageCreate,
    TicketNotFoundError,
    TicketService,
)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _error(error: str, error_code: str, status_code: int) -> JSONResponse:
    resp, code = error_response(
        error=error, error_code=error_code, status_code=status_code
    )
    return JSONResponse(status_code=code, content=jsonable_encoder(resp))


def _not_found(message: str = "工单不存在") -> JSONResponse:
    return _error(message, "NOT_FOUND", status.HTTP_404_NOT_FOUND)


@router.get("")
@handle_errors
async def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    status_filter: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user
    items, total = await TicketService(db).list_tickets(
        page=page, page_size=page_size, status=status_filter
    )
    return paginated_response(
        data=[item.model_dump() for item in items],
        page=page,
        page_size=page_size,
        total_items=total,
    )


@router.get("/{ticket_id}")
@handle_errors
async def get_ticket(
    ticket_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user
    try:
        detail = await TicketService(db).get_ticket(ticket_id)
    except TicketNotFoundError as exc:
        return _not_found(exc.message)
    return success_response(data=detail.model_dump(), message="ok")


@router.post("/{ticket_id}/accept")
@handle_errors
async def accept_ticket(
    ticket_id: int,
    body: EmptyBody | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user, body
    try:
        payload, events = await TicketService(db).accept(ticket_id)
    except TicketNotFoundError as exc:
        return _not_found(exc.message)
    except TicketConflictError as exc:
        return _error(str(exc), "CONFLICT", status.HTTP_409_CONFLICT)
    await db.commit()
    await publish_events(events)
    return success_response(data=payload.model_dump(), message="ok")


@router.post("/{ticket_id}/messages")
@handle_errors
async def reply_ticket(
    ticket_id: int,
    body: TicketMessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user
    try:
        payload, events = await TicketService(db).reply(ticket_id, body.content)
    except TicketNotFoundError as exc:
        return _not_found(exc.message)
    except TicketConflictError as exc:
        return _error(str(exc), "CONFLICT", status.HTTP_409_CONFLICT)
    await db.commit()
    await publish_events(events)
    return success_response(data=payload.model_dump(), message="ok")


@router.post("/{ticket_id}/close")
@handle_errors
async def close_ticket(
    ticket_id: int,
    body: EmptyBody | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user, body
    try:
        payload, events = await TicketService(db).close(ticket_id)
    except TicketNotFoundError as exc:
        return _not_found(exc.message)
    except TicketConflictError as exc:
        return _error(str(exc), "CONFLICT", status.HTTP_409_CONFLICT)
    await db.commit()
    await publish_events(events)
    return success_response(data=payload.model_dump(), message="ok")
