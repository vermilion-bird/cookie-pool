# Cookie Pool — 部署文档

Selenium Grid + noVNC 人工登录账号池。在无 GUI 的 Linux 服务器上运行 Chrome 浏览器，通过网页
(noVNC) 手动登录目标平台，持久化登录态，提供 HTTP API 提取 Cookie 供采集程序使用。

## 架构

```
┌── Docker Compose ──────────────────────────────────────┐
│                                                         │
│  cp-app (:8080)                cp-grid (standalone)     │
│  ┌──────────────┐              ┌──────────────────┐    │
│  │ FastAPI       │──http──────►│ Selenium Grid     │    │
│  │ + React SPA   │  :4444     │ (hub+node+Chrome) │    │
│  │               │              │                   │    │
│  │ /api/accounts │              │ Xvfb + VNC + noVNC│   │
│  │ /api/.../cookies            │ Chrome profiles   │    │
│  └──────────────┘              └──────────────────┘    │
│        │                              │                 │
│        ▼                              ▼                 │
│   ./data/ (SQLite + profiles)     ./data/profiles/     │
└─────────────────────────────────────────────────────────┘
```

- **cp-app**: FastAPI 后端 + React SPA 前端，端口 8080
- **cp-grid**: `selenium/standalone-chromium` 单容器 Grid，端口 4444（内部）+ 7901（noVNC）
- **数据**: SQLite 数据库 + Chrome profiles 持久化在 `./data/`

## 前置条件

| 要求 | 最低版本 | 说明 |
|------|---------|------|
| Docker | 20.10+ | |
| Docker Compose | v2 (`docker compose`) | |
| 内存 | 2 GB | Chrome 较吃内存 |
| 磁盘 | 5 GB 可用 | Chrome profiles 每个约 50-200MB |
| 网络 | 可访问 Docker Hub | 拉取镜像用 |

支持架构：`linux/amd64`、`linux/arm64`（Apple Silicon / Oracle Cloud Ampere 等）。

## 快速部署（3 步）

### 步骤 1：上传项目

```bash
# 在目标主机上
cd /opt
git clone <repo-url> cookie-pool   # 或 scp / rsync
cd cookie-pool
```

### 步骤 2：部署

```bash
chmod +x deploy.sh
./deploy.sh
```

部署脚本会：
1. 检查 Docker、内存、磁盘
2. 自动检测或让你输入公网 IP
3. 生成 `.env` 配置
4. 拉取镜像并构建
5. 启动所有服务
6. 输出健康检查结果和访问地址

### 步骤 3：验证

```bash
# 健康检查
curl http://localhost:8080/health
# → {"status":"ok"}

# Grid 状态
curl http://localhost:4444/status
# → {"value":{"ready":true,...}}
```

浏览器打开 `http://<你的IP>:8080/` 即可访问 Web UI。

---

## 配置说明

### `.env` 文件

```bash
# 主机公网 IP（必填，用于生成 noVNC 访问链接）
HOST_ADDRESS=1.2.3.4

# 端口（默认即可）
APP_PORT=8080       # Web UI
NOVNC_PORT=7901     # noVNC 远程浏览器

# API 密钥（自动生成）
API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx

# VNC 密码（留空 = 无密码；设置后 noVNC 需密码）
VNC_PASSWORD=

# Grid 配置
GRID_MAX_SESSIONS=1              # 最多同时几个浏览器（建议 1~3）
GRID_SESSION_TIMEOUT=300         # 会话超时秒数
GRID_IMAGE=selenium/standalone-chromium:latest
```

### 部署参数

```bash
./deploy.sh --host 1.2.3.4              # 指定 IP
./deploy.sh --host 1.2.3.4 --port 9090  # 自定义端口
./deploy.sh --novnc 7902                # 自定义 noVNC 端口
```

---

## 使用流程

### 1. 创建账号

Web UI → Accounts → **+ New Account**

| 字段 | 示例 | 说明 |
|------|------|------|
| Account Name | `google_ads_01` | 唯一标识 |
| Platform | `ads.google.com` | 目标网站域名 |
| Grid | Default | 使用哪个 Grid 实例 |

### 2. 手动登录

点击 **Login** 按钮 → 弹出 noVNC 内嵌浏览器 → 在新标签页中打开 → 手动输入账号密码登录平台 → 回到页面点 **Login Complete**。

账号状态：`WAIT_LOGIN` → `LOGIN` → `ACTIVE`

### 3. 提取 Cookie

```bash
# JSON 格式
curl http://HOST:8080/api/accounts/1/cookies
# → {"count":5,"cookie_string":"...","cookies":[{...}]}

# 纯文本（可直接做 Cookie header）
curl http://HOST:8080/api/accounts/1/cookies/plain
# → SID=xxx; HSID=yyy; SSID=zzz

# 按域名过滤
curl "http://HOST:8080/api/accounts/1/cookies/plain?domain=google.com"
```

---

## API 参考

### 账号管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/accounts` | 列出所有账号 |
| POST | `/api/accounts` | 创建账号 |
| GET | `/api/accounts/{id}` | 获取账号详情 |
| DELETE | `/api/accounts/{id}` | 删除账号 |

