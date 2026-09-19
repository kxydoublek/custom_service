# 智能客服系统 · 七层技术方案

status: Confirmed  
specification: default

本文件按已确认 PRD（`docs/PRD.md`）编写。D-001 方案 B、D-002 方案 A、D-003 方案 A 已于 2026-09-12 由用户确认，相关取值按确认结果写入。整体方案仍为 Draft，待一次总确认后再改为 Confirmed。

规范来源：项目 `.sdd/project.json` 的 `specification: default`。前端 React + TypeScript + Vite + React Router + Hooks/Context；后端 Python 3.11+ FastAPI + 项目内 `pycore/`。本系统**不是**带工具循环的 Agent：不注册 Plugin，不查询实时工单/申请/权限。

---

## 一、用户要完成什么

引用 `docs/PRD.md`「用户目标与完整流程」「需求与验收」「界面约定」。无已确认原型。

| 需求 | 验收 | 入口 | 用户输入 → 处理 → 结果 |
| --- | --- | --- | --- |
| REQ-001 | AC-001、AC-002 | `/login`，登录后切到三端 | 用户名+密码 → 校验预设内部账号 → 进入员工端 / 客服工作台 / 知识库管理端；错误则不能进 |
| REQ-003、REQ-007 | AC-005、AC-007、AC-019、AC-020、AC-021、AC-024 | `/knowledge` | 上传 PDF/Word/Markdown/txt → 立即收下并后台入库；可离开再回来看进度；成功后分块/标签/FAQ 立即生效；格式不支持当场拒绝；抽不出正文等失败可回看失败原因且不可检索 |
| REQ-002、REQ-007 | AC-003、AC-004、AC-016、AC-017、AC-018、AC-022、AC-023 | `/employee` | 当前会话发问 → FAQ 相近拦截 → 闲聊直接回 → 信息不足/超范围/需实时数据统一兜底 → 其余先打标签再范围内召回作答；先标来源再逐字出正文 |
| REQ-004、REQ-006 | AC-008～AC-015 | `/employee`、`/agent` | 员工点转人工即建待接入工单；员工只见「正在等待人工客服」；客服自行接入、回复、关闭；客服一发员工马上看到；关闭后该会话恢复自动回复 |
| REQ-005 | AC-011 | `/employee` 历史 | 打开本账号历史，看到当时完整问答与来源标记及客服回复；不用历史做跨会话记忆 |

完整数据链路（D-001 方案 B）：

1. 登录取得访问令牌，同一账号打开三端，并建立 WebSocket（API-018）。
2. 知识库提交文档后立即返回「已接收」；后台分块、打标、写向量、抽 FAQ。用户可切换到其它界面；再打开知识库页用列表/详情回看进度。成功即对提问生效，无需确认。
3. 员工在当前会话发消息；未处于未关闭转人工时，先走 FAQ → 闲聊 → 超范围兜底 → 标签范围内知识问答。来源经 SSE 先到达，正文逐字出现。
4. 员工点转人工后只走人工对话；客服接入与回复经 WebSocket 立即推到员工端；关闭后自动回复恢复。
5. 历史会话只读回放完整消息，不参与新会话检索。成功入库原文、会话、工单长期保留（D-003）。

业务规则以 PRD 为准，本节不重复改写。

---

## 二、前后端怎么分工，接口怎么拆

### 分工与栈

| 侧 | 职责 | 技术 |
| --- | --- | --- |
| 前端 `frontend/` | 登录、三端路由、对话流式展示、入库进度回看、工单工作台、WebSocket 收事件 | React 18 + TS + Vite + React Router；Axios 单例（JSON）；`EventSource` 或 fetch 读 SSE；WebSocket 走相对路径 `/ws`；状态用 Hooks / Context |
| 后端 `backend/` | 鉴权、入库后台任务、提问编排与 SSE、工单状态、实时推送、SQLite 与向量检索 | FastAPI + PyCore `APIServer`；业务在 `backend/src/`；`PYTHONPATH=..` 引入 `pycore`；入库用进程内 `asyncio` 后台任务（不另引 Redis 队列） |
| 百炼（外部） | 对话生成、JSON 分类/打标/抽 FAQ、文本向量；闲聊与知识问答可流式 | OpenAI 兼容 HTTP，`httpx.AsyncClient(trust_env=False)`，**禁止** `dashscope` SDK，也**不**走 PyCore `OpenAIProvider` |
| 本机存储 | 账号、会话、消息、文档（含进行中/失败）、分块、FAQ、工单、向量 | SQLite（`backend/data/Customer_Service.db`）；成功原文 `backend/data/uploads/` |

前端开发请求：`VITE_API_BASE_URL=/api`，Vite 代理 `/api` 与 `/ws` 到后端。Agent 开发端口前端 5199 / 后端 8099；用户验收前端 5175 / 后端 8003。后端 CORS 同时允许上述四类 origin。WebSocket 与 SSE 的鉴权见各接口。

鉴权：除登录外均需 `Authorization: Bearer <access_token>`（WS 见 API-018）。同一令牌可调三端接口。幂等：转人工、接入、关闭按资源状态拒绝重复副作用。

等待与通道（D-001 方案 B，已确认）：

| 场景 | 传输 | 用户侧 |
| --- | --- | --- |
| 入库提交 | API-004 同步只做校验与落盘，立即返回 `queued` | 可离开；回来靠 API-005/006；在页时另收 API-018 `document.*` |
| 自动回复 | API-010 先落员工消息并返回 JSON；正文走 API-017 SSE | 先出来源，再逐字；中途切走后再打开会话见完整条 |
| 人工消息 / 工单变化 | API-018 WebSocket 推送；API-009/012 仅作进入页面时的快照 | 客服一发，员工马上看到 |
| 普通 JSON | Axios 超时 15 秒 | 登录、转人工、关单等 |

统一成功/失败信封见 §三 `ApiEnvelope`。SSE 与 WebSocket **不**包该信封。下列 JSON 接口的 `data` 均为信封内业务对象。

### 接口索引

