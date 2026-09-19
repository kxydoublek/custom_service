# 工作日志

由编排器记录关键进展、验证证据、用户确认和阻塞原因。任务运行状态以 `.sdd/tasks.json` 为准，日志不维护第二份任务清单。

## 2026-09-12

- 项目已创建，进入需求对齐。用户确认：内部员工咨询；AI 先答、员工点击转人工后坐席接入；知识预先生入库；本次含登录、多轮问答、知识库、历史会话、工单。
- 已写入 `docs/PRD.md`（Draft）。待确认：AI 答不上时的提示、坐席工作台与排队、工单与转人工关系、入库权限与文档形态、登录方式、转人工后 AI 是否停止。
- 用户确认：答不上只提示转人工；同一网页客服工作台，未接入时员工见等待；点转人工即建工单，客服决定是否接入，员工不可见工单状态；管理员端入库 PDF/Word/Markdown/txt，员工只能提问用到知识；转人工后仅客服回复；不做多用户账号体系，一个内部账号进出三端。
- PRD 已按上述更新，待用户整体确认。工单状态为待接入 / 处理中 / 关闭；关闭后会话恢复 AI 问答。
- 用户确认需求定稿。`docs/PRD.md` 已标为 Confirmed。已派发 Solution Designer 编写七层技术方案，实例 ID：`1cb601c8-e967-41b7-a30a-4e1357adfccc`。输入：已确认 PRD；输出：`docs/tech-spec.md`（Draft）及必要时 `docs/decisions.md`。
- 用户撤回定稿：知识入库需展开（分块、按 IT 标签体系打标、写入向量检索库、提取 FAQ）；提问先 FAQ 拦截，再闲聊或按标签缩小召回后问答。PRD 改回 Draft；已中断同一 Solution Designer 实例，不继续按旧 PRD 写技术方案。
- [七层方案设计](1cb601c8-e967-41b7-a30a-4e1357adfccc) 已停止，执行结果：未写入 `docs/tech-spec.md`、`docs/decisions.md`，也未改 PRD。需求仍为 Draft，待用户确认追问/实时数据/超范围、入库生效方式、FAQ 拦截粒度、回复来源是否标明后再定稿。
- 用户确认：信息不足、超范围、实时工单/工具场景统一超范围兜底；入库标签与 FAQ 立即生效；FAQ 相近也拦截；回复标明 FAQ / 闲聊 / 知识问答。PRD 已更新，仍为 Draft，待整体定稿。
- 用户要求完整时序图，参与者为员工端、知识库页面、系统、客服端。已用一张覆盖登录、入库、提问、转人工与关单的时序图替换原先拆开的两张。
- 用户确认需求定稿。`docs/PRD.md` 已标为 Confirmed。已派发 Solution Designer，实例 ID：`1212e367-02b3-48b3-8b78-61149b54dc62`。输入：已确认 PRD 与 `docs/tag-taxonomy.json`；输出：`docs/tech-spec.md`（Draft）及必要时 `docs/decisions.md`。
- [七层方案设计](1212e367-02b3-48b3-8b78-61149b54dc62) 已交回 Draft：`docs/tech-spec.md`、`docs/decisions.md`（D-001～D-003 待确认）；PRD 仅细化时序图。待用户确认等待方式、模型/FAQ 松紧、数据留存后再整体确认技术方案。百炼密钥缺失只影响真实问答联调。
- 用户确认：D-001 方案 B（入库异步，可离开/切界面，提问流式，人工消息即时）；D-002 方案 A；D-003 方案 A。已将选择回传同一 Solution Designer 实例 `1212e367-02b3-48b3-8b78-61149b54dc62` 回写方案。
- [七层方案设计](1212e367-02b3-48b3-8b78-61149b54dc62) 已按确认回写：`docs/decisions.md` 三项为已确认；`docs/tech-spec.md` 改为异步入库/SSE/WebSocket（新增 API-017、API-018）；PRD 仅同步受影响 AC，仍为 Confirmed。技术方案仍 Draft，待用户总确认。百炼密钥只影响真实问答联调。
- 用户确认技术方案定稿。`docs/tech-spec.md` 已标 Confirmed。进入阶段 B：已写 `docs/ui-style.md`（Draft）并交付四页可操作原型；浏览器已走登录画面、员工问答/转人工、客服接入回复、知识库详情。待用户合并确认风格与原型。
- 用户确认风格与原型并要求下一步。`docs/ui-style.md` 已标 Confirmed。首次规划前待用户选择推进模式（automatic / step_by_step）。
- 用户选择逐步模式 `step_by_step`。已派发 Planner，实例 ID：`75f919fa-1042-4b53-bbcd-1878233d1e6a`。输入：已确认 PRD / tech-spec / ui-style；输出：`.sdd/tasks.json`。
- [任务规划](75f919fa-1042-4b53-bbcd-1878233d1e6a) 已写入 `.sdd/tasks.json`（T-001～T-013，user_gate=T-004，交付=T-013）。`sdd_dispatch.py` 通过。已派 T-001 Developer `385eaee6-e4bc-46ad-add7-9944b0957f15`，step_gate 指向 T-001。
- [登录与三端外壳](385eaee6-e4bc-46ad-add7-9944b0957f15) 被用户中止。T-001 改回 pending；`frontend/` 有未完成源码，依赖安装未完，未自验。不自动续派。
- 用户确认进入开发并要求 T-001 从头重做（上次 npm 过慢）。未整目录删除 `frontend/`。已派 [登录与三端外壳](a258aa6a-baad-4b32-8ea9-f61f2ef6a2f2)，step_gate 仍为 T-001。
- [登录与三端外壳](a258aa6a-baad-4b32-8ea9-f61f2ef6a2f2) 交回 T-001 自验（非 Tester）。源码与 lint/build 自称通过。`http://127.0.0.1:5199` 现由 PID 96127 提供。T-001 置 testing，派 [登录与外壳验收](609f5b48-004b-45d0-8175-a98c1f79900b)。Harness 根残留无关 `package.json`/`package-lock.json` 未清理。
- [登录与外壳验收](609f5b48-004b-45d0-8175-a98c1f79900b) 判定 T-001 PASS（前端阶段 / Mock），TC-01～TC-05 通过。T-001 置 passed，step_gate=awaiting_user。证据 `.sdd/test-reports/test-T-001.md`。未开 T-002。
- 用户将推进模式从 `step_by_step` 切到 `automatic`。已保存原门禁：T-001 awaiting_user、无 user_confirmation；不伪造 passed。切换解除逐步等待，不授权 Git 提交。
- 已并行派发：[员工端对话 Mock](ed7adfcd-2979-4077-aba1-cdbfc73c0800) T-002、[知识库入库 Mock](2fed9317-2671-4b13-a6cb-732f2cc4e5b4) T-003、[后端鉴权工程](051cc622-a0ed-43bb-8311-fe7ad338d3cf) T-005。写入范围不重叠。T-004 等前序前端完成。
- 用户要求暂停。已停止新派发，并中断上述三个进行中实例。T-001 仍为 passed。模式保持 automatic。未授权 Git。继续时再说一声即可。
- 三实例已停下：[员工端对话 Mock](ed7adfcd-2979-4077-aba1-cdbfc73c0800) T-002 尚未改代码；[知识库入库 Mock](2fed9317-2671-4b13-a6cb-732f2cc4e5b4) T-003 源码已写未自验；[后端鉴权工程](051cc622-a0ed-43bb-8311-fe7ad338d3cf) T-005 写到库层，鉴权路由与测试未做。均改回 pending，不交 Tester。
- 用户要求继续。已恢复同一批实例：T-002 实现员工端；T-003 补自验不重写；T-005 补路由/测试/venv。模式 automatic。
- [知识库入库 Mock](2fed9317-2671-4b13-a6cb-732f2cc4e5b4) 交回 T-003 自验。T-003 置 testing，派 [知识库入库验收](cafc7d4c-738e-4207-8b6c-44eba18b891d)。T-002/T-005 仍在开发。
- [员工端对话 Mock](ed7adfcd-2979-4077-aba1-cdbfc73c0800) 交回 T-002 自验。T-002 置 testing，派 [员工端对话验收](9327e6a3-6855-4592-a576-c3325ac35cdc)。T-005 仍在开发。
- [知识库入库验收](cafc7d4c-738e-4207-8b6c-44eba18b891d) 判定 T-003 PASS（前端阶段 / Mock），TC-01～TC-04 通过。证据 `.sdd/test-reports/test-T-003.md`。T-004 仍等 T-002。
- [员工端对话验收](9327e6a3-6855-4592-a576-c3325ac35cdc) 判定 T-002 PASS（前端阶段 / Mock），TC-01～TC-05 通过。证据 `.sdd/test-reports/test-T-002.md`。T-001～T-003 前端前置齐，T-004 解锁。write_scope 增补 `frontend/src/mocks/conversations.ts`。未宣称真实问答通过。
- 已派 [客服工作台 Mock](41b84c76-79cb-4567-aa00-138c58c745ee) T-004。user_gate 仍 pending。复用 5199 / PID 96127。
- [后端鉴权验收](2e440c7b-41df-4960-8d85-126e252c3c28) 判定 T-005 PASS（后端阶段 / 接口契约），TC-01～TC-05 通过。证据 `.sdd/test-reports/test-T-005.md`。AC-001/AC-002 在 T-009。8099 已停。
- 已派 [知识入库后台实现](95f51102-9a5d-4ea7-866b-b1b1fd5f2c31) T-006。无 Key 走 Mock 提供商。未宣称真实打标/向量通过。
- [客服工作台 Mock](41b84c76-79cb-4567-aa00-138c58c745ee) 交回 T-004 自验。T-004 置 testing，派 [客服工作台 Mock 验收](e6d12ada-935d-4319-9e2d-935308725af9)。user_gate 仍 pending。未宣称 AC-008～015。复用 5199 / PID 96127。
- [知识入库后台实现](95f51102-9a5d-4ea7-866b-b1b1fd5f2c31) 交回 T-006 自验（Mock 入库/WS，pytest 20 passed）。T-006 置 testing，派 [知识入库接口验收](f96c07f5-d80d-4669-a959-17720bb7ca9c)。T-004 仍在验收。未宣称真实打标/向量通过。
- [知识入库接口验收](f96c07f5-d80d-4669-a959-17720bb7ca9c) 判定 T-006 PASS（后端阶段 / Mock 入库），TC-01～TC-05 通过。证据 `.sdd/test-reports/test-T-006.md`。
- [客服工作台 Mock 验收](e6d12ada-935d-4319-9e2d-935308725af9) PING timed out，无报告、无判定。T-004 保持 testing。
- 用户要求继续。已重派 [客服工作台 Mock 复验](15350690-2b78-44e0-80d8-f256015d5f22) T-004（上次超时无结论）。已派 [会话流式回复实现](fadb5d15-baa2-4065-8209-ba1bd998bbb1) T-007。Vite 已重启 `http://127.0.0.1:5199` PID 81545。user_gate 仍 pending。未开 T-009。
- [客服工作台 Mock 复验](15350690-2b78-44e0-80d8-f256015d5f22) 再次 PING timed out，无报告。已再派 [客服工作台第三次验收](45e99d62-417e-4cfe-b125-c1c2762b7211)。T-004 保持 testing。
- [会话流式回复实现](fadb5d15-baa2-4065-8209-ba1bd998bbb1) pytest 已 31 passed，返回前被取消；已 resume 补交自验。
- [会话编排接口验收](c923b0dd-1f1e-44ff-a947-187968484a5d) 判定 T-007 PASS（后端阶段 / Mock 编排），TC-01～TC-05 通过。证据 `.sdd/test-reports/test-T-007.md`。不等于 T-011。
- [转人工工单状态机](108139f1-20a6-47e3-8dd5-83cf7ac44b66) 交回 T-008 自验（pytest 37 passed）。T-008 置 testing，派 [工单状态机接口验收](35a8c0f7-5559-4dbb-8e36-9b1cb917ee35)。未宣称 AC-008～015。
- T-004 第三次 Tester 无输出，视为终止。已再派 [客服工作台第四次验收](2949b75b-1a51-4008-935f-9bbc743d9313)。user_gate 仍 pending。未开 T-009。
- [客服工作台 Mock 再验](9ece816b-00ec-44ce-8f7d-8855652f1d0f) 判定 T-004 PASS（前端阶段 / Mock），TC-01～TC-05 通过。证据 `.sdd/test-reports/test-T-004.md`。user_gate=awaiting_user。停止新派发；T-008 Tester 可收尾。未开 T-009。
- [工单状态机接口验收](35a8c0f7-5559-4dbb-8e36-9b1cb917ee35) 判定 T-008 PASS（后端阶段 / 工单状态机），TC-01～TC-05 通过。证据 `.sdd/test-reports/test-T-008.md`。不等于 T-012。user_gate 仍 awaiting_user，未开 T-009。

