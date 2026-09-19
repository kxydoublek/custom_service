"""会话、FAQ 拦截与流式自动回复编排（API-007/008/009/010/017）。"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from pycore.core import get_logger
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.settings import get_settings
from src.db.models import Conversation, Message, Ticket
from src.db.session import get_db_context
from src.integrations.llm_http import (
    STREAM_UNAVAILABLE_TEXT,
    LlmHttpError,
    chat_json,
    chat_stream,
    embed_texts,
)
from src.prompts import load_prompt
from src.repositories.conversation import ConversationConflictError, ConversationRepository
from src.repositories.document import DocumentRepository
from src.services.ingest import (
    allowed_object_types,
    allowed_request_types,
    load_taxonomy,
)

logger = get_logger()

NEW_CONVERSATION_TITLE = "新会话"
TITLE_MAX_CHARS = 30
PREVIEW_MAX_CHARS = 30
SMALL_TALK_MAX_TOKENS = 256
CLASSIFY_TEMPERATURE = 0.1
SMALL_TALK_TEMPERATURE = 0.7
KNOWLEDGE_TEMPERATURE = 0.2
SOURCE_FAQ = "faq"
SOURCE_SMALL_TALK = "small_talk"
SOURCE_KNOWLEDGE = "knowledge_qa"
OUT_OF_SCOPE_STATUSES = {"needs_clarification", "requires_live_data", "out_of_scope"}
_DELTA_SPLIT = re.compile(r".+?(?:[。！？，、；：,.!?;:\n]|$)")
_FAQ_STRIP = re.compile(r"[\s\W_]+", re.UNICODE)
_CHITCHAT_HINT = re.compile(r"(天气|你好|早上好|哈哈|谢谢|随便聊聊)")


class QaNotFoundError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class MessageCreate(BaseModel):
    content: str


class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    source: str | None
    created_at: str


class ConversationSummary(BaseModel):
    id: int
    title: str
    updated_at: str
    preview: str


class ConversationDetail(BaseModel):
    id: int
    title: str
    handoff_state: str
    messages: list[MessagePublic] = Field(default_factory=list)
    created_at: str
    updated_at: str


class SendMessageData(BaseModel):
    user_message: MessagePublic
    assistant_message: None = None
    handoff_state: str
    stream: bool


def _format_dt(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def normalize_faq_question(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return _FAQ_STRIP.sub("", normalized)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    denom = math.sqrt(left_norm) * math.sqrt(right_norm)
    if denom == 0:
        return 0.0
    return float(dot / denom)


def split_delta_text(text: str) -> list[str]:
    if not text:
        return [""]
    parts = [part for part in _DELTA_SPLIT.findall(text) if part]
    return parts or [text]


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _handoff_state(ticket: Ticket | None) -> str:
    if ticket is None:
        return "none"
    if ticket.status == "pending":
        return "waiting"
    if ticket.status == "processing":
        return "in_progress"
    return "none"


def to_message_public(message: Message) -> MessagePublic:
    return MessagePublic(
        id=message.id,
        role=message.role,
        content=message.content,
        source=message.source,
        created_at=_format_dt(message.created_at),
    )


class QaService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conversations = ConversationRepository(db)
        self.documents = DocumentRepository(db)

    async def create_conversation(self) -> ConversationDetail:
        conversation = await self.conversations.create(title=NEW_CONVERSATION_TITLE)
        logger.info("已新建会话", conversation_id=conversation.id)
        return await self._to_detail(conversation, [])

    async def list_conversations(
        self, *, page: int, page_size: int
    ) -> tuple[list[ConversationSummary], int]:
        total = await self.conversations.count()
        rows = await self.conversations.list_page(
            offset=(page - 1) * page_size, limit=page_size
        )
        summaries: list[ConversationSummary] = []
        for conversation in rows:
            last = await self.conversations.last_message(conversation.id)
            preview = (last.content if last is not None else "")[:PREVIEW_MAX_CHARS]
            summaries.append(
                ConversationSummary(
                    id=conversation.id,
                    title=conversation.title,
                    updated_at=_format_dt(conversation.updated_at),
                    preview=preview,
                )
            )
        return summaries, total

    async def get_conversation(self, conversation_id: int) -> ConversationDetail:
        conversation = await self._require_conversation(conversation_id)
        messages = await self.conversations.list_messages(conversation_id)
        return await self._to_detail(conversation, messages)

    async def send_user_message(
        self, conversation_id: int, raw_content: str
    ) -> SendMessageData:
        settings = get_settings()
        content = raw_content.strip()
        if not content:
            raise ValueError("请输入要发送的内容")
        if len(content) > settings.message_max_chars:
            raise ValueError("请输入要发送的内容")

        conversation = await self._require_conversation(conversation_id)
        existing_lock = await self.conversations.get_lock(conversation_id)
        if existing_lock is not None:
            raise ConversationConflictError("请等待当前回复结束")

        ticket = await self.conversations.get_open_ticket(conversation_id)
        last = await self.conversations.last_message(conversation_id)
        reused = False
        if (
            ticket is None
            and last is not None
            and last.role == "user"
            and last.content == content
            and await self.conversations.assistant_after(conversation_id, last.id) is None
        ):
            user_message = last
            reused = True
        else:
            user_message = await self.conversations.add_message(
                conversation_id=conversation_id,
                role="user",
                content=content,
            )
            if conversation.title == NEW_CONVERSATION_TITLE:
                await self.conversations.update_title(
                    conversation, content[:TITLE_MAX_CHARS]
                )

        handoff = _handoff_state(ticket)
        if ticket is not None:
            logger.info(
                "人工进行中，已保存员工消息且不走自动回复",
                conversation_id=conversation_id,
                ticket_status=ticket.status,
            )
            return SendMessageData(
                user_message=to_message_public(user_message),
                handoff_state=handoff,
                stream=False,
            )

        try:
            await self.conversations.acquire_lock(
                conversation_id=conversation_id,
                user_message_id=user_message.id,
            )
        except ConversationConflictError:
            raise
        logger.info(
            "员工消息已保存并进入自动回复流",
            conversation_id=conversation_id,
            reused=reused,
        )
        return SendMessageData(
            user_message=to_message_public(user_message),
            handoff_state="none",
            stream=True,
        )

    async def _require_conversation(self, conversation_id: int) -> Conversation:
        conversation = await self.conversations.get_by_id(conversation_id)
        if conversation is None:
            raise QaNotFoundError("会话不存在")
        return conversation

    async def _to_detail(
        self, conversation: Conversation, messages: list[Message]
    ) -> ConversationDetail:
        ticket = await self.conversations.get_open_ticket(conversation.id)
        return ConversationDetail(
            id=conversation.id,
            title=conversation.title,
            handoff_state=_handoff_state(ticket),
            messages=[to_message_public(item) for item in messages],
            created_at=_format_dt(conversation.created_at),
            updated_at=_format_dt(conversation.updated_at),
        )


async def stream_assistant_reply(
    conversation_id: int, after_user_message_id: int
) -> AsyncIterator[str]:
    settings = get_settings()
    async with get_db_context() as db:
        service = QaService(db)
        conversation = await service.conversations.get_by_id(conversation_id)
        if conversation is None:
            raise QaNotFoundError("无法继续回复")
        user_message = await service.conversations.get_message(after_user_message_id)
        if (
            user_message is None
            or user_message.conversation_id != conversation_id
            or user_message.role != "user"
        ):
            raise QaNotFoundError("无法继续回复")
        existing = await service.conversations.assistant_after(
            conversation_id, after_user_message_id
        )
        ticket = await service.conversations.get_open_ticket(conversation_id)
        if existing is not None:
            async for chunk in _replay_existing(existing, _handoff_state(ticket)):
                yield chunk
            return
        lock = await service.conversations.get_lock(conversation_id)
        if lock is not None and lock.user_message_id != after_user_message_id:
            raise ConversationConflictError("请等待当前回复结束")
        if lock is None:
            await service.conversations.acquire_lock(
                conversation_id=conversation_id,
                user_message_id=after_user_message_id,
            )

    source = SOURCE_KNOWLEDGE
    full_text = settings.out_of_scope_text
    use_model_stream = False
    model_messages: list[dict[str, str]] = []
    temperature = KNOWLEDGE_TEMPERATURE
    max_tokens: int | None = None
    purpose = "knowledge_qa"

    try:
        plan = await _plan_reply(conversation_id, user_message.content)
        source = plan["source"]
        full_text = plan["text"]
        use_model_stream = plan["stream"]
        model_messages = plan["messages"]
        temperature = plan["temperature"]
        max_tokens = plan["max_tokens"]
        purpose = plan["purpose"]
    except Exception:
        logger.exception("自动回复编排失败，改走超范围兜底")
        source = SOURCE_KNOWLEDGE
        full_text = settings.out_of_scope_text
        use_model_stream = False

    yield format_sse(
        "meta",
        {
            "assistant_message_id": None,
            "source": source,
            "handoff_state": "none",
        },
    )

    collected = ""
    try:
        if use_model_stream:
            async for delta in chat_stream(
                model_messages,
                temperature=temperature,
                purpose=purpose,
                max_tokens=max_tokens,
            ):
                if not delta:
                    continue
                collected += delta
                yield format_sse("delta", {"text": delta})
        else:
            for piece in split_delta_text(full_text):
                collected += piece
                yield format_sse("delta", {"text": piece})
    except LlmHttpError as exc:
        logger.error("自动回复流式失败", detail=str(exc))
        async with get_db_context() as db:
            await ConversationRepository(db).release_lock(conversation_id)
        yield format_sse(
            "error",
            {"error": STREAM_UNAVAILABLE_TEXT, "error_code": "INTERNAL_ERROR"},
        )
        return
    except Exception:
        logger.exception("自动回复流式发生内部错误")
        async with get_db_context() as db:
            await ConversationRepository(db).release_lock(conversation_id)
        yield format_sse(
            "error",
            {"error": STREAM_UNAVAILABLE_TEXT, "error_code": "INTERNAL_ERROR"},
        )
        return

    async with get_db_context() as db:
        repo = ConversationRepository(db)
        assistant = await repo.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=collected,
            source=source,
        )
        await repo.release_lock(conversation_id)
        payload = to_message_public(assistant).model_dump()
        logger.info("自动回复已落库", conversation_id=conversation_id, source=source)
    yield format_sse("done", {"assistant_message": payload})


async def _replay_existing(message: Message, handoff_state: str) -> AsyncIterator[str]:
    public = to_message_public(message)
    yield format_sse(
        "meta",
        {
            "assistant_message_id": message.id,
            "source": message.source,
            "handoff_state": handoff_state,
        },
    )
    yield format_sse("delta", {"text": message.content})
    yield format_sse("done", {"assistant_message": public.model_dump()})


async def _plan_reply(conversation_id: int, user_text: str) -> dict[str, Any]:
    settings = get_settings()
    async with get_db_context() as db:
        faqs = await DocumentRepository(db).list_retrievable_faqs()
    faq_hit = await _match_faq(user_text, faqs)
    if faq_hit is not None:
        return {
            "source": SOURCE_FAQ,
            "text": faq_hit,
            "stream": False,
            "messages": [],
            "temperature": CLASSIFY_TEMPERATURE,
            "max_tokens": None,
            "purpose": "faq",
        }

    classification = await _classify(conversation_id, user_text)
    issues = classification.get("issues")
    if not isinstance(issues, list):
        issues = []
    oos_issues = [
        raw
        for raw in issues
        if isinstance(raw, dict)
        and str(raw.get("processing_status") or "") in OUT_OF_SCOPE_STATUSES
    ]
    oos_statuses = {
        str(raw.get("processing_status"))
        for raw in oos_issues
    }
    treat_as_small_talk = classification.get("message_type") == "small_talk"
    if treat_as_small_talk and oos_issues:
        # 寒暄即使被标 out_of_scope 仍走闲聊；信息不足/实时工单/非寒暄超范围走同一兜底。
        if oos_statuses & {"needs_clarification", "requires_live_data"}:
            treat_as_small_talk = False
        elif "out_of_scope" in oos_statuses and not _CHITCHAT_HINT.search(user_text):
            treat_as_small_talk = False
        if not treat_as_small_talk:
            logger.info("分类标为闲聊但含超范围类状态，改走同一兜底，不追问")
    if treat_as_small_talk:
        messages = await _small_talk_messages(conversation_id, user_text)
        return {
            "source": SOURCE_SMALL_TALK,
            "text": "",
            "stream": True,
            "messages": messages,
            "temperature": SMALL_TALK_TEMPERATURE,
            "max_tokens": SMALL_TALK_MAX_TOKENS,
            "purpose": "small_talk",
        }

    if not issues:
        return _fallback_plan(settings.out_of_scope_text)

    ready_issues: list[dict[str, Any]] = []
    for raw in issues:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("processing_status") or "")
        if status in OUT_OF_SCOPE_STATUSES:
            continue
        object_set, request_type = _issue_tags(raw)
        if not object_set and not request_type:
            continue
        ready_issues.append(raw)

    if not ready_issues:
        logger.info("分类结果全部为超范围或无标签，走兜底")
        return _fallback_plan(settings.out_of_scope_text)

    async with get_db_context() as db:
        chunks = await DocumentRepository(db).list_retrievable_chunks()
    recalled: list[dict[str, Any]] = []
    seen: set[int] = set()
    for issue in ready_issues:
        object_set, request_type = _issue_tags(issue)
        query = str(issue.get("retrieval_query") or user_text)
        logger.info(
            "准备按标签过滤后召回，不打全库",
            object_types=sorted(object_set),
            request_type=request_type,
            corpus=len(chunks),
        )
        matched = await _retrieve_chunks(query, chunks, object_set, request_type)
        for item in matched:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            recalled.append(item)

    if not recalled:
        logger.info("标签过滤后无召回，返回无法回答")
        return _fallback_plan(settings.no_knowledge_text)

    messages = await _knowledge_messages(conversation_id, user_text, recalled)
    return {
        "source": SOURCE_KNOWLEDGE,
        "text": "",
        "stream": True,
        "messages": messages,
        "temperature": KNOWLEDGE_TEMPERATURE,
        "max_tokens": None,
        "purpose": "knowledge_qa",
    }


def _fallback_plan(text: str) -> dict[str, Any]:
    return {
        "source": SOURCE_KNOWLEDGE,
        "text": text,
        "stream": False,
        "messages": [],
        "temperature": KNOWLEDGE_TEMPERATURE,
        "max_tokens": None,
        "purpose": "knowledge_qa",
    }


def _issue_tags(issue: dict[str, Any]) -> tuple[set[str], str | None]:
    taxonomy = load_taxonomy()
    objects = allowed_object_types(taxonomy)
    requests = allowed_request_types(taxonomy)
    object_set: set[str] = set()
    primary = issue.get("primary_object_type")
    if isinstance(primary, str) and primary in objects:
        object_set.add(primary)
    related = issue.get("related_object_types")
    if isinstance(related, list):
        for code in related:
            if isinstance(code, str) and code in objects:
                object_set.add(code)
    request_type = issue.get("request_type")
    if not isinstance(request_type, str) or request_type not in requests:
        request_type = None
    return object_set, request_type


async def _match_faq(user_text: str, faqs: list) -> str | None:
    settings = get_settings()
    needle = normalize_faq_question(user_text)
    if needle:
        for faq in faqs:
            if normalize_faq_question(faq.question) == needle:
                logger.info("FAQ 规范化全等命中，跳过分类与召回")
                return faq.answer
    if not faqs:
        return None
    try:
        vectors = await embed_texts([user_text])
    except LlmHttpError:
        logger.warning("FAQ 向量失败，跳过拦截并走分类")
        return None
    if not vectors:
        return None
    query_vec = vectors[0]
    best_score = -1.0
    best_answer: str | None = None
    for faq in faqs:
        score = cosine_similarity(query_vec, list(faq.embedding or []))
        if score > best_score:
            best_score = score
            best_answer = faq.answer
    if best_answer is not None and best_score >= settings.faq_similarity_threshold:
        logger.info(
            "FAQ 余弦命中，跳过分类与召回",
            score=round(best_score, 4),
            threshold=settings.faq_similarity_threshold,
        )
        return best_answer
    logger.info(
        "FAQ 未命中阈值，进入分类",
        score=round(best_score, 4),
        threshold=settings.faq_similarity_threshold,
    )
    return None


async def _classify(conversation_id: int, user_text: str) -> dict[str, Any]:
    settings = get_settings()
    taxonomy = load_taxonomy()
    async with get_db_context() as db:
        history = await ConversationRepository(db).list_recent_messages(
            conversation_id, settings.context_message_limit
        )
    payload = {
        "object_types": taxonomy.get("object_types", []),
        "request_types": taxonomy.get("request_types", []),
        "classification_rules": taxonomy.get("classification_rules", []),
        "processing_statuses": taxonomy.get("processing_statuses", {}),
        "query_output": taxonomy.get("query_output", {}),
        "context_policy": taxonomy.get("context_policy", {}),
        "conversation_messages": [
            {"role": item.role, "content": item.content} for item in history
        ],
        "current_user_message": user_text,
    }
    try:
        result = await chat_json(
            [
                {"role": "system", "content": load_prompt("m003_classify.txt").strip()},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=CLASSIFY_TEMPERATURE,
            purpose="classification",
        )
    except LlmHttpError:
        logger.warning("提问分类 JSON 失败，改走超范围兜底")
        return {}
    if not isinstance(result, dict):
        logger.warning("提问分类结果不是对象，改走超范围兜底")
        return {}
    result.pop("clarification_question", None)
    issues = result.get("issues")
    statuses: list[str] = []
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict):
                issue["clarification_question"] = None
                statuses.append(str(issue.get("processing_status") or ""))
    logger.info(
        "提问分类完成，已丢弃追问字段且不调用实时工单工具",
        message_type=result.get("message_type"),
        processing_statuses=statuses,
    )
    return result


async def _small_talk_messages(
    conversation_id: int, user_text: str
) -> list[dict[str, str]]:
    settings = get_settings()
    async with get_db_context() as db:
        history = await ConversationRepository(db).list_recent_messages(
            conversation_id, settings.context_message_limit
        )
    messages = [{"role": "system", "content": load_prompt("m004_small_talk.txt").strip()}]
    for item in history:
        if item.role in {"user", "assistant"}:
            messages.append({"role": item.role, "content": item.content})
    if not history or history[-1].content != user_text:
        messages.append({"role": "user", "content": user_text})
    return messages


async def _knowledge_messages(
    conversation_id: int,
    user_text: str,
    chunks: list[dict[str, Any]],
) -> list[dict[str, str]]:
    settings = get_settings()
    system = (
        load_prompt("m005_knowledge_qa.txt")
        .replace("{no_knowledge_text}", settings.no_knowledge_text)
        .strip()
    )
    async with get_db_context() as db:
        history = await ConversationRepository(db).list_recent_messages(
            conversation_id, settings.context_message_limit
        )
    messages = [{"role": "system", "content": system}]
    for item in history:
        if item.role in {"user", "assistant"}:
            messages.append({"role": item.role, "content": item.content})
    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                {"question": user_text, "chunks": chunks},
                ensure_ascii=False,
            ),
        }
    )
    return messages


async def _retrieve_chunks(
    query: str,
    chunks: list,
    object_set: set[str],
    request_type: str | None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    if not object_set and not request_type:
        logger.info("标签两侧皆空，跳过召回")
        return []
    filtered = []
    for chunk in chunks:
        chunk_objects = set(chunk.object_types or [])
        chunk_requests = list(chunk.request_types or [])
        if object_set and chunk_objects.isdisjoint(object_set):
            continue
        if request_type and request_type not in chunk_requests:
            continue
        filtered.append(chunk)
    logger.info(
        "检索前已按标签过滤，不是全库无过滤",
        object_types=sorted(object_set),
        request_type=request_type,
        corpus=len(chunks),
        filtered=len(filtered),
    )
    if not filtered:
        return []
    try:
        vectors = await embed_texts([query])
    except LlmHttpError:
        logger.warning("召回向量失败，视为空召回")
        return []
    if not vectors:
        return []
    query_vec = vectors[0]
    scored: list[tuple[float, Any]] = []
    for chunk in filtered:
        score = cosine_similarity(query_vec, list(chunk.embedding or []))
        if score >= settings.retrieval_min_score:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[: settings.retrieval_top_k]
    recalled = [
        {
            "id": chunk.id,
            "content": chunk.content,
            "object_types": list(chunk.object_types or []),
            "request_types": list(chunk.request_types or []),
        }
        for _, chunk in top
    ]
    logger.info(
        "标签过滤后余弦召回完成",
        recalled=len(recalled),
        chunk_ids=[item["id"] for item in recalled],
        chunk_object_types=[item["object_types"] for item in recalled],
        chunk_request_types=[item["request_types"] for item in recalled],
    )
    return recalled
