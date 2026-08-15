# Cookie Pool — 多服务器 Selenium Grid 账号池

> 无 GUI Linux 服务器上运行 Chrome，noVNC 网页手动登录，持久化 Profile，
> HTTP API 提取 Cookie 供采集程序使用。
>
> **当前版本：v0.5.0** — Standalone Grid · 集群 · 反检测 · 跨服务器 Cookie

## 架构

```
┌─ 主控服务器 ─────────────────────────────────────────────────┐
│                                                               │
│  cp-app (:8080)          cp-hub (:4444)   ← 可选             │
│  ┌──────────────┐        ┌──────────┐                        │
│  │ FastAPI       │        │ Hub      │                        │
│  │ + React SPA   │        └──┬──┬──┬─┘                        │
│  │ Web UI / API  │           │  │  │                          │
│  │ Cookie API    │     ┌─────┘  │  └─────┐                    │
│  │ Task 引擎     │     ▼        ▼        ▼                    │
│  └──────────────┘  node-1   node-2   node-3  ← 本地节点     │
│                    :7901    :7902    :7903   ← noVNC         │
│                                                               │
│  DB: GridInstance (hub_url, novnc_base_url)                    │
│      Account (grid_id → 绑定到哪个 Grid)                      │
└──────────────────────────────────────────────────────────────┘
         │                          │
         │ 跨公网 WebDriver          │
         ▼                          ▼
┌─ 服务器 B ──────────┐  ┌─ 服务器 C ──────────┐
│ grid-standalone     │  │ grid-standalone     │
│ Chrome :4444        │  │ Chrome :4444        │
│ noVNC :7900         │  │ noVNC :7900         │
│ Profile A, B        │  │ Profile C, D        │
└─────────────────────┘  └─────────────────────┘
```

**核心设计**：一个 Account → 绑定一个 Grid → Grid 可在本机或任何远程服务器。每个 Account 独立 Chrome Profile + noVNC。

**前端技术栈**：React 19 + Vite + TypeScript + Tailwind CSS + TanStack Query + React Router

---

## 快速开始

### 生产部署

```bash
git clone <repo> cookie-pool
cd cookie-pool
cp .env.example .env
# 编辑 .env: HOST_ADDRESS=你的公网IP

# 单机模式
docker compose up -d --build

# 或集群模式（Hub + 多个 Node）
docker compose -f docker-compose.cluster.yml up -d --build
```

### 本地开发

```bash
# 后端
cd app && pip install -r requirements.txt && uvicorn main:app --reload --port 8080

# 前端（另开终端，Vite 代理 /api 到 :8080）
cd frontend-react && npm install --include=dev && npm run dev
```

### 添加远程 Grid 节点

```bash
# 在新服务器上
scp -r grid-standalone/ user@new-server:/opt/
ssh new-server "cd /opt/grid-standalone && ./deploy.sh"

# 回到主控 Web UI → Grids → + Add Grid
#   Name: Server-X / Hub URL: http://<ip>:4444
```

---

## 使用流程

### 1. 创建账号

Web UI → Accounts → **+ New Account**

| 字段 | 示例 | 说明 |
|------|------|------|
| Name | `tiktok_ads_01` | 唯一标识 |
| Platform | `ads.tiktok.com` | 目标域名 |
| Grid | 选择对应节点 | Chrome 在哪台服务器上运行 |

### 2. 手动登录

点击 **Login** → noVNC 浏览器弹窗 → 输入账号密码 → **Login Complete**

状态流：`WAIT_LOGIN` → `LOGIN` → `ACTIVE`

### 3. 提取 Cookie

```bash
# 纯文本（直接当 Cookie header 用）
curl http://<host>:8080/api/accounts/8/cookies/plain
# → sessionid=xxx; s_v_web_id=yyy

# JSON 格式
curl http://<host>:8080/api/accounts/8/cookies

# 按域名过滤
curl "http://<host>:8080/api/accounts/8/cookies/plain?domain=tiktok.com"
```

### 4. 采集程序使用