| 编号 | Method / URL | 说明 | 关联 |
| --- | --- | --- | --- |
| API-001 | POST `/api/auth/login` | 内部账号登录 | REQ-001，AC-001、AC-002 |
| API-002 | GET `/api/auth/me` | 恢复登录状态 | REQ-001，AC-001、AC-002 |
| API-003 | POST `/api/auth/logout` | 前端丢弃令牌（无服务端黑名单） | REQ-001 |
| API-004 | POST `/api/documents` | 提交入库（立即返回，后台处理） | REQ-003、REQ-007；AC-005、AC-007、AC-019、AC-020、AC-021、AC-024 |
| API-005 | GET `/api/documents` | 知识库文档列表（含进行中/失败，供回看） | REQ-003；AC-019、AC-020 |
| API-006 | GET `/api/documents/{document_id}` | 进度、失败原因、或成功后的分块/标签/FAQ | REQ-003、REQ-007；AC-019、AC-020、AC-021 |
| API-007 | POST `/api/conversations` | 新建当前会话 | REQ-002、REQ-005 |
| API-008 | GET `/api/conversations` | 历史会话列表 | REQ-005；AC-011 |
| API-009 | GET `/api/conversations/{conversation_id}` | 会话快照（进页/回看，不作人工轮询主通道） | REQ-002、REQ-004、REQ-005；AC-011、AC-008、AC-010 |
| API-010 | POST `/api/conversations/{conversation_id}/messages` | 员工发消息（自动回复不在本响应给全文） | REQ-002、REQ-004、REQ-007；AC-003、AC-004、AC-016～AC-018、AC-022、AC-023、AC-010 |
| API-011 | POST `/api/conversations/{conversation_id}/transfer` | 转人工并建工单 | REQ-004、REQ-006；AC-008、AC-009、AC-012 |
| API-012 | GET `/api/tickets` | 客服工单列表快照 | REQ-006；AC-012、AC-013、AC-015 |
| API-013 | GET `/api/tickets/{ticket_id}` | 工单与对话上下文 | REQ-004、REQ-006；AC-008、AC-013 |
| API-014 | POST `/api/tickets/{ticket_id}/accept` | 接入 | REQ-006；AC-013 |
| API-015 | POST `/api/tickets/{ticket_id}/messages` | 客服回复（落库后经 API-018 推员工） | REQ-004、REQ-006；AC-010、AC-013 |
| API-016 | POST `/api/tickets/{ticket_id}/close` | 关闭工单 | REQ-004、REQ-006；AC-014 |
| API-017 | GET `/api/conversations/{conversation_id}/assistant-stream` | 自动回复 SSE（来源 + 逐字） | REQ-002；AC-003、AC-004、AC-016、AC-017、AC-023 |
| API-018 | GET `/ws` | 入库进度、人工消息、工单变化的 WebSocket | REQ-003、REQ-004、REQ-006；AC-005、AC-008、AC-010、AC-012、AC-013 |
| EXT-001 | POST `{LLM_BASE_URL}/chat/completions` | 百炼 Chat | 入库打标/抽 FAQ、分类；闲聊/知识问答可 `stream=true` |
| EXT-002 | POST `{LLM_BASE_URL}/embeddings` | 百炼 Embedding | FAQ 相近、分块向量、提问向量 |

相对上一版：API-001～API-003、API-007、API-008、API-011、API-013、API-014、API-016 含义不变。API-004 由「同步入库完成」改为「接收任务」。API-005/006 增加进行中/失败与进度字段。API-009/012 降为进页快照。API-010 自动回复改为先落用户消息再指示走 SSE。API-015 增加推送副作用。新增 API-017、API-018。

资源词与路由文件：`auth`、`documents`、`conversations`、`tickets`（对应 `backend/src/api/routes/` 下同名文件）。SSE 挂在 conversations 资源下。`/ws` 在 `main.py` 注册，不另造 tickets-ws 资源。

员工端接口不返回工单状态机枚举（`pending` / `processing` / `closed`）。员工侧只用 `handoff_state`：`none` | `waiting` | `in_progress`。

### API-001 内部账号登录

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-001；AC-001、AC-002 |
| Method / URL | POST `/api/auth/login` |
| 请求 | `Content-Type: application/json`；无 Token。`username` string 必填；`password` string 必填 |
| 成功响应 | 200；`data`: `access_token` string，`token_type` 固定 `"bearer"`，`user`: `{ "id": int, "username": string }` |
| 失败响应 | 400 `VALIDATION_ERROR`；401 `UNAUTHORIZED`（账号或密码错误，文案不区分哪一项） |
| 鉴权 | 公开 |

成功示例：

```json
{
  "success": true,
  "data": {
    "access_token": "<jwt>",
    "token_type": "bearer",
    "user": { "id": 1, "username": "it-admin" }
  },
  "error": null,
  "error_code": null,
  "message": "ok",
  "timestamp": "2026-09-12T07:00:00.000000",
  "request_id": "req-login-1",
  "metadata": {}
}
```

失败示例（密码错误）：HTTP 401，`error_code`=`UNAUTHORIZED`，`error`=`账号或密码不正确`，`data`=`null`。

登录成功后前端连接 API-018。

### API-002 当前登录

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-001；AC-001、AC-002 |
| Method / URL | GET `/api/auth/me` |
| 请求 | 无 body；Header `Authorization` 必填 |
| 成功响应 | 200；`data`: `{ "id": int, "username": string }` |
| 失败响应 | 401 `UNAUTHORIZED` |

未登录或令牌无效时前端不得进入三端。

### API-003 退出

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-001 |
| Method / URL | POST `/api/auth/logout` |
| 请求 | 无 body；Bearer 可选（无服务端会话） |
| 成功响应 | 200；`data`: `{ "logged_out": true }` |
| 失败响应 | 一般不因缺 Token 失败，便于前端清场 |

前端须同时清 Context、`localStorage` 中的 token，并关闭 WebSocket。

### API-004 提交入库

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-003、REQ-007；AC-005、AC-007、AC-019、AC-020、AC-021、AC-024 |
| Method / URL | POST `/api/documents` |
| 请求 | `multipart/form-data` 字段 `file` 必填。扩展名仅 `.pdf` `.docx` `.md` `.markdown` `.txt`（大小写不敏感）。`.doc` 与其它格式拒绝。大小上限见 §七 `upload_max_bytes`（20MB） |
| 成功响应 | **200**；`data` 为 `DocumentSummary`：`status`=`queued`，`stage`=`queued`，`progress_percent`=`0`，`chunks`/`faqs` 为空。**不表示**已可检索 |
| 失败响应 | 400 `VALIDATION_ERROR`（格式不支持、过大）；401 |
| 相对旧含义 | **必须改**：不再同步跑完整流水线，也不在本响应返回 `ready` 详情。格式错误仍当场拒绝、不建记录（AC-007） |
| 生效 | 仅当后台落到 `ready` 后，FAQ 与分块才可被提问使用；无需管理员再确认 |

成功提交后用户可立即切换界面。后台失败不进入可检索状态，记录保留为 `failed` 供回看（AC-020）。成功原文按 D-003 长期保留。

成功 `data` 示例（已接收，尚未完成）：

```json
{
  "id": 12,
  "filename": "vpn-auth.md",
  "content_type": "markdown",
  "status": "queued",
  "stage": "queued",
  "progress_percent": 0,
  "error_message": null,
  "char_count": 0,
  "chunk_count": 0,
  "faq_count": 0,
  "object_types": [],
  "request_types": [],
  "created_at": "2026-09-12T07:10:00.000000"
}
```

失败示例（`.xlsx`）：HTTP 400，`error`=`不支持该格式，请上传 PDF、Word（.docx）、Markdown 或 txt`。

