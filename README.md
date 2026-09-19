# SDD 项目

本项目由 SDD Harness 管理。身份、项目类型和规范选择见 `.sdd/project.json`。

- `docs/PRD.md`：需求、业务规则和验收标准。
- `docs/tech-spec.md`：技术方案、接口与数据约定。
- `.sdd/tasks.json`：任务和运行状态，由编排器维护。
- `docs/ui-style.md`：有界面时的设计风格，由 UI Skill 生成并供实现、验收引用。
- `docs/prototypes/`：可选界面设计。
- `.sdd/`：阶段摘要、工作日志、经验与验证报告。

`specification` 为集合名称时按需读取该集合，为 `null` 时不加载规范集。核心工作规则位于 Harness 根目录；本项目 `AGENTS.md` 提供轻量入口。

## 页面功能导航

打开 `docs/project-console.html`（本机双击，或用浏览器打开该文件路径）。左侧按页面，右侧是功能卡片；接口、算法、来源按需展开。不是旧的六区管理看板。

刷新（在项目根目录）：

```bash
python3 scripts/refresh-project-console.py
```

脚本用 `docs/project-map.json` 生成 HTML，并核对本页列出的源码指纹。源文件变了但未重读算法时，对应项会标「来源已变化待复核」，不会继续标「源码已核对」。首次写入空指纹可用 `--record-fingerprints`（只补空指纹，不把过期指纹改成已核对）。隔离样例（过期指纹 / 缺失文件 / 坏 JSON）写入临时目录，不覆盖正式页：

```bash
python3 scripts/refresh-project-console.py --isolation-sample /tmp/cs-console-iso
```

## 本地运行（不写密钥）

前端开发端口 **5199**，Vite 把 `/api` 和 `/ws` 代理到后端 **8099**（见 `frontend/vite.config.ts`，目标来自 `frontend/.env.example` 的 `VITE_BACKEND_PROXY_TARGET`，默认 `http://localhost:8099`）。

- 前端：在 `frontend/` 执行 `npm run dev`（`server.port` 已为 5199）。
- 后端：在 `backend/` 将 `PYTHONPATH` 指到项目根后启动 `uvicorn src.main:app --host 127.0.0.1 --port 8099`。
- 前端请求前缀见 `frontend/.env.example` 字段 `VITE_API_BASE_URL`（应为 `/api`），WebSocket 路径字段名为 `VITE_WS_PATH`。
- 后端配置只使用 `backend/.env.example` 的**字段名**：`SECRET_KEY`、`INTERNAL_USERNAME`、`INTERNAL_PASSWORD`、`LLM_API_KEY`、`HOST`、`PORT`、`DATABASE_PATH` 等。不要把真实密钥写进本 README 或导航页。`LLM_API_KEY` 为空时源码走本地 Mock，不调用百炼。

配置定义不等于当前机器上的 `.env` 取值；本说明未读取真实 `.env`。

## 上线（面试官用公网打开）

本机 5199/8099 不能当正式环境。上线后前后端打成 **同一端口**：浏览器打开 `http://公网IP/`，`/api` 与 `/ws` 同源，不再走 Vite 代理。

### 买哪台最省事

面试官多半在国内，买 **腾讯云轻量** 或 **阿里云轻量**（不要买海外的 Railway/Render，国内打开会慢）：

- 系统：Ubuntu 22.04
- 规格：**2 核 2G** 即可（SQLite + 单进程 uvicorn）
- 地域：面试官所在地附近（上海 / 北京 / 广州）
- 防火墙/安全组放行：**22、80**
- 学生价通常几十元一个月；先买 1 个月够用
- 可以先不买域名，用公网 IP。没有 HTTPS，浏览器会提示「不安全」，面试演示可以接受

本仓库配置是 `use_env=False`，**必须以文件 `backend/.env` 提供配置**，Docker 环境变量不会覆盖。不要把真实密钥写进本 README。

### 服务器上部署

在轻量控制台用「远程登录 / SSH」进入 Ubuntu 后：

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker "$USER"
```

退出再登录一次，让 docker 组生效。把本项目拷到服务器（U 盘、压缩包或 `scp`，不要把 `.env` 发到公开网盘）：

```bash
cd Customer_Service
# 服务器上的 backend/.env 必须已填写 SECRET_KEY、INTERNAL_*、LLM_API_KEY
docker compose up -d --build
```

成功标志：本机浏览器打开 `http://公网IP/` 出现登录页；`http://公网IP/health` 返回 `healthy`。

上线前把内部账号密码换成面试专用口令，用私下渠道发给面试官。演示结束可 `docker compose down`，并在云控制台关机以免继续产生模型费用。

