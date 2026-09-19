# T-001 Tester 报告（首次验收）

- 任务：T-001 登录页、三端外壳与前端工程初始化
- 角色：Tester（非复验）
- 项目：`Projects_Repo/Customer_Service`
- 时间：2026-09-12
- 总结果：**PASS（前端阶段 / Mock）**
- 业务 AC：本任务 `acceptanceCriteria=[]`；AC-001、AC-002 由 T-009 真实验收，本报告不宣称业务闭环通过
- 规范集：default
- 模式：Mock（未启动后端 8099，未调用外部服务）

## 环境

- 复用已有 Vite：PID **96127** = `frontend/node_modules/.bin/vite --host 127.0.0.1 --port 5199`，cwd=`frontend/`
- HTTP：`http://127.0.0.1:5199/` → 200，title「智能客服系统」
- 验收结束时 5199 仍由 PID 96127 监听；未另起 5199，未杀 8765 原型服务
- 浏览器：Cursor `cursor-ide-browser`，独立标签 viewId `767a29`（未操作他人标签）
- 前端无 `.env`，以 `.env.example` 的 `VITE_API_BASE_URL=/api` 与代码回退 `/api` 生效
- 质量命令在 `frontend/` 重跑（未执行 npm install）

## 检查表

| ID | 场景 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- |
| TC-01 | 启动 / 代理 / 端口 | 5199 可访问；`VITE_API_BASE_URL=/api`；vite 代理 `/api` 与 `/ws`；业务代码不写死后端端口 | HTTP + 读配置 + 源码 | PASS |
| TC-02 | 未登录 / 错密 / 正确登录 | 受保护路由回 `/login`；错密错误条且不进三端；正确账号进员工端并见三端入口 | 浏览器真实操作 | PASS（Mock） |
| TC-03 | 顶栏互斥与视觉 | 同时只高亮当前端、只渲染当前页；刷新一致；对照 UI-01 / 配色字体顶栏错误条 / 原型 01-login | 点击切换 + 刷新 + 截图 + 计算样式 | PASS |
| TC-04 | Mock 集中与信封 | Mock 仅 `src/mocks/`；API-001/002/003 信封 + `[Mock]`；组件无直接 axios | 源码定向核对 | PASS |
| TC-05 | type-check / lint / build | 三命令退出码 0 | 在 frontend 重跑 | PASS |

后续责任：AC-001、AC-002 → T-009。

---

## TC-01 启动、环境变量与代理 — PASS

预期：frontend 可在 127.0.0.1:5199 启动；`VITE_API_BASE_URL=/api`；`vite.config.ts` 代理 `/api` 与 `/ws`；代码不写死后端端口。

实际：

- `curl http://127.0.0.1:5199/` HTTP 200，`<title>智能客服系统</title>`
- 监听进程 PID 96127，host `127.0.0.1:5199`，工作目录 `frontend/`
- `.env.example`：`VITE_API_BASE_URL=/api`，`VITE_WS_PATH=/ws`；代理目标仅出现在 `VITE_BACKEND_PROXY_TARGET`（允许）
- `vite.config.ts`：`server.proxy['/api']`、`server.proxy['/ws']`（`ws: true`），target 来自 env，默认 `http://localhost:8099`（规范允许出现在 vite 代理配置）
- `src/services/api.ts`：`baseURL: import.meta.env.VITE_API_BASE_URL || '/api'`，timeout 15000；`src/` 内无 `8099`/`8003` 硬编码

证据：进程/HTTP 记录；`frontend/vite.config.ts`、`frontend/.env.example`、`frontend/src/services/api.ts`。

---

## TC-02 鉴权路径（Mock）— PASS

预期：未登录访问 `/employee`、`/agent`、`knowledge` 回到 `/login`；错误密码 Mock 401 显示错误条且不进入三端；正确账号进入员工端并可看到顶栏三端入口。

实际（独立标签，先清 `localStorage.access_token` 再整页打开）：

1. 打开 `/employee` → URL 变为 `/login`，无顶栏，登录按钮 disabled（空表）
2. 打开 `/agent` → `/login`
3. 打开 `/knowledge` → `/login`
4. 输入用户名 `demo` + 错误密码并点击「登录」：仍停留 `/login`，无三端顶栏；错误条文案「账号无效或需要登录」（UI-01）；用户名保留；密码框 `field-error` 红框。Mock handler 对错误凭证返回 HTTP 401 / `UNAUTHORIZED`（`src/mocks/auth.ts`），页面按 401 展示错误条
5. 使用 Mock 账号 `demo` / `demo` 登录：跳转 `/employee`，heading「员工端」，顶栏导航「员工端 / 客服工作台 / 知识库」，token 已写入（仅确认 present，未记录值）

证据：浏览器 URL 与 snapshot；截图 `t001-login-empty.png`、`t001-login-error.png`、`t001-login-success-employee.png`；错误条计算样式 `background rgb(254,242,242)`、`color rgb(185,28,28)`。

未将此条记为 AC-001/AC-002 真实通过。

---

