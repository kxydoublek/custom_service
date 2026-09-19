"""转人工工单状态机（API-011～016）与实时事件载荷。"""

from __future__ import annotations

from datetime import datetime, timezone

from pycore.core import get_logger
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.settings import get_settings
from src.db.models import Message, Ticket
from src.repositories.conversation import ConversationRepository
from src.repositories.ticket import TICKET_STATUSES, TicketRepository
from src.services.qa import PREVIEW_MAX_CHARS, MessagePublic, to_message_public

logger = get_logger()

HANDOFF_WAITING = "waiting"
HANDOFF_IN_PROGRESS = "in_progress"
HANDOFF_NONE = "none"


class TicketNotFoundError(Exception):
    def __init__(self, message: str = "工单不存在"):
        super().__init__(message)
        self.message = message


class TicketConflictError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TicketMessageCreate(BaseModel):
    content: str


class TicketSummary(BaseModel):
    id: int
    conversation_id: int
    status: str
    title: str
    preview: str
    created_at: str


class TicketDetail(TicketSummary):
    messages: list[MessagePublic] = Field(default_factory=list)
    accepted_at: str | None
    closed_at: str | None


class TransferData(BaseModel):
    handoff_state: str
    wait_message: MessagePublic


class AcceptTicketData(BaseModel):
    id: int
    status: str
    accepted_at: str


class CloseTicketData(BaseModel):
    id: int
    status: str
    closed_at: str


class ReplyTicketData(BaseModel):
    agent_message: MessagePublic


def _format_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _preview_text(messages: list[Message], title: str) -> str:
    for message in messages:
        if message.role == "user":
            return message.content[:PREVIEW_MAX_CHARS]
    if messages:
        return messages[-1].content[:PREVIEW_MAX_CHARS]
    return title[:PREVIEW_MAX_CHARS]


