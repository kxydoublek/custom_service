"""
数据库模型（由 pycore/integrations/db/models.py 模板扩展）。
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""

    pass


class User(Base):
    """内部账号。密码哈希不进入接口响应。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)


class Document(Base):
    """入库文档。仅 status=ready 可被 FAQ/召回。"""

    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_status_created_at", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    faqs: Mapped[list["Faq"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """成功入库文档的分块与向量。"""

    __tablename__ = "chunks"
    __table_args__ = (Index("ix_chunks_document_id", "document_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    object_types: Mapped[list] = mapped_column(JSON, nullable=False)
    request_types: Mapped[list] = mapped_column(JSON, nullable=False)
    entities: Mapped[list] = mapped_column(JSON, nullable=False)
    embedding: Mapped[list] = mapped_column(JSON, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class Faq(Base):
    """成功入库文档抽出的 FAQ。"""

    __tablename__ = "faqs"
    __table_args__ = (Index("ix_faqs_document_id", "document_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(JSON, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="faqs")


class Conversation(Base):
    """员工会话。长期保留，不含跨会话记忆。"""

    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_updated_at", "updated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="新会话")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    generation_lock: Mapped["GenerationLock | None"] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", uselist=False
    )


class Message(Base):
    """会话消息。流式 done 后才有完整 assistant。"""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Ticket(Base):
    """转人工工单。同一会话未关闭单至多一张；title/preview 由会话消息派生。"""

    __tablename__ = "tickets"
    __table_args__ = (Index("ix_tickets_status_created_at", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="tickets")


class GenerationLock(Base):
    """防止同一会话并行两路自动回复。"""

    __tablename__ = "generation_locks"

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), primary_key=True
    )
    user_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="generation_lock")
