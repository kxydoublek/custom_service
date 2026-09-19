# T-007 Tester 报告（首次验收）

- 任务：T-007 会话、FAQ 拦截与流式自动回复编排
- 角色：Tester（非复验）
- 项目：`Projects_Repo/Customer_Service`
- 时间：2026-09-18
- 总结果：**PASS（后端阶段 / Mock 编排）**
- 业务 AC：本任务 `acceptanceCriteria=[]`；AC-003/004/016/017/018/022/023 由 **T-011** 页面/真实联调验收。本报告只验 Mock 编排与 SSE 契约，**不宣称真实百炼/T-011 通过**。
- 规范集：default
- 派发：`sdd_dispatch.py --running-task T-004 --running-task T-007` → `gate_phase=frontend_in_progress`，`gate_task_id=T-004`，`errors=[]`，T-007 为 testing；非 integration/delivery。已开验收尾，不续派 T-008。
- 实例：Developer `fadb5d15`
- 未改业务代码、`.sdd/tasks.json`、方案/规范；未操作浏览器；未杀 5199。

## 环境

- Python：项目 `.venv` **3.12.13**；`pytest-timeout` 2.4.0。
- `backend/.env` **不存在**。配置回退 `.env.example`，`LLM_API_KEY` 为空。无真实 Key。`has_real_llm_key=False`；日志「无 LLM Key，使用本地 Mock Embedding / Mock Chat 流式」。
- pytest：项目根 `.venv/bin/python -m pytest backend/tests --timeout=120` → **31 passed**（10.85s）。夹具走 `tmp_path/test.db`，未碰业务库。
- 业务库 `backend/data/Customer_Service.db` 验收前后不变：`mtime=1789221980` / `size=77824`；`users=1` `documents=1` `chunks=1` `faqs=1`。库中尚无 `conversations` 等表（本轮未起 8099，未写业务库）。
- 本轮 **未启动 8099**（开工时未监听；结束仍未监听）。契约抽检用隔离 TestClient。
- 未操作浏览器，未杀 Vite / 5199（5199 仍为 node PID 81572）。未改 `frontend/`。
- `backend/src` 无 `dashscope` SDK / `OpenAIProvider` 引用；`httpx.AsyncClient(trust_env=False)`。无 Plugin / 实时查询工具调用。

## 检查表

| ID | 场景 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- |
| TC-01 | API-010 `stream=true` 后 API-017 事件 `meta→delta→done`；FAQ / small_talk / knowledge_qa 的 source 正确；超范围与无法回答文案等于配置常量 | 来源先于正文；FAQ 答案、闲聊 Mock 流、知识问答命中流、三类超范围与无法回答句分别正确 | pytest + 独立 TestClient | PASS（Mock） |
| TC-02 | FAQ 原文全等不走分类/召回；对象或诉求非空才召回；两侧都空走兜底，禁止无标签全库召回 | NFKC 全等命中 `source=faq` 且不调 `chat_json`/`embed_texts`；仅对象可召回；无标签即使向量可匹配也不召回全库 | pytest + 独立 TestClient | PASS（Mock） |
| TC-03 | 未关闭转人工时 API-010 `stream=false` 且不调 FAQ/闲聊/知识问答；`generation_lock` 第二下 409 | pending→`waiting`、processing→`in_progress`；第二下 409 `CONFLICT`「请等待当前回复结束」 | pytest + 独立 TestClient | PASS（Mock） |
| TC-04 | 分类 JSON 失败走超范围兜底不 500；不输出 `clarification_question`；不调用实时查询工具；历史列表不含工单状态 | 【分类失败】200 SSE 兜底句；查工单进度无追问文案；列表字段仅 `id/title/updated_at/preview` | pytest + 独立 TestClient | PASS（Mock） |
| TC-05 | pytest 覆盖 FAQ 全等、超范围三类同一文案、空召回无法回答、人工中停自动回复；无 Key 不得声称真实模型路径通过 | 上述用例均有断言且通过；`has_real_llm_key=False` | pytest 31 passed | PASS（Mock） |

后续责任：相近 FAQ、真实分类/闲聊/知识问答与 AC-003 等 → **T-011**。无 Key 不得把 Mock 编排当真实百炼通过。

---

## TC-01 SSE 顺序与 source / 固定文案 — PASS（Mock）

预期：`stream=true` 后 API-017 先 `meta` 再若干 `delta` 最后 `done`；`source` 为 `faq` / `small_talk` / `knowledge_qa`；超范围正文 = `out_of_scope_text`；无法回答 = `no_knowledge_text`。

实际：

- 配置常量与方案完全一致：`当前问题超出知识服务范围，你可以点击转人工。` / `现有知识无法回答。你可以点击转人工。`；`faq_similarity_threshold=0.82`。
- FAQ：`meta→delta→done`，`source=faq`，正文为 FAQ 答案。
- 闲聊「你好，在吗」：`meta, delta×4, done`，`source=small_talk`；`done` 后锁释放，下一句可再 `stream=true`。
- 标签命中召回（隔离库写入与问句相同的 Mock 向量）：`Outlook 崩溃怎么办` → `source=knowledge_qa`，事件 `meta, delta×3, done`，正文为分块原文，日志 `purpose=knowledge_qa`。
- 超范围三类同一句；空召回「显示器黑屏怎么办」对 software 分块 → 无法回答句。
- 已完成流重放：同一 `after_user_message_id` 只重放 SSE，不再分类。

