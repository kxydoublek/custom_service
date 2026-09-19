# T-012 Tester 报告（首次独立验收）

- 任务：T-012 转人工、客服工作台与历史会话真实联调
- 角色：Tester（独立验收，不采信 Developer 自验）
- 项目：`/Users/kxy/cursor/class_projects/Develop_Helper/Projects_Repo/Customer_Service`
- 时间：2026-09-19
- 总结果：**PASS**
- 业务 AC：AC-008 **PASS**；AC-009 **PASS**；AC-010 **PASS**；AC-011 **PASS**；AC-012 **PASS**；AC-013 **PASS**；AC-014 **PASS**；AC-015 **PASS**
- source_feature：F-004（REQ-004、REQ-005、REQ-006）
- type：integration；execution_mode：automatic；user_gate：passed；specification：default
- 依赖：T-008 / T-009 / T-011 均为 `passed`。`LLM_API_KEY` 非空；AC-014 用真实 SSE，不是 Mock。
- 派发：`python3 /Users/kxy/cursor/class_projects/Develop_Helper/scripts/sdd_dispatch.py --tasks .../Customer_Service/.sdd/tasks.json --running-task T-012` → `gate_phase=passed`，`gate_task_id=T-004`，`in_flight_or_queued=["T-012"]`，`errors=[]`。任务 status=testing。未开始 T-013。
- 浏览器：独立新标签 `viewId=b82816`（`/employee`）与 `viewId=44bfc7`（`/agent`），同一 `it-admin` 登录，与 Developer 会话隔离。本轮自建会话 **38 / 39 / 40**、工单 **2 / 3**。不把 Developer 会话 37 / 工单 1 当成本轮证据。
- 未改业务代码、`.sdd/tasks.json`、`.sdd/experience.md`、方案/规范；未 commit/push；未清空 `backend/data/Customer_Service.db`；未杀 5199 / 8099。
- 密钥：本报告不写 `INTERNAL_PASSWORD`、JWT、`LLM_API_KEY`。配置状态：`INTERNAL_USERNAME=it-admin`；`WAIT_HUMAN_TEXT=正在等待人工客服`；`LLM_API_KEY` 已配置（非空）。

## 环境

- 前端：`http://127.0.0.1:5199`，node PID **81572**。`GET /` 200。未再起 5199。
- 后端：`http://127.0.0.1:8099`，uvicorn PID **90461**（PPID 90438）。`GET /health` 200。库路径 `backend/data/Customer_Service.db`。未杀该进程。
- 登录：员工/客服两标签恢复为已登录 `it-admin`，令牌不是 `MOCK_TOKEN`。页面无 `[Mock]` 前缀。
- 实时通道：`ws://127.0.0.1:5199/ws?access_token=***`（已脱敏）。不是 `mocks/bus`。
- 本轮数据：会话 38=`T012A-1906…`（未转人工）；会话 39 + 工单 2=`T012B-1906…`（待接入，未接入）；会话 40 + 工单 3=`T012C-1906…`（接入→回复→关闭→恢复 FAQ）。

## 检查表

