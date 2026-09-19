from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Ticket, utc_now
from src.repositories.conversation import OPEN_TICKET_STATUSES

TICKET_STATUSES = ("pending", "processing", "closed")


class TicketRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_pending(self, conversation_id: int) -> Ticket:
        ticket = Ticket(conversation_id=conversation_id, status="pending")
        self.db.add(ticket)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            raise ValueError("当前已在等待或由人工处理") from exc
        await self.db.refresh(ticket)
        return ticket

    async def get_by_id(self, ticket_id: int) -> Ticket | None:
        result = await self.db.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    async def get_open(self, conversation_id: int) -> Ticket | None:
        result = await self.db.execute(
            select(Ticket)
            .where(
                Ticket.conversation_id == conversation_id,
                Ticket.status.in_(OPEN_TICKET_STATUSES),
            )
            .order_by(Ticket.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        status: str | None = None,
    ) -> list[Ticket]:
        stmt = select(Ticket)
        if status is not None:
            stmt = stmt.where(Ticket.status == status)
        stmt = stmt.order_by(Ticket.created_at.desc(), Ticket.id.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, status: str | None = None) -> int:
        stmt = select(func.count()).select_from(Ticket)
        if status is not None:
            stmt = stmt.where(Ticket.status == status)
        result = await self.db.execute(stmt)
        return int(result.scalar_one())

    async def mark_processing(self, ticket: Ticket) -> Ticket:
        ticket.status = "processing"
        ticket.accepted_at = utc_now()
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket

    async def mark_closed(self, ticket: Ticket) -> Ticket:
        ticket.status = "closed"
        ticket.closed_at = utc_now()
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket
