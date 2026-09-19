from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Chunk, Document, Faq, utc_now


class DocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        filename: str,
        content_type: str,
        storage_path: str,
        status: str = "queued",
        stage: str = "queued",
        progress_percent: int = 0,
    ) -> Document:
        document = Document(
            filename=filename,
            content_type=content_type,
            status=status,
            stage=stage,
            progress_percent=progress_percent,
            error_message=None,
            storage_path=storage_path,
            char_count=0,
        )
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def get_by_id(self, document_id: int) -> Document | None:
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        status: str | None = None,
    ) -> list[Document]:
        stmt = select(Document)
        if status:
            stmt = stmt.where(Document.status == status)
        stmt = stmt.order_by(Document.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, status: str | None = None) -> int:
        stmt = select(func.count()).select_from(Document)
        if status:
            stmt = stmt.where(Document.status == status)
        result = await self.db.execute(stmt)
        return int(result.scalar_one())

    async def list_interrupted(self) -> list[Document]:
        result = await self.db.execute(
            select(Document).where(Document.status.in_(("queued", "processing")))
        )
        return list(result.scalars().all())

    async def list_chunks(self, document_id: int) -> list[Chunk]:
        result = await self.db.execute(
            select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.ordinal)
        )
        return list(result.scalars().all())

    async def list_faqs(self, document_id: int) -> list[Faq]:
        result = await self.db.execute(
            select(Faq).where(Faq.document_id == document_id).order_by(Faq.id)
        )
        return list(result.scalars().all())

    async def add_chunk(
        self,
        *,
        document_id: int,
        ordinal: int,
        content: str,
        object_types: list[str],
        request_types: list[str],
        entities: list[dict],
        embedding: list[float],
    ) -> Chunk:
        chunk = Chunk(
            document_id=document_id,
            ordinal=ordinal,
            content=content,
            object_types=object_types,
            request_types=request_types,
            entities=entities,
            embedding=embedding,
        )
        self.db.add(chunk)
        await self.db.flush()
        await self.db.refresh(chunk)
        return chunk

    async def add_faq(
        self,
        *,
        document_id: int,
        question: str,
        answer: str,
        embedding: list[float],
    ) -> Faq:
        faq = Faq(
            document_id=document_id,
            question=question,
            answer=answer,
            embedding=embedding,
        )
        self.db.add(faq)
        await self.db.flush()
        await self.db.refresh(faq)
        return faq

    async def delete_chunks_and_faqs(self, document_id: int) -> None:
        await self.db.execute(delete(Chunk).where(Chunk.document_id == document_id))
        await self.db.execute(delete(Faq).where(Faq.document_id == document_id))
        await self.db.flush()

    async def list_retrievable_chunks(self) -> list[Chunk]:
        result = await self.db.execute(
            select(Chunk)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.status == "ready")
            .order_by(Chunk.id)
        )
        return list(result.scalars().all())

    async def list_retrievable_faqs(self) -> list[Faq]:
        result = await self.db.execute(
            select(Faq)
            .join(Document, Faq.document_id == Document.id)
            .where(Document.status == "ready")
            .order_by(Faq.id)
        )
        return list(result.scalars().all())

    async def save_progress(
        self,
        document: Document,
        *,
        status: str | None = None,
        stage: str | None = None,
        progress_percent: int | None = None,
        error_message: str | None = None,
        storage_path: str | None = None,
        char_count: int | None = None,
        clear_storage: bool = False,
        clear_error: bool = False,
    ) -> Document:
        if status is not None:
            document.status = status
        if stage is not None:
            document.stage = stage
        if progress_percent is not None:
            document.progress_percent = progress_percent
        if error_message is not None:
            document.error_message = error_message
        if clear_error:
            document.error_message = None
        if storage_path is not None:
            document.storage_path = storage_path
        if clear_storage:
            document.storage_path = None
        if char_count is not None:
            document.char_count = char_count
        document.updated_at = utc_now()
        await self.db.flush()
        await self.db.refresh(document)
        return document
