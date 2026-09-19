"""百炼 OpenAI 兼容 Chat / Embedding：httpx 直连，无 Key 时本地 Mock。
禁止 dashscope SDK 与 OpenAIProvider。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pycore.core import get_logger

from src.config.settings import get_settings

logger = get_logger()

# EXT-002：每批最多 10 条
EMBED_BATCH_LIMIT = 10

_OBJECT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hardware": ("电脑", "显示器", "键盘", "鼠标", "打印机", "摄像头", "麦克风", "硬件"),
    "software": ("outlook", "office", "photoshop", "windows", "驱动", "软件"),
    "account": ("账号", "密码", "登录", "mfa", "锁定", "认证"),
    "network": ("vpn", "wifi", "wi-fi", "网络", "远程桌面", "白名单"),
    "resource": ("crm", "erp", "gitlab", "nas", "共享", "仓库", "数据库"),
}
_REQUEST_KEYWORDS: dict[str, tuple[str, ...]] = {
    "troubleshooting": ("失败", "故障", "崩溃", "异常", "黑屏", "怎么办", "排查"),
    "maintenance": ("报修", "重装", "送修", "维修"),
    "resource_request": ("申请", "安装", "扩容", "归还"),
    "permission_request": ("权限", "开通", "usb"),
    "usage_guidance": ("怎么", "如何", "配置", "导入", "ssh"),
    "policy_process": ("几年", "审批", "制度", "流程"),
}


class LlmHttpError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def has_real_llm_key() -> bool:
    return bool(get_settings().llm_api_key)


def _parse_json_content(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            data = json.loads(fenced.group(1))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _mock_embed_one(text: str, dimensions: int) -> list[float]:
    seed = text.encode("utf-8")
    values: list[float] = []
    while len(values) < dimensions:
        seed = hashlib.sha256(seed).digest()
        for offset in range(0, 32, 4):
            n = int.from_bytes(seed[offset : offset + 4], "big") / 2**32
            values.append(n * 2 - 1)
    values = values[:dimensions]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def _match_codes(text: str, table: dict[str, tuple[str, ...]]) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for code, keywords in table.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            hits.append(code)
    return hits


def _mock_entities(text: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    for name, kind in (
        ("VPN", "product"),
        ("Outlook", "product"),
        ("GitLab", "product"),
        ("NAS", "resource"),
        ("WiFi", "product"),
    ):
        if name.lower() in text.lower():
            entities.append({"name": name, "type": kind})
    return entities


def _mock_tagging(messages: list[dict[str, str]]) -> dict[str, Any]:
    user_text = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    chunks_in: list[dict[str, Any]] = []
    parsed = _parse_json_content(user_text)
    if parsed and isinstance(parsed.get("chunks"), list):
        chunks_in = [c for c in parsed["chunks"] if isinstance(c, dict)]
    else:
        numbered = re.findall(
            r'"ordinal"\s*:\s*(\d+).*?"content"\s*:\s*"(.*?)"',
            user_text,
            re.DOTALL,
        )
        for ordinal, content in numbered:
            chunks_in.append({"ordinal": int(ordinal), "content": content})
    tagged = []
    for item in chunks_in:
        content = str(item.get("content") or "")
        tagged.append(
            {
                "ordinal": int(item.get("ordinal") or 0),
                "object_types": _match_codes(content, _OBJECT_KEYWORDS),
                "request_types": _match_codes(content, _REQUEST_KEYWORDS),
                "entities": _mock_entities(content),
            }
        )
    return {"chunks": tagged}


def _mock_faq(messages: list[dict[str, str]], limit: int) -> dict[str, Any]:
    user_text = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    body = user_text.strip()
    faqs: list[dict[str, str]] = []
    if "vpn" in body.lower() and ("失败" in body or "认证" in body):
        faqs.append(
            {
                "question": "VPN 提示认证失败怎么办？",
                "answer": "请先检查账号是否锁定，再重试导入配置文件。",
            }
        )
    snippet = re.split(r"[。！？\n]", body)
    first = next((part.strip() for part in snippet if len(part.strip()) >= 8), "")
    if first and not faqs:
        faqs.append(
            {
                "question": f"{first[:40]}？",
                "answer": first[:400],
            }
        )
    if body and not faqs:
        faqs.append(
            {
                "question": "这份文档讲了什么？",
                "answer": body[:400],
            }
        )
    return {"faqs": faqs[:limit]}


def _last_user_text(messages: list[dict[str, str]]) -> str:
    return next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")


def _classification_user_text(messages: list[dict[str, str]]) -> str:
    raw = _last_user_text(messages)
    parsed = _parse_json_content(raw)
    if parsed and isinstance(parsed.get("current_user_message"), str):
        return parsed["current_user_message"]
    return raw


def _mock_classify(messages: list[dict[str, str]]) -> dict[str, Any]:
    text = _classification_user_text(messages)

    def issue(
        status: str,
        *,
        primary: str | None = None,
        related: list[str] | None = None,
        request: str | None = None,
        clarification: str | None = None,
    ) -> dict[str, Any]:
        return {
            "issue_id": "1",
            "summary": text[:80],
            "primary_object_type": primary,
            "related_object_types": related or [],
            "request_type": request,
            "entities": [],
            "symptom": None,
            "error_message": None,
            "processing_status": status,
            "retrieval_query": text if status == "ready" else None,
            "missing_information": [],
            "clarification_question": clarification,
        }

    if any(keyword in text for keyword in ("你好", "谢谢", "在吗", "早上好", "哈哈")):
        return {"message_type": "small_talk", "issues": []}
    if any(keyword in text for keyword in ("工单进度", "申请进度", "查工单", "实时工单")):
        return {
            "message_type": "service_request",
            "issues": [issue("requires_live_data", clarification="工单号是多少？")],
        }
    if any(keyword in text for keyword in ("今天天气", "股票", "晚饭吃什么", "超出范围")):
        return {"message_type": "service_request", "issues": [issue("out_of_scope")]}
    if any(keyword in text for keyword in ("那个东西坏了", "信息不足", "怎么弄一下")):
        return {
            "message_type": "service_request",
            "issues": [issue("needs_clarification", clarification="具体是什么设备？")],
        }
    if "无标签" in text:
        return {"message_type": "service_request", "issues": [issue("ready")]}

    objects = _match_codes(text, _OBJECT_KEYWORDS)
    requests = _match_codes(text, _REQUEST_KEYWORDS)
    primary = objects[0] if objects else None
    related = objects[1:]
    request_type = requests[0] if requests else None
    if primary or request_type:
        return {
            "message_type": "service_request",
            "issues": [
                issue(
                    "ready",
                    primary=primary,
                    related=related,
                    request=request_type,
                )
            ],
        }
    return {"message_type": "service_request", "issues": [issue("out_of_scope")]}


def _mock_knowledge_answer(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    raw = _last_user_text(messages)
    parsed = _parse_json_content(raw)
    chunks = parsed.get("chunks") if parsed and isinstance(parsed.get("chunks"), list) else []
    contents = [
        str(item.get("content") or "").strip()
        for item in chunks
        if isinstance(item, dict) and str(item.get("content") or "").strip()
    ]
    if contents:
        return contents[0][:400]
    return settings.no_knowledge_text


async def _mock_chat(messages: list[dict[str, str]], purpose: str) -> str:
    settings = get_settings()
    if purpose == "tagging":
        payload = _mock_tagging(messages)
    elif purpose == "classification":
        if "【分类失败】" in _classification_user_text(messages):
            return "NOT_JSON"
        payload = _mock_classify(messages)
    else:
        payload = _mock_faq(messages, settings.faq_max_per_document)
    return json.dumps(payload, ensure_ascii=False)


async def _mock_stream(messages: list[dict[str, str]], purpose: str) -> AsyncIterator[str]:
    if purpose == "small_talk":
        text = "你好，我是企业内部 IT 助手，有 IT 问题随时问我。"
    else:
        text = _mock_knowledge_answer(messages)
    step = 8
    for index in range(0, len(text), step):
        yield text[index : index + step]


STREAM_UNAVAILABLE_TEXT = "暂时无法回答，请稍后重试"


async def _http_chat(
    messages: list[dict[str, str]],
    temperature: float,
    json_object: bool,
    max_tokens: int | None = None,
) -> str:
    settings = get_settings()
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    body: dict[str, Any] = {
        "model": settings.llm_chat_model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if json_object:
        body["response_format"] = {"type": "json_object"}
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    attempts = settings.llm_max_retries + 1
    last_error: Exception | None = None
    async with httpx.AsyncClient(trust_env=False, timeout=timeout) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(url, headers=headers, json=body)
                if response.status_code in (401, 403):
                    logger.error("百炼 Chat 鉴权失败", status_code=response.status_code)
                    raise LlmHttpError("入库失败，请重新上传", status_code=response.status_code)
                if response.status_code == 429 or response.status_code >= 500:
                    logger.warning(
                        "百炼 Chat 可重试失败",
                        status_code=response.status_code,
                        attempt=attempt + 1,
                    )
                    last_error = LlmHttpError(
                        "入库失败，请重新上传", status_code=response.status_code
                    )
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                if response.status_code >= 400:
                    logger.error("百炼 Chat 调用失败", status_code=response.status_code)
                    raise LlmHttpError("入库失败，请重新上传", status_code=response.status_code)
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.info("调用百炼 Chat 成功，返回含 choices 字段")
                return content if isinstance(content, str) else json.dumps(content)
            except LlmHttpError:
                raise
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("百炼 Chat 超时", attempt=attempt + 1)
                await asyncio.sleep(0.1 * (attempt + 1))
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("百炼 Chat 网络失败", attempt=attempt + 1, detail=str(exc))
                await asyncio.sleep(0.1 * (attempt + 1))
    logger.error("百炼 Chat 重试耗尽")
    raise LlmHttpError("入库失败，请重新上传") from last_error


async def _http_stream(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None,
) -> AsyncIterator[str]:
    settings = get_settings()
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    body: dict[str, Any] = {
        "model": settings.llm_chat_model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    attempts = settings.llm_max_retries + 1
    last_error: Exception | None = None
    yielded = False
    async with httpx.AsyncClient(trust_env=False, timeout=timeout) as client:
        for attempt in range(attempts):
            try:
                async with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code in (401, 403):
                        logger.error("百炼 Chat 流式鉴权失败", status_code=response.status_code)
                        raise LlmHttpError(
                            STREAM_UNAVAILABLE_TEXT, status_code=response.status_code
                        )
                    if response.status_code == 429 or response.status_code >= 500:
                        logger.warning(
                            "百炼 Chat 流式可重试失败",
                            status_code=response.status_code,
                            attempt=attempt + 1,
                        )
                        last_error = LlmHttpError(
                            STREAM_UNAVAILABLE_TEXT, status_code=response.status_code
                        )
                        if yielded:
                            break
                        await asyncio.sleep(0.1 * (attempt + 1))
                        continue
                    if response.status_code >= 400:
                        logger.error("百炼 Chat 流式调用失败", status_code=response.status_code)
                        raise LlmHttpError(
                            STREAM_UNAVAILABLE_TEXT, status_code=response.status_code
                        )
                    async for line in response.aiter_lines():
                        stripped = line.strip()
                        if not stripped.startswith("data:"):
                            continue
                        payload = stripped[5:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            data = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta") or {}
                        content = delta.get("content") or ""
                        if content:
                            yielded = True
                            yield content
                        if choice.get("finish_reason") == "length":
                            logger.info("百炼 Chat 流式因长度结束，按已输出落库")
                            return
                    logger.info("调用百炼 Chat 流式成功，返回含 choices 增量")
                    return
            except LlmHttpError:
                raise
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("百炼 Chat 流式超时", attempt=attempt + 1)
                if yielded:
                    break
                await asyncio.sleep(0.1 * (attempt + 1))
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("百炼 Chat 流式网络失败", attempt=attempt + 1, detail=str(exc))
                if yielded:
                    break
                await asyncio.sleep(0.1 * (attempt + 1))
    logger.error("百炼 Chat 流式重试耗尽")
    raise LlmHttpError(STREAM_UNAVAILABLE_TEXT) from last_error


async def chat_json(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    purpose: str,
) -> dict[str, Any]:
    if not has_real_llm_key():
        raw = await _mock_chat(messages, purpose)
        parsed = _parse_json_content(raw)
        if parsed is None:
            raise LlmHttpError("入库失败，请重新上传")
        return parsed

    raw = await _http_chat(messages, temperature, json_object=True)
    parsed = _parse_json_content(raw)
    if parsed is None:
        logger.warning("百炼 Chat JSON 解析失败，再请求一次")
        raw = await _http_chat(messages, temperature, json_object=True)
        parsed = _parse_json_content(raw)
    if parsed is None:
        raise LlmHttpError("入库失败，请重新上传")
    return parsed


async def chat_stream(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    purpose: str,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    if not has_real_llm_key():
        logger.info("无 LLM Key，使用本地 Mock Chat 流式", purpose=purpose)
        async for chunk in _mock_stream(messages, purpose):
            yield chunk
        return
    async for chunk in _http_stream(messages, temperature, max_tokens):
        yield chunk


async def _http_embed(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    url = f"{settings.llm_base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    vectors: list[list[float] | None] = [None] * len(texts)
    attempts = settings.llm_max_retries + 1
    async with httpx.AsyncClient(trust_env=False, timeout=timeout) as client:
        for start in range(0, len(texts), EMBED_BATCH_LIMIT):
            batch = texts[start : start + EMBED_BATCH_LIMIT]
            body = {
                "model": settings.llm_embed_model,
                "input": batch,
                "dimensions": settings.llm_embed_dimensions,
                "encoding_format": "float",
            }
            last_error: Exception | None = None
            for attempt in range(attempts):
                try:
                    response = await client.post(url, headers=headers, json=body)
                    if response.status_code in (401, 403):
                        logger.error("百炼 Embedding 鉴权失败", status_code=response.status_code)
                        raise LlmHttpError(
                            "入库失败，请重新上传", status_code=response.status_code
                        )
                    if response.status_code == 429 or response.status_code >= 500:
                        logger.warning(
                            "百炼 Embedding 可重试失败",
                            status_code=response.status_code,
                            attempt=attempt + 1,
                        )
                        last_error = LlmHttpError(
                            "入库失败，请重新上传", status_code=response.status_code
                        )
                        await asyncio.sleep(0.1 * (attempt + 1))
                        continue
                    if response.status_code >= 400:
                        logger.error("百炼 Embedding 调用失败", status_code=response.status_code)
                        raise LlmHttpError(
                            "入库失败，请重新上传", status_code=response.status_code
                        )
                    data = response.json()
                    items = sorted(data["data"], key=lambda item: int(item["index"]))
                    for offset, item in enumerate(items):
                        vectors[start + offset] = list(item["embedding"])
                    logger.info("调用百炼 Embedding 成功，返回含 data 字段")
                    last_error = None
                    break
                except LlmHttpError:
                    raise
                except httpx.TimeoutException as exc:
                    last_error = exc
                    logger.warning("百炼 Embedding 超时", attempt=attempt + 1)
                    await asyncio.sleep(0.1 * (attempt + 1))
                except httpx.HTTPError as exc:
                    last_error = exc
                    logger.warning("百炼 Embedding 网络失败", attempt=attempt + 1, detail=str(exc))
                    await asyncio.sleep(0.1 * (attempt + 1))
            if any(slot is None for slot in vectors[start : start + len(batch)]):
                logger.error("百炼 Embedding 重试耗尽")
                raise LlmHttpError("入库失败，请重新上传") from last_error
    return [item if item is not None else [] for item in vectors]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    if not has_real_llm_key():
        logger.info("无 LLM Key，使用本地 Mock Embedding")
        return [_mock_embed_one(text, settings.llm_embed_dimensions) for text in texts]
    return await _http_embed(texts)