```python
import requests

cookies = requests.get(
    "http://158.180.87.150:8080/api/accounts/8/cookies/plain"
).text

resp = requests.get(
    "https://ads.tiktok.com/",
    headers={"Cookie": cookies}
)
```

---

## API

### 账号

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/accounts` | 列出所有账号 |
| POST | `/api/accounts` | 创建 `{name, platform, grid_id?}` |
| DELETE | `/api/accounts/{id}` | 删除 |

### 登录

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/accounts/{id}/login` | 启动登录 → 返回 noVNC URL |
| POST | `/api/accounts/{id}/login/complete` | 确认登录完成 |
| POST | `/api/accounts/{id}/login/cancel` | 取消 |

### Cookie

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/accounts/{id}/cookies` | JSON 含 name/value/domain |
| GET | `/api/accounts/{id}/cookies/plain` | 纯文本 Cookie 字符串 |
| `?domain=xxx` | | 按域名过滤 |

### Grid

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/grids` | 列出 Grid 实例 |
| POST | `/api/grids` | 添加 `{name, hub_url, novnc_base_url?}` |
| POST | `/api/grids/{id}/check` | 健康探测 |

### Task

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/tasks` | 创建 `{account_id, type, params}` |
| POST | `/api/tasks/{id}/run` | 入队执行 |
| GET | `/api/tasks/{id}` | 查看结果 |
| GET | `/api/tasks/{id}/artifacts/{name}` | 下载截图 |

---

## 目录结构

```
cookie-pool/
├── Dockerfile                    # 多阶段构建：Node SPA → Python 运行时
├── docker-compose.yml            # 单机部署
├── docker-compose.cluster.yml    # 集群部署
├── .env.example                  # 环境变量模板
├── deploy.sh                     # 一键部署
├── cluster.sh                    # 集群管理
├── app/
│   ├── main.py                   # FastAPI 入口
│   ├── config.py / database.py / models.py
│   ├── api/                      # accounts, sessions, tasks, grids
│   ├── services/                 # grid_service, browser_service, task_service
│   ├── executors/                # 任务执行器注册表
│   ├── scheduler.py / worker.py / notifiers.py
│   └── requirements.txt
├── frontend-react/               # React 19 + Vite + TS + Tailwind
│   └── src/  pages/ components/ hooks/ lib/ types/
├── grid-standalone/              # 独立 Grid 部署包
│   ├── docker-compose.yml / deploy.sh / README.md
├── data/                         # 持久化（SQLite + Chrome Profiles）
└── scripts/
```

---

## 部署模式

| 模式 | 文件 | 适用 |
|------|------|------|
| 单机 | `docker-compose.yml` | 1-5 账号 |
| 集群 | `docker-compose.cluster.yml` | 5-15 账号，同机多节点 |
| 多服务器 | 主控 + 多台 `grid-standalone` | 15+ 账号，不同 IP 出口 |

---

## 反检测

每个 Chrome 会话自动注入：

- `--disable-blink-features=AutomationControlled` + `excludeSwitches`
- CDP 覆盖：`navigator.webdriver` / `plugins` / `languages` / WebGL
- 随机 Windows/macOS User-Agent 池
- `--disable-automation`

---

## 账号状态机

```
WAIT_LOGIN → LOGIN → ACTIVE ↔ IN_USE
                        ↘ LOGIN_EXPIRED
```

---

## 运维

```bash
docker compose ps && docker compose logs -f app
docker compose restart app
docker compose up -d --build app
tar czf backup-$(date +%Y%m%d).tar.gz data/
```

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| Grid OFFLINE | probe 端点不匹配 | 已修复 `/wd/hub/status` → `/status` 回退 |
| noVNC 无法输入 | VNC `-viewonly` | 删除 `SE_VNC_VIEW_ONLY` 环境变量 |
| 远程 Cookie 空 | Profile 路径不对 | 远程 Grid 挂载 `/data/profiles` |
| Login 二次创建 | 旧 session 未复用 | 已优化：复用存活 LOGIN session |
| Chrome 崩溃 | shm 不足 | `shm_size: 2gb`，`SE_NODE_MAX_SESSIONS=1` |