| ID | 场景 / 输入 | 动作 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- | --- |
| TC-01 | 新会话自动回复，不点转人工 | 会话 38 发送「T012A-1906 今天天气真好，随便聊聊」 | 保持自动回复（闲聊）；客服待接入列表不出现新工单 | 独立两端浏览器 + SSE 捕获 | PASS |
| TC-02 | 自动回复中点转人工 | 会话 39 FAQ 后点「转人工」 | 员工横幅「正在等待人工客服」；客服待接入立即出现工单及 FAQ 上下文，无需刷新 | 两端对照 + WS 帧 | PASS |
| TC-03 | 转人工立即建待接入单；员工不见工单状态 | 同上 | 工单 2 `pending`；员工主区无「待接入/处理中/关闭」 | 客服列表/标题 vs 员工 `.main` / `.wait-banner` | PASS |
| TC-04 | 待接入期间客服不接入 | 工单 2 保持不点接入；随后跑完会话 40 再回看 | 工单 2 仍待接入；员工横幅仍「正在等待人工客服」；转人工按钮禁用 | 客服待接入列表 + 再打开会话 39 | PASS |
| TC-05 | 两端走通转人工→接入→回复立即可见 | 会话 40 转人工建工单 3；客服接入并回复「T012C-AGENT …」 | 员工横幅改「人工客服处理中」；客服句立即出现且无 FAQ/闲聊/知识问答标记 | 两端对照 + WS `ticket.accepted` / `message.created` | PASS |
| TC-06 | 处理中员工继续发消息 | 会话 40 发送「T012C-EMP 处理中继续提问，不要走自动回复」 | 只进人工对话；无 FAQ/闲聊/AI 新回复；客服端立刻看到该员工句 | 员工气泡 + 2.5s 观察 + 客服 transcript + 无新 SSE | PASS |
| TC-07 | 关闭工单后不能再回；员工恢复自动回复 | 客服关闭工单 3；再 POST 回复；员工再问 FAQ 原问 | 工单关闭；再回复 HTTP 409 `CONFLICT`；真实 SSE `meta→delta→done`，`source=faq` | 浏览器关闭 + fetch 409 + SSE 捕获 | PASS |
| TC-08 | 曾发起会话后打开历史 | 离开会话 40 到 38，再打开 40 | 历史列表可见；打开后看到当时 FAQ 来源、等待句、客服句（无来源三种标记）及关闭后 FAQ | 员工历史侧栏 + 重开 DOM | PASS |
| TC-09 | 事件来自真实 WebSocket 而非 2s/3s 轮询 | 全程捕获 `/ws?access_token=` 帧与 `/api/tickets` XHR | `ticket.created/accepted/closed`、`message.created`、`handoff.changed` 来自 WS；工单列表 GET 只在切 Tab/快照，间隔约 70s+，不是 2s/3s 轮询 | 页面拦截 WS/XHR | PASS |
| TC-10 | 员工无工单状态机文案；历史来源保留 | 会话 39/40 主区与重开 | 员工不见待接入/处理中/关闭；自动回复保留 FAQ/闲聊标记；客服句无来源芯片 | DOM `.wait-banner` / `.source` / `.bubble.agent` | PASS |
| TC-11 | 关闭后再回复 409 | `POST /api/tickets/3/messages` | HTTP 409，`error_code=CONFLICT`，`error=不能回复`；关闭页无回复输入框 | fetch + 客服关闭 Tab | PASS |

---

## AC-008 自动回复中点转人工 → 等待 + 客服立即见待接入 — PASS

预期：员工看到「正在等待人工客服」；客服工作台立即出现对应待接入工单及对话上下文，无需手动刷新。

实际：

- 会话 **39** 先 FAQ 自动回复「先确认账号未被锁定，可在门户重置密码。」，再点「转人工」。
- 员工 `.wait-banner` = `正在等待人工客服`。
- 客服待接入立即插入 `T012B-1906 VPN认证失败时，第一步应该做什么？ 待接入`；详情气泡含用户问、FAQ 答、系统等待句。
- WS（员工/客服两端同时收到）：`ticket.created` ticket_id=2 conversation_id=39 → `handoff.changed` waiting → `message.created` role=system content=正在等待人工客服 source=null。
- 客服在 `ticket.created` 后只 `GET /api/tickets/2` 拉详情，**没有** `GET /api/tickets?status=pending` 作为到达通道。

证据：会话 39 / 工单 2；WS 帧 t≈1789772189817–2189827；客服 DOM 列表行。

---

## AC-009 未点转人工 → 保持自动回复、不出现新工单 — PASS

预期：仅与系统多轮对话时保持自动回复链路，客服工作台不出现新工单。

实际：