### API-005 文档列表

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-003；AC-019、AC-020 |
| Method / URL | GET `/api/documents?page=1&page_size=20&status=` |
| 请求 | Query：`page` int ≥1 默认 1；`page_size` int 1～50 默认 20；`status` 可选 `queued` \| `processing` \| `ready` \| `failed`，缺省为全部 |
| 成功响应 | 200；`paginated_response`；`data` 为 `DocumentSummary[]`（含进度字段，不含分块全文） |
| 失败响应 | 400、401 |
| 相对旧含义 | 列表从「只含 ready」改为含进行中与失败，供离开后再回看 |

排序：`created_at` 降序。`ready` 项可点进详情看分块/FAQ。

### API-006 文档详情

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-003、REQ-007；AC-019、AC-020、AC-021 |
| Method / URL | GET `/api/documents/{document_id}` |
| 请求 | 路径 `document_id` int |
| 成功响应 | 200；`data`=`DocumentDetail`：进行中时 `chunks`/`faqs` 为空；`ready` 时带齐分块标签与 FAQ；`failed` 时 `error_message` 有中文原因 |
| 失败响应 | 404 `NOT_FOUND`；401 |
| 相对旧含义 | 增加 `status`/`stage`/`progress_percent`/`error_message`；未完成不再假装已入库 |

知识库页用本接口回看进度与结果。员工端不得作为产品入口调用上传或文档列表（AC-006）。

`ready` 时 `data` 关键形状：

```json
{
  "id": 12,
  "filename": "vpn-auth.md",
  "content_type": "markdown",
  "status": "ready",
  "stage": "ready",
  "progress_percent": 100,
  "error_message": null,
  "char_count": 1820,
  "chunk_count": 4,
  "faq_count": 3,
  "object_types": ["network"],
  "request_types": ["troubleshooting"],
  "chunks": [
    {
      "id": 101,
      "ordinal": 0,
      "content": "VPN 认证失败时……",
      "object_types": ["network"],
      "request_types": ["troubleshooting"],
      "entities": [{ "name": "VPN", "type": "product" }]
    }
  ],
  "faqs": [
    {
      "id": 21,
      "question": "VPN 提示认证失败怎么办？",
      "answer": "请先检查账号是否锁定，再重试导入配置文件。"
    }
  ],
  "created_at": "2026-09-12T07:10:00.000000"
}
```

### API-007 新建会话

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-002、REQ-005 |
| Method / URL | POST `/api/conversations` |
| 请求 | JSON `{}` 或无字段 |
| 成功响应 | 200；`data`: `ConversationDetail`，`title` 初始为 `"新会话"`，`messages` 空数组，`handoff_state`=`none` |
| 失败响应 | 401 |

员工点「新会话」先调本接口，再发 API-010。

### API-008 历史会话列表

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-005；AC-011 |
| Method / URL | GET `/api/conversations?page=1&page_size=20` |
| 请求 | 分页同 API-005（无 status） |
| 成功响应 | 200；`data`: `ConversationSummary[]`（`id`、`title`、`updated_at`、`preview`） |
| 失败响应 | 401 |

`preview` 为最近一条可见消息截断，不含工单状态。列表排序：`updated_at` 降序。不把本列表内容送入新会话模型上下文。长期保留（D-003）。

### API-009 会话详情

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-002、REQ-004、REQ-005；AC-011、AC-008、AC-010 |
| Method / URL | GET `/api/conversations/{conversation_id}` |
| 请求 | 路径 id |
| 成功响应 | 200；`data`=`ConversationDetail`：消息含 `source`；`handoff_state` 如上；**无** `ticket_status`。流式已完成的助手消息为完整 `content` |
| 失败响应 | 404、401 |
| 相对旧含义 | **不再**作为转人工期间的 2 秒轮询主通道；进页、刷新、从历史打开时用 |

等待文案以 `role=system` 的消息「正在等待人工客服」出现，不标三种来源。

### API-010 员工发送消息

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-002、REQ-004、REQ-007；AC-003、AC-004、AC-016、AC-017、AC-018、AC-022、AC-023、AC-010 |
| Method / URL | POST `/api/conversations/{conversation_id}/messages` |
| 请求 | JSON：`content` string 必填，去空白后 1～2000 字 |
| 成功响应 | 200；`data`: `{ "user_message": MessagePublic, "assistant_message": null, "handoff_state": HandoffState, "stream": bool }` |
| 失败响应 | 400 空内容；404；401；409 该会话已有未结束的自动回复流 |
| 相对旧含义 | **必须改**：自动回复不再在本响应返回 `assistant_message` 全文。`stream=true` 时前端立刻打开 API-017（`after_user_message_id=user_message.id`）。人工路径 `stream=false`，并经 API-018 把该员工消息推给客服端 |

`stream=true` 示例：

```json
{
  "success": true,
  "data": {
    "user_message": {
      "id": 301,
      "role": "user",
      "content": "连不上公司 VPN，提示认证失败",
      "source": null,
      "created_at": "2026-09-12T07:20:00.000000"
    },
    "assistant_message": null,
    "handoff_state": "none",
    "stream": true
  },
  "error": null,
  "error_code": null,
  "message": "ok",
  "timestamp": "2026-09-12T07:20:00.000000",
  "request_id": "req-msg-1",
  "metadata": {}
}
```

人工未关闭：保存员工消息，`stream=false`，`handoff_state` 为 `waiting` 或 `in_progress`，不调用 FAQ/闲聊/知识问答。

同一 `content` 且会话末尾已是这条 user、尚无后续 assistant（生成失败或客户端重连）：不重复插入 user，返回已有 `user_message` 并 `stream=true`，允许重开 API-017。

### API-011 转人工

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-004、REQ-006；AC-008、AC-009、AC-012 |
| Method / URL | POST `/api/conversations/{conversation_id}/transfer` |
| 请求 | JSON `{}` |
| 成功响应 | 200；`data`: `{ "handoff_state": "waiting", "wait_message": MessagePublic }`，`wait_message.role`=`system`，`content`=`正在等待人工客服`，`source`=`null`。**不返回**工单 id/状态 |
| 失败响应 | 409 `CONFLICT` 当前已有未关闭转人工；404；401 |

一点即建 `pending` 工单，并通过 API-018 向客服端推 `ticket.created`、向员工端推 `handoff.changed` 与 `message.created`（等待文案）。

### API-012 工单列表

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-006；AC-012、AC-013、AC-015 |
| Method / URL | GET `/api/tickets?status=pending&page=1&page_size=20` |
| 请求 | Query `status` 可选 `pending` \| `processing` \| `closed`；缺省为全部，按 `created_at` 降序 |
| 成功响应 | 200 分页；`data`: `TicketSummary[]` |
| 失败响应 | 400、401 |
| 相对旧含义 | 进入工作台时的快照；新单到达靠 API-018，**不再** 3 秒轮询 |

### API-013 工单详情

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-004、REQ-006；AC-008、AC-013 |
| Method / URL | GET `/api/tickets/{ticket_id}` |
| 成功响应 | 200；`data`=`TicketDetail`：工单字段 + 该会话全部消息 |
| 失败响应 | 404、401 |

