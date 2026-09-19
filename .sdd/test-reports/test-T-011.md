# T-011 Tester 报告（首次独立验收）

- 任务：T-011 提问链路真实联调（FAQ、闲聊、标签召回、兜底）
- 角色：Tester（独立验收，不采信 Developer 自验）
- 项目：`/Users/kxy/cursor/class_projects/Develop_Helper/Projects_Repo/Customer_Service`
- 时间：2026-09-19
- 总结果：**PASS**
- 业务 AC：AC-003 **PASS**；AC-004 **PASS**；AC-016 **PASS**；AC-017 **PASS**；AC-018 **PASS**；AC-022 **PASS**；AC-023 **PASS**
- source_feature：F-002（REQ-002、REQ-007）
- type：integration；execution_mode：automatic；user_gate：passed；specification：default
- 派发：`python3 .../scripts/sdd_dispatch.py --tasks .../Customer_Service/.sdd/tasks.json --running-task T-011` → `gate_phase=passed`，`gate_task_id=T-004`，`in_flight_or_queued=["T-011"]`，`errors=[]`。任务 status=testing。未开始 T-012。
- 浏览器：独立新标签 `viewId=d6092f`，`http://127.0.0.1:5199/employee`。本轮自建会话 **31–36**，不复用 Developer 会话 ID。
- 未改业务代码、`.sdd/tasks.json`、`.sdd/experience.md`、方案/规范；未 commit/push；未清空 `backend/data/Customer_Service.db`；未杀编排器持有的 5199 / 8099。
- 密钥：本报告不写 `INTERNAL_PASSWORD`、JWT、`LLM_API_KEY`。配置状态：`INTERNAL_USERNAME=it-admin`；`LLM_API_KEY` 已配置（非空）；Chat=`qwen-plus`；Embedding=`text-embedding-v3`；`FAQ_SIMILARITY_THRESHOLD=0.82`。

## 环境

- 前端：`http://127.0.0.1:5199`，`GET /` 200。未再起 5199。
- 后端：`http://127.0.0.1:8099`，uvicorn PID **90461**（PPID 90438），cwd=`.../Customer_Service/backend`。库路径 `backend/data/Customer_Service.db`。未杀该进程。
- 登录：本标签恢复为已登录 `it-admin` 员工端，未打印令牌。
- 知识背景（不作为本轮问答证据）：硬件文档 id14 `BLUEFLASH-HW-8821`；软件 id15 `SOFTLICENSE-SW-3399`；网络 id16 `JUMPGATE-NET-7744`；T-010 VPN FAQ。本轮问答证据来自会话 31–36 的 SSE / 落库消息 / 本进程日志。
- 本轮开始前 `tickets` 行数 0；结束后仍为 0。

## 检查表

