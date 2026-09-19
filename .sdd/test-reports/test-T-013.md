# T-013 Tester 报告（首次独立验收）

- 任务：T-013 生成或刷新页面功能导航
- 角色：Tester（独立验收，不采信 Developer 自验）
- 项目：`/Users/kxy/cursor/class_projects/Develop_Helper/Projects_Repo/Customer_Service`
- 时间：2026-09-19
- 总结果：**PASS**
- DEL AC：DEL-001 **PASS**；DEL-002 **PASS**；DEL-003 **PASS**；DEL-004 **PASS**；DEL-005 **PASS**
- source_feature：F-DELIVERY / SDD-DELIVERY
- type：delivery；execution_mode：automatic；user_gate：passed；T-001–T-012 passed
- specification：default，但本任务 `rules_files=[]`，未加载规范集；按交付协议 + DEL AC 验收
- 派发：`python3 .../scripts/sdd_dispatch.py --tasks .../Customer_Service/.sdd/tasks.json --running-task T-013` → `gate_phase=passed`，`gate_task_id=T-004`，`in_flight_or_queued=["T-013"]`，`errors=[]`。任务 status=testing。
- 本轮只验收**页面功能导航**，不重跑业务联调，不调用百炼 / 登录 / 入库。
- 未改业务代码、`.sdd/tasks.json`、方案/规范；未 commit/push；未读 `backend/.env`；未杀 Vite PID 81572 / uvicorn PID 90461。
- 密钥：本报告不写运行值。README / 导航页只出现 `.env.example` 字段名。

## 环境

- 产物：`docs/project-console.html` SHA256 `eba5d4430fb1ea4c71b1e44fe77c42e4192277814a4968b239cceda7e64d37b1`；`docs/project-map.json` SHA256 `c8fe93cde95069382553b41bb201a1dccba99e0a0245b81849992472d67bf7dc`。隔离与 `--html` 临时刷新后正式页哈希不变。
- 浏览器：独立标签 `viewId=07715b`，短时静态服务 `http://127.0.0.1:65206/project-console.html`（PID 83647，验收后已停；65206 已释放）。不是 5199/8099，也不是 Developer 8765。
- 受保护进程仍在：Vite 81572（5199）、uvicorn 90461（8099）。
- 隔离样例：`/tmp/cs-console-t013-kbZG2k`（新临时目录，未覆盖正式 HTML）。
- 截图：`.sdd/test-reports/t013-assets/`。

## 检查表

| ID | 场景 / 输入 | 动作 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- | --- |
| TC-01 | 打开导航页 | 静态服务打开正式 HTML | 按实际页面组织；无旧六区看板 | 浏览器 1280 / 894 | PASS |
| TC-02 | 功能卡导航与展开 | 点左侧页面/算法/参数；展开请求/来源 | 卡片可跳转、可展开；摘要与主流程可见 | 浏览器点击 + 截图 | PASS |
| TC-03 | 窄屏 ~390px | `Emulation.setDeviceMetricsOverride` 390×844 | 导航换行、卡片换行；无遮挡/整页横向溢出 | CDP scrollWidth=390，overflowing=[] | PASS |
| TC-04 | 共享接口可到达 | 员工提问卡点 API-010 | URL 变为 `#api-API-010`，卡片含 method/URL/字段 | 浏览器 | PASS |
| TC-05 | 路径复制失败手选 | 复制路径（剪贴板因未聚焦失败） | toast「复制失败，请手选路径」；只读框可选中 | 浏览器 + CDP | PASS |
| TC-06 | 功能 trigger/io/flow | 核 9 个功能 | 均有触发、输入输出、带 branch 的前后端流程 | map JSON + 页面 | PASS |
| TC-07 | API-001～018 vs 路由 | 对照 routes + 抽检 API-001/010 | method/URL/请求响应字段类型与代码对应 | 源码 + 控制台 | PASS |
| TC-08 | 入库 500/80、FAQ 0.82 | ALG-INGEST / ALG-FAQ | 与 `settings.py` 源码默认一致，`value_kind=source_default` | 源码 + 页面 | PASS |
| TC-09 | OUT_OF_SCOPE 三类同文案 | ALG-QA | 三类状态走同一 `out_of_scope_text` | 源码 `qa.py` + 页面 | PASS |
| TC-10 | 工单状态机与员工 handoff | ALG-TICKET / 员工端 / 工作台 | pending→processing→closed；员工只见 handoff_state | 源码 + 页面 | PASS |
| TC-11 | 无编造 Agent/Plugin | 模块与 ALG-LLM-HTTP | 百炼为 httpx Chat/Embedding；无 Agent 观察环 | 浏览器 + `llm_http.py` | PASS |
| TC-12 | `ws_reconnect_max_seconds` | 参数表 vs `ws.ts` | 标「未找到重连实现 / 仅设计」，不当成前端已实现 | 页面 + `ws.ts` 无匹配 | PASS |
| TC-13 | 来源与核对状态 | 展开来源 | 可定位文件/符号；正式页指纹全部相符，「源码已核对」 | 指纹扫描 + 浏览器 | PASS |
| TC-14 | 无业务/付费调用 | 资源列表 | 仅静态 HTML，无 `/api`、无 dashscope | `performance.getEntries` 空 | PASS |
| TC-15 | README 刷新方式 | 读 README；`--html` 临时刷新 | 打开/刷新/5199/8099 说明有效；无密钥 | 读文件 + 脚本 | PASS |
| TC-16 | 隔离：过期指纹 | `--isolation-sample` 新目录 | ALG-QA 标「来源已变化待复核」，不再标「源码已核对」 | `/tmp/cs-console-t013-kbZG2k/stale.html` | PASS |
| TC-17 | 隔离：缺失来源 | 同上 | 「来源缺失」+ `does-not-exist.py` | `missing.html` | PASS |
| TC-18 | 隔离：坏 JSON | 同上 | 错误页「不是合法 JSON」 | `bad.html` | PASS |
| TC-19 | 仅导航产物 | 对照 write_scope 与业务文件 mtime | 导航产物晚于业务源码；正式 HTML 未被隔离改写 | 文件时间 + 哈希 | PASS |

