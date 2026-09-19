"""知识入库：校验、异步状态机、失败回滚。

打标 / 向量 / FAQ 一律走 llm_http（httpx）。有 Key 时调用真实百炼 Chat/Embedding；
无 Key 时由 llm_http 使用本地 Mock，本模块不另开 Mock 入库通道。
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pycore.core import get_logger
from pydantic import BaseModel, ConfigDict, Field
from src.config.settings import BACKEND_DIR, get_settings
from src.db.models import Chunk, Document, Faq
from src.db.session import get_db_context
from src.integrations.llm_http import LlmHttpError, chat_json, embed_texts, has_real_llm_key
from src.prompts import load_prompt
from src.repositories.document import DocumentRepository

logger = get_logger()

PROJECT_ROOT = BACKEND_DIR.parent
UNSUPPORTED_FORMAT_MESSAGE = "不支持该格式，请上传 PDF、Word（.docx）、Markdown 或 txt"
EXTRACT_FAILED_MESSAGE = "无法提取正文，文档未入库"
INGEST_FAILED_MESSAGE = "入库失败，请重新上传"
INTERRUPTED_MESSAGE = "入库中断，请重新上传"
ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "txt",
}
DOCUMENT_STATUSES = {"queued", "processing", "ready", "failed"}
STAGE_PROGRESS = {
    "queued": 0,
    "extracting": 10,
    "chunking": 25,
    "tagging": 45,
    "embedding": 70,
    "faq_extracting": 90,
    "ready": 100,
}
ENTITY_TYPES = {"product", "device", "resource"}
_INGEST_TASKS: set[asyncio.Task] = set()


class EntityPublic(BaseModel):
    name: str
    type: str


class ChunkPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordinal: int
    content: str
    object_types: list[str]
    request_types: list[str]
    entities: list[EntityPublic]


class FaqPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str


class DocumentSummary(BaseModel):
    id: int
    filename: str
    content_type: str
    status: str
    stage: str
    progress_percent: int
    error_message: str | None
    char_count: int
    chunk_count: int
    faq_count: int
    object_types: list[str]
    request_types: list[str]
    created_at: str


class DocumentDetail(DocumentSummary):
    chunks: list[ChunkPublic] = Field(default_factory=list)
    faqs: list[FaqPublic] = Field(default_factory=list)


class IngestError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def resolve_upload_dir(upload_dir: str) -> Path:
    path = Path(upload_dir)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()
    else:
        path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_taxonomy_path(tag_taxonomy_path: str) -> Path:
    path = Path(tag_taxonomy_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def extension_content_type(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    return ALLOWED_EXTENSIONS.get(suffix)


def too_large_message() -> str:
    settings = get_settings()
    max_mb = max(1, settings.upload_max_bytes // (1024 * 1024))
    return f"文件过大，最大 {max_mb}MB"


def _format_dt(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def load_taxonomy() -> dict[str, Any]:
    path = resolve_taxonomy_path(get_settings().tag_taxonomy_path)
    return json.loads(path.read_text(encoding="utf-8"))


def allowed_object_types(taxonomy: dict[str, Any]) -> set[str]:
    return {item["code"] for item in taxonomy.get("object_types", [])}


def allowed_request_types(taxonomy: dict[str, Any]) -> set[str]:
    return {item["code"] for item in taxonomy.get("request_types", [])}


def extract_text(path: Path, content_type: str) -> str:
    if content_type == "pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(str(path))
            if getattr(reader, "is_encrypted", False):
                return ""
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception:
            logger.exception("PDF 正文提取失败")
            return ""
        return "\n".join(pages).strip()

    if content_type == "docx":
        from docx import Document as DocxDocument

        try:
            document = DocxDocument(str(path))
            return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
        except Exception:
            logger.exception("DOCX 正文提取失败")
            return ""

    raw = path.read_bytes()
    for encoding in ("utf-8", "gbk"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return ""


def split_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        paragraphs = [text.strip()] if text.strip() else []
    chunks: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= chunk_size:
            chunks.append(paragraph)
            continue
        start = 0
        step = max(1, chunk_size - overlap)
        while start < len(paragraph):
            end = min(len(paragraph), start + chunk_size)
            piece = paragraph[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(paragraph):
                break
            start += step
    return chunks


def _sanitize_entities(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        kind = str(item.get("type") or "").strip()
        if name and kind in ENTITY_TYPES:
            cleaned.append({"name": name, "type": kind})
    return cleaned


def _delete_file(path_str: str | None) -> None:
    if not path_str:
        return
    path = Path(path_str)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("删除未完成原文失败", path=str(path))


class IngestService:
    def __init__(self, repo: DocumentRepository):
        self.repo = repo

    def to_summary(
        self,
        document: Document,
        chunks: list[Chunk] | None = None,
        faqs: list[Faq] | None = None,
    ) -> DocumentSummary:
        ready = document.status == "ready"
        chunk_items = chunks or []
        faq_items = faqs or []
        object_types = _unique(
            [code for chunk in chunk_items for code in (chunk.object_types or [])]
        )
        request_types = _unique(
            [code for chunk in chunk_items for code in (chunk.request_types or [])]
        )
        return DocumentSummary(
            id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            status=document.status,
            stage=document.stage,
            progress_percent=document.progress_percent,
            error_message=document.error_message,
            char_count=document.char_count,
            chunk_count=len(chunk_items) if ready else 0,
            faq_count=len(faq_items) if ready else 0,
            object_types=object_types if ready else [],
            request_types=request_types if ready else [],
            created_at=_format_dt(document.created_at),
        )

    def to_detail(
        self,
        document: Document,
        chunks: list[Chunk],
        faqs: list[Faq],
    ) -> DocumentDetail:
        summary = self.to_summary(document, chunks, faqs)
        ready = document.status == "ready"
        return DocumentDetail(
            **summary.model_dump(),
            chunks=(
                [
                    ChunkPublic(
                        id=chunk.id,
                        ordinal=chunk.ordinal,
                        content=chunk.content,
                        object_types=list(chunk.object_types or []),
                        request_types=list(chunk.request_types or []),
                        entities=_sanitize_entities(chunk.entities),
                    )
                    for chunk in chunks
                ]
                if ready
                else []
            ),
            faqs=(
                [
                    FaqPublic(id=faq.id, question=faq.question, answer=faq.answer)
                    for faq in faqs
                ]
                if ready
                else []
            ),
        )

    async def submit_upload(self, filename: str, payload: bytes) -> DocumentSummary:
        settings = get_settings()
        safe_name = Path(filename).name
        content_type = extension_content_type(safe_name)
        if content_type is None:
            raise ValueError(UNSUPPORTED_FORMAT_MESSAGE)
        if len(payload) > settings.upload_max_bytes:
            raise ValueError(too_large_message())

        upload_dir = resolve_upload_dir(settings.upload_dir)
        stored = upload_dir / f"{uuid.uuid4().hex}_{safe_name}"
        stored.write_bytes(payload)
        try:
            document = await self.repo.create(
                filename=safe_name,
                content_type=content_type,
                storage_path=str(stored),
            )
        except Exception:
            _delete_file(str(stored))
            raise
        logger.info("文档已接收并进入队列", document_id=document.id)
        return self.to_summary(document)

    async def get_summary(self, document: Document) -> DocumentSummary:
        chunks: list[Chunk] = []
        faqs: list[Faq] = []
        if document.status == "ready":
            chunks = await self.repo.list_chunks(document.id)
            faqs = await self.repo.list_faqs(document.id)
        return self.to_summary(document, chunks, faqs)

    async def get_detail(self, document: Document) -> DocumentDetail:
        chunks = await self.repo.list_chunks(document.id) if document.status == "ready" else []
        faqs = await self.repo.list_faqs(document.id) if document.status == "ready" else []
        return self.to_detail(document, chunks, faqs)


def schedule_ingest(document_id: int, user_id: int) -> None:
    task = asyncio.create_task(_run_ingest_job(document_id, user_id))
    _INGEST_TASKS.add(task)
    task.add_done_callback(_INGEST_TASKS.discard)


async def fail_interrupted_ingests() -> None:
    async with get_db_context() as session:
        repo = DocumentRepository(session)
        documents = await repo.list_interrupted()
        for document in documents:
            path = document.storage_path
            await repo.delete_chunks_and_faqs(document.id)
            await repo.save_progress(
                document,
                status="failed",
                stage="failed",
                error_message=INTERRUPTED_MESSAGE,
                clear_storage=True,
            )
            _delete_file(path)
            logger.info("启动时将中断入库标为失败", document_id=document.id)


async def _run_ingest_job(document_id: int, user_id: int) -> None:
    settings = get_settings()
    try:
        await asyncio.wait_for(
            _ingest_document(document_id, user_id),
            timeout=settings.ingest_job_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.error("入库任务超时", document_id=document_id)
        await _fail_document(document_id, user_id, INGEST_FAILED_MESSAGE)
    except IngestError as exc:
        await _fail_document(document_id, user_id, exc.message)
    except LlmHttpError as exc:
        logger.error("入库外部模型失败", document_id=document_id, detail=str(exc))
        await _fail_document(document_id, user_id, INGEST_FAILED_MESSAGE)
    except Exception:
        logger.exception("入库任务异常", document_id=document_id)
        await _fail_document(document_id, user_id, INGEST_FAILED_MESSAGE)


async def _set_stage(document_id: int, user_id: int, stage: str, status: str) -> None:
    from src.api.ws import publish_document_progress

    percent = STAGE_PROGRESS[stage]
    async with get_db_context() as session:
        repo = DocumentRepository(session)
        document = await repo.get_by_id(document_id)
        if document is None:
            raise IngestError(INGEST_FAILED_MESSAGE)
        await repo.save_progress(
            document,
            status=status,
            stage=stage,
            progress_percent=percent,
        )
    await publish_document_progress(user_id, document_id, status, stage, percent)


async def _fail_document(document_id: int, user_id: int, message: str) -> None:
    from src.api.ws import publish_document_failed, publish_document_progress

    async with get_db_context() as session:
        repo = DocumentRepository(session)
        document = await repo.get_by_id(document_id)
        if document is None:
            return
        path = document.storage_path
        await repo.delete_chunks_and_faqs(document_id)
        await repo.save_progress(
            document,
            status="failed",
            stage="failed",
            error_message=message,
            clear_storage=True,
        )
    _delete_file(path)
    await publish_document_progress(
        user_id, document_id, "failed", "failed", STAGE_PROGRESS.get("extracting", 10)
    )
    await publish_document_failed(user_id, document_id, message)
    logger.info("文档入库失败并已回滚", document_id=document_id)


async def _ingest_document(document_id: int, user_id: int) -> None:
    from src.api.ws import publish_document_progress, publish_document_ready

    settings = get_settings()
    await _set_stage(document_id, user_id, "extracting", "processing")
    async with get_db_context() as session:
        repo = DocumentRepository(session)
        document = await repo.get_by_id(document_id)
        if document is None or not document.storage_path:
            raise IngestError(INGEST_FAILED_MESSAGE)
        storage_path = Path(document.storage_path)
        content_type = document.content_type
        filename = document.filename

    text = extract_text(storage_path, content_type)
    if not text:
        raise IngestError(EXTRACT_FAILED_MESSAGE)

    await _set_stage(document_id, user_id, "chunking", "processing")
    chunk_texts = split_chunks(text, settings.chunk_size_chars, settings.chunk_overlap_chars)
    if not chunk_texts:
        raise IngestError(EXTRACT_FAILED_MESSAGE)

    await _set_stage(document_id, user_id, "tagging", "processing")
    if has_real_llm_key():
        logger.info("入库将调用真实百炼 Chat/Embedding（llm_http）", document_id=document_id)
    else:
        logger.info("无 LLM Key，使用本地 Mock", document_id=document_id)
    tagged = await _tag_chunks(chunk_texts)
    if not any(item["object_types"] or item["request_types"] for item in tagged):
        raise IngestError(INGEST_FAILED_MESSAGE)

    await _set_stage(document_id, user_id, "embedding", "processing")
    chunk_vectors = await embed_texts(chunk_texts)

    await _set_stage(document_id, user_id, "faq_extracting", "processing")
    faqs = await _extract_faqs(text, filename)
    faq_vectors = await embed_texts([item["question"] for item in faqs]) if faqs else []

    async with get_db_context() as session:
        repo = DocumentRepository(session)
        document = await repo.get_by_id(document_id)
        if document is None:
            raise IngestError(INGEST_FAILED_MESSAGE)
        await repo.delete_chunks_and_faqs(document_id)
        for item, vector in zip(tagged, chunk_vectors, strict=True):
            await repo.add_chunk(
                document_id=document_id,
                ordinal=item["ordinal"],
                content=item["content"],
                object_types=item["object_types"],
                request_types=item["request_types"],
                entities=item["entities"],
                embedding=vector,
            )
        for item, vector in zip(faqs, faq_vectors, strict=True):
            await repo.add_faq(
                document_id=document_id,
                question=item["question"],
                answer=item["answer"],
                embedding=vector,
            )
        await repo.save_progress(
            document,
            status="ready",
            stage="ready",
            progress_percent=STAGE_PROGRESS["ready"],
            char_count=len(text),
            clear_error=True,
        )
    await publish_document_progress(
        user_id, document_id, "ready", "ready", STAGE_PROGRESS["ready"]
    )
    await publish_document_ready(user_id, document_id)
    logger.info("文档入库成功", document_id=document_id)


async def _tag_chunks(chunk_texts: list[str]) -> list[dict[str, Any]]:
    settings = get_settings()
    taxonomy = load_taxonomy()
    object_codes = allowed_object_types(taxonomy)
    request_codes = allowed_request_types(taxonomy)
    system_prompt = load_prompt("m001_tagging.txt").strip()
    tagged: list[dict[str, Any]] = [
        {
            "ordinal": index,
            "content": content,
            "object_types": [],
            "request_types": [],
            "entities": [],
        }
        for index, content in enumerate(chunk_texts)
    ]
    for start in range(0, len(chunk_texts), settings.tag_batch_size):
        batch = [
            {"ordinal": start + offset, "content": content}
            for offset, content in enumerate(chunk_texts[start : start + settings.tag_batch_size])
        ]
        user_payload = {
            "object_types": taxonomy.get("object_types", []),
            "request_types": taxonomy.get("request_types", []),
            "classification_rules": taxonomy.get("classification_rules", []),
            "chunks": batch,
        }
        result = await chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0.1,
            purpose="tagging",
        )
        rows = result.get("chunks") if isinstance(result.get("chunks"), list) else []
        by_ordinal = {
            int(row.get("ordinal")): row
            for row in rows
            if isinstance(row, dict) and row.get("ordinal") is not None
        }
        for item in tagged[start : start + len(batch)]:
            row = by_ordinal.get(item["ordinal"], {})
            objects = [
                code
                for code in row.get("object_types", [])
                if isinstance(code, str) and code in object_codes
            ]
            requests = [
                code
                for code in row.get("request_types", [])
                if isinstance(code, str) and code in request_codes
            ]
            item["object_types"] = _unique(objects)
            item["request_types"] = _unique(requests)
            item["entities"] = _sanitize_entities(row.get("entities"))
    return tagged


async def _extract_faqs(text: str, filename: str) -> list[dict[str, str]]:
    settings = get_settings()
    system_prompt = (
        load_prompt("m002_faq.txt")
        .replace("{faq_max_per_document}", str(settings.faq_max_per_document))
        .strip()
    )
    source = text[: settings.faq_source_max_chars]
    result = await chat_json(
        [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {"filename": filename, "text": source}, ensure_ascii=False
                ),
            },
        ],
        temperature=0.2,
        purpose="faq",
    )
    rows = result.get("faqs") if isinstance(result.get("faqs"), list) else []
    faqs: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        question = str(row.get("question") or "").strip()
        answer = str(row.get("answer") or "").strip()
        if question and answer:
            faqs.append({"question": question, "answer": answer})
        if len(faqs) >= settings.faq_max_per_document:
            break
    return faqs
