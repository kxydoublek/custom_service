# T-009 Tester 报告（首次独立验收）

- 任务：T-009 登录与三端入口真实联调
- 角色：Tester（独立验收，不采信 Developer 自验）
- 项目：`/Users/kxy/cursor/class_projects/Develop_Helper/Projects_Repo/Customer_Service`
- 时间：2026-09-18
- 总结果：**PASS**
- 业务 AC：AC-001 **PASS**；AC-002 **PASS**
- 规范集：default
- 派发：`python3 .../scripts/sdd_dispatch.py --tasks .../Customer_Service/.sdd/tasks.json --running-task T-009` → `execution_mode=automatic`，`gate_phase=passed`，`gate_task_id=T-004`，`in_flight_or_queued=["T-009"]`，`errors=[]`。任务 status=testing。未开始 T-010。
- 浏览器：独立新标签 `viewId=77ad11`（list 时无既有标签，未附着 Developer 会话）。站点 localStorage 清空后实测。
- 未改业务代码、`.sdd/tasks.json`、方案/规范；未 commit/push；未杀编排器持有的 5199 / 8099。

## 环境

- 前端：`http://127.0.0.1:5199`，Vite cwd=`.../Customer_Service/frontend`，node PID **81572**，strictPort。验收结束仍 200。未再起 5199。
- 后端：`http://127.0.0.1:8099`，uvicorn PID **96886**（PPID 96880），cwd=`.../Customer_Service/backend`。`POST /api/auth/login` 可达。未杀该进程。
- 登录账号：`INTERNAL_USERNAME=it-admin`（`backend/.env`）。密码只从 `INTERNAL_PASSWORD` 读取，本报告不写值。`demo/demo` 必须失败。
- Vite 代理 `/api`、`/ws` → 8099。`VITE_API_BASE_URL` 按 `.env.example` 为相对路径 `/api`。未调用百炼。`externalServices=[]`。
- 未清空 `backend/data/Customer_Service.db`。
- type-check/lint/build：Developer 自称已过；本轮以浏览器用户路径与真实网络为准，未重跑构建。

## 检查表

| ID | 场景 / 输入 | 动作 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- | --- |
| TC-01 | 匿名打开登录 | 打开 `/login`，空存储 | 标题「智能客服系统」；无 `[Mock]`；无 demo/demo 演示账号；空字段登录禁用；居中卡片约 400px | 独立浏览器 + DOM | PASS |
| TC-02 | `demo` / `demo` | 提交登录 | 停留 `/login`；错误「账号或密码不正确」；真实 `POST /api/auth/login` 401；无 token；不能进三端 | 浏览器 + XHR 记录 | PASS |
| TC-03 | `it-admin` + 错误密码 | 提交登录 | 停留 `/login`；错误「账号或密码不正确」（API-001）；用户名保留；401 信封 `UNAUTHORIZED`；无 token | 浏览器 + XHR 记录；curl 对照 | PASS |
| TC-04 | `it-admin` + 正确内部密码 | 提交登录后查 `/api/auth/me` | 真实 `POST /api/auth/login` 200；`token_type=bearer`；令牌为 3 段 JWT 且 **不是** `mock-token-cs-001`；写入 localStorage；同令牌 `GET /api/auth/me` 200，`user.username=it-admin`；进入 `/employee` | 浏览器 + XHR/fetch | PASS |
| TC-05 | 同一会话三入口 | 登录后打开 `/employee`、`/agent`、`/knowledge` | 三端都能进入；顶栏互斥高亮；受保护接口走真实 GET（conversations / tickets / documents） | 浏览器点击 + 网络 | PASS |
| TC-06 | 未登录直访受保护路由 | 清 token 后访问 `/employee` `/agent` `/knowledge` | 回到 `/login`；明确提示「请先登录」；无 token | 浏览器导航 | PASS |
| TC-07 | 已登录工作台后 401 | `/agent` 上 native WS 已 OPEN；写入无效 JWT；点「处理中」触发 `GET /api/tickets` | HTTP 401，`error=请先登录`；token 清除；WS 从 OPEN 被 close；跳转 `/login` 并显示「请先登录」 | 浏览器 + WS hook + pagehide 探针 | PASS |

后续责任：知识入库 / 提问 / 转人工联调在 T-010～T-012。本 PASS 只覆盖 F-001 / REQ-001 登录与三端入口。

