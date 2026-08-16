# Selenium Standalone Grid — 标准化部署

单容器 Selenium Grid，含 Chrome + VNC + noVNC，独立于任何业务应用。

## 特性

- **单容器全栈**：hub + node + Chrome + Xvfb + VNC + noVNC 合一
- **noVNC 远程桌面**：浏览器访问 `http://host:7900/vnc.html` 直接操作 Chrome
- **Chrome Profile 持久化**：登录态跨容器重启保留
- **多实例支持**：改端口即可同机跑多个 Grid
- **健康检查**：自动检测 Grid 就绪状态

## 快速开始

```bash
# 1. 复制项目到目标主机
scp -r grid-standalone/ user@host:/opt/

# 2. 部署（自动检测环境 + 生成配置）
cd /opt/grid-standalone
chmod +x deploy.sh
./deploy.sh

# 3. 打开 noVNC
# http://<host>:7900/vnc.html
```

## 配置

### 默认端口

| 端口 | 用途 |
|------|------|
| 4444 | Selenium Grid API (`/wd/hub`) |
| 7900 | noVNC 网页远程桌面 |
| 5900 | 原生 VNC |

### 自定义

```bash
# 指定端口和并发数
./deploy.sh --port 4445 --novnc 7901 --sessions 3

# 设置 VNC 密码
./deploy.sh --password my-secret

# 多实例（不同端口隔离）
./deploy.sh --name grid-youtube --port 4445 --novnc 7901
./deploy.sh --name grid-google  --port 4446 --novnc 7902
```

### .env 参考

```bash
CONTAINER_NAME=selenium-grid
GRID_PORT=4444
NOVNC_PORT=7900
GRID_MAX_SESSIONS=1
VNC_PASSWORD=
GRID_IMAGE=selenium/standalone-chromium:latest
PROFILES_DIR=./profiles
```

## 客户端连接

### Python (Selenium)

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

# 持久化 Profile（登录态复用）
options.add_argument("--user-data-dir=/home/seluser/chrome-profiles/my-account")

driver = webdriver.Remote(
    command_executor="http://<host>:4444/wd/hub",
    options=options
)
```

### 任意语言 (W3C WebDriver)

```bash
# 创建会话
curl -X POST http://localhost:4444/wd/hub/session \
  -H "Content-Type: application/json" \
  -d '{"capabilities":{"alwaysMatch":{"browserName":"chrome"}}}'

# 查看状态
curl http://localhost:4444/status
```

## 运维

```bash
docker compose ps                  # 状态
docker compose logs -f             # 日志
docker compose restart             # 重启
docker compose down                # 停止
docker compose up -d --pull always # 更新镜像
docker exec -it selenium-grid bash # 进入容器
```

## Chrome Profile 管理

Profile 保存在 `./profiles/` 目录，与容器内 `/data/profiles/` 映射。

```
profiles/
├── session_ad-pool-01/       # 常驻 Session profile
├── session_health-test/       # 常驻 Session profile
└── ...
```

每个 profile 目录由 cookie-pool 通过 `--user-data-dir` 指定。

> 注意：容器内 Chrome 以 `seluser` 用户运行，profile 目录需可写。
> 如需外部创建 profile 目录：`mkdir -p profiles/new-account && chmod 777 profiles/new-account`

### ⚠ 跨服务器 Profile 预创建

**限制：cookie-pool 与 Grid 不在同一服务器时，app 的 `os.makedirs(profile_path)` 在本地执行，远端 Grid 看不到。**

**使用前必须在 Grid 服务器上预创建 profile 目录：**

```bash
# 在 Grid 服务器上（如 192.9.249.67）
sudo mkdir -p /path/to/grid-standalone/profiles/session_<name>
sudo chmod 777 /path/to/grid-standalone/profiles/session_<name>
```

profile 命名规则：`session_<session-name>`（空格替换为下划线，小写）。

> 此限制仅影响「跨服务器 Grid」。同一 Docker 主机上的 Grid（如 hub+node 集群）共享 `./data/profiles` 卷，不受影响。

### 接入 cookie-pool

部署 Grid 后，在 cookie-pool Web UI（Grids 页面）或 API 注册：

```bash
curl -X POST http://<cookie-pool-host>:8080/api/grids \
  -H "X-API-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Grid-192",
    "hub_url": "http://192.9.249.67:4444",
    "novnc_base_url": "http://192.9.249.67:7900/vnc.html",
    "max_sessions": 1,
    "notes": "Standalone Chromium on 192.9.249.67"
  }'
```

创建 Session 时选择对应 Node，点击 Start 即可在远端浏览器登录。

## 故障排查

### Grid 不启动

```bash
docker logs selenium-grid --tail 50
```

### noVNC 无法输入

确认 VNC 没有 `-viewonly`：
```bash
docker exec selenium-grid sh -c "ps aux | grep x11vnc"
```
输出中不应出现 `-viewonly`。如有，说明设置了 `SE_VNC_VIEW_ONLY` 环境变量，请删除。

### Chrome 崩溃

```bash
# 增加共享内存或减少并发
# docker-compose.yml: shm_size: "4gb"
# .env: GRID_MAX_SESSIONS=1
```

### 端口冲突

```bash
# 检查端口占用
ss -tlnp | grep -E "4444|5900|7900"

# 改用其他端口
./deploy.sh --port 4445 --novnc 7901 --vnc 5901
```

## 镜像版本

| Tag | 说明 |
|-----|------|
| `selenium/standalone-chromium:latest` | 最新稳定版（推荐） |
| `selenium/standalone-chromium:150.0` | 固定版本 |

查看可用版本：https://hub.docker.com/r/selenium/standalone-chromium