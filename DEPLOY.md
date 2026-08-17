# Cookie Pool — 部署文档

> **生产服务器**: `158.180.87.150` (Oracle Cloud ARM64)  
> **域名**: `https://cookie.8tb.cc` (Caddy 反代 → cp-app:8080)  
> **当前版本**: v0.5.0

Selenium Grid 集群 + noVNC 人工登录账号池。在无 GUI 的 Linux 服务器上运行 Chrome
浏览器，通过网页 (noVNC) 手动登录目标平台，持久化登录态，提供 HTTP API 提取 Cookie
供采集程序使用。

---

## 生产架构

```
                             Caddy (SSL termination)
                              │
          ┌───────────────────┼───────────────────────┐
          │                   │                       │
     cookie.8tb.cc    130.61.144.130           192.9.249.67
     (158.180.87.150)  (Grid 130 standalone)   (Grid 192 standalone)
          │
┌─────────┴──────────────────────────────────────────┐
│  Docker Compose (cookie-extract)                    │
│                                                     │
│  cp-hub (:4444)  ─── Selenium Hub ───┐              │
│  cp-node-1 (7901)  Chrome node       │              │
│  cp-node-2 (7902)  Chrome node       │  (同机节点)  │
│  cp-app  (:8080)   FastAPI + React   │              │
│                                                     │
│  网络: cookie-extract_cp-network (172.30.0.0/16)    │
│  ┌──────────────────────────────────────────────┐   │
│  │ cp-hub    172.30.0.2                         │   │
│  │ cp-node-1 172.30.0.3  (noVNC :7901)         │   │
│  │ cp-node-2 172.30.0.4  (noVNC :7902)         │   │
│  │ cp-app    172.30.0.5  (API :8080)            │   │
│  │ caddy     172.30.0.6  (HTTPS :443)          │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  外部 Grid（通过 Grid API 注册）：                  │
│  - Server-130 (130.61.144.130:4444, noVNC :7900)    │
│  - Server-192 (192.9.249.67:4444, noVNC :7900)      │
└─────────────────────────────────────────────────────┘
```

- **cp-app**: FastAPI 后端 + React SPA，端口 8080，多阶段 Docker 构建
- **cp-hub**: `selenium/hub:latest`，会话路由中枢
- **cp-node-1/2**: `selenium/node-chromium:latest`，各 1 个 Chrome slot，独立 VNC/noVNC
- **Caddy**: SSL 自动签发 + 反向代理到 cp-app
- **外部 Grid**: 远程 standalone Grid，通过 `/api/grids` 注册后使用

---

## 前置条件

| 要求 | 最低版本 | 说明 |
|------|---------|------|
| Docker | 20.10+ | |
| Docker Compose | v2 (`docker compose`) | |
| 内存 | 4 GB | Hub + 2 Node + App ≈ 3GB，建议 4GB+ |
| 磁盘 | 10 GB 可用 | Chrome profiles 每个约 50-200MB |
| 架构 | arm64 / amd64 | Oracle Cloud 为 ARM64 |

---

## 日常部署（推荐：rsync 增量同步）

从开发机推送到生产服务器：

```bash
# —— 在开发机上执行 ——

# 1. SSH 密钥（一次性配置）
export SSH_KEY="$HOME/.ssh/id_rsa"   # 或指定路径
export REMOTE="ubuntu@158.180.87.150"
export PROJECT="/tmp/cookie-extract"

# 2. 同步源码（排除 .git / data / node_modules）
rsync -avz --delete \
  -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
  --exclude '.git' --exclude 'data' --exclude 'node_modules' \
  --exclude '__pycache__' --exclude '.pytest_cache' --exclude '*.pyc' \
  --exclude '.env' \
  . \
  ${REMOTE}:${PROJECT}/

# 3. 重建并重启
ssh -i "$SSH_KEY" "$REMOTE" \
  "cd ${PROJECT} && docker compose -f docker-compose.cluster.yml up -d --build app"

# 4. 验证
curl -s https://cookie.8tb.cc/health
# → {"status":"ok","version":"0.5.0","database":"ok"}
```

> **注意**：rsync 务必排除 `.env` 和 `data/`，否则会覆盖生产配置和数据。

---

## 全新部署（从零开始）

### 1. 上传项目

```bash
# 在目标服务器上
mkdir -p /opt/cookie-pool
cd /opt/cookie-pool

# Git clone（或 scp / rsync）
git clone <repo-url> .
```

### 2. 创建 .env

```bash
cat > .env << 'EOF'
HOST_ADDRESS=158.180.87.150
APP_PORT=8080
NOVNC_PORT=7901
API_KEY=<生成强密钥>
VNC_PASSWORD=
GRID_MAX_SESSIONS=1
GRID_SESSION_TIMEOUT=300
GRID_IMAGE=selenium/hub:latest
DATA_DIR=./data
EOF

# 生成 API Key:
#  openssl rand -hex 16
```