class TicketService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tickets = TicketRepository(db)
        self.conversations = ConversationRepository(db)

    async def transfer(self, conversation_id: int) -> tuple[TransferData, list[dict]]:
        conversation = await self.conversations.get_by_id(conversation_id)
        if conversation is None:
            raise TicketNotFoundError("会话不存在")
        existing = await self.tickets.get_open(conversation_id)
        if existing is not None:
            raise TicketConflictError("当前已在等待或由人工处理")

        ticket = await self.tickets.create_pending(conversation_id)
        wait_text = get_settings().wait_human_text
        wait_message = await self.conversations.add_message(
            conversation_id=conversation_id,
            role="system",
            content=wait_text,
            source=None,
        )
        messages = await self.conversations.list_messages(conversation_id)
        preview = _preview_text(
            [item for item in messages if item.id != wait_message.id],
            conversation.title,
        )
        wait_public = to_message_public(wait_message)
        events = [
            {
                "event": "ticket.created",
                "ticket_id": ticket.id,
                "conversation_id": conversation_id,
                "title": conversation.title,
                "preview": preview,
            },
            {
                "event": "handoff.changed",
                "conversation_id": conversation_id,
                "handoff_state": HANDOFF_WAITING,
            },
            {
                "event": "message.created",
                "conversation_id": conversation_id,
                "message": wait_public.model_dump(),
            },
        ]
        logger.info(
            "已创建待接入工单并写入等待文案",
            ticket_id=ticket.id,
            conversation_id=conversation_id,
        )
        return (
            TransferData(handoff_state=HANDOFF_WAITING, wait_message=wait_public),
            events,
        )

    async def list_tickets(
        self, *, page: int, page_size: int, status: str | None
    ) -> tuple[list[TicketSummary], int]:
        if status is not None and status not in TICKET_STATUSES:
            raise ValueError("状态不正确")
        total = await self.tickets.count(status)
        rows = await self.tickets.list_page(
            offset=(page - 1) * page_size,
            limit=page_size,
            status=status,
        )
        items = [await self._to_summary(ticket) for ticket in rows]
        return items, total

    async def get_ticket(self, ticket_id: int) -> TicketDetail:
        ticket = await self._require_ticket(ticket_id)
        summary = await self._to_summary(ticket)
        messages = await self.conversations.list_messages(ticket.conversation_id)
        return TicketDetail(
            **summary.model_dump(),
            messages=[to_message_public(item) for item in messages],
            accepted_at=_format_dt(ticket.accepted_at),
            closed_at=_format_dt(ticket.closed_at),
        )

    async def accept(self, ticket_id: int) -> tuple[AcceptTicketData, list[dict]]:
        ticket = await self._require_ticket(ticket_id)
        if ticket.status != "pending":
            raise TicketConflictError("无法接入")
        ticket = await self.tickets.mark_processing(ticket)
        accepted_at = _format_dt(ticket.accepted_at)
        assert accepted_at is not None
        events = [
            {
                "event": "ticket.accepted",
                "ticket_id": ticket.id,
                "conversation_id": ticket.conversation_id,
            },
            {
                "event": "handoff.changed",
                "conversation_id": ticket.conversation_id,
                "handoff_state": HANDOFF_IN_PROGRESS,
            },
        ]
        logger.info("工单已接入", ticket_id=ticket.id, conversation_id=ticket.conversation_id)
        return (
            AcceptTicketData(id=ticket.id, status="processing", accepted_at=accepted_at),
            events,
        )

    async def reply(self, ticket_id: int, raw_content: str) -> tuple[ReplyTicketData, list[dict]]:
        settings = get_settings()
        content = raw_content.strip()
        if not content:
            raise ValueError("请输入要发送的内容")
        if len(content) > settings.message_max_chars:
            raise ValueError("请输入要发送的内容")

        ticket = await self._require_ticket(ticket_id)
        if ticket.status != "processing":
            raise TicketConflictError("不能回复")
        if await self.conversations.get_by_id(ticket.conversation_id) is None:
            raise TicketNotFoundError("工单不存在")

        message = await self.conversations.add_message(
            conversation_id=ticket.conversation_id,
            role="agent",
            content=content,
            source=None,
        )
        public = to_message_public(message)
        events = [
            {
                "event": "message.created",
                "conversation_id": ticket.conversation_id,
                "message": public.model_dump(),
            }
        ]
        logger.info(
            "客服回复已落库并待推送",
            ticket_id=ticket.id,
            conversation_id=ticket.conversation_id,
        )
        return ReplyTicketData(agent_message=public), events

    async def close(self, ticket_id: int) -> tuple[CloseTicketData, list[dict]]:
        ticket = await self._require_ticket(ticket_id)
        if ticket.status == "closed":
            raise TicketConflictError("已关闭")
        ticket = await self.tickets.mark_closed(ticket)
        closed_at = _format_dt(ticket.closed_at)
        assert closed_at is not None
        events = [
            {
                "event": "ticket.closed",
                "ticket_id": ticket.id,
                "conversation_id": ticket.conversation_id,
            },
            {
                "event": "handoff.changed",
                "conversation_id": ticket.conversation_id,
                "handoff_state": HANDOFF_NONE,
            },
        ]
        logger.info("工单已关闭", ticket_id=ticket.id, conversation_id=ticket.conversation_id)
        return (
            CloseTicketData(id=ticket.id, status="closed", closed_at=closed_at),
            events,
        )

    async def _require_ticket(self, ticket_id: int) -> Ticket:
        ticket = await self.tickets.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError("工单不存在")
        return ticket

    async def _to_summary(self, ticket: Ticket) -> TicketSummary:
        conversation = await self.conversations.get_by_id(ticket.conversation_id)
        title = conversation.title if conversation is not None else ""
        messages = await self.conversations.list_messages(ticket.conversation_id)
        created_at = _format_dt(ticket.created_at)
        assert created_at is not None
        return TicketSummary(
            id=ticket.id,
            conversation_id=ticket.conversation_id,
            status=ticket.status,
            title=title,
            preview=_preview_text(messages, title),
            created_at=created_at,
        )
