# T-006 Tester 报告（首次验收）

- 任务：T-006 知识入库后台任务、文档 API 与文档进度通道
- 角色：Tester（非复验）
- 项目：`Projects_Repo/Customer_Service`
- 时间：2026-09-12
- 总结果：**PASS（后端阶段 / Mock 入库）**
- 业务 AC：本任务 `acceptanceCriteria=[]`；AC-005/007/019/020/021/024 由 **T-010** 页面/真实联调验收。本报告只验 Mock 状态机与接口契约，**不宣称真实百炼打标/向量 AC 通过**。
- 规范集：default
- 派发：`sdd_dispatch.py --running-task T-004 --running-task T-006` → `gate_phase=frontend_in_progress`，`errors=[]`，T-006 为 testing；非 integration/delivery。`step_gate.status=awaiting_user` 属于 T-001 历史门禁，脚本 `gate_phase` 不是 awaiting_user，已开验。
- 实例：Developer `95f51102-9a5d-4ea7-866b-b1b1fd5f2c31`
- 未改业务代码、`.sdd/tasks.json`、方案/规范；未续派 T-007。

## 环境

- Python：项目 `.venv` **3.12.13**；`pytest-timeout` 2.4.0。
- `backend/.env` **不存在**。配置回退 `.env.example`，`LLM_API_KEY` 为空。无真实 Key。`has_real_llm_key=False`；日志多次「无 LLM Key，使用本地 Mock Embedding」。
- pytest：项目根 `.venv/bin/python -m pytest backend/tests --timeout=120` → **20 passed**（6.18s）。夹具走 `tmp_path/test.db`，未碰业务库。
- 业务库 `backend/data/Customer_Service.db` 验收前后不变：1 用户、1 行 `t006-vpn.txt`/`ready`（Developer 抽检残留）。pytest 后 mtime/size 仍为 `1789221980` / `77824`。
- 本轮 **未启动 8099**（开工时未监听；活端口会写入业务库）。契约抽检用隔离 TestClient（含 WS）。验收结束 **8099 仍未监听**。
- 未操作浏览器，未杀 Vite PID 96127 / 5199，未改 `frontend/`。
- `backend/src` 无 `dashscope` / `OpenAIProvider` 引用；`httpx.AsyncClient(trust_env=False)`。
- `python-multipart` 0.0.32 已在 `.venv`，**未写入** `backend/requirements.txt`。对照 `shared/env-policy.md`：该件只管 `.env`/端口/存储落点，不要求登记此包。本轮必要检查未受阻。新鲜 `pip install -r requirements.txt` 可能缺 multipart、API-004 上传会失败——范围外记录，未改代码。

## 检查表

| ID | 场景 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- |
| TC-01 | API-004 支持扩展名 queued；`.xlsx`/`.doc` 与超限 400 且不建行 | `.pdf/.docx/.md/.markdown/.txt` 立即 `status=queued`；不支持格式与过大 400 `VALIDATION_ERROR`，documents 行数不变 | pytest + 独立 TestClient | PASS（Mock） |
| TC-02 | 空文档/无法提取正文 | `failed`，`error_message` 含「无法提取正文」；chunks/faqs 不进可检索；列表/详情可回看 | pytest + TestClient（空 txt、空白 PDF） | PASS（Mock） |
| TC-03 | Mock ready 含分块/标签/FAQ；未 ready 不可检索；进度与 WS `document.*` | ready 有 chunks、`object_types`/`request_types`、FAQ；progress 按阶段；WS `document.progress`/`ready`/`failed` | pytest + TestClient WS | PASS（Mock） |
| TC-04 | 进程重启回收中断任务；pytest 覆盖 | queued/processing → `failed`「入库中断，请重新上传」并删未完成文件；无 Key 走 Mock | pytest + TestClient lifespan | PASS（Mock） |
| TC-05 | 无半可检索；失败回滚 chunks/faqs | 失败/processing 行不出现在 `list_retrievable_*`；打标失败后该文档 0 chunk/0 faq | pytest + 定向抽检 | PASS（Mock） |

后续责任：AC-005/007/019/020/021/024 及真实打标/向量 → T-010。无 Key 不得把 Mock 入库当真实百炼通过。

---

## TC-01 上传校验与 queued — PASS（Mock）

预期：支持格式立即 200、`status=queued`、`progress_percent=0`，不表示可检索；`.xlsx`/`.doc` 400，文案「不支持该格式，请上传 PDF、Word（.docx）、Markdown 或 txt」，不建行；超过 `upload_max_bytes` 400。

实际：

