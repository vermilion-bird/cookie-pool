from __future__ import annotations
"""cron 调度线程：周期 tick，为匹配的 Schedule 创建任务并入队。"""
import logging
import threading
from datetime import datetime, timedelta, timezone

from database import SessionLocal
from models import Schedule, Account
from services.cron import matches
from services.task_service import TaskService

logger = logging.getLogger(__name__)


class SchedulerThread:
    """周期性检查 schedules 表并触发匹配的调度。"""

    def __init__(self, tick_seconds: int = 30):
        self.tick_seconds = tick_seconds
        self._running = False
        self._thread = None  # type: threading.Thread | None

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="cron-scheduler", daemon=True)
        self._thread.start()
        logger.info(f"SchedulerThread started (tick={self.tick_seconds}s)")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("SchedulerThread stopped")

    def _loop(self) -> None:
        import time
        while self._running:
            try:
                self.tick_once()
            except Exception:
                logger.exception("SchedulerThread tick error")
            for _ in range(self.tick_seconds):
                if not self._running:
                    return
                time.sleep(1)

    def tick_once(self) -> int:
        """触发当前时刻匹配的调度，为每个目标账号创建任务并入队。返回创建的任务数。"""
        from worker import worker
        now = datetime.now(timezone.utc)
        db = SessionLocal()
        created = 0
        try:
            schedules = db.query(Schedule).filter(Schedule.enabled.is_(True)).all()
            for s in schedules:
                if not self._cron_ok(s.cron, now):
                    continue
                # 同一分钟只触发一次（防止多个 tick 重复触发）
                if s.last_run_at and (now - s.last_run_at) < timedelta(minutes=1):
                    continue
                accounts = self._target_accounts(db, s)
                for acc in accounts:
                    task = TaskService.create(db, acc.id, s.task_type, s.params)
                    worker.submit(task.id)
                    created += 1
                s.last_run_at = now
                db.commit()
                if created:
                    logger.info(f"Schedule '{s.name}' triggered: {len(accounts)} task(s) created")
        finally:
            db.close()
        return created

    @staticmethod
    def _cron_ok(cron: str, now: datetime) -> bool:
        try:
            return matches(cron, now)
        except ValueError:
            logger.warning(f"Skipping invalid cron '{cron}'")
            return False

    @staticmethod
    def _target_accounts(db, schedule: Schedule) -> list:
        if schedule.account_id:
            acc = db.query(Account).filter(Account.id == schedule.account_id).first()
            return [acc] if acc else []
        return db.query(Account).filter(Account.status == "ACTIVE").all()

# 进程级单例：api 层手动触发、main lifespan 启停均使用此实例
scheduler = SchedulerThread()