---

## DEL-001 页面按实际入口组织，可导航展开，桌面/窄屏无整页溢出，无旧六区看板 — PASS

预期：左侧按真实页面，右侧功能卡；桌面与约 390px 无遮挡/整页溢出；不再展示旧六区管理看板。

实际：

- 左栏：`/login` 登录、`/employee` 员工端、`/knowledge` 知识库、`/agent` 客服工作台，以及全部接口/算法/模块/参数。标题「页面功能与实现导航」。
- 无「项目概况 / 启动指南 / 验收看板 / 决策看板」。仅出现「不是旧的六区管理看板」。
- 9 张功能卡均可展开；主流程默认可见。
- 桌面 1280：`scrollWidth=clientWidth=1280`，两栏 `224px 1056px`，侧栏 sticky，横向溢出元素 0。
- 390px：`wrap` 为 `block`，导航 `flex` 换行，`scrollWidth=390`，溢出元素 0。参数表单元格换行较密，但无整页横向溢出或遮挡。
- 导航点击：`#page-page-employee`、`#page-page-knowledge`、`#page-page-agent`、`#page-page-login`、`#algorithms`、`#parameters` 均到达。

证据：`t013-assets/t013-desktop-top.png`、`t013-desktop-1280.png`、`t013-narrow-390-login.png`、`t013-narrow-390-knowledge.png`、`t013-narrow-390-agent.png`、`t013-narrow-390-parameters.png`。

---

## DEL-002 功能含触发/输入输出/带分支流程；接口与代码对应；共享接口可到达 — PASS

预期：每项功能有 trigger、input、output、带 branch 的前后端流程；method/URL/请求响应字段及类型与代码对应；共享接口引用可跳转。

实际：

- map 中 4 页面、9 功能、20 接口（含 EXT Chat/Embedding）、7 算法、6 模块。功能完整性扫描：无缺失 trigger/input/output/flow；每条 flow 均有 actor/action；均至少一条 branch；`api_ids` 均可解析。
- 抽检 API-001：`POST /api/auth/login`，body `username`/`password` string，401「账号或密码不正确」，400「请输入用户名和密码」。对应 `auth.py` + `LoginRequest` + `frontend/src/services/auth.ts` `POST /auth/login`（Axios `baseURL=/api`）。
- 抽检 API-010：`POST /api/conversations/{conversation_id}/messages`；path `conversation_id` int；body `content` string；响应 `user_message` / `assistant_message=null` / `handoff_state` / `stream`；409 CONFLICT。对应 `conversations.py` `send_message` + `conversations.ts` `sendMessage`。浏览器从员工卡跳到 `#api-API-010`。
- API-001～018 的 method/URL 与 `auth.py` / `documents.py` / `conversations.py` / `tickets.py` / `ws.py` 前缀+装饰器一致。

证据：浏览器 `t013-api-010.png`、`t013-api-010-expanded.png`、`t013-nav-employee.png`；`docs/project-map.json`；上述路由文件。

---

## DEL-003 关键算法与源码一致；不编造 Agent/Plugin — PASS

预期：分块/打标/FAQ、FAQ 拦截与标签召回、提问编排、工单状态机与源码一致；工具/Agent 仅按实际存在呈现；百炼是 httpx Chat/Embedding。

实际：

