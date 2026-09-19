# T-004 Tester 报告（本轮独立验收）

- 任务：T-004 「客服工作台 Mock 与四页整体收口」
- 角色：Tester
- 时间：2026-09-18
- 总结果：**PASS（前端阶段 / Mock）**
- 类型：`frontend`；`acceptanceCriteria=[]`；**不把 Mock 行为记为业务 AC 通过**
- 后续责任：AC-008～AC-015 → T-012
- 门禁：**需交用户验收 Mock 与填写 backend/.env 的 llm_api_key、llm_base_url、llm_chat_model、llm_embed_model**
- 预览：`http://127.0.0.1:5199`
- 派发：`gate_phase=frontend_in_progress`，`gate_task_id=T-004`；`in_flight_or_queued=["T-004","T-007"]`。未请求 T-009。
- 规范集：`default`

## 环境

- Mock 前端：`http://127.0.0.1:5199`。本轮 `lsof` 见 `node` **81572** LISTEN `127.0.0.1:5199`（派发记录 PID 81545；未杀、未另起、未 npm install）。
- 未打后端 8099；请求走 Axios Mock 适配器，未见 Vite 代理失败。
- 浏览器：新标签 `viewId=dbd21f`。未操作 `f35eff` / `0bf819` / `26a122` 及既有 `f4f6bb` / `ea5eb7`。
- 登录：表单填写 demo 账号后进入员工端。跨页只用顶栏，未整页刷新（清会话后的未登录探测除外）。
- 不记录口令或 token。

## 检查表

| ID | 场景 / 输入 | 动作 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- | --- |
| TC-01 | 客服：转人工后待接入立即出现；不接入保持；接入→处理中；回复后员工见无来源客服气泡；关闭后不能再回。对照 UI-04 | 顶栏员工↔客服 | 见预期 | 浏览器主路径 | PASS（Mock） |
| TC-02 | 跨页：登录→FAQ/闲聊/知识问答/兜底→转人工→接入回复立即可见；知识库顶栏离开再回；未登录不能进三端 | 顶栏 SPA | 见预期 | 浏览器 | PASS（Mock） |
| TC-03 | 中文工单状态只在客服端；员工只见等待文案；输入钉底；Mock API-012～016 / API-018 | 页面 + Mock 探针 | 见预期 | 浏览器 + 页面内 Mock 调用 | PASS（Mock） |
| TC-04 | 四页视觉 + 1280 导航/输入可用 | 截图 + 计算样式 | ui-style 配色/字阶/圆角/来源色 | 浏览器 | PASS |
| TC-05 | type-check / lint / build | 本轮不重跑 3 分钟 npm | 抽检 Developer 自述与脚本存在 | 抽检 | PASS（抽检） |

## 实际操作（独立实测）

1. 新开 `http://127.0.0.1:5199/login`，清会话后落到登录页。填写 demo 账号，点「登录」→ `/employee`。点「新会话」。
2. 同会话四类 Mock 回复（真实输入 + 点发送）：
   - 「VPN 提示认证失败怎么办」→ **FAQ**「先检查账号是否锁定，再重试连接公司 VPN。」
   - 「今天天气真好」→ **闲聊**
   - 「打印机怎么连接共享」→ **知识问答**
   - 「红烧肉怎么做」→ **知识问答** + 超范围「当前问题超出知识服务范围，你可以点击转人工。」
3. 点「转人工」：员工横幅「正在等待人工客服」，「转人工」禁用；页面无工单切卡「待接入/处理中/关闭」。
4. 顶栏「客服工作台」：待接入立即出现 `[Mock] VPN 提示认证失败怎么办` + 中文「待接入」。切「处理中」为空（「这个状态下没有工单。」），再回「待接入」该单仍在（不接入保持）。
5. 点工单见转人工前上下文，点「接入」→ 标题「处理中」，出现回复框。回复「我帮你看一下账号锁定情况。」
6. 顶栏回员工端（不刷新）：灰气泡该句，旁无 FAQ/闲聊/知识问答；横幅「人工客服处理中」。
7. 顶栏回客服「处理中」→「关闭」：状态「关闭」；回复区消失。Mock `replyTicket` 409「不能回复」，再 `closeTicket` 409「已关闭」。
8. 再回员工：无等待横幅（历史里仅系统气泡「正在等待人工客服」）；「转人工」重新可用。
9. 知识库：上传区 +「还没有文档，请上传。」顶栏去员工端再回知识库，空列表与上传入口仍在。本轮 File 注入被自动化策略拒绝，**未新提交文档**。
10. 视口 1280×800：顶栏可切员工/客服/知识库。更窄约 628 宽时员工输入仍钉底（textarea `bottom=635` / `vh=647`）。
11. 清会话后 `history` 探 `/employee` `/knowledge` `/agent`：均落到 `/login`，无三端导航。

