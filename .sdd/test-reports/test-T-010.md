# T-010 Tester 报告（首次独立验收）

- 任务：T-010 知识入库真实联调（含立即提问生效）
- 角色：Tester（独立验收，不采信 Developer 自验）
- 项目：`/Users/kxy/cursor/class_projects/Develop_Helper/Projects_Repo/Customer_Service`
- 时间：2026-09-19
- 总结果：**PASS**
- 业务 AC：AC-005 **PASS**；AC-006 **PASS**；AC-007 **PASS**；AC-019 **PASS**；AC-020 **PASS**；AC-021 **PASS**；AC-024 **PASS**
- source_feature：F-003（REQ-003、REQ-007）
- type：integration；execution_mode：automatic；user_gate：passed；specification：default
- 派发：`python3 .../scripts/sdd_dispatch.py --tasks .../Customer_Service/.sdd/tasks.json --running-task T-010` → `gate_phase=passed`，`gate_task_id=T-004`，`in_flight_or_queued=["T-010"]`，`errors=[]`。任务 status=testing。未开始 T-011。
- 浏览器：独立新标签 `viewId=544ece`（list 时无既有标签）。清空本标签 `localStorage.access_token` 后用 `it-admin` 重新登录，未附着 Developer 会话操作。
- 未改业务代码、`.sdd/tasks.json`、方案/规范；未 commit/push；未清空 `backend/data/Customer_Service.db`；未杀编排器持有的 5199 / 8099。
- 密钥：本报告不写 `INTERNAL_PASSWORD`、JWT、`LLM_API_KEY`。配置状态：`.env` 与 `.env.example` 键一致；`INTERNAL_USERNAME=it-admin`；`LLM_API_KEY` 已配置（非空）；Chat=`qwen-plus`；Embedding=`text-embedding-v3`；`LLM_BASE_URL` host=`dashscope.aliyuncs.com`。

## 环境

- 前端：`http://127.0.0.1:5199`，Vite cwd=`.../Customer_Service/frontend`（终端 PID 81545，用户交接 node PID 81572）。`GET /` 200。未再起 5199。
- 后端：`http://127.0.0.1:8099`，uvicorn PID **46453**（PPID 46446），cwd=`.../Customer_Service/backend`。库路径 `backend/data/Customer_Service.db`。未杀该进程。
- 登录：`demo/demo` 直连 `POST /api/auth/login` → HTTP 401，`success=false`，`error_code=UNAUTHORIZED`。`it-admin` + `.env` 内部密码 → HTTP 200，`token_type=bearer`，`user.username=it-admin`。浏览器同样进入 `/employee`。
- 本轮夹具（时间戳前缀，不把 Developer 旧行当本轮结果）：`.sdd/test-reports/fixtures-T-010/t010-20260919-011544-*`
- 本轮新建文档 id：8 txt / 9 empty / 10 corrupt / 11 docx / 12 md / 13 pdf。旧行 id 1–7 仅作背景，不判本轮。

## 检查表

| ID | 场景 / 输入 | 动作 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- | --- |
| TC-01 | 四种支持格式各一份，唯一文件名 | 知识库页提交 txt/md/pdf；docx 走真实 API-004；提交后离开再回 | 真实 `POST /api/documents` multipart 200 `queued`；API-005/006 可见 queued/processing/ready；进度主通道为 WS `document.progress`，不是 2s 轮询 | 独立浏览器 + XHR/WS 探针 + HTTP | PASS |
| TC-02 | ready 后立刻提问；网络+故障排查文档 | 打开本轮 vpn txt 详情；员工端用相近问提问 | 无「确认入库」；分块/中文对象诉求标签/FAQ 可见；`object_types=network`、`request_types=troubleshooting` 与 `docs/tag-taxonomy.json` 一致；员工端 FAQ 命中本轮标志词 | 浏览器 + API-006 | PASS |
| TC-03 | 不支持格式；空/损坏；员工端 | 上传 `.xlsx`；上传本轮 empty/corrupt；查看员工端 | 当场「不支持该格式」；API-004 400 且不建 id；failed 文案明确，chunks/faqs 空，离开再回仍失败；员工端无上传/检索入口 | 浏览器 + API | PASS |
| TC-04 | 有 Key，真实百炼 | 本轮 4 份成功入库作业日志 | 出现「入库将调用真实百炼 Chat/Embedding（llm_http）」「调用百炼 Chat 成功」「调用百炼 Embedding 成功」；**不得**出现「无 LLM Key，使用本地 Mock」 | 后端终端日志（脱敏） | PASS |