### 3. 创建数据目录

```bash
mkdir -p data/profiles data/artifacts
```

### 4. 构建并启动

```bash
# 集群模式（Hub + Node-1 + Node-2 + App）
docker compose -f docker-compose.cluster.yml up -d --build

# 单机模式（Standalone Chromium + App）
docker compose up -d --build
```

### 5. 配置 Caddy 反代（可选）

Caddyfile 片段（用于 `https://cookie.8tb.cc`）：

```
cookie.8tb.cc {
    reverse_proxy 172.30.0.5:8080
}
```

> **关键**：Caddy 必须加入 `cookie-extract_cp-network` 网络才能解析 `172.30.0.5`：
> ```bash
> docker network connect cookie-extract_cp-network caddy
> ```

---

## 配置说明

### `.env` 变量

```bash
HOST_ADDRESS=158.180.87.150    # 公网 IP 或域名
APP_PORT=8080                  # Web UI 端口
NOVNC_PORT=7901                # Node-1 noVNC 端口
API_KEY=cookie-pool-158-2026   # API 认证密钥（所有 API 请求需带 X-API-Key）
VNC_PASSWORD=                  # VNC 密码（空 = 不需要）
GRID_MAX_SESSIONS=1            # 每个 Node 最多 1 个 session
GRID_SESSION_TIMEOUT=300       # Grid 会话超时（秒）
GRID_IMAGE=selenium/hub:latest # Hub 镜像
DATA_DIR=./data                # 数据持久化目录
```

### 多 Node 端口映射

| Node | 容器名 | noVNC 端口 |
|------|--------|-----------|
| node-1 | cp-node-1 | 7901 |
| node-2 | cp-node-2 | 7902 |
| node-3 | cp-node-3 | 7903 |

### 外部 Grid 注册

```bash
curl -X POST https://cookie.8tb.cc/api/grids \
  -H "X-API-Key: cookie-pool-158-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Server-130",
    "hub_url": "http://130.61.144.130:4444",
    "novnc_base_url": "http://130.61.144.130:7900/vnc.html",
    "max_sessions": 1
  }'
```

> 外部 Grid 需要 Profile 目录预创建（见下文「外部 Grid Profile 管理」）。

---

## 外部 Grid Profile 管理

当 Session 绑定到外部 Grid（不同服务器）时，app 容器内的 `os.makedirs(profile_path)`
只在 app 本地生效，远端 Grid 看不到。

**每次创建新 Session 后、Start 之前，在 Grid 服务器上执行：**

```bash
# Profile 路径命名规则: session_<name>（名称小写、空格换下划线）
sudo mkdir -p /path/to/profiles/session_<session-name>
sudo chmod 777 /path/to/profiles/session_<session-name>
```

**同机 Node（cp-node-1/2）不需要此步骤** — 它们通过 Docker 卷共享
`./data/profiles/`。

---

## API 认证

所有 API 请求需携带 `X-API-Key` 头：

```bash
curl -H "X-API-Key: cookie-pool-158-2026" https://cookie.8tb.cc/api/accounts
```

Web UI 会自动从 `localStorage` 获取 API Key。

---

## 使用流程

### Session v2（推荐）

1. 创建 Session（绑定到某个 Grid Node）
2. 绑定 Account 到 Session（Session 是一个 Chrome 浏览器，承载多个不同平台的账号）
3. Start → noVNC 登录所有绑定的平台 → Complete
4. 通过 `/api/sessions/{id}/cookies?platform=tiktok.com` 提取 cookie

### 旧版 Account 流程（仍然可用）

1. Web UI → Accounts → + New → 填写 name/platform/grid
2. Login → noVNC 登录 → Login Complete
3. 账号 status: `WAIT_LOGIN` → `LOGIN` → `ACTIVE`
4. `/api/accounts/{id}/cookies/plain` 提取

---

## 后台守护进程

| 组件 | 间隔 | 职责 |
|------|------|------|
| **SessionWatchdog** | 30s | 守护 ACTIVE/LOGIN session driver 存活；死了自动 Grid 重连 → 完整重启 |
| **SessionSweeper** | 60s | 回收超时登录会话；释放 IN_USE 泄漏锁（>15min → ACTIVE）|
| **TaskWorker** | 事件驱动 | 异步执行 cookie 提取任务 |
| **Scheduler** | 30s | Cron 定时调度 |

### Account 状态自动修复（v0.5.0+）

```
IN_USE > 15min  →  SessionSweeper 自动释放为 ACTIVE
Session 重启     →  绑定 Account 退回 WAIT_LOGIN（手动 + watchdog 自动）
Watchdog 恢复失败 →  绑定 Account 标记 LOGIN_EXPIRED
```

通过环境变量禁用后台守护（调试用）：

