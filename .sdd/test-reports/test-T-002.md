# T-002 Tester 报告（首次验收）

- 任务：T-002 员工端对话、历史列表与转人工 Mock
- 角色：Tester（非复验）
- 项目：`Projects_Repo/Customer_Service`
- 时间：2026-09-12
- 总结果：**PASS（前端阶段 / Mock）**
- 业务 AC：本任务 `acceptanceCriteria=[]`；关联 AC-003、AC-004、AC-006、AC-008～AC-011、AC-016～AC-018、AC-023 由 T-010/T-011/T-012 真实验收，本报告不宣称真实问答或真实转人工闭环通过
- 规范集：default
- 模式：Mock（未调用百炼，未走真实 API-010/017）

## 环境

- 复用已有 Vite：PID **96127** 监听 `127.0.0.1:5199`；`curl /employee` HTTP 200。未杀进程，未 `npm install`
- 预览：`http://127.0.0.1:5199/employee`
- 浏览器：Cursor `cursor-ide-browser` 独立标签 viewId `937bba`（未点知识库验收标签 `6f8e6a` / `9451ca` / `628e23` / 原型 `36be9f`）
- Mock 内存按标签隔离；本标签自有 seed 会话，未依赖知识库验收的入库数据
- 登录态沿用本机已有 demo 会话进入员工端；发送均为真实输入 + 点击「发送」
- 前端门禁在 T-004，不阻塞本验收

## 检查表

| ID | 场景 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- |
| TC-01 | 新建会话、发送、来源与 §三文案 | 员工气泡立即出现；系统先来源再逐字；FAQ/闲聊/知识问答/兜底/无法回答均带来源且文案符合常量 | 浏览器真实发送 + DOM 帧采样 | PASS（Mock） |
| TC-02 | 转人工横幅、无工单状态、禁用、bus | 横幅「正在等待人工客服」；无 pending/processing/closed；等待中禁用转人工；bus 发 transfer 相关事件 | 点击转人工 + 页面效果 + mocks 源码 | PASS（Mock） |
| TC-03 | 历史、回看、钉底滚动 | 最近在上；打开一条见完整助手句与来源；中途离开再进见完整一条；输入钉底，消息区单独滚动 | 列表切换 + 布局测量 + 中途离开 | PASS（Mock） |
| TC-04 | 无上传检索、UI-02、Mock 信封 | 员工端无上传/检索；对照 UI-02/来源色/等待横幅/原型 02-employee；[Mock] 对齐 API-007～011、API-017 | 页面 DOM + 计算样式 + 源码 | PASS（Mock） |
| TC-05 | 不轮询，只走 Mock SSE | 无 2 秒轮询；自动回复 `Accept: text/event-stream` 打开 API-017 Mock | fetch 记录 + 源码；无 setInterval | PASS（Mock） |

后续责任：AC-006 → T-010；AC-003、AC-004、AC-016～AC-018、AC-023 → T-011；AC-008～AC-011 → T-012。

`prefers-reduced-motion` 抽检：emulate `reduce` 后闲聊先出「闲聊」标签（正文长度 0），约 762ms 后整段出现，无 1…n 中间长度。属 UI-02/风格动效，计入 TC-01/TC-04 抽检，不单列 AC。

客服接入后横幅改「人工客服处理中」属 T-004，未因此 FAIL。

---

## TC-01 新建会话、发送、来源与 §三常量 — PASS（Mock）

预期：新建会话、发送后员工气泡立即出现、系统先来源标签再逐字正文；FAQ/闲聊/知识问答/兜底/无法回答均带来源且文案符合 `docs/tech-spec.md` §三。

实际（独立标签，点「新会话」后逐条真实输入发送）：

| 输入 | 来源标签 | 正文 | SSE |
| --- | --- | --- | --- |
| 连不上公司VPN，提示认证失败 | FAQ | `先检查账号是否锁定，再重试连接公司 VPN。` | `/api/conversations/2/assistant-stream?after_user_message_id=3`，`Accept: text/event-stream` |
| 今天天气真好 | 闲聊 | `你好，我是内部智能客服，有 IT 问题可以直接问我。` | `after_user_message_id=5` |
| 打印机驱动怎么安装 | 知识问答 | `连接公司 VPN 前请确认网络正常，并使用公司下发的配置文件。` | `after_user_message_id=7` |
| 我那张工单办到哪了 | 知识问答 | `当前问题超出知识服务范围，你可以点击转人工。`（`OUT_OF_SCOPE_TEXT`） | 页面完成句与常量一致 |
| 没见过的系统怎么处理 | 知识问答 | `现有知识无法回答。你可以点击转人工。`（`NO_KNOWLEDGE_TEXT`） | `after_user_message_id=11` |

流式证据（FAQ，MutationObserver 去重帧）：空消息区 → 员工句已在 + 助手 `FAQ` + 正文由「先」逐字增至 22 字全文。闲聊同样 `闲聊` 标签下长度 1→26。未稳定截到「仅来源、正文为空」的中间帧（meta 与首个 delta 同批）；首帧已带来源，其后逐字增长。员工句在助手未完成时已存在。

减弱动效：`Emulation.setEmulatedMedia prefers-reduced-motion=reduce` 后发送「早上好」：dt 9ms 来源「闲聊」len=0，dt 762ms 一次变为 26 字全文，中间无 1…n。

证据：独立标签操作记录；截图 `t002-faq-result.png`；§三常量 `frontend/src/types/enums.ts`。

未将此条记为 AC-003/004/016/017/023 真实通过。

---