---

## AC-005 支持格式提交后可离开，回来成功，立刻提问命中 — PASS

预期：知识库管理端提交支持格式后可离开/切换；再打开见入库成功；立刻到员工端就该内容提问；FAQ（含相近）或标签召回，回复与原文要点相符。

实际：

- 浏览器上传 `t010-20260919-011544-vpn-auth.txt`。XHR：`POST /api/documents` **200**，`data.id=8`，`status=queued`，`stage=queued`。
- 停留页上即见「处理中 70%」和「正在处理，你可以切换到其它页面」。WS 收到 `document.progress`：extracting 10% → chunking 25% → tagging 45% → embedding 70%（非 2s HTTP 轮询）。
- 处理中切到 `/employee`，再回 `/knowledge`：该文件「已生效」。详情含分块原文要点与抽出 FAQ。
- 员工端新会话相近问：「怎么知道这次公司 VPN 排查已经成功了？有没有成功标志词？」回复带来源 **FAQ**，正文「出现成功标志词：T010-VPN-RESET-OK-20260919-011544。」与本轮夹具原文一致，不是 Developer 旧文档 FAQ。

证据：本报告 TC-01/TC-02；浏览器 snapshot（知识库详情 + 员工端 FAQ 回复）；API-006 id=8。

---

## AC-006 员工端不能上传或检索知识库 — PASS

预期：员工端无入库/检索入口，无法写入知识。

实际：登录后 `/employee`：`input[type=file]` 数量 0；无「上传」按钮；无 `type=search`；正文无「上传」「检索」。仅有提问输入、发送、转人工与历史。知识库入口只在顶栏切到 `/knowledge`。

证据：本标签 Runtime 检查；员工端 snapshot。

---

## AC-007 不支持格式当场拒绝、不建记录 — PASS

预期：不支持格式当场「不支持该格式」；不分块、不打标、不进检索、无 FAQ。

实际：

- 浏览器选择 `t010-20260919-011544-unsupported.xlsx`：错误条「不支持该格式」；列表仍 7 条旧文档 + 随后本轮支持格式，**没有** xlsx 新行。
- 直连 API-004 同一文件：HTTP **400**，`error_code=VALIDATION_ERROR`，`error=不支持该格式，请上传 PDF、Word（.docx）、Markdown 或 txt`，`data=null`。提交前后文档 id 集合均为 `[1..7]`，无新 id。

证据：浏览器 DOM `role=alert`；`/tmp` 对照已删除，结论写入本报告 TC-03。

---

## AC-019 进度可见；成功后分块/中文标签/检索库/FAQ；无确认按钮 — PASS

预期：入库中或回来能看到进度；成功后确认已分块、对象/诉求中文标签、已写入检索库、已抽出 FAQ；无「确认入库」按钮。

实际：

- 进行中：列表「处理中 70% / 45% / 90%」，详情「处理中 N%」。离开后再进页 API-005 快照可见 queued/processing/ready/failed。
- id=8 ready：中文标签「网络与远程接入」「故障与异常排查」；分块 2；FAQ 7；详情文案「入库成功立即生效，无需再确认。」页内无「确认入库」。
- 四种格式 ready 后 API-006 均有 chunks 与 faqs（txt 2/7，docx 1/10，md 3/8，pdf 1/5）。
- 知识库页无 `[Mock]` 上传提示（与 Developer 改动一致，且实测）。无检索框（UI-03）。

证据：浏览器 snapshot；API-005/006。

---

## AC-020 无法提取正文则失败且不可检索，离开后再见失败 — PASS

预期：入库失败（无法提取正文）不进入可检索状态；离开后再打开仍见明确失败。

实际：

- `t010-20260919-011544-empty.txt` id=9、`t010-20260919-011544-corrupt.pdf` id=10：`status=failed`，`error_message=无法提取正文，文档未入库`，`chunks=0`，`faqs=0`，标签空。
- 切到员工端提问本轮成功文档后，再回知识库：两条仍显示「失败」。点开详情仅失败原因，无分块/FAQ 区。
- 失败文档未进入 FAQ/召回库（无分块向量、无 FAQ）。成功文档可被 FAQ 命中，失败文档无内容可命中。

证据：API-006 id=9/10；浏览器失败详情「无法提取正文，文档未入库」。

---

## AC-021 网络 + 故障排查标签语义一致且立刻可提问 — PASS

预期：入库一份可识别为「网络 + 故障排查」的文档；对象/诉求标签与该语义一致，且立刻可用于提问。

实际：

