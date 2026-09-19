# T-005 Tester 报告（首次验收）

- 任务：T-005 后端鉴权、内部账号与工程初始化
- 角色：Tester（非复验）
- 项目：`Projects_Repo/Customer_Service`
- 时间：2026-09-12
- 总结果：**PASS（后端阶段 / 接口契约）**
- 业务 AC：本任务 `acceptanceCriteria=[]`；AC-001、AC-002 由 T-009 在页面验收，本报告不宣称页面登录通过
- 规范集：default
- 派发：`sdd_dispatch.py --running-task T-004 --running-task T-005` → `gate_phase=frontend_in_progress`，`errors=[]`，T-005 为 testing；非 integration/delivery，已开验

## 环境

- Python：`python3.11` 不在 PATH；项目 `.venv` 存在，解释器 **3.12.13**（满足 3.11+）。系统 `python3` 为 3.14.7，未用于本轮命令。
- 启动（Tester 自启，已停）：`cd backend && PYTHONPATH=.. .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8099`
- 该命令 **可以启动**（uvicorn PID 95075，日志 `Application startup complete`）。Developer 称仅 `PYTHONPATH=..` 找不到 `src`；本轮在 `backend/` 工作目录下 `PYTHONPATH=..` 可导入并监听 8099，**未**需要补 `backend` 到 PYTHONPATH。
- 方案字面 `python3.11` 不可用，实际用 `.venv` 的 3.12.13。
- `backend/.env` **不存在**。启动回退 `backend/.env.example`（占位，不等于已填密钥）。活 HTTP 成功登录未对业务库发正确账号；成功路径用隔离 TestClient（`TEST_USERNAME=it-admin` / 测试夹具密码）。
- pytest：项目根 `.venv/bin/python -m pytest backend/tests --timeout=120` → **11 passed**（3.69s），`pytest-timeout` 2.4.0。
- SQLite 业务库仍在 `backend/data/Customer_Service.db`（未清空）；pytest / TestClient 走临时库。
- 未操作前端，未杀 Vite PID **96127**，未改 5199。验收结束时 **8099 已停**；5199 仍由 96127 监听。

## 检查表

| ID | 场景 | 预期 | 方法 | 结果 |
| --- | --- | --- | --- | --- |
| TC-01 | Python 3.11+、`.venv`、按方案启动 8099 | 探测 3.11+ 且存在项目 `.venv`；`cd backend && PYTHONPATH=.. … uvicorn … :8099` 能启动 | 版本探测 + 真实启动 | PASS（3.12.13；`PYTHONPATH=..` 可用） |
| TC-02 | POST `/api/auth/login` | 正确账号 200，`access_token` / `token_type=bearer` / `user`；错密与未知用户 401 `UNAUTHORIZED`，`error` 均为「账号或密码不正确」 | TestClient + 活 HTTP 401 | PASS |
| TC-03 | GET `/api/auth/me`、POST `/api/auth/logout` | 无 Token / 坏 Token → 401；有效 Token → `id`/`username`；logout → `logged_out=true` | TestClient + 活 HTTP 401/logout | PASS |
| TC-04 | SQLite 路径、配置不读进程环境、httpx | 相对路径解析绝对路径并建父目录，落 `backend/data/Customer_Service.db`；`use_env=False`；无 `os.environ`；httpx 若出现须 `trust_env=False` | 源码 + 启动日志 + 文件存在 | PASS |
| TC-05 | pytest 覆盖登录成功/失败/未授权 | 项目根 `pytest backend/tests --timeout=120` | 独立重跑 | PASS |

后续责任：AC-001、AC-002 → T-009。本任务不接百炼。

---

## TC-01 解释器、venv 与启动 — PASS

预期：存在 Python 3.11+ 与项目 `.venv`；按方案从 `backend/` 用 `PYTHONPATH=..` 启动 uvicorn 于 `127.0.0.1:8099`。

实际：

- `python3.11 --version`：command not found
- `.venv/bin/python --version`：Python 3.12.13；`.venv` 目录存在
- 启动前 8099 空闲；`cd backend && PYTHONPATH=.. .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8099` 成功
- 日志：`应用已装配 | host=127.0.0.1 port=8099`；引擎路径解析为  
  `/Users/kxy/cursor/class_projects/Develop_Helper/Projects_Repo/Customer_Service/backend/data/Customer_Service.db`；`内部账号已存在，跳过种子`；`Uvicorn running on http://127.0.0.1:8099`
- 与 Developer 自述不一致处：本轮 **不必** 把 `backend` 补进 PYTHONPATH。`pyproject.toml` 的 pytest `pythonpath = [".", "backend"]` 只影响测试收集，不影响上述启动命令。

证据：进程 95075 监听；终端启动日志；验收结束已 `kill` 95075/95069，8099 不再监听。

---

## TC-02 登录契约 — PASS