## TC-03 顶栏互斥、刷新与视觉 — PASS

预期：顶栏同一时刻只高亮当前端，只渲染当前页；刷新后地址、高亮与内容一致。对照 `docs/ui-style.md` UI-01、配色/字体/顶栏/错误条与原型 01-login。

实际：

- `/knowledge`：仅「知识库」为 `span.nav-item.active`（`aria-current=page`，Primary `#0F766E` + 底边 2px），员工端/客服为链接 Text-muted；仅一个 `<main>`「知识库」占位
- 点击「员工端」→ `/employee`，仅员工端高亮且不可再点自己，内容仅「员工端」
- 点击「客服工作台」→ `/agent`，仅该入口高亮，内容仅「客服工作台」
- 在 `/agent` 刷新：仍为 `/agent`，高亮与「客服工作台」占位一致

视觉取值（计算样式 vs ui-style / 原型 `:root`）：

| 项 | 实际 | 约定 |
| --- | --- | --- |
| Canvas | `rgb(241,245,249)` | `#F1F5F9` |
| Text | `rgb(15,23,42)` | `#0F172A` |
| 字体栈 | Source Han Sans SC / Noto Sans SC / PingFang SC | 同 |
| 正文 | 14px | 14px / 400 / 22px |
| 页标题 | 20px / 600 | UI-01 页面标题 |
| 顶栏 | 高 56px，白底，padding 0 24px | 顶栏 56px / Surface / 24px |
| 选中导航 | `rgb(15,118,110)` + 底边 2px / 600 | Primary + 底边 2px |
| 未选导航 | `rgb(100,116,139)` | Text-muted |
| 登录卡 | 居中 400px，圆角 8px，padding 24px，无顶栏 | UI-01 / 原型 |
| 主按钮 | 高 36px，圆角 6px；空表 Disabled `#94A3B8`；可提交 Primary | 主按钮 |
| 错误条 | 浅底 `#FEF2F2` + Error 字，位于标题下、字段上 | 错误条；原型 01-login |

登录页阅读顺序：标题 →（失败时）错误条 → 用户名 → 密码 → 登录 → `[Mock]` 演示说明。与原型 `docs/prototypes/01-login/index.html` 一致。占位三端未实现业务，不判 FAIL。

证据：截图 `t001-employee-header.png`、`t001-agent-header.png`、`t001-login-empty.png`、`t001-login-error.png`；CDP 计算样式；刷新后 snapshot。

---

## TC-04 Mock 位置、信封、无组件 axios — PASS

预期：Mock 数据仅在 `frontend/src/mocks/`；信封与 API-001/002/003 一致并带 `[Mock]`；组件内无直接 axios 调用。

实际：

- `src/mocks/` 仅 `auth.ts`、`bus.ts`
- 登录页/三端占位展示带 `[Mock]`；Mock 用户 `username` 为 `[Mock] demo`
- 信封字段：`success` / `data` / `error` / `error_code` / `message` / `timestamp` / `request_id` / `metadata`，成功 `message: "ok"`
- API-001 成功：`access_token`、`token_type: "bearer"`、`user.id` + `user.username`
- API-001 失败：401、`UNAUTHORIZED`、`error`「账号或密码不正确」、`data: null`
- API-002：200 返回 `{id, username}`；无 token → 401
- API-003：200 `{ logged_out: true }`
- axios 仅出现在 `services/api.ts`、`utils/apiError.ts`、`mocks/auth.ts`；页面/顶栏经 `useAuth` / `services/auth.ts`，无组件内 `axios.get/post`

证据：`frontend/src/mocks/auth.ts`、`frontend/src/types/api.ts`、`frontend/src/services/auth.ts`、对 `frontend/src` 的 axios 检索。

---

## TC-05 type-check / lint / build — PASS

在 `Projects_Repo/Customer_Service/frontend` 重跑（未 npm install）：

```
npm run type-check   # tsc -b --noEmit    退出码 0
npm run lint         # eslint .           退出码 0
npm run build        # tsc -b && vite build  退出码 0；vite v6.4.3 built in 437ms
```

`package.json` 含上述脚本；eslint 含 `eslint-plugin-react-hooks`。

---

## 业务 AC

| AC | 本任务 | 责任任务 |
| --- | --- | --- |
| AC-001 | 未验收（frontend Mock 阶段） | T-009 |
| AC-002 | 未验收（frontend Mock 阶段） | T-009 |

## 未验项

- 真实 POST `/api/auth/login`、GET `/api/auth/me`、后端 JWT（T-009）
- 三端占位页的业务功能（后续前端任务）
- 用户门禁端口 5175 / 后端 8003（T-004 门禁）
- 退出按钮 UI（API-003 Mock 已实现，本任务 TC 未要求页面退出入口）
- 百炼 Key：missing，本任务不需要

## 范围外

- 无退出入口不影响本任务判定
- 无 `frontend/.env`：开发以 example + 代码回退 `/api` 运行，不构成本任务 FAIL

## 5199 归属

验收结束时 **仍由 PID 96127** 提供。