```bash
CP_DISABLE_BACKGROUND=1 docker compose -f docker-compose.cluster.yml up -d
```

---

## 运维命令

```bash
# 在 158 服务器上（ssh ubuntu@158.180.87.150）

cd /tmp/cookie-extract

# 查看状态
docker compose -f docker-compose.cluster.yml ps

# 查看日志
docker compose -f docker-compose.cluster.yml logs -f --tail 100
docker logs cp-app --tail 50
docker logs cp-node-1 --tail 50

# 只重启 app（代码更新后）
docker compose -f docker-compose.cluster.yml up -d --build app

# 完全重建
docker compose -f docker-compose.cluster.yml down
docker compose -f docker-compose.cluster.yml up -d --build

# 进入容器
docker exec -it cp-app sh
docker exec -it cp-hub bash

# 数据库操作
docker exec cp-app sqlite3 /data/accounts.db ".tables"
docker exec cp-app sqlite3 /data/accounts.db "SELECT id,name,status FROM accounts;"

# 健康检查
curl http://localhost:8080/health
curl -s http://localhost:4444/status | python3 -m json.tool

# 删除 Grid 僵尸 session
docker exec cp-app python3 -c "
from database import SessionLocal
from models import GridInstance
db = SessionLocal()
g = db.query(GridInstance).filter_by(id=3).first()
# 在 Grid 服务器上: docker restart cp-grid 或 docker exec ... rm session
"
```

---

## 容器和端口一览

| 容器 | 端口 | 说明 |
|------|------|------|
| cp-app | 8080 | FastAPI + React SPA |
| cp-hub | 4444 | Selenium Hub（内部）|
| cp-node-1 | 7901 | Chrome node，noVNC |
| cp-node-2 | 7902 | Chrome node，noVNC |
| cp-node-3 | 7903 | Chrome node（停止，profile 启动）|
| caddy | 80, 443 | SSL 反代 |

---

## 数据备份

```bash
# 在 158 上
cd /tmp/cookie-extract
tar czf cookie-pool-backup-$(date +%Y%m%d-%H%M).tar.gz data/

# 恢复到另一台机器
tar xzf cookie-pool-backup-*.tar.gz
docker compose -f docker-compose.cluster.yml up -d --build
```

---

## 故障排查

### cp-app 启动失败

```bash
docker logs cp-app --tail 50
# 常见：.env 缺失、GRID_URL 不可达、DATA_DIR 权限
```

### Grid Node 无反应

```bash
docker logs cp-node-1 --tail 30
# 常见：内存不足、shm_size 太小、session 超时未释放
```

### Grid 僵尸 session 阻塞 Node

每个 Node 只有 1 slot。僵尸 session 会永久占用：

```bash
# 在 158 上重启对应 Node
docker compose -f docker-compose.cluster.yml restart node-1

# 或在远程 Grid 上删除僵尸容器
# 130: docker restart cp-grid
# 192: sudo docker restart <grid-container>
```

### Caddy 502

```bash
# Caddy 必须在 cp-network 内
docker network inspect cookie-extract_cp-network | grep -A2 caddy

# 如果不在，加入：
docker network connect cookie-extract_cp-network caddy

# Caddyfile 中 reverse_proxy 用 IP 而非容器名（隔离网络 DNS 不可达）：
#   reverse_proxy 172.30.0.5:8080
```

### noVNC 白屏或无法交互

```bash
# 确认 node 的 VNC 启用
docker exec cp-node-1 sh -c "ps aux | grep x11vnc"

# 检查 noVNC 端口
curl -s http://localhost:7901 | head -5
```

### Chrome 崩溃 / Out of Memory

```bash
free -h
# 如果内存不足：关闭 node-3，减少并发 Node

# 增加 shm_size（docker-compose.cluster.yml）：
#   shm_size: "4gb"
```

---

## 开发环境

```bash
# 本地开发
cd cookie-pool

# 后端
cd app
pip install -r requirements.txt
uvicorn main:app --reload --port 8080

# 前端
cd frontend-react
npm install
npm run dev   # Vite HMR on :5173

# Docker 构建（不启动 Grid）
docker compose -f docker-compose.cluster.yml build app
```

---

## 版本历史

| 版本 | 日期 | 关键变更 |
|------|------|---------|
| 0.5.0 | 2026-08 | SessionWatchdog 自动恢复；Account 状态修复（IN_USE 泄漏、restart 联动、LOGIN_EXPIRED）；Grid 重连清理孤儿 session |
| 0.4.0 | 2026-08 | Session v2（常驻浏览器）；多 Grid 支持；登录 session 持久化修复 |
| 0.3.0 | 2026-08 | VNC viewonly 修复；noVNC iframe 大屏化 |
| 0.2.0 | 2026-08 | React SPA 前端 |
| 0.1.0 | 2026-08 | 初始版本：FastAPI + seleniarm hub/node |