预期：正确账号 200，data 含 `access_token`、`token_type=bearer`、`user.id`/`user.username`；错误密码 401 `UNAUTHORIZED`，`error` 为「账号或密码不正确」，不区分哪一项。

实际（隔离 TestClient + 临时库，lifespan 建表并种子）：

- POST `/api/auth/login` 正确测试账号 → HTTP 200，`success=true`，`token_type=bearer`，`access_token` 非空（仅记录 present），`user.username=it-admin`，`user.id` 为 int；信封含 `success/data/error/error_code/message/timestamp/request_id/metadata`
- 错误密码 → HTTP 401，`error_code=UNAUTHORIZED`，`error=账号或密码不正确`，`data=null`
- 未知用户 → 同一 401 文案与错误码（不区分账号或密码）

活 HTTP `127.0.0.1:8099`（未使用 `.env.example` 占位当正确账号）：

- 未知用户/错密 → HTTP 401，同样信封与「账号或密码不正确」

未对业务库发正确密码，故不宣称活实例种子密码已验证；接口成功路径由 TestClient 覆盖。

证据：Tester 独立 TestClient 输出；curl 活 8099 401 响应。pytest `test_login_success` / `test_login_wrong_password` / `test_login_unknown_user_same_message` 同向。

---

## TC-03 当前登录与退出 — PASS

预期：无 Token 或坏 Token 的 GET `/api/auth/me` 为 401；有效 Token 返回 `id`/`username`；POST `/api/auth/logout` 返回 `logged_out=true`（可无 Token）。

实际：

- TestClient：无 Token / `Bearer not-a-valid-token` → 401 `UNAUTHORIZED`，`error=请先登录`；有效 Token → 200，`data.id` int、`data.username=it-admin`
- TestClient：无 Token 与带 Token 的 POST `/api/auth/logout` 均为 200，`data.logged_out=true`
- 活 8099 curl：GET `/api/auth/me` 无 Token 与坏 Token → 401 `请先登录` / `UNAUTHORIZED`；POST `/api/auth/logout` → 200 `logged_out=true`

证据：TestClient 脱敏信封；curl 活实例响应。对应 pytest `test_me_*` / `test_logout_*`。

---

## TC-04 SQLite、配置与 httpx — PASS

预期：SQLite 落 `backend/data/Customer_Service.db`（相对路径先解析绝对路径并建父目录）；配置不读 `os.environ`；httpx 若出现必须 `trust_env=False`。

实际：

- `resolve_sqlite_path`：相对路径相对 `backend/` 解析，`mkdir(parents=True, exist_ok=True)`；启动日志绝对路径与文件名均符合
- 磁盘：`backend/data/Customer_Service.db` 存在；`users` 表存在（未 dump 账号值）；验收后文件仍在
- `load_app_config()` 调用 `ConfigManager.load(..., use_env=False)`；PyCore `use_env=True` 会报错
- `backend/src` 与 `backend/tests` 无 `os.environ` / `os.getenv` / `httpx`（本任务无百炼客户端）。Starlette TestClient 弃用警告提到 httpx，属测试依赖，不是应用 HTTP 客户端
- pytest `test_sqlite_relative_path_resolves_under_backend`、`test_config_load_ignores_process_env` 通过
- CORS 默认四 origin（5199/5175 的 localhost 与 127.0.0.1）写入 `AppSettings` 并交给 `APIServer`

证据：`backend/src/db/session.py`、`backend/src/config/settings.py`、`pycore/core/config.py` load；启动日志；grep 无 `os.environ`/`httpx`。

---

## TC-05 pytest — PASS

命令（项目根，复用 `.venv`，未全局重装）：

```
.venv/bin/python -m pytest backend/tests --timeout=120 -v
```

结果：11 passed，1 warning（TestClient/httpx 弃用）。覆盖登录成功/失败/未知用户同文案、缺字段 400、未授权 me、坏 Token、有效 Token、logout、SQLite 路径、配置忽略进程环境。

---

## 判定

全部 technicalChecks 通过 → **PASS（后端阶段 / 接口契约）**。不等于 AC-001/AC-002 页面通过。

## 范围外（不计入本任务判定）

- GET `/` 与 `/docs` 在本轮 8099 上为 404（方案未要求本任务提供文档页）
- `backend/.env` 缺失；活实例用 `.env.example` 回退启动。后续 T-009 联调需有真实本地 `.env`
- urllib 直连 8099 曾 `RemoteDisconnected`；同端口 curl 正常，判定以 curl / TestClient 为准
- 未验页面登录、未接百炼、未改 5199

## 交回编排器

- 任务 ID：T-005
- 总结果：PASS（后端阶段 / 接口契约）
- 逐 TC：TC-01～TC-05 均为 PASS
- 报告：`/Users/kxy/cursor/class_projects/Develop_Helper/Projects_Repo/Customer_Service/.sdd/test-reports/test-T-005.md`
- 启动命令：`cd backend && PYTHONPATH=.. .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8099`
- **8099 已停**。不请求下一任务。
