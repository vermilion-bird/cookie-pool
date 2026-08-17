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

# 日志
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# noVNC 公网访问 URL 模板
NOVNC_PUBLIC_URL = f"http://{HOST_ADDRESS}:{NOVNC_PORT}/vnc.html"