| ID | 场景 / 输入 | 动作 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- | --- |
| TC-01 | 已缓存 FAQ 原问 | 新会话 31 发送「VPN认证失败时，第一步应该做什么？」 | 先「FAQ」再逐字 FAQ 答案；SSE `meta→delta→done`；不进知识问答 | 独立浏览器 + fetch SSE 探针 + DB | PASS |
| TC-02 | 已缓存 FAQ 相近问 | 同会话发送「连公司 VPN 认证没过的时候，最先该做哪一步啊？」 | 同源 FAQ 答案；余弦 ≥ 0.82 命中；不进知识问答 | 同上 | PASS |
| TC-03 | 闲聊 | 新会话 32「嘿先不谈电脑，随便聊聊：下午茶想喝桂花乌龙…」 | 先「闲聊」再闲聊回复；不按知识库、不走超范围兜底、不建工单 | 浏览器 + SSE + 日志 + tickets | PASS |
| TC-04 | 有知识且 FAQ 未拦 + 同会话追问 | 新会话 33 硬件故障长问；再追问「刚才那串硬件码…」 | 先「知识问答」；首答含 `BLUEFLASH-HW-8821`；追问复述该码 | 浏览器 + SSE + 日志 | PASS |
| TC-05 | 企业 IT 可检索但范围内无知识 | 新会话 34 地下车库闸机抬杆电机卡住 | 先「知识问答」再「现有知识无法回答。你可以点击转人工。」不产生工单 | 浏览器 + SSE + tickets 计数 | PASS |
| TC-06 | 明确硬件故障（软硬件均已入库） | 会话 33 硬件问 | `source=knowledge_qa`；答案无 `SOFTLICENSE-SW-3399` / SoftExport；召回块均为 hardware | 浏览器 + 召回日志 | PASS |
| TC-07 | 明确对象与诉求 | 会话 33 / 34 提问 | 检索前标签过滤 `object_types=['hardware'] request_type=troubleshooting`，corpus=18 filtered=3，不是全库无过滤 | 后端日志 | PASS |
| TC-08 | 信息不足 | 会话 35「就是那个，你懂的，坏掉了，怎么办。」 | 先「知识问答」再同一超范围句；无追问 | 浏览器 + 分类日志 | PASS |
| TC-09 | 超出 IT | 会话 35「帮我看看下周二黄山团建的高铁一等座还有没有票。」 | 同一超范围句；无追问 | 浏览器 + 分类日志 | PASS |
| TC-10 | 查询某张工单进度 | 会话 35「查一下工单 CS-T011-99821…」 | 同一超范围句；`requires_live_data`；日志声明不调实时工单工具 | 浏览器 + 分类日志 | PASS |
| TC-11 | SSE 来源先于正文；历史完整一条 | 切走天气历史再打开会话 31 | 气泡 HTML 先 `<span class="source">FAQ</span>` 再全文；非流式残留 | 浏览器 DOM | PASS |
| TC-12 | FAQ 阈值与模型名来自配置 | 读 settings / .env / 运行日志 | `threshold=0.82` 来自 `settings.faq_similarity_threshold`；Chat/Embed 来自 settings；代码无散落硬编码 0.82/qwen-plus | 定向读代码 + 日志 | PASS |
| TC-13 | 只用当前会话；新会话不受历史影响 | 会话 36 问上一通暗号 `T11-ISO-7F2A` 门牌号 | 不复述会话 33 硬件码；走超范围兜底 | 浏览器 + SSE | PASS |
| TC-14 | 真实百炼；0 次本地 Mock | 本轮 04:29 后日志 | 多条「调用百炼 … 成功」；本进程 **0** 条「无 LLM Key，使用本地 Mock」 | 后端终端 712094 | PASS |
| TC-15 | 未点转人工不建工单 | AC-004 / 闲聊 / 兜底全程 | `tickets` 始终 0；转人工按钮可见但未点 | SQLite | PASS |
| TC-16 | 主对话去掉 `[Mock]` | 本轮气泡 | 主区来源为 FAQ/闲聊/知识问答，气泡无 `[Mock]`；侧栏标题仍有 `[Mock]`（不在 write_scope，且未造成 mock SSE） | 浏览器 DOM | PASS |
| TC-17 | SSE 末包 `done` 不丢 | 全部本轮流 | 每条捕获流均含最终 `event: done` 且落库 assistant | SSE 探针 + DB | PASS |

---

## AC-003 有知识且未被 FAQ 拦截 → 知识问答 + 同会话追问 — PASS

预期：先标明「知识问答」，再基于标签范围内知识回复；追问承接当前会话上文。

实际：

- 会话 **33**，SSE `/api/conversations/33/assistant-stream?after_user_message_id=77`：`source=knowledge_qa`。FAQ 分 0.7096 < 0.82，未拦截。
- 气泡：`知识问答` + 「按住 ESC 与空格键，成功后会跳出硬件码 BLUEFLASH-HW-8821。」
- 追问 after_user_message_id=79：仍 `knowledge_qa`，复述 `BLUEFLASH-HW-8821`（追问原文未再写该码）。
- 日志：`检索前已按标签过滤 … object_types=['hardware'] request_type=troubleshooting corpus=18 filtered=3`；召回 `chunk_ids=[16, 6, 12]` 全为 hardware。

证据：会话 33 消息 77–80；SSE 探针；后端 04:32:09–04:33:01。

---

