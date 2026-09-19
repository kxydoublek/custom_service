# T-008 Tester 报告（首次验收）

- 任务：T-008 转人工工单状态机与人工实时通道
- 角色：Tester（非复验）
- 项目：`Projects_Repo/Customer_Service`
- 时间：2026-09-18
- 总结果：**PASS（后端阶段 / 工单状态机）**
- 业务 AC：本任务 `acceptanceCriteria=[]`；AC-008～AC-015 由 **T-012** 页面验收。本报告只验 API-011～016 / API-018 状态机与推送副作用，**不宣称页面 AC 或 T-012 通过**。
- 规范集：default
- 派发：`sdd_dispatch.py --running-task T-004 --running-task T-008` → `gate_phase=frontend_in_progress`，`gate_task_id=T-004`，`errors=[]`，T-008 为 testing；非 integration/delivery。已开验收尾，不续派 T-009。
- 实例：Developer `108139f1`
- 未改业务代码、`.sdd/tasks.json`、方案/规范；未操作浏览器；未杀 5199。

## 环境

- Python：项目 `.venv` **3.12.13**；`pytest-timeout` 2.4.0。
- 命令：项目根 `.venv/bin/python -m pytest backend/tests --timeout=120` → **37 passed**（12.79s）。夹具走 `tmp_path/test.db`，未碰业务库。
- 独立抽检：隔离 TestClient + `/ws?access_token=`，临时库 `/private/var/folders/.../tester-t008.db`；29/29 PASS。日志「无 LLM Key，使用本地 Mock Embedding」。本任务不依赖百炼。
- 业务库 `backend/data/Customer_Service.db` 验收前后不变：`mtime=1789672848` / `size=106496`；`users=1` `documents=1` `chunks=1` `faqs=1`；`conversations/messages/tickets/generation_locks=0`。
- 本轮 **未启动 8099**（开工与结束均未监听）。未操作浏览器，未杀 Vite / 5199（5199 仍为 node PID 81572）。未改 `frontend/`。

## 检查表

| ID | 场景 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- |
| TC-01 | API-011 建 pending 并推 `ticket.created` / `handoff.changed`；重复转人工 409；员工接口不返回 `ticket_status` | 200 仅 `handoff_state=waiting` + 等待文案；WS 三事件；409 `CONFLICT`「当前已在等待或由人工处理」；会话/列表/发消息无 `ticket_status` | pytest + 独立 TestClient | PASS |
| TC-02 | API-014 pending→processing 推 `ticket.accepted`；非 pending 409。API-015 仅 processing 可回并广播 `message.created`。API-016 关闭后再回 409 | 接入 200 `processing`；再接入 409「无法接入」；pending/关闭后回复 409「不能回复」；关闭推 `ticket.closed` + `handoff.changed=none` | pytest + 独立 TestClient | PASS |
| TC-03 | 人工未关闭时 API-010 `stream=false`，员工消息推客服端，不走 FAQ/闲聊/AI；关闭后同一会话可再走自动回复 | pending/processing 均 `stream=false` 且 LLM 补丁未触发；关闭后 `stream=true`、`handoff_state=none` | pytest + 独立 TestClient + monkeypatch | PASS |
| TC-04 | 不接入保持 pending。WS `/ws?access_token=`；坏 Token 关连接。pytest 覆盖状态机与推送副作用 | 未接入仍 `pending`；坏/缺 Token `WebSocketDisconnect`；pytest 37 passed 含断言 | pytest + 独立 TestClient | PASS |
| TC-05 | 不实现 3 秒轮询工单列表作为主通道 | 新单靠 WS 推送；API-012 仅为快照；后端无 3s 轮询循环 | 定向读代码 + WS 抽检 | PASS |

后续责任：AC-008～015 页面与真实 WS 跨页 → **T-012**。本 PASS 不等于页面通过。

---

## TC-01 API-011 建单、推送、重复 409、员工无工单状态 — PASS

预期：一点转人工建 `pending`；向客服推 `ticket.created`、向员工推 `handoff.changed` 与等待 `message.created`；响应不含工单 id/状态；未关闭时再转 409。

实际：

- `POST /api/conversations/{id}/transfer` 200，`data` 仅 `handoff_state` / `wait_message`；`wait_message.role=system`，`content=正在等待人工客服`，`source=null`。
- WS 事件顺序：`ticket.created` → `handoff.changed(waiting)` → `message.created`（等待文案）。`ticket.created` 含 `ticket_id` / `conversation_id` / `title` / `preview`。
- `GET /api/tickets?status=pending` 一张 `pending`，id 与事件一致。
- `GET /api/conversations/{id}` 字段 `created_at,handoff_state,id,messages,title,updated_at`，`handoff_state=waiting`，无 `ticket_status`。列表仅 `id,preview,title,updated_at`。
- 重复转人工 409 `CONFLICT`「当前已在等待或由人工处理」。关闭后再转 200，未关闭单仍仅一张且 id 不同。

