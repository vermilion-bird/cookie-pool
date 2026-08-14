# Cookie Pool — Selenium Grid + noVNC 人工登录账号池

> 无桌面服务器上的账号管理与自动化执行平台。
>
> **当前版本：v0.3.0** — 详见 [ROADMAP.md](./ROADMAP.md)（Phase 1：API 认证、异步任务执行、会话超时回收、测试体系）。

## 架构

```
React SPA (Vite build, served by FastAPI) → FastAPI API → Selenium Grid → Chrome Node(s) + VNC → noVNC
```

**核心原则**：不把 Cookie 作为主要存储对象，而是持久化 Chrome Profile。

**前端技术栈**：React 19 + Vite + TypeScript + Tailwind CSS + TanStack Query + React Router
（与 `influencer-platform` 项目保持一致的构建模式：Docker 多阶段构建，Node 编译 SPA → Python 单容器托管 API + 静态资源）

## 快速启动

### 生产部署（Docker）

```bash
docker compose up -d --build
```

访问 `http://localhost:8080/` 打开 Web Admin（FastAPI 直接托管编译好的 React 产物）。

### 本地开发（前端热更新）

> **API 认证**：v0.3.0 起所有 `/api/*` 请求需携带 `X-API-Key` 头（默认 `dev-key`，仅限本地；生产通过 `API_KEY` 环境变量注入强密钥）。前端右上角 🔑 按钮可设置密钥（存于 localStorage）。

```bash
# 后端（需要本机已跑起 Selenium Grid，或指向远程 Grid）
cd app && pip install -r requirements.txt && uvicorn main:app --reload --port 8080

# 前端（另开一个终端；Vite dev server 会把 /api、/health 代理到 :8080）
cd frontend-react && npm install --include=dev && npm run dev
```

## 目录结构

```
cookie-pool/
├── Dockerfile                # 多阶段构建：Node 编译 SPA → Python 运行时
├── docker-compose.yml        # 主编排
├── app/                      # FastAPI 后端（纯 API + SPA 托管）
│   ├── requirements.txt
│   ├── main.py               # 入口：API 路由 + SPA 静态资源托管/回退
│   ├── config.py             # 配置
│   ├── database.py           # SQLite
│   ├── models.py             # ORM 模型
│   ├── api/                  # API 路由
│   └── services/             # 业务服务
├── frontend-react/           # React 19 + Vite + TS + Tailwind 前端
│   ├── src/
│   │   ├── pages/            # Dashboard / Accounts / Tasks
│   │   ├── components/       # Layout / Modal / Badge / LoginModal ...
│   │   ├── hooks/            # useToast / useHealth
│   │   ├── lib/              # api.ts (fetch 封装) / format.ts
│   │   └── types/            # 共享类型定义
│   └── dist/                 # `npm run build` 产物（Docker 构建时生成，不提交）
├── data/                     # 持久化数据
│   ├── accounts.db           # 数据库
│   └── profiles/             # Chrome Profile
└── scripts/                  # 工具脚本
```

## 账号状态

```
WAIT_LOGIN → ACTIVE ↔ IN_USE
                 ↘ LOGIN_EXPIRED → ACTIVE
```

账号可配置 **login_indicator**（CSS 选择器）：登录校验时优先用它在浏览器中判断是否已登录，未配置则回退到 URL 关键词启发式。

## API

> 所有 `/api/*` 请求需携带 `X-API-Key` 头（`/health` 与 SPA 静态资源除外）。

| 分组 | 端点 | 说明 |
|------|------|------|
| 账号 | `GET/POST /api/accounts` | 列表/创建（支持 `login_indicator`） |
| 账号 | `GET/PUT/DELETE /api/accounts/{id}` | 详情/编辑/删除（删除时清理 Profile 磁盘） |
| 登录 | `POST /api/accounts/{id}/login` | 打开登录浏览器 |
| 登录 | `POST /api/accounts/{id}/login/complete` | 确认登录（经 Grid REST 校验现有会话） |
| 登录 | `POST /api/accounts/{id}/login/cancel` | 取消登录 |
| Session | `GET/DELETE /api/sessions/{id}` | 会话管理 |
| 任务 | `POST /api/tasks` | 创建任务（校验执行器类型与 JSON 参数） |
| 任务 | `GET /api/tasks` | 任务列表 |
| 任务 | `GET /api/tasks/{id}` | 任务详情 |
| 任务 | `POST /api/tasks/{id}/run` | 入队后台执行（立即返回，异步运行） |
| 任务 | `POST /api/tasks/{id}/cancel` | 取消任务 |
| Grid | `GET/POST /api/grids`、`/{id}/check` 等 | Grid 管理（原样） |

内置任务执行器（`app/executors/registry.py`）：`visit_url`、`check_login_status`。自定义执行器通过注册表扩展。

## 测试

```bash
# 后端（pytest）
cd app && pip install -r requirements-dev.txt && python -m pytest tests -q

# 前端（vitest）
cd frontend-react && npm test
```

## 前端页面

| 路由 | 说明 |
|------|------|
| `/` | Dashboard — 账号统计 + 最近任务 |
| `/accounts` | 账号管理 — 创建 / 筛选 / 登录（noVNC 弹窗）/ 删除 |
| `/tasks` | 任务管理 — 创建 / 筛选 / 运行 / 取消 / 详情 |