from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Conversation, GenerationLock, Message, Ticket, utc_now

OPEN_TICKET_STATUSES = ("pending", "processing")


class ConversationConflictError(Exception):
    def __init__(self, message: str = "请等待当前回复结束"):
        super().__init__(message)


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, title: str) -> Conversation:
        conversation = Conversation(title=title)
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def get_by_id(self, conversation_id: int) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def list_page(self, *, offset: int, limit: int) -> list[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Conversation))
        return int(result.scalar_one())

    async def add_message(
        self,
        *,
        conversation_id: int,
        role: str,
        content: str,
        source: str | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            source=source,
        )
        self.db.add(message)
        conversation = await self.get_by_id(conversation_id)
        if conversation is not None:
            conversation.updated_at = utc_now()
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get_message(self, message_id: int) -> Message | None:
        result = await self.db.execute(select(Message).where(Message.id == message_id))
        return result.scalar_one_or_none()

    async def list_messages(self, conversation_id: int) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list(result.scalars().all())

    async def list_recent_messages(
        self, conversation_id: int, limit: int
    ) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        items = list(result.scalars().all())
        items.reverse()
        return items

    async def last_message(self, conversation_id: int) -> Message | None:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def assistant_after(
        self, conversation_id: int, user_message_id: int
    ) -> Message | None:
        result = await self.db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.id > user_message_id,
                Message.role == "assistant",
            )
            .order_by(Message.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_open_ticket(self, conversation_id: int) -> Ticket | None:
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

    async def get_lock(self, conversation_id: int) -> GenerationLock | None:
        result = await self.db.execute(
            select(GenerationLock).where(
                GenerationLock.conversation_id == conversation_id
            )
        )
        return result.scalar_one_or_none()

    async def acquire_lock(
        self, *, conversation_id: int, user_message_id: int
    ) -> GenerationLock:
        lock = GenerationLock(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
        )
        async with self.db.begin_nested():
            try:
                self.db.add(lock)
                await self.db.flush()
            except IntegrityError as exc:
                raise ConversationConflictError("请等待当前回复结束") from exc
        await self.db.refresh(lock)
        return lock

    async def release_lock(self, conversation_id: int) -> None:
        lock = await self.get_lock(conversation_id)
        if lock is not None:
            await self.db.delete(lock)
            await self.db.flush()

    async def update_title(self, conversation: Conversation, title: str) -> None:
        conversation.title = title
        conversation.updated_at = utc_now()
        await self.db.flush()