- pytest `test_upload_supported_formats_return_queued` / `test_reject_unsupported_formats_without_row` / `test_reject_oversize_without_row` 通过。
- 独立 TestClient：txt/md/markdown/docx/pdf 均 200 `queued`；xlsx/doc 400 `VALIDATION_ERROR`，行数不变；超限（夹具将上限改为 8 字节）400，`error` 含「文件过大」，不建行。

证据：pytest 20 passed；抽检日志 `文档已接收并进入队列`。空白 PDF 仅验证 queued，后续失败见 TC-02。

---

## TC-02 提取失败与回看 — PASS（Mock）

预期：空文档或抽不出正文 → 记录 `failed`，`error_message` 含「无法提取正文」；chunks/faqs 不可检索；API-005/006 可回看。

实际：

- 空 txt：详情 `status=failed`，`error_message=无法提取正文，文档未入库`，`chunks=[]` `faqs=[]`；`GET /api/documents?status=failed` 可见该 id。
- 空白 PDF：同样 failed +「无法提取正文」。
- 失败后该文档无 chunk/faq 行；上传文件被删。

证据：pytest `test_empty_document_failed_not_retrievable`；抽检 `empty_failed` / `empty_list_review` / `blank_pdf_failed_extract`。

---

## TC-03 Mock ready、不可检索、WS — PASS（Mock）

预期：无 Key 走 Mock；ready 含分块、对象/诉求标签、FAQ；未 ready 不能被后续检索；`progress_percent` 按阶段更新并向 WS 推 `document.*`。

实际：

- `has_real_llm_key=False`；重复日志「无 LLM Key，使用本地 Mock Embedding」。
- `vpn-auth.md` ready：`progress_percent=100`，`chunk_count>=1`，`faq_count>=1`，`object_types` 含 `network`（Mock 关键词还带出 `account`），`request_types` 含 `troubleshooting`；成功原文保留在隔离 uploads。
- 在途 `queued` 文档自身不出现在 `list_retrievable_chunks/faqs`（`leaked_chunks_of_this_doc=[]`；库内可检索条数只来自已 ready 文档）。
- WS 成功路径事件含 `document.progress` 与 `document.ready`，进度 `10,25,45,70,90,100`（queued 的 0 在 HTTP 响应，不在 WS）。空文档 WS 含 `document.failed`。
- 坏 Token 连接被拒绝（pytest `test_ws_rejects_bad_token`）。

本条标签与 FAQ 为 **Mock 关键词/模板**，不等于 AC-021 真实打标。

证据：pytest `test_ready_document_has_chunks_tags_and_faq`、`test_ws_pushes_document_events`；抽检 `ready_mock_shape`、`ws_progress_ready`、定向 unready 查询。

---

## TC-04 启动回收与 pytest — PASS（Mock）

预期：重启将 `queued`/`processing` 标 failed，文案「入库中断，请重新上传」，删除未完成文件；pytest 覆盖校验、失败回看、ready 事务。

实际：

- `main.py` startup 调用 `fail_interrupted_ingests`。
- pytest `test_interrupt_marks_failed_and_deletes_file` 通过。
- 独立：先写入 queued 文件 + processing 行，再开 TestClient lifespan → 两行均为 failed /「入库中断，请重新上传」，`storage_path=None`，残留文件删除，chunks/faqs 清零。日志「启动时将中断入库标为失败」。

证据：pytest 20 passed；抽检 `startup_*`。

---

## TC-05 无半可检索、失败回滚 — PASS（Mock）

预期：不出现半可检索；失败回滚 chunks/faqs。实现上将 chunk/faq 与 `status=ready` 写在同一事务；失败走 `delete_chunks_and_faqs`。

实际：

- 无领域关键词正文 → failed「入库失败，请重新上传」，该 `document_id` 的 chunks/faqs 为 0。
- 手工给 processing 文档插孤儿 chunk：`list_retrievable_chunks()` 仍为 0（过滤 `documents.status='ready'`）。
- 启动回收后孤儿 chunk 被删。
- 空/失败文档未泄漏进可检索集合。

证据：抽检 `tag_fail_*`、`processing_orphan_not_retrievable`、`failed_not_retrievable`、`startup_rolled_chunks`；`ingest.py` ready 事务与 `_fail_document`。

---

## 范围外（不计入判定）

- `backend/requirements.txt` 未列 `python-multipart`（env-policy 不覆盖；当前 `.venv` 已装，本轮检查通过）。
- Mock 标签比方案示例更宽（VPN 文同时命中 account 等），真实语义一致性留给 T-010。
- 超限提示在夹具 8 字节上限下显示「最大 1MB」（整除取整），默认 20MB 文案未在本轮用真实 20MB 文件打满。

## 8099

开工未监听；本轮未启动；结束仍未监听。