证据：pytest `test_transfer_creates_pending_and_pushes_ws`；抽检 `TC01-*`。

---

## TC-02 接入 / 回复 / 关闭状态机 — PASS

预期：仅 pending 可接入并推 `ticket.accepted`；仅 processing 可回复并广播 `message.created`（`role=agent` `source=null`）；关闭后再回 409。

实际：

- pending 回复 409「不能回复」。
- `POST /api/tickets/{id}/accept` 200，`status=processing`，有 `accepted_at`；WS `ticket.accepted` + `handoff.changed=in_progress`。再接入 409「无法接入」。
- `POST /api/tickets/{id}/messages` 200，客服句 `role=agent` `source=null`；WS `message.created` 同内容。
- 关闭 200 `closed` + `closed_at`；WS `ticket.closed` + `handoff.changed=none`。再回复 409「不能回复」。详情仍可读，含客服消息。

证据：pytest `test_accept_reply_close_state_machine_and_ws`；抽检 `TC02-*`。

---

## TC-03 人工期停自动回复，关闭后恢复 — PASS

预期：未关闭工单时 API-010 `stream=false`，员工消息经 WS 推客服，不调 FAQ/闲聊/AI；关闭后同一会话可再走自动回复。

实际：

- pending：发「待接入期间再问一句」→ `stream=false` `handoff_state=waiting` `assistant_message=null`；WS `message.created` role=user。`chat_json`/`chat_stream`/`embed_texts` 被断言拦截且未调用。日志「人工进行中，已保存员工消息且不走自动回复」。
- processing：发「处理中再发一句」同样 `stream=false` `handoff_state=in_progress`，并推用户消息。
- 关闭后会话 `handoff_state=none`；再发「关闭后继续问系统」→ `stream=true`。

证据：pytest `test_accept_reply_close_state_machine_and_ws`（monkeypatch）；抽检 `TC03-*`。关闭后自动回复为编排入口（`stream=true`），不等于 T-011 真实百炼。

---

## TC-04 不接入保持 pending；WS 鉴权；pytest 覆盖 — PASS

预期：不接入则保持 pending；路径 `/ws`，查询参数 `access_token`；坏 Token 关连接；pytest 覆盖状态机与推送副作用。

实际：

- 转人工后不接入：pending 列表 1 条，processing 空，会话仍 `waiting`。
- 坏 Token / 缺 Token：连接关闭，异常 `WebSocketDisconnect`；日志「WebSocket 鉴权失败，关闭连接」，日志不含 Token 原文。
- pytest 37 collected / 37 passed；`test_tickets.py` 6 条含 WS 事件断言，非只打印布尔。心跳 `asyncio.sleep` 读 `ws_heartbeat_seconds`（配置 20），不是工单轮询。

证据：pytest `test_unaccepted_ticket_stays_pending`、`test_ws_rejects_bad_token`；抽检 `TC04-*`。

---

## TC-05 不以 3 秒轮询工单列表为主通道 — PASS

预期：新单到达靠 API-018；API-012 仅为进页快照。

实际：

- 后端 `backend/src` 无 `setInterval` / `3000` / 工单列表轮询循环。工单变化经 `publish_events` → WS 广播。
- API-012 `GET /api/tickets` 存在且用于快照（独立抽检可按 status 过滤）；主通道验证为 WS `ticket.created` 在 HTTP 200 后立即到达，无需二次列表请求。
- 前端 `AgentPage` 进页/切 Tab 调一次列表，后续靠 `connectRealtime` 的 `ticket.created` 等事件；`frontend/src` 无 3s `setInterval`。本条只作后端主通道旁证，不作为页面 AC。

证据：定向 grep；抽检 `TC01-ws-events`；`frontend/src/services/ws.ts` 路径为相对 `/ws?access_token=`。

---

## 范围外（不计入判定）

- AC-008～015 页面对照、真实浏览器跨页 WS → T-012。
- 关闭后自动回复未跑完整 SSE/FAQ 命中（T-011）。
- `PREVIEW_MAX_CHARS=30` 仍写在 `qa.py`（T-007 既有），工单 title/preview 截断沿用该值。

未请求、未派发 T-009。