- 本轮 `t010-20260919-011544-vpn-auth.txt`（VPN 认证失败排查）：API `object_types=["network"]`，`request_types=["troubleshooting"]`。界面中文名与 `docs/tag-taxonomy.json` 一致：网络与远程接入 / 故障与异常排查。
- 同语义 pdf `t010-20260919-011544-wifi.pdf` 同样是 `network` + `troubleshooting`。
- ready 后未经确认即可员工端提问命中（见 AC-005/024）。

证据：API-006 id=8/13；知识库详情 snapshot。

---

## AC-024 成功后不经确认即可被 FAQ 相近或标签召回 — PASS

预期：入库成功后不经任何确认步骤，员工端立即能被该文档 FAQ 相近拦截或标签召回；离开期间成功的同样立即生效。

实际：id=8 在离开员工端期间完成 ready。未点任何确认。员工端用**相近问**（非 FAQ 原问逐字）立刻得到 **FAQ** 答案，含本轮唯一成功标志词。知识库详情写明「无需再确认」，无确认按钮。

证据：员工端 snapshot / Runtime：`hasFAQ=true`，`hasMarker=true`。

---

## TC-01 四种格式真实 API-004 与回看 — PASS

| 文件 | 通道 | id | 过程 | 终态 |
| --- | --- | --- | --- | --- |
| `...-vpn-auth.txt` | 浏览器 POST `/api/documents` | 8 | queued → processing（WS progress）→ 离开再回 | ready，chunks=2，faqs=7 |
| `...-printer.md` | 浏览器 POST `/api/documents` | 12 | processing faq_extracting 90% | ready，chunks=3，faqs=8，hardware+troubleshooting |
| `...-outlook.docx` | curl 真实 API-004 multipart | 11 | 200 queued | ready，chunks=1，faqs=10，software+troubleshooting |
| `...-wifi.pdf` | 浏览器 POST `/api/documents` | 13 | 处理中 45% 后离开再回 | ready，chunks=1，faqs=5，network+troubleshooting |

HTTP 时间差：POST 后只跟一次 GET 详情（选中行），之后数十秒无按 2s 重复拉列表；进页才再 GET list（含 React Strict Mode 双挂载 dt≈0）。主进度为 WS `document.*`。

---

## TC-02 ready 后无确认且员工端命中 — PASS

见 AC-005、AC-019、AC-021、AC-024。taxonomy：`network`→网络与远程接入，`troubleshooting`→故障与异常排查。

---

## TC-03 不支持 / 失败 / 员工无入口 — PASS

见 AC-006、AC-007、AC-020。

---

## TC-04 真实百炼，不是无 Key Mock — PASS

本轮成功作业（document_id=8,11,12,13）后端日志（PID 46453 终端，脱敏）：

- 「入库将调用真实百炼 Chat/Embedding（llm_http）」**4** 次（对应四份成功文档）
- 「调用百炼 Chat 成功，返回含 choices 字段」**8** 次
- 「调用百炼 Embedding 成功，返回含 data 字段」**8** 次
- 「无 LLM Key，使用本地 Mock」**0** 次

空/损坏文件在抽正文失败，不走百炼，符合方案。未把 Mock 提供商结果当真实百炼。

`llm_http.py` 使用 `httpx.AsyncClient(trust_env=False)`，注释禁止 dashscope SDK；本任务未把 Key 写入报告。

---

## 范围外（不计入本任务判定）

- 员工端会话标题/顶栏仍有 `[Mock]` 字样：任务说明属 T-011，不得单独因此 FAIL T-010。知识库页本身无 `[Mock]`。
- 库中 Developer 旧文档 id 1–7（含旧 `empty.txt` / `corrupt.pdf` / `vpn-network-troubleshooting.md`）未清空，仅作背景。本轮只依据 `t010-20260919-011544-*`。
- FastAPI `/docs`、`/openapi.json` 对本进程返回 404：非本任务 AC，T-009 已 PASS 登录联调。未当作 T-010 FAIL。
- 未跑完整 T-011 FAQ/闲聊/兜底矩阵；只验 T-010 要求的立即提问。
- 截图工具两次超时，视觉证据以可访问性 snapshot 与 DOM 文案为准；未逐像素核对 UI-03 色值。

## 未修改文件

本次 Tester 未改业务代码。新增报告与夹具：

- `.sdd/test-reports/test-T-010.md`（本文件）
- `.sdd/test-reports/fixtures-T-010/t010-20260919-011544-*`

本 PASS 只覆盖 T-010 / F-003 知识入库真实联调，不表示整个项目完成，也不请求或开始 T-011。