---

## AC-001 正确账号进入三端 — PASS

预期：使用预设内部账号登录成功后，同一账号分别进入员工端、客服工作台、知识库管理端。

实际：

- 登录页提交 `it-admin` + `.env` 内部密码。
- 页面 XHR：`POST /api/auth/login` **200**，信封 `success=true`，`data.token_type=bearer`，`data.user={id:1,username:"it-admin"}`。请求体含 `username=it-admin`（密码已脱敏）。
- 令牌写入 `localStorage.access_token`：长度 171，3 段，**不等于** `mock-token-cs-001`。
- 同令牌 `GET /api/auth/me` **200**，`success=true`，`data={id:1,username:"it-admin"}`。
- 登录后落地 `http://127.0.0.1:5199/employee`；顶栏「员工端」高亮；可点「客服工作台」到 `/agent`；可点「知识库」到 `/knowledge`。
- 进入后真实接口：`GET /api/conversations` 200、`GET /api/tickets?status=pending` 200、`GET /api/documents` 200。不是 auth mock。

证据：

- 截图：`.sdd/test-reports/t009-assets/03-employee-after-login.png`、`04-agent-after-login.png`、`05-knowledge-after-login.png`
- 网络：本报告 TC-04 / TC-05 节

---

## AC-002 错密或未登录不能进入 — PASS

预期：密码错误或未登录不能进入任一端，并看到需登录或账号无效的明确提示。失败文案以 API-001 为准：「账号或密码不正确」。未登录/坏 token：「请先登录」。

实际：

- `demo/demo` 与 `it-admin`+错误密码：均停留 `/login`，错误条「账号或密码不正确」，无三端顶栏，无 token。XHR 均为 `POST /api/auth/login` **401**，`error_code=UNAUTHORIZED`，`error=账号或密码不正确`，`data=null`。用户名 `it-admin` 在失败后保留。
- 直连后端与 Vite 代理同样 401（curl 抽检，文案一致）。空 body：400 `VALIDATION_ERROR`「请输入用户名和密码」（接口对照，非本 AC 主路径）。
- 未登录访问 `/employee`、`/agent`、`/knowledge`：均回到 `/login`，错误条「请先登录」，token 为空。
- 已登录后把 token 换成无效 JWT，在客服工作台点「处理中」：`GET /api/tickets?...status=processing` **401** `error=请先登录`；token 被清；native WS 在 OPEN 时被 close；整页跳到 `/login` 并显示「请先登录」。

证据：

- 截图：`t009-assets/02-login-wrong-password.png`、`06-login-after-401.png`、`07-login-anonymous-employee.png`
- WS 探针见 TC-07

---

## TC-01 登录页不再展示 [Mock] 演示账号 — PASS

预期：登录主路径无 `[Mock]`、无 `demo/demo` 演示说明；空表登录禁用。UI-01：无三端顶栏，居中卡片。

实际：独立标签打开 `http://127.0.0.1:5199/login`。`document.body.innerText` 仅为「智能客服系统 / 用户名 / 密码 / 登录」。`hasMock=false`，`hasDemoCreds=false`。登录按钮 `disabled=true`。卡片宽度 400px。无顶栏三端入口。

证据：`t009-assets/01-login-clean.png`

---

## TC-02 demo/demo 不能登录 — PASS

预期：`demo/demo` 不得成功（不得走前端 mock token `mock-token-cs-001`）。

实际：真实 `POST /api/auth/login` 401，「账号或密码不正确」。`localStorage.access_token=null`。URL 仍为 `/login`。

证据：页面 XHR 日志（密码已替换为 `[redacted]`）。

---

## TC-03 错误密码不进入三端 — PASS

预期：API-001 密码错 → 401 `UNAUTHORIZED`，「账号或密码不正确」，可重试。

实际：浏览器提交 `it-admin` + 错误密码。XHR `POST /api/auth/login` 401，信封同上。页面错误条相同。无员工端导航。用户名仍为 `it-admin`。

curl 对照（8099）：同一 401 / 文案。

证据：`t009-assets/02-login-wrong-password.png`

---

## TC-04 真实登录 + 同令牌 /me — PASS

预期：浏览器登录走真实 `POST /api/auth/login`；令牌写入后 `GET /api/auth/me` 成功。