- 入库：`chunk_size_chars=500`、`chunk_overlap_chars=80`（`settings.py` 默认）；步骤含空行切段 + 字符滑动、taxonomy 打标、embed 每批 10、FAQ 抽取、失败回滚。页面 ALG-INGEST 一致。
- FAQ 拦截：阈值源码默认 **0.82**（`faq_similarity_threshold`）；页面写明 `source_default`，未读运行 `.env`。
- 召回：标签过滤后余弦，`retrieval_min_score=0.45`、`retrieval_top_k=5`；无全库回退、无重排。与 `qa.py` `_retrieve_chunks` 一致。
- 提问编排：`OUT_OF_SCOPE_STATUSES = {needs_clarification, requires_live_data, out_of_scope}` 走同一 `out_of_scope_text`。页面 ALG-QA 写「同一句 out_of_scope_text」。
- 工单：pending → processing → closed；员工只见 `handoff_state`（none/waiting/in_progress）。工作台页明确「员工端不出现这些工单状态字」。`EmployeePage.tsx` 无 pending/processing/closed UI 文案。
- 模块 kind 仅为「普通函数/服务」或「外部服务」。MOD-LLM-HTTP：「httpx Chat/Embedding；kind 不是 Agent 工具」。ALG-LLM-HTTP：「不是 Agent：无工具列表、无观察环、无 Plugin」。对应 `llm_http.py`。
- `ws_reconnect_max_seconds=30` 在参数表标明「`ws.ts` 未找到重连实现，属仅设计/未接到前端」。`frontend/src/services/ws.ts` 无 reconnect 逻辑。未当成已实现。

证据：`t013-algo-ingest.png`、`t013-algo-qa.png`、`t013-narrow-390-agent.png`；`backend/src/config/settings.py`、`ingest.py`、`qa.py`、`ticket.py`、`llm_http.py`、`ws.ts`。

---

## DEL-004 来源可定位；设计/默认/运行边界清晰；浏览器交互可用；无付费调用 — PASS

预期：功能/接口/算法有来源与核对状态；浏览器可导航、展开、看来源、复制或失败手选；无业务或付费调用。

实际：

- 正式 map 全部指纹与当前文件 SHA256 相符（stale/missing/unrecorded 均为 0）；页面状态「源码已核对」。来源含 path + symbol +「指纹相符」。
- 参数区分 `source_default` / `source_constant` / `runtime_unknown`。密钥字段只写名称，未读运行值。
- 复制：剪贴板 `NotAllowedError: Document is not focused` → toast「复制失败，请手选路径」→ `#api-API-010 .copy-fallback` `display:block`、`readonly`、值为 `backend/src/api/routes/conversations.py`，可全选。
- 资源请求：单页内联 CSS/JS，`performance.getEntriesByType('resource')=[]`。未打 `/api`、未打百炼、未登录、未入库。

证据：`t013-copy-fallback-field.png`、`t013-api-010-expanded.png`；指纹扫描输出。

---

## DEL-005 README 刷新有效；隔离样例反映过期/缺失/坏 JSON；仅导航产物 — PASS

预期：README 刷新命令可用；隔离目录中源变更标待复核、缺失与解析错误明确；过期算法不继续标已核对；不改业务代码。

实际：

- README「页面功能导航」给出打开 `docs/project-console.html`、`python3 scripts/refresh-project-console.py`、`--record-fingerprints`、`--isolation-sample`；前端 5199 / 后端 8099；只列 `SECRET_KEY`、`INTERNAL_USERNAME`、`INTERNAL_PASSWORD`、`LLM_API_KEY`、`HOST`、`PORT`、`DATABASE_PATH`、`VITE_API_BASE_URL`、`VITE_WS_PATH` 等字段名。无 32+ hex 密钥块。
- `python3 scripts/refresh-project-console.py --html /tmp/cs-console-t013-refresh.html` 写出的 HTML 与正式页哈希相同（指纹当前有效），正式页未被改写。
- 隔离（新目录 `/tmp/cs-console-t013-kbZG2k`，脚本自报 `isolation sample passed`）：
  - `stale.html`：ALG-QA 卡片含「来源已变化待复核」，不含「源码已核对」。
  - `missing.html`：ALG-INGEST「来源缺失：backend/src/services/does-not-exist.py」。
  - `bad.html`：标题「页面功能导航 · 无法生成」，正文「说明数据不是合法 JSON」。
- 业务文件 mtime 早于导航产物（例：`qa.py` 04:15、`ingest.py` 09-18、`ws.ts` 05:53；`project-map.json` 08:18、`project-console.html` 08:23、`refresh-project-console.py` 09:01、`README.md` 08:18）。隔离与临时刷新后正式哈希仍为 `eba5d443…` / `c8fe93cd…`。

证据：README；隔离目录文件；本报告环境哈希。

---

## 技术检查

1. 浏览器检查导航、功能展开、接口跳转、路径复制、窄屏布局，无旧六区看板 — **PASS**
2. 按源码核入库分块/打标/FAQ、FAQ 拦截与标签召回、提问编排、工单状态机；Agent/Plugin 不存在则不展示 — **PASS**
3. 隔离样例验证刷新、源码变更待复核、缺失和格式错误提示；不读取真实密钥 — **PASS**

---

## 范围外（不计入本任务判定）

- 项目内 git 尚无 commit（全部未跟踪），无法用 diff 证明历史；本轮用产物 mtime + 指纹 + 正式页哈希判定导航任务未改业务代码。
- 390px 参数表换行较碎，不影响整页溢出判定。
- 未重测登录/入库/提问/工单业务路径；T-013 PASS 只表示**导航页**通过。

## 交回编排器

Tester 不更新 `tasks.json`。请编排器将 T-013 置 `passed` 并走用户门禁。Tester PASS 不等于用户已放行，也不表示整轮编排已结束。
