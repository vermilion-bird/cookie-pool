import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from contextlib import asynccontextmanager

from database import init_db, SessionLocal
from config import PROFILES_DIR, LOG_LEVEL, API_KEY
from version import __version__
from worker import worker, sweeper
from scheduler import scheduler

logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    os.makedirs(PROFILES_DIR, exist_ok=True)
    # 测试环境通过 CP_DISABLE_BACKGROUND=1 关闭后台线程
    if os.getenv("CP_DISABLE_BACKGROUND", "0") != "1":
        worker.start()
        sweeper.start()
        scheduler.start()
    logger.info("Cookie Pool started (version %s)", app.version)
    yield
    scheduler.stop()
    sweeper.stop()
    worker.stop()
    logger.info("Cookie Pool stopped")


app = FastAPI(
    title="Cookie Pool",
    description="Selenium Grid + noVNC 人工登录账号池",
    version=__version__,
    lifespan=lifespan,
)

# ── API 认证中间件：/api/* 与文档端点需 X-API-Key 头；/health 与 SPA 静态资源放行 ──
AUTH_PROTECTED_DOCS = {"/docs", "/redoc", "/openapi.json"}


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api") or path in AUTH_PROTECTED_DOCS:
        key = request.headers.get("X-API-Key")
        if not key or key != API_KEY:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


# 导入 API 路由
from api.accounts import router as accounts_router
from api.sessions import router as sessions_router_v1
from api.sessions_v2 import router as sessions_router
from api.tasks import router as tasks_router
from api.grids import router as grids_router
from api.schedules import router as schedules_router

app.include_router(accounts_router, prefix="/api/accounts", tags=["accounts"])
app.include_router(sessions_router_v1, prefix="/api/sessions", tags=["sessions"])
app.include_router(sessions_router, prefix="/api", tags=["sessions-v2"])
app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"])
app.include_router(grids_router, prefix="/api/grids", tags=["grids"])
app.include_router(schedules_router, prefix="/api/schedules", tags=["schedules"])


@app.get("/health")
async def health():
    db_ok = True
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning("Health check: database error: %s", e)
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": app.version,
        "database": "ok" if db_ok else "error",
    }


# --- React SPA (built by frontend-react, copied to FRONTEND_DIR at image build time) ---
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", str(Path(__file__).parent.parent / "frontend-react" / "dist")))

if FRONTEND_DIR.exists():
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    async def spa_root():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/{full_path:path}")
    async def spa_catch_all(full_path: str):
        # 让 API 路由优先匹配；未命中的非 /api 路径都回退到 SPA index.html（client-side routing）
        if full_path.startswith("api/") or full_path.startswith("assets/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        candidate = FRONTEND_DIR / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIR / "index.html"))
else:
    logger.warning(f"Frontend dist not found at {FRONTEND_DIR}. Run `npm run build` in frontend-react/, or use `npm run dev` for local development.")

    @app.get("/")
    async def spa_missing():
        return JSONResponse(
            status_code=200,
            content={"message": "Cookie Pool API is running. Frontend not built — see frontend-react/ (npm run dev / npm run build)."},
        )