"""Session Watchdog — 周期性守护 v2 Session 浏览器存活，自动恢复死亡的 driver。"""
import logging
import threading
import time
from datetime import datetime, timezone

from database import SessionLocal
from models import Session, GridInstance
from config import PROFILES_DIR

logger = logging.getLogger(__name__)

# 延迟导入避免循环依赖 — sessions_v2 模块在 watchdog 之后才被 import
_live_drivers_ref = None
_ping_driver_ref = None
_reconnect_via_grid_ref = None
_create_driver_ref = None


def _resolve_refs():
    """延迟解析对 sessions_v2 模块的引用（避免循环 import）。"""
    global _live_drivers_ref, _ping_driver_ref, _reconnect_via_grid_ref, _create_driver_ref
    if _live_drivers_ref is None:
        from api.sessions_v2 import _live_drivers, _ping_driver, _reconnect_via_grid
        from services.grid_service import GridService
        _live_drivers_ref = _live_drivers
        _ping_driver_ref = _ping_driver
        _reconnect_via_grid_ref = _reconnect_via_grid
        _create_driver_ref = GridService.create_driver


class SessionWatchdog:
    """周期性检查所有 ACTIVE/LOGIN session 的 driver 是否存活，死了自动恢复。"""

    def __init__(self, interval_seconds: int = 30):
        self.interval_seconds = interval_seconds
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        _resolve_refs()
        self._running = True
        # 后台线程：启动时先做一轮恢复（app 重启后重建 _live_drivers）
        self._thread = threading.Thread(target=self._loop, name="session-watchdog", daemon=True)
        self._thread.start()
        logger.info(f"SessionWatchdog started (interval={self.interval_seconds}s)")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("SessionWatchdog stopped")

    def _loop(self) -> None:
        # 首轮：启动恢复
        try:
            self.startup_recovery()
        except Exception:
            logger.exception("Watchdog startup recovery error")
        # 后续：周期扫描
        while self._running:
            try:
                self.sweep_once()
            except Exception:
                logger.exception("SessionWatchdog sweep error")
            for _ in range(self.interval_seconds):
                if not self._running:
                    return
                time.sleep(1)

    def sweep_once(self) -> int:
        """扫描所有 ACTIVE/LOGIN session，自动恢复死亡的 driver。返回恢复数量。"""
        _resolve_refs()
        db = SessionLocal()
        try:
            sessions = db.query(Session).filter(
                Session.status.in_(["ACTIVE", "LOGIN"])
            ).all()

            recovered = 0
            for s in sessions:
                if self._check_and_recover(s, db):
                    recovered += 1
            if recovered:
                logger.info(f"Watchdog recovered {recovered} dead session(s)")
            return recovered
        finally:
            db.close()

    def startup_recovery(self) -> int:
        """app 启动时：恢复所有 ACTIVE/LOGIN session 的 driver 到 _live_drivers。"""
        _resolve_refs()
        db = SessionLocal()
        try:
            sessions = db.query(Session).filter(
                Session.status.in_(["ACTIVE", "LOGIN"])
            ).all()
            if not sessions:
                return 0

            recovered = 0
            for s in sessions:
                # 跳过已有活跃 driver 的
                existing = _live_drivers_ref.get(s.id)
                if existing is not None and _ping_driver_ref(existing):
                    continue

                # 尝试 Grid 重连
                if s.grid_session_id:
                    try:
                        reconnected = _reconnect_via_grid_ref(s)
                        if reconnected:
                            _live_drivers_ref[s.id] = reconnected
                            recovered += 1
                            logger.info(f"Startup: reconnected session {s.id} ({s.name})")
                            continue
                    except Exception as e:
                        logger.warning(f"Startup: reconnect failed for session {s.id}: {e}")

            if recovered:
                logger.info(f"Startup recovery: {recovered}/{len(sessions)} sessions reconnected")
            return recovered
        finally:
            db.close()

    def _check_and_recover(self, s: Session, db) -> bool:
        """检查单个 session 的 driver，死了就尝试恢复。返回是否执行了恢复操作。"""
        driver = _live_drivers_ref.get(s.id)

        # 1. driver 存在且活着 → 跳过
        if driver is not None and _ping_driver_ref(driver):
            return False

        # 2. driver 存在但死了 → 先清理
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
            if _live_drivers_ref.get(s.id) is not None:
                del _live_drivers_ref[s.id]

        # 3. 尝试 Grid 重连（快速，保留登录态）
        if s.grid_session_id:
            try:
                reconnected = _reconnect_via_grid_ref(s)
                if reconnected:
                    _live_drivers_ref[s.id] = reconnected
                    logger.info(f"Watchdog reconnected session {s.id} ({s.name}) via Grid")
                    return True
            except Exception as e:
                logger.warning(f"Watchdog reconnect failed for session {s.id}: {e}")

        # 4. Grid 重连失败 → 完整重启（复用 profile，需重新 LOGIN）
        try:
            node = db.query(GridInstance).filter(GridInstance.id == s.node_id).first()
            if node is None:
                logger.error(f"Watchdog: node {s.node_id} not found for session {s.id}")
                return False

            import os
            os.makedirs(s.profile_path, exist_ok=True)
            os.chmod(s.profile_path, 0o777)

            driver = _create_driver_ref(s.profile_path, grid_url=node.hub_url)
            _live_drivers_ref[s.id] = driver

            s.grid_session_id = driver.session_id
            if s.status == "ACTIVE":
                s.status = "LOGIN"  # 重启后需要重新确认登录态
                # 标记绑定 account 为 WAIT_LOGIN
                from services.account_service import AccountService
                for sa in s.accounts:
                    acc = sa.account
                    if acc and acc.status in ("ACTIVE", "IN_USE"):
                        AccountService.set_status(db, acc, "WAIT_LOGIN")
                        logger.info(f"Account {acc.id} ({acc.name}) → WAIT_LOGIN (session {s.id} restarted by watchdog)")
            db.commit()

            logger.info(f"Watchdog restarted session {s.id} ({s.name}) — status → LOGIN")
            return True
        except Exception as e:
            # 彻底失败 → 标记绑定 account 为 LOGIN_EXPIRED
            try:
                from services.account_service import AccountService
                for sa in s.accounts:
                    acc = sa.account
                    if acc and acc.status in ("ACTIVE", "IN_USE", "WAIT_LOGIN"):
                        AccountService.mark_login_expired(db, acc.id)
                        logger.warning(f"Account {acc.id} ({acc.name}) → LOGIN_EXPIRED (session {s.id} recovery failed)")
                db.commit()
            except Exception as ae:
                logger.error(f"Failed to mark accounts expired for session {s.id}: {ae}")
            logger.error(f"Watchdog full restart failed for session {s.id}: {e}")
            return False


# 进程级单例
watchdog = SessionWatchdog()