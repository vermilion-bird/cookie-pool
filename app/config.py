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
PROFILES_DIR = os.path.join(DATA_DIR, "profiles")

# API 认证
API_KEY = os.getenv("API_KEY", "dev-key")

# 浏览器配置
BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "30"))
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "15"))

# 日志
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# noVNC 公网访问 URL 模板
NOVNC_PUBLIC_URL = f"http://{HOST_ADDRESS}:{NOVNC_PORT}/vnc.html"