证据：pytest `test_faq_exact_match_skips_classification`、`test_small_talk_source_and_sse_order`、`test_out_of_scope_three_paths_same_text`、`test_empty_recall_returns_no_knowledge_text`；抽检 `knowledge_qa_hit_source_and_order`、`small_talk_order`、`replay_existing_sse`。

本条闲聊/分类/召回为 **Mock 关键词路径**，不等于 T-011 真实模型。

---

## TC-02 FAQ 全等与标签过滤 — PASS（Mock）

预期：NFKC 原文全等命中不走分类/召回；对象或诉求非空才召回；两侧都空走超范围兜底，禁止无标签全库召回。

实际：

- 「ＶＰＮ提示认证失败怎么办？」命中「VPN 提示认证失败怎么办？」；`classify=[]` `embed=0`；日志「FAQ 原文或阈值命中，跳过分类与召回」。
- 仅对象「公司显示器型号」召回 hardware 分块，`source=knowledge_qa`，正文为硬件分块，不是超范围句。
- 「这个问题无标签」即使分块向量与问句相同，仍走超范围兜底，不含 software 分块正文；日志「分类结果全部为超范围或无标签，走兜底」。
- pytest `test_empty_tags_do_not_recall_all_chunks`、`test_empty_recall_returns_no_knowledge_text` 通过。

相近 FAQ 余弦拦截未作为本任务真实验收（T-011）。

证据：pytest 上述用例；抽检 `faq_exact_skips_classify_embed`、`object_only_recalls_not_oos`、`empty_tags_no_full_recall`。

---

## TC-03 人工中停与 generation_lock — PASS（Mock）

预期：未关闭转人工时 `stream=false`，不调 FAQ/闲聊/知识问答；并行第二下 409。

实际：

- pending 工单：`stream=false`，`handoff_state=waiting`，无 assistant；`chat_json`/`chat_stream`/`embed_texts` 被断言拦截且未调用。
- processing 工单：`stream=false`，`handoff_state=in_progress`，LLM/FAQ 调用数为 0。
- 未消费流时第二句 409，`error_code=CONFLICT`，`error=请等待当前回复结束`。
- 流结束后锁释放，可再发。

证据：pytest `test_handoff_stops_auto_reply`、`test_generation_lock_second_send_conflict`；抽检 `processing_handoff_stream_false`、`lock_released_after_done`。

工单状态机与 WS 人工通道属 T-008，本条只验停自动回复。

---

## TC-04 分类失败、无追问、无工具、历史无工单状态 — PASS（Mock）

预期：分类 JSON 失败走超范围兜底不 500；SSE 不含 `clarification_question`；不调用实时查询工具；历史列表不含工单状态。

实际：

- 「请处理【分类失败】这个问题」：API-010 200、`stream=true`，SSE 正文为超范围常量；日志「提问分类 JSON 失败，改走超范围兜底」；非 500。
- 「帮我查工单进度和申请进度」：同一超范围句；事件 JSON 无 `clarification_question`，正文无「工单号是多少」。
- `backend/src` 问答路径无 Plugin / tools / `OpenAIProvider`。
- `GET /api/conversations` 项字段仅为 `id, title, updated_at, preview`；详情无 `ticket_status`。

证据：pytest `test_classification_json_failure_falls_back`、`test_create_conversation_and_history_without_ticket_status`、`test_out_of_scope_three_paths_same_text`；抽检 `classify_fail_not_500`、`live_data_no_tool_no_clarification`、`history_no_ticket_status`。

---

## TC-05 pytest 覆盖与无 Key 边界 — PASS（Mock）

预期：pytest 覆盖 FAQ 全等、超范围三类同一文案、空召回无法回答、人工中停；无 Key 不得声称真实模型路径通过。

实际：

- `backend/tests --timeout=120`：**31 passed**（10.85s），含 `test_qa.py` 11 项。
- 覆盖点：`test_faq_exact_match_skips_classification`、`test_out_of_scope_three_paths_same_text`、`test_empty_recall_returns_no_knowledge_text`、`test_handoff_stops_auto_reply`（均有断言，非只打印布尔）。
- `has_real_llm_key=False`。本轮未调用真实百炼。

证据：pytest 汇总；抽检 `no_real_key`。

---

## 范围外（不计入判定）

- 业务库尚未建会话表：因未起 8099，不影响 Mock 验收。
- T-004 前端仍在 5199，未纳入本轮。
- 相近 FAQ、真实分类/闲聊/知识问答、浏览器 AC → T-011。
- 转人工工单状态机与 WS 人工通道 → T-008。