### 登录流程

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/accounts/{id}/login` | 启动登录（创建浏览器会话） |
| POST | `/api/accounts/{id}/login/complete` | 确认登录完成 |
| POST | `/api/accounts/{id}/login/cancel` | 取消登录 |

### Cookie 提取

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/accounts/{id}/cookies` | JSON 格式 cookie |
| GET | `/api/accounts/{id}/cookies/plain` | 纯文本 cookie 字符串 |
| `?domain=xxx` | | 按域名过滤 |

### 其他

| 端点 | 说明 |
|------|------|
| GET `/health` | 健康检查 |
| GET `/api/grids` | Grid 实例管理 |
| GET `/api/tasks` | 任务管理 |

---

## 常用运维命令

```bash
# 查看状态
docker compose ps
docker compose logs -f              # 实时日志
docker compose logs app --tail 50   # app 最近 50 行

# 重启
docker compose restart              # 重启所有
docker compose restart app          # 只重启 app
docker compose up -d --build app    # 重新构建 app

# 停止/启动
docker compose down                 # 停止并清除容器（数据不丢）
docker compose up -d                # 重新启动
docker compose down -v              # ⚠️ 清除容器+网络+卷（数据丢失！）

# 更新 Grid 镜像
docker compose pull grid
docker compose up -d grid

# 进入容器排查
docker exec -it cp-app sh
docker exec -it cp-grid bash

# 查看 Grid 状态
curl http://localhost:4444/status | python3 -m json.tool
```

---

## 数据备份

所有持久化数据在 `./data/` 目录：

```
data/
├── accounts.db              # SQLite 数据库（账号、Grid、任务记录）
└── profiles/                # Chrome profiles（每个账号一个目录）
    ├── account_google_ads_01/
    └── account_youtube_01/
```

**备份**：
```bash
tar czf cookie-pool-backup-$(date +%Y%m%d).tar.gz data/
```

**恢复**：
```bash
tar xzf cookie-pool-backup-YYYYMMDD.tar.gz
```

---

## 故障排查

### Grid 状态异常

```bash
# 查看 Grid 容器日志
docker logs cp-grid --tail 50

# 重启 Grid
docker compose restart grid
```

### Chrome 崩溃 / tab crash

```bash
# 检查内存
free -h

# 增加 shm_size（docker-compose.yml 中已设 2gb）
# 如果还崩溃，检查 docker 内存限制

# 清除残留 Chrome 锁
docker exec cp-grid sh -c "rm -f /tmp/.com.google.Chrome.* /tmp/Singleton*"
```

### noVNC 无法连接

1. 检查 VNC 进程：`docker exec cp-grid sh -c "ps aux | grep x11vnc"`
2. 确认 `-viewonly` 不在参数中
3. 确认端口映射：`docker port cp-grid`

### 账号登录后 cookie 为空

- 确认账号 status 为 `ACTIVE`
- 确认 platform 字段是正确的域名（不是中文/乱码）
- 如果 platform 错误：Web UI 中编辑账号修正

### 镜像拉取慢

```bash
# 使用镜像加速器（阿里云/中科大等）
# 编辑 /etc/docker/daemon.json:
{
  "registry-mirrors": ["https://docker.m.daocloud.io"]
}
sudo systemctl restart docker
```

---

## 多实例部署

同一台机器部署多个 cookie-pool 实例（不同端口）：

```bash
# 实例 1
cp -r cookie-pool cookie-pool-1
cd cookie-pool-1
# 编辑 .env: APP_PORT=8080 NOVNC_PORT=7901
./deploy.sh

# 实例 2
cp -r cookie-pool cookie-pool-2
cd cookie-pool-2
# 编辑 .env: APP_PORT=8081 NOVNC_PORT=7902
./deploy.sh
```

> 注意：两个实例使用独立的 `data/` 目录，互不影响。

---

## 从旧版升级（seleniarm hub+node → standalone）

如果之前使用 `seleniarm/hub` + `seleniarm/node-chromium` 部署：

```bash
# 1. 停止旧容器
docker stop cp-hub cp-chrome cp-app
docker rm cp-hub cp-chrome cp-app

# 2. 更新 db 中的 grid hub_url
docker compose up -d --build
docker exec cp-app python3 -c "
from database import SessionLocal
from models import GridInstance
db = SessionLocal()
for g in db.query(GridInstance).all():
    if 'selenium-hub' in g.hub_url:
        g.hub_url = 'http://grid:4444'
        print(f'Updated grid {g.id}')
db.commit()
"
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.5.0 | 2026-08 | 切换为 standalone-chromium 单容器 Grid；新增 Cookie API；反检测加强 |
| 0.4.0 | 2026-08 | 多 Grid 支持；登录 session 持久化修复 |
| 0.3.0 | 2026-08 | VNC viewonly 修复；noVNC iframe 大屏化 |
| 0.2.0 | 2026-08 | React SPA 前端 |
| 0.1.0 | 2026-08 | 初始版本：FastAPI + seleniarm hub/node |