打开某张工单时拉齐上下文；之后员工新消息经 API-018 `message.created` 追加。

### API-014 接入工单

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-006；AC-013 |
| Method / URL | POST `/api/tickets/{ticket_id}/accept` |
| 请求 | JSON `{}` |
| 成功响应 | 200；`data`: `{ "id": int, "status": "processing", "accepted_at": string }` |
| 失败响应 | 409 非 `pending`；404；401 |

成功后 API-018 推 `ticket.accepted` 与员工侧 `handoff.changed`=`in_progress`。单账号接入者即为该内部账号。

### API-015 客服回复

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-004、REQ-006；AC-010、AC-013 |
| Method / URL | POST `/api/tickets/{ticket_id}/messages` |
| 请求 | JSON：`content` 1～2000 字 |
| 成功响应 | 200；`data`: `{ "agent_message": MessagePublic }`，`role`=`agent`，`source`=`null` |
| 失败响应 | 409 工单不是 `processing`；400；404；401 |
| 相对旧含义 | 落库后**必须**经 API-018 向该会话推 `message.created`，使员工马上看到 |

### API-016 关闭工单

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-004、REQ-006；AC-014 |
| Method / URL | POST `/api/tickets/{ticket_id}/close` |
| 请求 | JSON `{}` |
| 成功响应 | 200；`data`: `{ "id": int, "status": "closed", "closed_at": string }` |
| 失败响应 | 409 已关闭或不存在未关闭单；404；401 |

关闭后 `handoff_state` 回到 `none`，API-018 推 `ticket.closed` 与 `handoff.changed`。再点转人工生成新工单。不设超时关单、员工取消。

### API-017 自动回复流（新增）

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-002；AC-003、AC-004、AC-016、AC-017、AC-023 |
| Method / URL | GET `/api/conversations/{conversation_id}/assistant-stream?after_user_message_id={id}` |
| 请求 | Query `after_user_message_id` int 必填，等于刚保存的员工消息 id。Header `Authorization`；`Accept: text/event-stream` |
| 成功响应 | 200，`Content-Type: text/event-stream`。事件顺序：先 `meta`（含 `source`），再若干 `delta`，最后 `done`（完整 `MessagePublic`） |
| 失败响应 | 开流前可用 JSON 信封：400/404/401/409。开流后用 SSE `event: error` |

SSE 事件（每条 `data` 为 JSON 对象）：

| event | data 字段 | 含义 |
| --- | --- | --- |
| `meta` | `assistant_message_id` int 可空（落库前可暂空）；`source`: `faq` \| `small_talk` \| `knowledge_qa`；`handoff_state` | 来源先于正文，供界面先标「FAQ / 闲聊 / 知识问答」 |
| `delta` | `text` string | 追加正文 |
| `done` | `assistant_message`：完整 `MessagePublic` | 已落库，之后 API-009 能读到全文 |
| `error` | `error` 中文；`error_code` | 本轮无 assistant 落库；前端可重开本流或提示重试 |

FAQ / 超范围兜底 / 无法回答：全文已知，仍先 `meta` 再按小段 `delta` 推出，满足「逐字出现」。闲聊与知识问答：对百炼使用 `stream=true`，把增量转发为 `delta`。

同一 `after_user_message_id` 若已有完整 assistant：不再调模型，只重放 `meta` + 全文一条 `delta` + `done`（断线回看）。

示例：

```
event: meta
data: {"assistant_message_id": null, "source": "faq", "handoff_state": "none"}

event: delta
data: {"text": "请先检查账号是否锁定"}

event: delta
data: {"text": "，再重试导入配置文件。"}

event: done
data: {"assistant_message": {"id": 302, "role": "assistant", "content": "请先检查账号是否锁定，再重试导入配置文件。", "source": "faq", "created_at": "2026-09-12T07:20:01.000000"}}
```

超范围 `source=knowledge_qa`，正文为固定兜底句。无法回答同理。

### API-018 实时通道（新增）

| 项目 | 内容 |
| --- | --- |
| 关联需求 | REQ-003、REQ-004、REQ-006；AC-005、AC-008、AC-010、AC-012、AC-013 |
| Method / URL | GET `/ws`（WebSocket，升级后通信） |
| 鉴权 | 查询参数 `access_token`（浏览器 WS 不便带 Header）；无效则关闭。禁止把 Token 写入日志 |
| 成功 | 101 升级。服务端可发心跳文本 `ping`，客户端回 `pong` |
| 失败 | 鉴权失败关闭连接 |

服务端 → 客户端 JSON 文本帧：

| event | 负载 | 谁用 |
| --- | --- | --- |
| `document.progress` | `document_id`，`status`，`stage`，`progress_percent` | 知识库页在场时更新进度条 |
| `document.ready` | `document_id` | 可去员工端提问；列表标成功 |
| `document.failed` | `document_id`，`error_message` | 回看失败原因 |
| `ticket.created` | `ticket_id`，`conversation_id`，`title`，`preview` | 仅客服工作台增待接入（员工不展示工单状态） |
| `ticket.accepted` | `ticket_id`，`conversation_id` | 工作台状态；员工收 `handoff.changed` |
| `ticket.closed` | `ticket_id`，`conversation_id` | 同上 |
| `message.created` | `conversation_id`，`message`=`MessagePublic` | 员工立即看到客服句；客服立即看到员工句 |
| `handoff.changed` | `conversation_id`，`handoff_state` | 员工端切换等待 / 对话中 / 恢复自动 |

单账号同一时间允许多个页签各持一条连接，事件广播给该账号全部连接。前端路径必须是相对 `/ws`，由 Vite 代理，禁止写死后端端口。

进入知识库或工作台时仍先调 API-005 / API-012 做快照，避免漏掉连接建立前的事件。

### EXT-001 百炼 Chat（外部）

