"""后台任务执行器与登录会话回收器。

TaskWorker: PENDING 任务入队后由 worker 线程异步执行（避免同步阻塞 HTTP 请求）。
SessionSweeper: 周期性回收超时的登录会话（CREATING/READY/LOGIN）。
"""
import logging
import queue
import threading
from datetime import datetime, timedelta, timezone

from database import SessionLocal
from models import BrowserSession
from services.task_service import TaskService
from executors.registry import get_executor, ExecutorError

logger = logging.getLogger(__name__)


class TaskWorker:

    """后台任务执行队列。"""

    def __init__(self, num_workers: int = 2):
        self.num_workers = num_workers
        self._queue: "queue.Queue[int | None]" = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        for i in range(self.num_workers):
            t = threading.Thread(target=self._loop, name=f"task-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        logger.info(f"TaskWorker started ({self.num_workers} workers)")

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for _ in self._threads:
            self._queue.put(None)  # sentinel
        for t in self._threads:
            t.join(timeout=10)
        self._threads.clear()
        logger.info("TaskWorker stopped")

    def submit(self, task_id: int) -> None:
        self._queue.put(task_id)

    def _loop(self) -> None:
        while self._running:
            item = self._queue.get()
            if item is None:
                break
            try:
                self._process(item)
            except Exception:
                logger.exception(f"Worker error processing task {item}")
            finally:
                self._queue.task_done()

    def _process(self, task_id: int) -> None:
        db = SessionLocal()
        try:
            from models import Task
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.warning(f"Task {task_id} not found, skipping")
                return
            if task.status != "PENDING":
                logger.info(f"Task {task_id} status is {task.status}, skipping")
                return
            try:
                executor_cls = get_executor(task.type)
            except ExecutorError as e:
                task.status = "FAILED"
                task.error = str(e)
                task.completed_at = datetime.now(timezone.utc)
                db.commit()
                logger.warning(f"Task {task_id} failed: {e}")
                return
            TaskService.run(db, task, executor_cls)
        finally:
            db.close()


class SessionSweeper:
    """周期性回收超时登录会话。"""

    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="session-sweeper", daemon=True)
        self._thread.start()
        logger.info(f"SessionSweeper started (interval={self.interval_seconds}s)")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("SessionSweeper stopped")

    def _loop(self) -> None:
        import time
        while self._running:
            try:
                self.sweep_once()
            except Exception:
                logger.exception("SessionSweeper error")
            for _ in range(self.interval_seconds):
                if not self._running:
                    return
                time.sleep(1)

    def sweep_once(self) -> int:
        """回收超过 SESSION_TIMEOUT_MINUTES 未结束的登录会话，返回回收数量。"""
        from config import SESSION_TIMEOUT_MINUTES
        if SESSION_TIMEOUT_MINUTES <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        db = SessionLocal()
        try:
            stale = db.query(BrowserSession).filter(
                BrowserSession.status.in_(["CREATING", "READY", "LOGIN"]),
                BrowserSession.created_at < cutoff,
            ).all()
            closed = 0
            for s in stale:
                # 释放底层 Grid 会话，避免僵尸浏览器占用 Profile
                if s.account and s.account.grid and s.grid_session_id:
                    from services.grid_service import GridService
                    GridService.delete_session(s.account.grid.hub_url, s.grid_session_id)
                s.status = "CLOSED"
                s.closed_at = datetime.now(timezone.utc)
                closed += 1
            if closed:
                db.commit()
                logger.info(f"SessionSweeper closed {closed} stale login session(s)")
            return closed
        finally:
            db.close()


# 进程级单例：api 层入队、main lifespan 启停均使用此实例
worker = TaskWorker()
sweeper = SessionSweeper()