- 会话 **38** 发送「T012A-1906 今天天气真好，随便聊聊」。
- 员工来源「闲聊」；SSE `/api/conversations/38/assistant-stream?after_user_message_id=102`：`meta source=small_talk` → 若干 `delta` → `done`，`handoff_state=none`。
- 发完后客服待接入仍为「这个状态下没有工单。」列表行空。之后新建的工单 2/3 标题均为 T012B/T012C，与会话 38 无关。
- 无等待横幅。无 `[Mock]`。

证据：会话 38 消息气泡与 SSE 捕获；客服待接入空态（转人工之前）。

---

## AC-010 处理中员工再发只进人工；客服句立即可见且无来源三种标记 — PASS

预期：处理中员工继续发送不出现 FAQ/闲聊/AI 新回复；客服发出的消息立即出现在员工端，不带来源三种标记。

实际：

- 工单 3 接入后，客服发送「T012C-AGENT 我帮你看一下账号锁定情况。」
- 员工立即出现 `.bubble.agent`，无 `.source`。WS `message.created` conversation_id=40 role=agent source=null。
- 员工再发「T012C-EMP 处理中继续提问，不要走自动回复」。2.5s 后气泡仍只有原 FAQ 一条带「FAQ」标记；无新闲聊/知识问答/FAQ。会话 40 在处理中没有新的 assistant-stream（仅关闭前那条 FAQ 流 `after_user_message_id=107`）。
- 客服端同一条员工句经 WS `message.created` role=user 立即追加。

证据：会话 40 气泡顺序；WS message id 110（agent）、111（user）。

---

## AC-011 历史列表并能打开看到当时内容与来源 — PASS

预期：能看到会话列表并打开一条，看到当时问答、来源标记，以及转人工后的客服回复。

实际：

- 历史侧栏可见本轮 `T012C` / `T012B` / `T012A`。
- 切到会话 38 再打开会话 40：FAQ 两条均保留「FAQ」来源；系统句「正在等待人工客服」无来源；客服句 `T012C-AGENT …` 为 `.bubble.agent` 且 `agentNoSource=true`；关闭后 FAQ 原问回复仍带来源。
- 列表 `preview` 不含工单状态枚举。

证据：员工历史 DOM；会话 40 重开气泡 7 条。

---

## AC-012 一点转人工即待接入工单；员工不展示工单状态 — PASS

预期：立即产生待接入工单，客服立即可见；员工界面不展示待接入/处理中/关闭。

实际：

- 工单 2、3 均在点击转人工当毫秒经 `ticket.created` 插入待接入。工单 3 插入时客服 **没有** 再拉 pending 列表（该次 `GET .../tickets?status=pending` 发生在约 70s 后手动切 Tab）。
- 员工主区：无「待接入」「关闭」；等待只用横幅「正在等待人工客服」。`.wait-banner` 存在时「转人工」disabled=true。
- 客服标题/列表使用中文「待接入」。

证据：WS ticket_id=2/3；员工 `.main` 文本检查；客服列表文案。

---

## AC-013 接入后处理中，员工马上看到客服回复而不再只是等待 — PASS

预期：待接入 → 接入后处理中；员工马上看到客服回复，不必刷新。

实际：

- 客服对工单 3 点「接入」。员工 WS：`ticket.accepted` ticket_id=3 conversation_id=40 → `handoff.changed` in_progress。横幅立刻变为「人工客服处理中」，无刷新。
- 客服回复后员工马上出现客服灰气泡（见 AC-010），不再只显示等待句。
- 客服头「… · 处理中」，Tab 切到「处理中」。`GET /tickets?status=processing` 是接入后快照，不是轮询主通道。

证据：WS t≈1789772337696–2337697；员工横幅与客服句。

---

## AC-014 关闭后该单不能再回；同一会话恢复真实自动回复 — PASS

预期：工单变为关闭且不能再发客服回复；员工端该会话可再次进入 FAQ/闲聊/知识问答（真实 SSE）。

实际：