来源：[如何通过 OpenAI 接口调用千问](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)、[OpenAI 兼容 Chat](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions)、[结构化输出](https://help.aliyun.com/zh/model-studio/qwen-structured-output)。

| 项目 | 内容 |
| --- | --- |
| Method / URL | POST `{LLM_BASE_URL}/chat/completions` |
| Header | `Authorization: Bearer <LLM_API_KEY>`；`Content-Type: application/json` |
| 请求体 | `model`=`qwen-plus`（D-002 已确认）；`messages`；`temperature`；`max_tokens`；分类/打标/抽 FAQ 时 `response_format`: `{ "type": "json_object" }`（提示词须含单词 JSON）；`stream`：M-001～M-003 为 false；M-004 / M-005 为 true |
| 非流式成功 | `choices[0].message.content`；`finish_reason`；`usage` |
| 流式成功 | `text/event-stream`，chunk 含 `choices[0].delta.content`；可选 `stream_options.include_usage=true` 以便最后一帧带 usage。来源：[Chat 流式说明](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions) |
| 失败 | HTTP 401/403/404/429/5xx；地域与 Key 不匹配时 401 `invalid_api_key` |

默认 `LLM_BASE_URL`=`https://dashscope.aliyuncs.com/compatible-mode/v1`。官方建议迁移到 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`，现有域名仍可用。禁止把真实 Key 写入本文件。

### EXT-002 百炼 Embedding（外部）

来源：[OpenAI 兼容 Embedding](https://help.aliyun.com/zh/model-studio/embedding-interfaces-compatible-with-openai)、[同步 Embedding](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api)。

| 项目 | 内容 |
| --- | --- |
| Method / URL | POST `{LLM_BASE_URL}/embeddings` |
| 请求体 | `model`=`text-embedding-v3`（D-002 已确认）；`input` string 或 string[]（每批最多 10 条，每条最多 8192 token）；`dimensions`: 1024；`encoding_format`: `"float"` |
| 成功 | `data[].embedding`；`data[].index`；`usage.total_tokens` |
| 失败 | 同 Chat 的鉴权与限流 |

入库与提问共用同一模型与维度。

---

## 三、接口请求数据的类型选型

### 传输与校验

| 场景 | 格式 | 适用 |
| --- | --- | --- |
| 普通接口 | JSON，`snake_case`，前后端同名 | API-001～016 除上传外 |
| 入库提交 | `multipart/form-data` 字段 `file` | API-004 |
| 自动回复 | SSE `text/event-stream` | API-017 |
| 实时事件 | WebSocket JSON 文本帧 | API-018 |
| 外部模型 | JSON HTTP；闲聊/知识问答可流式 | EXT-001、EXT-002 |

共享信封 `ApiEnvelope`：`success` bool；`data` object/array/null；`error` string/null；`error_code` string/null；`message` string/null；`timestamp` ISO 时间；`request_id` string/null；`metadata` object。分页另含 `pagination`。由 PyCore `success_response` / `error_response` / `paginated_response` 输出。

标准 `error_code`：`VALIDATION_ERROR` 400、`UNAUTHORIZED` 401、`FORBIDDEN` 403、`NOT_FOUND` 404、`CONFLICT` 409、`INTERNAL_ERROR` 500。

### 枚举与常量

| 名 | 取值 | 说明 |
| --- | --- | --- |
| `SourceType` | `faq` \| `small_talk` \| `knowledge_qa` | 仅 `role=assistant`；客服与等待为 `null` |
| `MessageRole` | `user` \| `assistant` \| `agent` \| `system` | 员工 / 系统自动 / 客服 / 等待提示 |
| `HandoffState` | `none` \| `waiting` \| `in_progress` | 仅员工端可见 |
| `TicketStatus` | `pending` \| `processing` \| `closed` | 仅工单 API |
| `ObjectType` | `hardware` \| `software` \| `account` \| `network` \| `resource` | `tag-taxonomy.json` |
| `RequestType` | `troubleshooting` \| `maintenance` \| `resource_request` \| `permission_request` \| `usage_guidance` \| `policy_process` | 同上 |
| `DocumentStatus` | `queued` \| `processing` \| `ready` \| `failed` | 仅 `ready` 可被 FAQ/召回 |
| `IngestStage` | `queued` \| `extracting` \| `chunking` \| `tagging` \| `embedding` \| `faq_extracting` \| `ready` \| `failed` | 回看进度 |
| `ContentType` | `pdf` \| `docx` \| `markdown` \| `txt` | 扩展名映射 |

用户可见固定文案：

- `OUT_OF_SCOPE_TEXT`：`当前问题超出知识服务范围，你可以点击转人工。`
- `NO_KNOWLEDGE_TEXT`：`现有知识无法回答。你可以点击转人工。`
- `WAIT_HUMAN_TEXT`：`正在等待人工客服`

### 前端 DTO

`MessagePublic`：`id` int，`role`，`content` string，`source` `SourceType | null`，`created_at` string。  
`ConversationSummary` / `ConversationDetail` 同前，Detail 含 `handoff_state`、`messages`。  
`DocumentSummary`：`id`，`filename`，`content_type`，`status`，`stage`，`progress_percent` int 0～100，`error_message` string/null，`chunk_count`，`faq_count`，`object_types`，`request_types`，`created_at`。  
`DocumentDetail` 另含 `char_count`、`chunks`、`faqs`。  
`TicketSummary` 同前。

校验：消息 1～`message_max_chars`（2000）。文件扩展名白名单 + 大小。JWT 过期 401。

### 跨请求传递

- 登录：`access_token` 存 `localStorage`，Axios 与 WS 查询参数使用；API-002 恢复会话。
- 会话：`conversation_id`；流式用 `after_user_message_id` 衔接 API-010 与 API-017。
- 文档：`document_id` 在离开后仍有效，回看 API-005/006。
- 工单：仅客服侧使用 `ticket_id`。
- 向量：不经过前端。

释放：退出清令牌并关 WS。D-003：成功入库原文、会话、工单不自动删。失败入库：保留 `failed` 行与 `error_message`，删除未成功原文文件。进程内任务随进程结束；重启处理见 §五。

### 持久化（SQLite）

库文件：`backend/data/Customer_Service.db`（先解析绝对路径并建父目录）。

| 表 | 关键字段 | 关系与生命周期 |
| --- | --- | --- |
| `users` | `id` PK；`username` unique；`hashed_password` | 空表则按内部账号种子写入 bcrypt。密码不进 Response |
| `documents` | `id`；`filename`；`content_type`；`status`；`stage`；`progress_percent`；`error_message` null；`storage_path` null；`char_count`；`created_at`；`updated_at` | `queued`/`processing`/`failed`/`ready` 均可见。仅 `ready` 的 `storage_path` 按 D-003 长期保留 |
| `chunks` | `id`；`document_id` FK；`ordinal`；`content`；`object_types` JSON；`request_types` JSON；`entities` JSON；`embedding` JSON float[1024] | 仅成功文档；检索先标签过滤再余弦 |
| `faqs` | `id`；`document_id` FK；`question`；`answer`；`embedding` JSON | 随 `ready` 立即参与拦截 |
| `conversations` | `id`；`title`；`created_at`；`updated_at` | 长期保留 |
| `messages` | `id`；`conversation_id` FK；`role`；`content`；`source` null；`created_at` | 流式 `done` 后才有完整 assistant |
| `tickets` | `id`；`conversation_id` FK；`status`；`created_at`；`accepted_at` null；`closed_at` null | 同一会话未关闭单至多一张 |
| `generation_locks` | `conversation_id` unique；`user_message_id`；`started_at` | 防止并行两路自动回复；`done`/失败时删除 |

索引：`documents(status, created_at)`；`chunks(document_id)`；`faqs(document_id)`；`messages(conversation_id, created_at)`；`tickets(status, created_at)`；`conversations(updated_at)`。

向量检索库 = `chunks.embedding` + 标签列。不另引外部向量库。

---

## 四、模型选型与提示词设计

不适用 Plugin / Function Calling：`requires_live_data` 只走统一超范围兜底。

### 服务与模型（D-002 已确认）

| 项 | 取值 | 依据 |
| --- | --- | --- |
| 服务商 | 阿里云百炼，默认 `dashscope.aliyuncs.com` 兼容域 | 旧域名仍可用；专属 `{WorkspaceId}` 可配置替换 |
| 对话/JSON | `llm_chat_model=qwen-plus` | 用户确认方案 A；JSON Object 见 [结构化输出](https://help.aliyun.com/zh/model-studio/qwen-structured-output) |
| 向量 | `llm_embed_model=text-embedding-v3`，维度 1024 | 用户确认方案 A |
| FAQ 阈值 | `faq_similarity_threshold=0.82` | 先原文规范化全等，再余弦 |
| 接入 | `httpx`，`trust_env=False` | `shared/security.md` |
| 重试 | 429/超时最多再试 2 次；JSON 格式再解析 1 次；禁止无限重试付费调用 | — |

提示词文件：`backend/src/prompts/`。

### M-001 分块打标（入库，非流式）

- **职责**：按标签体系给每批分块打 `object_types`、`request_types`、`entities`。
- **系统提示**：你是企业 IT 知识标注器。只使用给定对象/诉求代码。按完整语义，不用产品名直接当诉求；不把现象当原因；每块一个主要诉求。输出 **JSON** `{"chunks":[{"ordinal":0,"object_types":["network"],"request_types":["troubleshooting"],"entities":[{"name":"VPN","type":"product"}]}]}`。非法代码丢弃；无法判断则空数组。
- **用户输入**：标签定义 + 本批 `{ordinal, content}`。
- **约束**：整批既无对象也无诉求 → 入库失败。温度 0.1。

### M-002 抽取 FAQ（入库，非流式）

- **职责**：抽出员工可能原样或改着问的 FAQ。
- **系统提示**：只根据给定正文，不编造。输出 **JSON** `{"faqs":[{"question":"...","answer":"..."}]}`。最多 `faq_max_per_document` 条；无合适则空数组（仍可靠分块召回）。
- **用户输入**：截断正文（`faq_source_max_chars`）。温度 0.2。

### M-003 提问分类（非流式，仅当前会话）

- **职责**：产出 `tag-taxonomy.json` 的 `query_output`，不把三种 `processing_status` 展示给员工。
- **系统提示要点**：`message_type` 为 `service_request` 或 `small_talk`。闲聊 → `small_talk`。`needs_clarification` / `requires_live_data` / `out_of_scope` 都不要写给用户的追问。禁止建议调用查询工具。输出 **JSON**。
- **动态输入**：标签枚举 + 当前会话最近 `context_message_limit` 条 + 本轮用户句。温度 0.1。

### M-004 闲聊回复（流式）

- **职责**：短回复，不引用知识库。
- **系统提示**：企业内部 IT 助手闲聊语气，一两句中文，不编造政策，不引导查工单。
- **调用**：EXT-001 `stream=true`，增量转 API-017 `delta`。温度 0.7，`max_tokens` 256。

### M-005 知识问答（流式正文）

- **职责**：只根据给定分块回答；不能答则只输出与 `NO_KNOWLEDGE_TEXT` 完全一致的一句。
- **系统提示**：只使用 `chunks` 中的事实。禁止块外规定。能够回答则只输出答案正文，不要 JSON、不要来源名称、不要追问。不能回答则只输出这一句：`现有知识无法回答。你可以点击转人工。`
- **调用**：`stream=true`。`source` 在流式前已定为 `knowledge_qa`。结束后若全文等于无法回答句，按 AC-004 验收。
- **温度**：0.2。

FAQ 拦截不用对话模型，只用 EXT-002 + 规范化字符串。

---

## 五、接口逻辑算法设计

共用：`get_current_user`；标签文件 `tag_taxonomy_path`。

### 检索与 FAQ（跨入库后台任务 / API-017）

**分块**：空行切段，再按 `chunk_size_chars`（500）滑动，重叠 `chunk_overlap_chars`（80）。

**标签过滤**：`object_set` = primary + related；`request_type` 单独。对象侧非空则块对象须有交集；诉求非空则块须包含该诉求。两侧都空 → 不召回，走超范围兜底。

**余弦**：过滤后取 `retrieval_top_k`（5）且 ≥ `retrieval_min_score`（0.45）。没有 → 无法回答。

**FAQ**：NFKC、小写、去空白与常见标点后先全等；否则问句向量与 FAQ 向量最大余弦 ≥ **0.82**（D-002 已确认）。多条取最高。不按标签过滤。

**多 issue**：`ready` 的分别召回后合并再一次 M-005；全部为超范围类或无标签 → 一句兜底；整句闲聊不拆。

### 入库后台任务（API-004 触发）

1. 扩展名与大小校验失败 → 400，不建行。
2. 插入 `documents` `queued`，文件落到 `UPLOAD_DIR/{uuid}_{filename}`，`storage_path` 暂存。立即返回 API-004。
3. `asyncio` 任务：`extracting` → 抽正文（pypdf / python-docx / UTF-8 回退 GBK）。扫描件、加密 PDF、空文档 → `failed`，删文件，`error_message`=`无法提取正文，文档未入库`，推 `document.failed`。
4. `chunking` → `tagging`（M-001）→ `embedding`（EXT-002 每批 ≤10）→ 写 `chunks`。
5. `faq_extracting`（M-002 + FAQ 向量）。
6. 事务将文档标 `ready`，推 `document.ready`。任一步失败：回滚 chunks/faqs，标 `failed`，删未成功原文，推失败事件。不出现「半可检索」。
7. 各阶段更新 `stage`/`progress_percent`（0/10/25/45/70/90/100）并推 `document.progress`。

不提供 OCR、不解析 `.doc`。

进程重启：启动时把仍为 `queued`/`processing` 的行标 `failed`，`error_message`=`入库中断，请重新上传`，删除对应未完成文件。不自动续跑（避免半向量）。用户重传即可。

| 技术选择与触发场景 | 用户可见结果或代价 | 当前处理与依据 | 验收或验证 |
| --- | --- | --- | --- |
| 提交后立即返回 | 可去其它界面，不必盯着上传页 | D-001 方案 B 已确认 | AC-005：离开再回来看到进度/成功 |
| 回来看列表/详情 | 能看到进行中百分比或失败原因 | API-005/006 持久化状态 | AC-019、AC-020 |
| 在页时 WebSocket | 进度条实时走；断线靠回看接口补 | API-018 + 进页快照 | 提交后不关页也能看到走到成功 |
| 同时多份 | 并行后台任务，费用叠加 | 不排队 | 两份各自成功或失败 |
| 进程重启 | 进行中的那次显示失败，需重传 | 避免半生效 | 杀进程后再打开知识库页 |

### API-001 / API-002 / API-003

bcrypt 校验 → JWT。logout 关 WS。

| 技术选择与触发场景 | 用户可见结果或代价 | 当前处理与依据 | 验收或验证 |
| --- | --- | --- | --- |
| 密码错误 | 不能进三端 | AC-002 | 错误密码 |
| 令牌过期 | 回登录，WS 断开 | Axios/WS 401 | 过期后访问 |

### API-005 / API-006 / API-007 / API-008 / API-009

列表含未完成项。首条员工消息成功后 `title` 改为前 30 字。API-009 只做快照。

| 技术选择与触发场景 | 用户可见结果或代价 | 当前处理与依据 | 验收或验证 |
| --- | --- | --- | --- |
| 长期保留成功数据 | 历史与成功入库一直可打开 | D-003 方案 A 已确认 | AC-011、AC-019 |
| 流式中途离开再进会话 | 若已 `done` 则见完整助手句；若仍在生成可重连 API-017 | 先落 user，完成后再落 assistant | 发送后立刻切走再回来 |

### API-010 + API-017 提问编排

```
校验会话；若已有 generation_lock → 409
若存在未关闭 ticket → 写 user，stream=false，WS 推客服，返回
写 user（或复用失败未完成的同一句）
加 lock，返回 stream=true
API-017：
  FAQ 命中 → meta source=faq → 切段 delta → 落库 done
  否则 M-003
    small_talk → meta small_talk → 流式 M-004
    全部超范围类或无标签 → meta knowledge_qa → 切段兜底句
    否则召回
      无块 → meta knowledge_qa → 切段无法回答句
      否则 meta knowledge_qa → 流式 M-005
  成功落 assistant，去 lock，done
分类 JSON 失败 → 当超范围兜底（不 500）
M-004/M-005 流式失败 → SSE error，不落 assistant，去 lock
FAQ 向量失败 → 跳过拦截走分类
clarification_question 丢弃；不调实时查询工具
```

当前会话上下文：本 id 最近 `context_message_limit` 条。

| 技术选择与触发场景 | 用户可见结果或代价 | 当前处理与依据 | 验收或验证 |
| --- | --- | --- | --- |
| 来源先于正文 | 先看到「FAQ / 闲聊 / 知识问答」再逐字 | D-001 B | AC-003、AC-016、AC-017 |
| 客户端断开 SSE | 服务端仍跑完并落库；回来 API-009 见全文 | 可恢复 | 发送后关页再打开 |
| FAQ 阈值 0.82 | 很近改写能拦；擦边可能漏 | D-002 A | AC-016 |
| 无标签不召回 | 硬件问不打软件全库 | PRD | AC-018、AC-022 |
| 并行连点发送 | 第二下 409，避免两路回答 | generation_lock | 连点两次只有一路流 |

### API-011～API-016 + API-018

转人工建 `pending` + 等待消息 + WS。接入/回复/关闭后推对应事件。员工消息在人工期只落库并推客服。

| 技术选择与触发场景 | 用户可见结果或代价 | 当前处理与依据 | 验收或验证 |
| --- | --- | --- | --- |
| 客服一发 | 员工当前会话立刻出现客服句，不标三种来源 | D-001 B + API-018 | AC-010、AC-013 |
| 新待接入单 | 工作台立刻出现，无需刷新 | API-018 `ticket.created` | AC-008、AC-012 |
| 客服不接入 | 一直等待 | 不超时关单 | AC-015 |
| WS 未连上就发了回复 | 进页 API-009/013 快照仍能看到 | 快照 + 推送 | 先断网再恢复 |

---

## 六、接口失败异常设计

共享：`@handle_errors`；`ValueError`→400；其余→500。用户文案中文；日志不写密码、Token、Key。

### 校验与业务

| 接口 | 触发 | HTTP / error_code | 用户提示 | 是否落库 / 恢复 |
| --- | --- | --- | --- | --- |
| API-001 | 缺字段 | 400 VALIDATION_ERROR | 请输入用户名和密码 | 无 |
| API-001 | 密码错 | 401 UNAUTHORIZED | 账号或密码不正确 | 可重试 |
| 受保护接口 / WS | 坏 Token | 401 或关连接 | 请先登录 | 跳转登录 |
| API-004 | 扩展名不支持 | 400 VALIDATION_ERROR | 不支持该格式，请上传 PDF、Word（.docx）、Markdown 或 txt | 不建记录；AC-007 |
| API-004 | 超过大小 | 400 VALIDATION_ERROR | 文件过大，最大 20MB | 不建记录 |
| 入库任务 | 抽不出正文 / 打标失败 | 记录 `failed` | 回看页：无法提取正文或入库失败，请重新上传 | 不可检索；可重传（新 id） |
| API-010 | 空消息 | 400 | 请输入要发送的内容 | 不落库 |
| API-010 | 已有进行中的流 | 409 CONFLICT | 请等待当前回复结束 | 不重复 user |
| API-010 | 人工进行中 | 200 stream=false | 无自动回复 | 只落 user + WS |
| API-011 | 已有未关闭单 | 409 CONFLICT | 当前已在等待或由人工处理 | 不新建 |
| API-014/015/016 | 状态不符 | 409 | 无法接入 / 不能回复 / 已关闭 | 以服务端为准 |
| API-017 | after_user_message_id 不属于该会话 | 400/404 | 无法继续回复 | 不调模型 |

### 外部依赖与通道

| 触发 | 处理 | 用户可见 |
| --- | --- | --- |
| 百炼 429/超时 | 最多 2 次退避 | 入库任务 → `failed` 可重传。分类失败 → 超范围兜底。闲聊/知识问答流式失败 → SSE `error`「暂时无法回答，请稍后重试」，不落 assistant |
| 百炼 401/403 | 不重试 | 入库失败或 SSE error；界面不暴露 Key |
| 流式 `finish_reason=length` | 已输出的当完成并落库 | 可能看到半句；历史保留该半句 |
| SSE 客户端断开 | 服务端继续至落库 | 回来见完整条或见失败可重开流 |
| WS 断开 | 前端指数退避重连（上限见配置）；重连后重新 GET 快照 | 重连窗口内最多漏事件，靠快照补 |
| 入库提交后浏览器没收到 200 | 可能已建 `queued` 行 | 回列表可见，勿连点造成第二份（按钮在提交中禁用） |

前端：提交入库后按钮恢复，因已可离开；同一文件连点仍可能两行，列表会看到两次任务。提问发送中到 `done`/`error` 前禁用输入。401 清 token 并关 WS。

---

## 七、项目本地层级设计

```
Projects_Repo/Customer_Service/
├── docs/
├── pycore/
├── backend/
│   ├── .env / .env.example
│   ├── requirements.txt
│   ├── data/
│   ├── src/
│   │   ├── main.py              # APIServer、CORS、/ws、启动回收中断入库
│   │   ├── config/
│   │   ├── api/deps.py
│   │   ├── api/routes/          # auth、documents、conversations、tickets
│   │   ├── api/ws.py            # API-018 连接与广播
│   │   ├── db/models.py
│   │   ├── db/session.py
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── services/            # ingest 后台、qa 流、ticket、auth
│   │   ├── integrations/llm_http.py
│   │   ├── prompts/
│   │   └── utils/
│   ├── tests/
│   └── scripts/
├── frontend/src/
│   ├── pages/
│   ├── services/                # api.ts、documents.ts、conversations.ts、ws.ts
│   ├── stores/
│   └── ...
├── pyproject.toml
└── .sdd/
```

无 Plugin。质量门禁不扫 `pycore/`。Vite `/api` 与 `/ws` 均需代理。

### 运行

- 后端：`cd backend && PYTHONPATH=.. python3.11 -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8099`
- 前端：`cd frontend && npm run dev -- --host 127.0.0.1 --port 5199`；验收端口 5175 且 `VITE_BACKEND_PROXY_TARGET=http://localhost:8003`
- 依赖：`uvicorn`、`sqlalchemy[asyncio]`、`aiosqlite`、`python-dotenv`、`httpx`、`bcrypt`、`PyJWT`、`pypdf`、`python-docx`、`numpy`、`websockets` 或 FastAPI 自带 WS、`pytest`、`pytest-timeout`
- 验证：`python3.11 -m pytest backend/tests --timeout=120`。无百炼 Key 只跑 Mock。SSE/WS 用例可用 httpx/websockets 测，不得无 Key 声称真实模型通过。

### 配置

后端 `backend/.env`（`ConfigManager`，`use_env=False`）：

| 字段 | 类型 | 默认 | 用途 | 敏感 |
| --- | --- | --- | --- | --- |
| `debug` | bool | false | 调试 | 否 |
| `secret_key` | string | 无默认，必填 | JWT | 是 |
| `database_path` | string | `data/Customer_Service.db` | SQLite | 否 |
| `upload_dir` | string | `data/uploads` | 成功原文 | 否 |
| `host` | string | `127.0.0.1` | 监听 | 否 |
| `port` | int | 8099 | 监听 | 否 |
| `cors_origins` | JSON list | 5199 与 5175 的 localhost/127.0.0.1 | CORS | 否 |
| `internal_username` | string | 必填 | 唯一内部账号 | 否 |
| `internal_password` | string | 必填 | 种子密码 | 是 |
| `jwt_expire_hours` | int | 12 | 登录有效期 | 否 |
| `llm_base_url` | string | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 百炼兼容根 | 否 |
| `llm_api_key` | string | 空 | 空则真实模型不可用 | 是 |
| `llm_chat_model` | string | `qwen-plus` | D-002 已确认 | 否 |
| `llm_embed_model` | string | `text-embedding-v3` | D-002 已确认 | 否 |
| `llm_embed_dimensions` | int | 1024 | 与库内向量一致 | 否 |
| `llm_timeout_seconds` | float | 60 | 单次模型 HTTP | 否 |
| `llm_max_retries` | int | 2 | 429/超时 | 否 |
| `upload_max_bytes` | int | 20971520 | 20MB | 否 |
| `ingest_job_timeout_seconds` | int | 300 | 单文档后台上限，超时标 failed | 否 |
| `chunk_size_chars` | int | 500 | 分块 | 否 |
| `chunk_overlap_chars` | int | 80 | 分块 | 否 |
| `tag_batch_size` | int | 8 | M-001 | 否 |
| `faq_max_per_document` | int | 20 | M-002 | 否 |
| `faq_source_max_chars` | int | 20000 | 抽 FAQ 截断 | 否 |
| `faq_similarity_threshold` | float | 0.82 | D-002 已确认 | 否 |
| `retrieval_top_k` | int | 5 | 召回 | 否 |
| `retrieval_min_score` | float | 0.45 | 召回 | 否 |
| `context_message_limit` | int | 16 | 当前会话条数 | 否 |
| `message_max_chars` | int | 2000 | 输入上限 | 否 |
| `out_of_scope_text` | string | PRD 兜底句 | 展示 | 否 |
| `no_knowledge_text` | string | 见 §三 | 展示 | 否 |
| `wait_human_text` | string | 正在等待人工客服 | 展示 | 否 |
| `tag_taxonomy_path` | string | `docs/tag-taxonomy.json` | 标签 | 否 |
| `ws_heartbeat_seconds` | int | 20 | WS 心跳 | 否 |
| `ws_reconnect_max_seconds` | int | 30 | 前端重连上限（写入前端常量时可同源） | 否 |

前端：`VITE_API_BASE_URL=/api`；`VITE_BACKEND_PROXY_TARGET=http://localhost:8099`；`VITE_WS_PATH=/ws`。已删除短轮询间隔配置。

`backend/data/`、`.venv`、`.env` 忽略。

### 外部服务清单

| 名称 | 用途 | 依赖 API | 配置状态 | Mock / 真实 | 真实验证所需 |
| --- | --- | --- | --- | --- | --- |
| 百炼 Chat | 打标、抽 FAQ、分类、闲聊流、知识问答流 | EXT-001 | 仅字段名 | 无 Key 时 Mock | 地域匹配的 API Key、`qwen-plus` 开通 |
| 百炼 Embedding | 分块/FAQ/问句向量 | EXT-002 | 仅字段名 | 同上 | `text-embedding-v3` 开通 |

缺凭据不阻塞：登录、异步状态机（可用假进度）、工单 WS 用夹具、页面路由。缺凭据不得宣称真实问答/打标 AC 已通过。

### REQ / AC 覆盖

| AC | 实现路径 |
| --- | --- |
| AC-001、AC-002 | API-001、API-002，三路由 + RequireAuth |
| AC-003、AC-018、AC-022 | API-010 + API-017 标签过滤 + M-005 流 |
| AC-004 | API-017 空召回 / 无法回答句 |
| AC-005、AC-024 | API-004 接收 + 后台 `ready` 后立即生效；可离开 |
| AC-006 | 员工端无知识入口 |
| AC-007 | API-004 当场校验 |
| AC-019、AC-021 | API-006；进行中看进度 |
| AC-020 | 后台 `failed` + 回看 |
| AC-016 | API-017 `source=faq` 后逐字 |
| AC-017 | API-017 `source=small_talk` 后逐字 |
| AC-023 | 三类 status → 同一文案流 |
| AC-008、AC-012 | API-011 + API-018 `ticket.created` |
| AC-009 | 未调 API-011 则无新单 |
| AC-010、AC-013 | API-015 + API-018 `message.created` |
| AC-011 | API-008、API-009 |
| AC-014 | API-016 后 API-010 恢复 |
| AC-015 | 不接入则保持 pending + 等待文案 |

### 仍待确认

三项体验取舍已确认，不再阻挡按本草案实现。整体 tech-spec 仍为 Draft，待用户对方案做一次总确认。

不阻塞独立开发、但挡住真实联调的项：百炼 Key / 模型开通 / 地域是否匹配。

界面风格与原型不在本阶段产出，不进入阶段 B。

Mermaid 已按本确认方案回写 PRD「流程图与时序图」；无独立渲染预览，仅完成源文本结构检查。