## AC-004 范围内无对应知识 → 无法回答且不建工单 — PASS

预期：先「知识问答」再「现有知识无法回答。你可以点击转人工。」不产生工单。

实际：

- 会话 **34** 闸机故障问。SSE `source=knowledge_qa`，正文与配置 `NO_KNOWLEDGE_TEXT` 逐字一致。
- 日志：FAQ 未命中；分类 `service_request`/`ready`；硬件标签过滤后 `标签过滤后无召回，返回无法回答`（04:34:53）。
- 页上「转人工」按钮可见；本轮未点击。`tickets` 提问前后均为 0。

证据：会话 34 消息 81–82；SSE；SQLite `SELECT COUNT(*) FROM tickets`。

---

## AC-016 已缓存 FAQ 原问或相近 → FAQ 不进知识问答 — PASS

预期：先「FAQ」再逐字 FAQ 答案，不进入标签召回后的知识问答。

实际：

- 原问（会话 31 / user 71）：规范化全等命中，跳过分类与召回。气泡 `FAQ` + 「先确认账号未被锁定，可在门户重置密码。」（FAQ id15 答案）。SSE：`meta source=faq` → 两段 delta → `done`。
- 相近问（user 73）：`FAQ 余弦命中 … score=0.8926 threshold=0.82`，同一答案，`source=faq`。
- 切到其它历史再打开会话 31：两条助手气泡均为完整一条，`<span class="source source-faq">FAQ</span>` 后接全文。

证据：会话 31 消息 71–74；SSE 探针 eventOrder=`meta,delta,delta,done`；日志 04:29:30、04:30:05。

---

## AC-017 闲聊 → 闲聊回复，不走知识库/超范围/建单 — PASS

预期：先「闲聊」再闲聊回复。

实际：

- 会话 **32**。分类 `message_type=small_talk processing_statuses=['ready']`。SSE `source=small_talk`。气泡 `闲聊` + 「哇～桂花乌龙配秋日阳光，绝了！🍵」
- 未出现 FAQ/知识问答/超范围句/无法回答句。未建工单。
- 流式：`meta` 后多段 `delta`，最后 `done`；日志「调用百炼 Chat 流式成功」。

证据：会话 32 消息 75–76；SSE；日志 04:31:23–04:31:27。

---

## AC-018 明确硬件故障只依据硬件范围 — PASS

预期：先「知识问答」；回答只依据硬件相关知识，不得出现软件-only 标志词。

实际：首答与追问均 `knowledge_qa`；正文含 `BLUEFLASH-HW-8821` / ESC+空格；**未出现** `SOFTLICENSE-SW-3399`、SoftExport、`T011-SW-MARKER-SOFTLICENSE`。召回块 object_types 均为 `['hardware']`。

证据：会话 33；召回日志 `chunk_object_types=[['hardware'], ['hardware'], ['hardware']]`。

---

## AC-022 按标签缩小召回后再答 — PASS

预期：检索前有标签过滤，不是全库无过滤。

实际：本轮硬件问日志原文：「检索前已按标签过滤，不是全库无过滤 | object_types=['hardware'] request_type=troubleshooting corpus=18 filtered=3」。闸机无知识路径同样先过滤再判定无召回，不是全库检索。

证据：后端 04:32:14、04:32:43、04:34:21。

---

## AC-023 信息不足 / 超出 IT / 查工单进度 → 同一超范围兜底 — PASS

预期：均先「知识问答」再同一句「当前问题超出知识服务范围，你可以点击转人工。」无针对性追问，不查真实工单状态。

实际（会话 **35**，三句正文完全一致）：

| 问 | 分类日志 | 用户可见 |
| --- | --- | --- |
| 就是那个，你懂的，坏掉了，怎么办。 | `small_talk` + `needs_clarification` →「分类标为闲聊但含超范围类状态，改走同一兜底，不追问」 | 知识问答 + 超范围句 |
| 黄山团建高铁一等座 | `small_talk` + `out_of_scope` → 同上改走兜底 | 同上 |
| 工单 CS-T011-99821 进度 | `service_request` + `requires_live_data`；「已丢弃追问字段且不调用实时工单工具」 | 同上；未出现待接入/处理中等工单状态 |