## 2026-09-18

- 已从 `backend/.env.example` 生成本地 `backend/.env`（git 忽略，不入库）。
- 用户明确认可前端 Mock 界面。核对 `backend/.env`（不记录配置值）：`LLM_BASE_URL` / `LLM_CHAT_MODEL` / `LLM_EMBED_MODEL` / `LLM_EMBED_DIMENSIONS` 非空；`LLM_API_KEY` 为空；`SECRET_KEY`、`INTERNAL_PASSWORD` 仍为示例占位。user_gate 保持 awaiting_user，百炼服务状态仍 missing，未开 T-009。未宣称真实百炼连通。
- 用户再次确认已填写配置。再核 `backend/.env`：`llm_api_key` 及模型相关键均非空，JWT/内部密码已非占位。user_gate=passed，百炼 Chat/Embedding 顶层 status=confirmed（仅配置齐备，未验证连通）。已按当前配置更新本地种子用户密码哈希，未清空库。已派 [登录真实联调](4783c162-4b9b-4a28-a48a-fcc624780a34) 实现 T-009。
- [登录真实联调](4783c162-4b9b-4a28-a48a-fcc624780a34) 交回 T-009 自验（非 Tester）：关登录 Mock，真实 API-001/002；错密「账号或密码不正确」；未登录「请先登录」。复用 Vite 5199 / uvicorn 8099。T-009 置 testing，派 [登录联调验收](6ce1a739-9a75-4ea8-a2fd-791a1d95efca)。未开 T-010。未宣称百炼连通。
- [登录联调验收](6ce1a739-9a75-4ea8-a2fd-791a1d95efca) 判定 T-009 PASS。证据 `.sdd/test-reports/test-T-009.md`。AC-001/AC-002 通过。已派 [知识入库联调](168f447e-07e2-47bf-a873-b071f680e51c) 实现 T-010。未宣称入库/问答通过。
- [知识入库联调](168f447e-07e2-47bf-a873-b071f680e51c) 交回 T-010 自验（非 Tester）：知识页真实 WS；四格式入库；自称真实百炼。后端现为 uvicorn PID 46453。T-010 置 testing，派 [知识入库验收](8d3e3f9d-6419-40e2-839b-e18b11cb0e44)。未开 T-011。
- [知识入库验收](8d3e3f9d-6419-40e2-839b-e18b11cb0e44) 判定 T-010 PASS。证据 `.sdd/test-reports/test-T-010.md`。真实入库与立刻 FAQ 命中已验。已派 [提问链路联调](48e64b88-3712-4d84-98cb-bbe4bfa4095f) 实现 T-011。未宣称 FAQ/闲聊/召回/兜底验收通过。
- [提问链路联调](48e64b88-3712-4d84-98cb-bbe4bfa4095f) 交回 T-011 自验（非 Tester）。后端现为 uvicorn PID 90461。T-011 置 testing，派 [提问链路验收](61a68ed9-2dc5-451a-97eb-ab1dbec6455b)。未开 T-012。分类双标闲聊短路已在 qa.py 自修，待 Tester 复核后再决定是否写入经验。
- [提问链路验收](61a68ed9-2dc5-451a-97eb-ab1dbec6455b) 判定 T-011 PASS。证据 `.sdd/test-reports/test-T-011.md`。已沉淀经验「分类同时标闲聊与超范围类状态时优先走同一兜底」。已派 [转人工联调](c8c18ab9-ee12-4572-bbf1-b60f064ca558) 实现 T-012。未宣称工单联调通过。
- [转人工联调](c8c18ab9-ee12-4572-bbf1-b60f064ca558) 交回 T-012 自验（非 Tester）。员工端真实 WS。T-012 置 testing，派 [转人工验收](bcb24c39-5f48-43ff-b936-5767e5bae612)。未开 T-013。
- [转人工验收](bcb24c39-5f48-43ff-b936-5767e5bae612) 判定 T-012 PASS。证据 `.sdd/test-reports/test-T-012.md`。已派 [页面功能导航](8665012e-2a88-4a60-8a7e-8561774d3af6) 实现 T-013。未宣称整轮交付完成。
- [页面功能导航](8665012e-2a88-4a60-8a7e-8561774d3af6) 交回 T-013 自验（非 Tester）。T-013 置 testing，派 [导航页验收](45d06abe-ed53-4425-b0f1-13edce8931a9)。未宣称整轮完成。
- [导航页验收](45d06abe-ed53-4425-b0f1-13edce8931a9) 判定 T-013 PASS。证据 `.sdd/test-reports/test-T-013.md`。T-001～T-013 均 passed。本轮开发任务结束。未授权 Git 提交。