- 客服关闭工单 3：WS `ticket.closed` + `handoff.changed` none。客服头「… · 关闭」；关闭态无回复输入框。
- `POST /api/tickets/3/messages`（关闭后再回）→ HTTP **409**，`success=false`，`error_code=CONFLICT`，`error=不能回复`。
- 员工横幅消失，「转人工」重新可用。同一会话 40 再问「VPN认证失败时，第一步应该做什么？」：
  - 真实 SSE `/api/conversations/40/assistant-stream?after_user_message_id=112`
  - 事件顺序 **meta → delta → delta → done**
  - `meta.source=faq`，`handoff_state=none`
  - `done.assistant_message.source=faq`，正文「先确认账号未被锁定，可在门户重置密码。」
- 不是 Mock 流，不是 bus。本轮 AC-014 走 FAQ 规范化命中，**未进入分类路径**，因此未核验经验「分类同时标闲聊与超范围类状态时优先走同一兜底」。

证据：工单 3 关闭帧；409 JSON；SSE 捕获 latest n=4。

---

## AC-015 待接入不接入则保持待接入与等待文案 — PASS

预期：客服不接入则工单保持待接入，员工持续「正在等待人工客服」。

实际：

- 工单 2 / 会话 39 全程未点接入。跑完工单 3 的接入/关闭后，客服「待接入」仍只有 `T012B-1906 … 待接入`。
- 再打开会话 39：`.wait-banner=正在等待人工客服`；转人工 disabled；主区无待接入/关闭标签。

证据：客服 pending 列表；会话 39 重开 DOM。

---

## 技术检查

1. **真实 WebSocket 而非轮询（TC-09）— PASS**  
   客服拦截到 `/ws?access_token=***`。事件计数：`ticket.created=2`，`ticket.accepted=1`，`ticket.closed=1`，`message.created=4`，`handoff.changed=4`（另有 ping）。列表 GET 仅 3 次且对应切到处理中 / 关闭 / 待接入，间隔 78720ms、71418ms，不是 2s/3s 主通道。工单 3 进入待接入列表时没有 pending 列表 GET。

2. **员工无工单状态机文案；历史来源（TC-10）— PASS**  
   员工主区不展示「待接入/处理中/关闭」。自动回复保留 FAQ / 闲聊来源；客服句无三种来源芯片。

3. **关闭后再回复 409（TC-11）— PASS**  
   见 AC-014。

4. **Developer 改动核对（定位，非以源码代替产品）**  
   `EmployeePage.tsx` 用 `connectRealtime` 处理 `handoff.changed` / `message.created`。`AgentPage.tsx` 在 `ticket.created` 立即插入 pending；`[Mock]` 仅 `isMockSession()`。`ws.ts` 每标签共享 socket、按 token 复用。`tickets.ts` / mocks 对真实 JWT passthrough。本轮页面无 `[Mock]`。`ticket.py` 本任务宣称未改；行为与 T-008 状态机及本轮 API/WS 一致。

---

## 规范核对（本任务 rules_files）

- 前端验收：真实闭环用实际页面动作；Mock 与真实分开。本轮真实 JWT，无 Mock 主路径。
- 后端信封：关闭后再回复 409 + `CONFLICT`，与 api-design 错误码表及 tech-spec API-015/016 一致。
- 安全：报告未写密钥/JWT；WS URL 已脱敏 `access_token=***`。

## 范围外 / 未宣称

- 未验收 T-013 交付导航，也未宣称整个项目完成。
- Tester 侧用 urllib 直连 `POST /api/auth/login` 曾遇连接断开/503；浏览器登录恢复成功，不计入产品缺陷。
- 截图工具超时，本报告以 DOM / WS / SSE / HTTP 为准。
- 经验候选未在本轮 AC-014 路径触发，不核验、不落盘。

## 交回编排器

- 任务 ID：T-012
- 总结果：**PASS**
- 请编排器更新任务状态；不要由 Tester 改 `tasks.json`。不调度 T-013。
