import os

# Selenium Grid (default, overridden per-account when multi-grid is configured)
GRID_URL = os.getenv("GRID_URL", "http://selenium-hub:4444")
DEFAULT_GRID_NAME = os.getenv("DEFAULT_GRID_NAME", "Default Internal Grid")

# 外部访问地址（noVNC 用）
HOST_ADDRESS = os.getenv("HOST_ADDRESS", "localhost")
NOVNC_PORT = os.getenv("NOVNC_PORT", "7900")

# 数据目录
DATA_DIR = os.getenv("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "accounts.db")
DATABASE_URL = os.getenv("DATABASE_URL", "")  # 为空则使用 SQLite；设为 postgresql://... 则使用 PostgreSQL
PROFILES_DIR = os.path.join(DATA_DIR, "profiles")
ARTIFACTS_DIR = os.path.join(DATA_DIR, "artifacts")

# 调度器
SCHEDULER_TICK_SECONDS = int(os.getenv("SCHEDULER_TICK_SECONDS", "30"))

# 通知（Webhook，配置后任务完成/失败事件将 POST JSON 到该 URL）
NOTIFY_WEBHOOK_URL = os.getenv("NOTIFY_WEBHOOK_URL", "")

# API 认证（生产环境必须通过环境变量 API_KEY 注入强密钥；dev-key 仅限本地开发）
API_KEY = os.getenv("API_KEY", "dev-key")

# 浏览器配置
BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "30"))
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "15"))

# Session V2 超时回收（分钟）：
# CREATING / READY 超过此时间未进入 LOGIN → FAILED
SESSION_V2_CREATING_TIMEOUT_MINUTES = int(os.getenv("SESSION_V2_CREATING_TIMEOUT_MINUTES", "5"))
# LOGIN 超过此时间未 complete → FAILED（默认 120 分钟，给 VNC 手动登录留足时间）
SESSION_V2_LOGIN_TIMEOUT_MINUTES = int(os.getenv("SESSION_V2_LOGIN_TIMEOUT_MINUTES", "120"))

# 日志
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# noVNC 公网访问 URL 模板
NOVNC_PUBLIC_URL = f"http://{HOST_ADDRESS}:{NOVNC_PORT}/vnc.html"

# VNC 密码（设值后 noVNC 需要密码认证）
VNC_PASSWORD = os.getenv("VNC_PASSWORD", "")

# ── 稳定性配置 ──

# 节点心跳间隔（秒）：周期探测所有 Grid 节点健康状态
NODE_HEARTBEAT_INTERVAL = int(os.getenv("NODE_HEARTBEAT_INTERVAL", "30"))

# Session 最大生命周期（小时）：超过此时间的 session 被强制关闭，防止泄漏
SESSION_MAX_LIFETIME_HOURS = int(os.getenv("SESSION_MAX_LIFETIME_HOURS", "24"))

# Cookie 提取最大重试次数
COOKIE_EXTRACT_MAX_RETRIES = int(os.getenv("COOKIE_EXTRACT_MAX_RETRIES", "3"))

# 僵尸 session 清理间隔（秒）：扫描 Grid 上未被 DB 记录的孤立 session
ZOMBIE_CLEANUP_INTERVAL = int(os.getenv("ZOMBIE_CLEANUP_INTERVAL", "60"))