实际：

- XHR `POST /api/auth/login` 200，非 mock。成功信封含 `access_token`（已脱敏为 `len=171 not-mock`）、`token_type=bearer`、`user.it-admin`。
- localStorage 令牌 3 段 JWT，不是 `mock-token-cs-001`。
- 同页 `fetch('/api/auth/me', Authorization: Bearer <同一令牌>)` → 200，`user.id=1`，`username=it-admin`。
- 路由进入 `/employee`。

证据：XHR/fetch 记录；截图 `03-employee-after-login.png`

---

## TC-05 同一账号三个入口 — PASS

预期：登录后同一会话分别打开员工端、客服工作台、知识库。

实际：

- `/employee`：顶栏「员工端」高亮；历史/对话壳可见。
- `/agent`：顶栏「客服工作台」高亮；待接入/处理中/关闭切卡；`GET /api/tickets?status=pending` 200。
- `/knowledge`：顶栏「知识库」高亮；上传区与已入库文档列表；`GET /api/documents` 200。文件选择器存在。

证据：截图 `03`/`04`/`05`。

范围外（不计入本任务判定）：员工会话标题、客服空态标题、知识库说明仍带存量 `[Mock]` 字样。这些标记不阻止进入三端外壳，T-009 说明为 out of scope。

---

## TC-06 未登录访问受保护路由 — PASS

预期：直接访问受保护路由回到登录，并有「请先登录」类提示。

实际：清 token 与 notice 后分别打开：

| 访问 | 最终 URL | 提示 | token |
| --- | --- | --- | --- |
| `/employee` | `/login` | 请先登录 | 无 |
| `/agent` | `/login` | 请先登录 | 无 |
| `/knowledge` | `/login` | 请先登录 | 无 |

登录页无 `[Mock]`。

证据：`t009-assets/07-login-anonymous-employee.png`；`/agent` 与 `/knowledge` 结果由 DOM `role=alert` 记录。

---

## TC-07 401 清 token 并关 WS — PASS

预期：受保护接口 401 时清 token、关 WS、回登录并提示「请先登录」。登录主路径 WS 使用真实通道（非 `MOCK_TOKEN` 的 MockAppSocket）。

实际：

- 在 `/agent` 挂钩 `window.WebSocket`：出现 `ws://127.0.0.1:5199/ws?access_token=[redacted]`，构造名 `WebSocket`（不是 MockAppSocket）。一条 `readyState=1`（OPEN）。
- 将 `access_token` 换成无效 JWT（仍不是 `mock-token-cs-001`），点击「处理中」。
- pagehide 探针：`GET /api/tickets?page=1&page_size=20&status=processing` **401**，`error=请先登录`；`tokenNow=absent`；两条 socket `readyState=3`（CLOSED）；close 日志含 `readyStateBefore=1`（从 OPEN 关闭）。
- 跳转后：URL `/login`，`localStorage.access_token=null`，`sessionStorage.auth_notice=请先登录`，错误条「请先登录」。

证据：`t009-assets/06-login-after-401.png`；sessionStorage `t009_ws_probe`（令牌已脱敏）。

---

## 规范抽检（本任务相关）

- 前端 API：单一 axios，`baseURL` 来自 `import.meta.env.VITE_API_BASE_URL || '/api'`，非硬编码后端 URL；401 在拦截器处理（登录 URL 除外）。`auth.ts` 仍经 service 调 `/auth/login`、`/auth/me`。
- 登录失败文案与 tech-spec §六 API-001 一致。坏 token / 未登录提示「请先登录」。
- `installAuthMocks` 为空操作；`main.tsx` 不再安装 auth mock。
- 端口：Agent 前端 5199 / 后端 8099，符合 env-policy。
- 报告未写入密码、完整 JWT、Key。

## 范围外

- 员工端/客服/知识库页面上的存量 `[Mock]` 文案（会话标题、空工单标题、上传说明）。不阻止进入三端，不作为 T-009 FAIL。
- 未验收提问、入库、转人工（T-010～T-012）。
- 未重跑 frontend type-check/lint/build。
- 未宣称整个项目交付完成，不请求 T-010。

## 经验

`.sdd/experience.md` 仅模板，无条目。本轮无待沉淀经验候选。