## TC 证据

### TC-01 PASS（Mock）

- 转人工后客服待接入立即出现；处理中切卡无该单，待接入保持。
- 接入后中文「处理中」，可回复。
- 员工立刻见客服灰气泡「我帮你看一下账号锁定情况。」，无三种来源标记；横幅「人工客服处理中」。截图 `t004-employee.png`。
- 关闭后客服标题「· 关闭」；界面无「回复员工」；Mock 409 不能再回。对照 UI-04。

### TC-02 PASS（Mock）

- 登录进入员工端；未登录三端均回登录页（无顶栏）。
- FAQ / 闲聊 / 知识问答 / 兜底同一 SPA 会话走通。
- 转人工→接入回复→顶栏回员工立即可见。
- 知识库顶栏离开再回：空列表与「上传文档」+ `[Mock]` 提示保持。截图 `t004-knowledge.png`。本轮未新提交文件看进度（File 控件自动化被拒，非产品缺陷）。

### TC-03 PASS（Mock）

- 客服端工单状态中文「待接入 / 处理中 / 关闭」，未见把 `queued` 写到界面。
- 员工只见「正在等待人工客服」或「人工客服处理中」，无工单切卡。关闭后横幅消失。
- 输入钉底：员工 textarea 在视口内；客服处理中「回复员工」在底栏。
- 页面内 Mock（关闭单）：
  - API-012 列表信封含 `success/data/error/error_code/message/timestamp/request_id/metadata` + `pagination`；`TicketSummary` 键 `id, conversation_id, status, title, preview, created_at`
  - API-013 详情另含 `messages, accepted_at, closed_at`；客服消息 `role=agent`、`source=null`
  - API-015 对已关闭 409 `CONFLICT`「不能回复」
  - API-016 再关 409 `CONFLICT`「已关闭」
  - API-014/018：主路径接入/回复即时可见，对应 Mock `ticket.*` / `message.created` / `handoff.changed`；`mocks/ws.ts` 路径 `/ws`

### TC-04 PASS

- 登录：无顶栏；卡片宽 400px、Surface 白底；标题 20px；空表主按钮高 36px、圆角 6px、Disabled `rgb(148,163,184)`。截图 `t004-login.png`。
- 知识库：顶栏「知识库」Primary 底边；「上传文档」主按钮 teal。截图 `t004-knowledge.png`。
- 员工：来源「知识问答」浅底；客服气泡灰、无来源三种标记；输入钉底。截图 `t004-employee.png`。
- 客服 1280×800：顶栏「客服工作台」高亮；切卡「待接入 / 处理中 / 关闭」可用。截图 `t004-agent-1280.png`。
- 约 628 宽时三端导航与输入仍可用，未被挤出视口。

### TC-05 PASS（抽检）

本轮按派发要求**未**先跑完整 `npm run type-check` / `lint` / `build`。

- Developer `41b84c76` 自验记录：type-check / lint / build 通过（任务 notes）。
- `frontend/package.json` 现有脚本：`type-check` = `tsc -b --noEmit`；`lint` = `eslint .`；`build` = `tsc -b && vite build`；依赖含 `eslint-plugin-react-hooks`。
- T-001 Tester 曾实测三命令退出码 0。本轮未重跑，故标 **抽检**。

## 业务 AC（本任务不验收）

| AC | 本任务 | 后续 |
| --- | --- | --- |
| AC-008～AC-015 | 仅 Mock 工作台与跨页收口 | T-012 真实联调 |

## 范围外 / 未当作缺陷

- 本轮未能把真实 `File` 写入知识库选择器（自动化策略拦截），故未再验提交后排队中/已生效。T-003 已验该 Mock 入库回看；本任务收口验证的是顶栏离开再回。
- 未宣称真实 WebSocket、真实工单持久化、多用户或百炼。
- 百炼配置 `missing`：本任务 `externalServices=[]`，不阻塞 Mock 验收；**用户门禁仍须填写 llm_***。

## 交回编排器

- 任务：**T-004**
- 总结果：**PASS（前端阶段 / Mock）**
- AC：无（空数组）；AC-008～015 在 T-012，本任务不通过它们
- 技术检查：TC-01～TC-04 PASS；TC-05 PASS（抽检）
- **需交用户验收 Mock 与填写 backend/.env 的 llm_api_key、llm_base_url、llm_chat_model、llm_embed_model**
- 预览：`http://127.0.0.1:5199`
- 报告：`/Users/kxy/cursor/class_projects/Develop_Helper/Projects_Repo/Customer_Service/.sdd/test-reports/test-T-004.md`
- Tester 未改 `.sdd/tasks.json`、PRD、方案或业务代码；未代用户确认门禁；未请求 T-009