## TC-02 转人工横幅、禁用与 bus — PASS（Mock）

预期：转人工后等待横幅，不展示 pending/processing/closed；等待/处理中禁用转人工；经 bus 发出 transfer 相关事件。

实际：

- 点击「转人工」后横幅文案「正在等待人工客服」，计算样式 `color rgb(180,83,9)`（Wait `#B45309`），底 `rgb(255,251,235)`
- 消息区另有 `role=system` 句「正在等待人工客服」，`source=null`，无 FAQ/闲聊/知识问答标记
- 页面正文不含 `pending` / `processing` / `closed` / 「待接入」/「处理中」/「关闭」
- 「转人工」`disabled=true`，截图中按钮为 Disabled 灰
- `frontend/src/mocks/conversations.ts` 成功转人工后 `publish`：`ticket.created`、`handoff.changed`（`waiting`）、`message.created`（等待句）；HTTP 响应仅 `handoff_state` + `wait_message`，不返回工单 id/状态
- 处理中禁用：`Composer` 在 `handoffState === 'in_progress'` 同样 `disabled`；本任务无法接入客服，未实测处理中横幅（T-004）

证据：截图 `t002-wait-banner.png`；`WaitBanner.tsx`、`Composer.tsx`、`mocks/conversations.ts` transfer 分支。

未将此条记为 AC-008/012 真实通过。

---

## TC-03 历史、回看、布局 — PASS（Mock）

预期：历史最近在上；打开一条可见完整助手句与来源；中途离开再进入当前会话见完整一条。输入区钉底，消息区单独滚动。

实际：

- 列表自上而下：当前会话 → 更早会话；新建后「[Mock] 新会话」置顶；发送后标题改为首问截断
- 打开 seed「VPN 提示认证失败怎么办」：完整员工句 + 助手 FAQ + 全文，无工单状态
- 发送「打印机驱动怎么安装」后立即切到 seed 会话，再切回：回看含完整「知识问答」句 `连接公司 VPN 前请确认网络正常，并使用公司下发的配置文件。`
- 布局：`.messages` `flex:1; overflow:auto; min-height:0`；composer `top=668, bottom=755`（视口 755），`composerAfterMessages=true`；有等待横幅时输入仍钉在底部（截图）

中途离开瞬间（约 42ms）seed 会话 DOM 曾短暂叠上对会话的流式「知识问答 / 连接」碎片，结算后打开历史已干净。不作为本 TC FAIL。

证据：历史 DOM 顺序；回看气泡列表；布局 getBoundingClientRect。

---

## TC-04 无上传检索、UI-02、Mock 信封 — PASS（Mock）

预期：员工端无上传/检索知识入口。对照 UI-02、来源标签色、等待横幅与原型 02-employee。Mock 带 `[Mock]` 且信封对齐 API-007～011、API-017。

实际：

- 无 `input[type=file]` / `.upload`；无可点击「上传」「检索」入口；顶栏可去知识库但不在员工页提供入库/检索
- 布局：左历史 280px 量到 240px（窄视口 651）、右对话；顶栏「员工端」`nav-item active`；输入钉底；转人工次按钮 + 发送主按钮。与 UI-02 / 原型 02-employee 一致
- 来源色：FAQ `rgb(29,78,216)` + `rgba(29,78,216,0.12)`；闲聊 `rgb(124,58,237)` + `rgba(124,58,237,0.12)`；知识问答 `rgb(15,118,110)` + `rgba(15,118,110,0.12)`，与 ui-style / 原型 `:root` 一致
- 历史行与标题带可见 `[Mock]`
- Mock 集中在 `frontend/src/mocks/conversations.ts`；页面走 `services/conversations.ts`，组件内无 axios
- 信封：`success/data/error/error_code/message/timestamp/request_id/metadata`；列表含 `pagination`；`toSummary`/`toDetail` 显式 DTO，Detail 无 `ticket_status`；API-010 `assistant_message: null` + `stream`；API-017 先 `meta.source` 再 `delta.text` 再 `done.assistant_message`

证据：页面查询；`t002-faq-result.png`、`t002-wait-banner.png`；`mocks/conversations.ts`、`services/conversations.ts`、`types/dto.ts`。

---

## TC-05 不实现 2 秒轮询；自动回复只走 Mock SSE — PASS（Mock）

预期：不实现 2 秒轮询会话；自动回复只走 Mock SSE（D-001 方案 B）。

实际：

- `EmployeePage.tsx` / `components/chat/*` / `services/conversations.ts` 无 `setInterval`，无对 API-009 的定时刷新
- 本标签拦截到的 `window.fetch` 均为 `/api/conversations/{id}/assistant-stream?after_user_message_id=…` 且 `Accept: text/event-stream`
- 本标签未记录 1500–3000ms 的会话轮询 `setTimeout`；Mock SSE 内部仅用 28ms 逐字间隔
- `openAssistantStream` 使用 `fetch` + `getReader()` 解析 `event: meta|delta|done`

证据：fetch 日志；`services/conversations.ts` `openAssistantStream`；`mocks/conversations.ts` `mockAssistantStream`。

---

## 范围外（不计入判定）

- 流式过程中瞬间切换历史，可能闪过对会话的未完成助手碎片；结算后回看正常
- 知识库页、客服接入后「人工客服处理中」、真实百炼问答均非本任务
- 未重跑 type-check/lint/build（T-002 technicalChecks 未列；Developer 口头通过未沿用为证据）

## 判定

全部 TC-01～TC-05 通过 → **PASS（前端阶段 / Mock）**。
5199 PID：**96127**。