证据：消息 83–88；日志 04:35:28、04:36:00、05:23:47。

---

## 技术检查

- SSE meta 先于正文：本轮全部捕获流 `eventOrder` 均以 `meta` 开头，随后 `delta`，最后 `done`。历史打开为完整一条（TC-11）。
- FAQ 阈值 0.82、模型名：运行日志打印 `threshold=0.82`；`qa.py` 读 `settings.faq_similarity_threshold`；`llm_http.py` 读 `settings.llm_chat_model` / `llm_embed_model`。`backend/src` 中 `0.82` / `qwen-plus` / `text-embedding-v3` 仅出现在 `config/settings.py` 默认值，与 `.env` / `.env.example` 一致。
- 无跨会话记忆：会话 36 问 `T11-ISO-7F2A` 门牌号 → 超范围兜底，未泄漏 `BLUEFLASH-HW-8821`。
- 真实百炼：本轮多次「调用百炼 Embedding/Chat/流式成功」。对 `712094.txt` 全文检索「无 LLM Key」**0 命中**。答案非 Mock 模板（闲聊为桂花乌龙即时生成，而非 mocks 固定句）。
- 无 dashscope SDK；`httpx.AsyncClient(trust_env=False)` 仍在。
- 主对话无 `[Mock]` 标签；`EmployeePage.tsx` 仍 `subscribe` mocks/bus（转人工通道，T-012 范围）。`conversations.ts` 循环结束后 `if (buffer.trim()) dispatchBlock(buffer)`，本轮 `done` 均收到。`ConversationSidebar.tsx` 历史标题仍前缀 `[Mock]`：不在 write_scope；本轮 SSE 均为 `/api/conversations/{31-36}/assistant-stream`，不是 mock-token 路径。

---

## 经验候选核对（不写 experience.md）

Developer 候选：信息不足/超出 IT 曾被标成闲聊并追问，因为 M-003 可同时 `small_talk` + `needs_clarification`/`out_of_scope`；qa.py 改为超范围类状态优先同一兜底。

| 项 | 判定 | 证据 |
| --- | --- | --- |
| AC-017 仍走闲聊 | **已验证** | 会话 32：`small_talk` + `ready` → 闲聊流式，不是兜底 |
| AC-023 仍同一兜底 | **已验证** | 会话 35 三类同一句；工单类 `requires_live_data` 未调工具 |
| 双标短路修复本身 | **已验证** | 本轮 04:35:28：`small_talk` + `needs_clarification` →「分类标为闲聊但含超范围类状态，改走同一兜底，不追问」。04:36:00：`small_talk` + `out_of_scope`（高铁票，无寒暄 hint）同样改走兜底 |
| 推广到其它模型/提示词版本 | **未验证** | 仅本轮 qwen-plus 分类输出 |

适用边界：当前 `qa.py` 在 `small_talk` 且 issues 含 `needs_clarification`/`requires_live_data`，或含 `out_of_scope` 且用户句不匹配寒暄 hint 时，改走 `OUT_OF_SCOPE_TEXT`。真闲聊（`small_talk` + `ready`，或 `out_of_scope` 但命中寒暄 hint）仍走 M-004。

---

## 范围外发现（不计入本任务判定）

- 历史侧栏标题仍带 `[Mock]`（`ConversationSidebar.tsx`，不在 T-011 write_scope）。未导致 mock SSE 或假答案。
- 会话 33 追问在复述硬件码之外，写了文档未记载的「断电 30 秒后重新上电」。首答与标签召回符合 AC-003/018；该句属知识问答忠实度问题，不单独把 AC-003 判 FAIL。
- 未执行 T-012 转人工主路径（仅确认未点转人工且无新工单）。

## 未验项

- 未故意制造分类 JSON 失败（方案：失败则超范围兜底；本轮分类均成功）。
- 截图工具超时，视觉以 DOM/SSE 为准。

本报告只覆盖 T-011。不代表整个项目完成，不请求开始 T-012。
