# T-003 Tester 报告（首次验收，非复验）

- 任务：T-003 「知识库管理端上传、进度回看与结果 Mock」
- 角色：Tester
- 时间：2026-09-12
- 总结果：**PASS（前端阶段 / Mock）**
- 类型：`frontend`；`acceptanceCriteria=[]`；业务 AC 不在本任务宣称通过
- 后续责任：AC-005 / AC-006 / AC-007 / AC-019 / AC-020 / AC-021 / AC-024 → T-010 / T-011
- 环境：`http://127.0.0.1:5199` Mock；Vite **仍为 PID 96127**（`127.0.0.1:5199` LISTEN）；未杀进程、未另起、未 npm install；未用后端 8099
- 浏览器：独立标签 `viewId=f0f597`；未操作既有员工端标签 `6f8e6a` / `9451ca` / `628e23`
- 登录：沿用已有 demo 会话（打开 `/login` 已落到已登录员工端，再进知识库）
- 判定口径：仅 Mock 行为；不得当作真实入库 / 检索 / 提问通过

## 检查表

| ID | 场景 / 输入 | 动作 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- | --- |
| TC-01 | 支持格式 `.md` | 选文件提交 → 立即看列表 → 切员工端再回知识库 | 立即「排队中」；回来见处理中或已生效/失败；已生效无确认按钮 | 真实 File + input change；SPA 切 `/employee` 再回 `/knowledge` | PASS |
| TC-02a | `unsupported.xlsx` | 选不支持格式 | 当场「不支持该格式」；列表不新增 | 真实 File + input change | PASS |
| TC-02b | `空文件.txt`（0 字节） | 提交后离开再回 | 失败项详情只显示原因；无分块/FAQ | 同上 + 离开再回 | PASS |
| TC-02c | 已生效详情 | 查看对象/诉求标签 | 中文名，不出现 hardware / network 等 code | 页面 innerText + 截图 | PASS |
| TC-03 | UI-03 / 原型 03-knowledge / Mock API | 对照布局、状态点、上传区、[Mock]、DTO | 上传在上且不随列表消失；状态点配色；Mock 对齐 API-004/005/006 与 document.* | 截图 + 计算样式 + 调 Mock 信封 | PASS |
| TC-04 | 在页停留 / 进页 | 看 Axios 调用与 setInterval | 无短轮询列表；进页快照 + 事件 | 包装 axios / setInterval | PASS |

## 实际操作（独立实测，未沿用 Developer 口头结论）

1. 打开独立标签 `http://127.0.0.1:5199/login` → 已登录落到员工端 → 点「知识库」。空态：上传区 +「还没有文档，请上传。」
2. 通过隐藏 `input[type=file]` 放入真实 `File` 并 `change`（与「上传文档」同一选择器路径；未用 CDP Input.*）：
   - `VPN认证失败.md`：80ms 内列表「排队中」，详情「排队中 0%」
   - 切员工端（只离开，不操作对话）再回：文档仍在，「已生效」，无「确认入库」
   - `打印机离线.md`：立即「排队中」；立刻切员工端约 2.2s 再回：列表「处理中 25%」，详情「处理中 25%」
   - 稍后同页变为「已生效」，上传区仍在
3. `unsupported.xlsx`：错误条「不支持该格式」；列表仍 2 条，无 POST `/documents`
4. `空文件.txt`：立即「排队中」；切员工端再回：列表「失败」，详情仅文件名 +「无法提取正文，文档未入库」，无分块/FAQ/确认按钮
5. 空闲 3s：无 `GET /documents` 列表调用，无 `setInterval`

## TC 证据

### TC-01 PASS

- 提交后立即：`listText=VPN认证失败.md / 排队中`，`detail=排队中 0%`，`bodyHasConfirm=false`；随后 POST `/api/documents` + GET `/api/documents/1`（选中详情，非列表轮询）
- 离开再回已生效：中文标签「网络与远程接入」「故障与异常排查」；文案「入库成功立即生效，无需再确认。[Mock]」；无「确认入库」
- 第二份在途离开再回：`打印机离线.md` 列表「处理中 25%」
- 截图：`t003-queued` 因 Mock ~5.8s 完成，截帧已是已生效；排队中/处理中以 CDP 文本为准。已生效截图：`t003-after-leave-and-return.png`、`t003-processing-after-return.png`（截帧时已转已生效）

### TC-02 PASS

- xlsx：`errorText=不支持该格式`；`beforeCount=afterCount=2`；错误条 Error `#B91C1C` / 浅红底；截图 `t003-xlsx-format-error.png`
- 页面预校验不打 API；另用 `uploadDocument(probe.xlsx)` 探 Mock：HTTP **400**，`VALIDATION_ERROR`，`error=不支持该格式，请上传 PDF、Word（.docx）、Markdown 或 txt`，`data=null`，列表条数不变（对齐 API-004）
- 失败项：详情 HTML 仅 `h2` + `error-bar`；`hasChunksHeading=false`；`hasFaqHeading=false`；截图 `t003-failed-empty-file.png`
- 标签：页面无 `\bhardware\b` / `\bnetwork\b`；展示「网络与远程接入」「故障与异常排查」。API 内部仍为 `object_types: ["network"]`（契约 code），界面已映射中文

### TC-03 PASS

- 布局对照 UI-03 / 原型：顶栏「知识库」高亮；上区上传；下列表 | 详情；空态与原型一致
- 上传区不随列表消失：有文档时仍见「上传文档」；`uploadStillAboveSplit=true`，上传高 69px（< 120px）
- 状态点：Success `rgb(21,128,61)`=#15803D 8px；Warning `rgb(180,83,9)`=#B45309；Error `rgb(185,28,28)`=#B91C1C；选中行 `::before` 3px Primary `#0F766E`
- 主按钮：高 36px、圆角 6px、Primary；`:hover/:active/:focus-visible/:disabled` 在全局 `.btn-primary` 已覆盖
- `[Mock]`：上传提示、分块、FAQ、成功说明均带
- Mock 信封：list 含 `success/data/error/error_code/message/timestamp/request_id/metadata/pagination`；`DocumentSummary` 字段与 §三 DTO 一致；详情 `ready` 含 chunks/faqs，`failed` 含 `error_message`、空 chunks/faqs
- 侧栏实测 240px（窄视口媒体查询，与原型 1280 以下收为 240px 一致）；非精确 40%/60% 百分比，结构与原型 `.side`+`.split` 一致，不另判 FAIL

### TC-04 PASS

- `KnowledgePage` 进页 `listDocuments()` 一次快照 + `subscribe` `document.progress|ready|failed`；卸载退订。无 `setInterval` 拉列表
- 实测：`window.__t003_intervals=[]`；在页空闲 2s/3s 无额外 `GET /documents`
- 第一份上传到 ready：仅 POST `/documents`、GET `/documents/1`（选中）、再 GET `/documents/1`（`document.ready` 后拉详情）。中间无列表 GET
- 离开再进：`GET /documents` 快照（开发态 Strict Mode 同毫秒双调用，不是短轮询）+ GET 当前详情
- Mock 后台用 `setTimeout` 发布 `document.progress` / `document.ready` / `document.failed`，不是列表轮询主通道

## 业务 AC（本任务不验收）

| AC | 本任务 | 后续 |
| --- | --- | --- |
| AC-005 / 019 / 021 / 024 | 仅 Mock 回看与无确认按钮；未做真实入库/提问 | T-010/T-011 |
| AC-006 | 未验员工端无上传入口 | T-010 |
| AC-007 / 020 | 仅 Mock 格式拒绝与失败回看 | T-010 |

百炼 `missing`：本任务 `externalServices=[]`，不阻塞 Mock 验收。

## 范围外

- 员工端对话/HMR：切走时可见员工页已有会话 UI；未操作、未当 T-003 缺陷。占位员工端未完成不是本任务 FAIL。
- 未重跑 type-check/lint/build（不在 T-003 technicalChecks；用户行为已独立实测）。

## 5199 进程

验收结束时：**PID 96127 仍在**，`vite --host 127.0.0.1 --port 5199`。
