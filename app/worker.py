from __future__ import annotations
"""后台任务执行器与登录会话回收器。

TaskWorker: PENDING 任务入队后由 worker 线程异步执行（避免同步阻塞 HTTP 请求）。
SessionSweeper: 周期性回收超时的 Session V2 会话。
"""
import logging
import queue
import threading
from datetime import datetime, timedelta, timezone

from database import SessionLocal
from models import Session as SessionV2
from services.task_service import TaskService
from services.grid_service import GridService
from services.account_service import AccountService
from executors.registry import get_executor, ExecutorError

logger = logging.getLogger(__name__)

# 延迟引用：避免与 sessions_v2 的循环 import
_live_drivers_ref = None


def _resolve_live_drivers():  # -> Optional[dict]
    """延迟解析 sessions_v2._live_drivers，失败返回 None（sweeper 独立于 API 模块）。"""
    global _live_drivers_ref
    if _live_drivers_ref is None:
        try:
            from api.sessions_v2 import _live_drivers
            _live_drivers_ref = _live_drivers
        except Exception:
            logger.debug("Cannot resolve sessions_v2._live_drivers (API not loaded yet)")
            return None
    return _live_drivers_ref


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

    def submit(self, task_id: int, delay_seconds: float = 0) -> None:
        """入队任务；delay_seconds > 0 时延迟入队（用于失败重试）。"""
        if delay_seconds and delay_seconds > 0:
            t = threading.Timer(delay_seconds, self._queue.put, args=(task_id,))
            t.daemon = True
            t.start()
        else:
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
            db.refresh(task)
            # 失败且配置了重试：任务已被置回 PENDING，延迟重投
            if task.status == "PENDING" and task.retry_count > 0:
                self.submit(task.id, delay_seconds=task.retry_delay_seconds)
                logger.info(f"Task {task.id} scheduled for retry #{task.retry_count} "
                            f"in {task.retry_delay_seconds}s")
        finally:
            db.close()


class SessionSweeper:
    """周期性回收超时 Session V2 会话。

    CREATING / READY 超过 SESSION_V2_CREATING_TIMEOUT_MINUTES → FAILED
    LOGIN             超过 SESSION_V2_LOGIN_TIMEOUT_MINUTES   → FAILED
    同时释放 account IN_USE 锁泄漏。
    """

    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self._running = False
        self._thread = None  # type: threading.Thread | None

    @property
    def running(self) -> bool:
        return self._running

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

    # ── 公开入口 ──

    def sweep_once(self) -> int:
        """执行一轮全量回收，返回本轮关停的会话总数。"""
        db = SessionLocal()
        try:
            v2 = self._sweep_sessions_v2(db)
            locks = AccountService.release_stale_locks(db)
            zombies = self._sweep_grid_zombies(db)
            total = v2 + locks + zombies
            if total:
                logger.info(
                    f"SessionSweeper round: sessions_v2={v2} stale_locks={locks} grid_zombies={zombies}"
                )
            return total
        finally:
            db.close()

    # ── Session V2 回收 ──

    def _sweep_sessions_v2(self, db) -> int:
        """回收 Session V2 中长时间停留在中间状态的记录。

        中间状态分两档超时：
        - CREATING / READY → SESSION_V2_CREATING_TIMEOUT_MINUTES（默认 5 分钟）
        - LOGIN            → SESSION_V2_LOGIN_TIMEOUT_MINUTES（默认 30 分钟）
        """
        from config import SESSION_V2_CREATING_TIMEOUT_MINUTES, SESSION_V2_LOGIN_TIMEOUT_MINUTES
        now = datetime.now(timezone.utc)
        closed = 0

        # ── 档 1：CREATING / READY 超时 ──
        if SESSION_V2_CREATING_TIMEOUT_MINUTES > 0:
            cutoff_creating = now - timedelta(minutes=SESSION_V2_CREATING_TIMEOUT_MINUTES)
            stale_creating = db.query(SessionV2).filter(
                SessionV2.status.in_(["CREATING", "READY"]),
                SessionV2.created_at < cutoff_creating,
            ).all()
            for s in stale_creating:
                self._close_session_v2(s, db, reason=f"stuck in {s.status} for "
                                         f"{SESSION_V2_CREATING_TIMEOUT_MINUTES} min")
                s.status = "FAILED"
                s.closed_at = now
                closed += 1

        # ── 档 2：LOGIN 超时（仅当 driver 已死且超过时限）──
        if SESSION_V2_LOGIN_TIMEOUT_MINUTES > 0:
            cutoff_login = now - timedelta(minutes=SESSION_V2_LOGIN_TIMEOUT_MINUTES)
            stale_login = db.query(SessionV2).filter(
                SessionV2.status == "LOGIN",
                SessionV2.created_at < cutoff_login,
            ).all()
            for s in stale_login:
                # 关键：检查 driver 是否还活着，活着就跳过不关
                live_drivers = _resolve_live_drivers()
                driver_alive = False
                if live_drivers is not None:
                    drv = live_drivers.get(s.id)
                    if drv is not None:
                        try:
                            driver_alive = drv.execute_script("return 1") == 1
                        except Exception:
                            pass
                if driver_alive:
                    # Driver 活着 → 用户还在用，不关，只更新 created_at 防止下轮再触发
                    s.created_at = now
                    db.commit()
                    logger.info(f"SessionSweeper: session V2 {s.id} ({s.name}) driver alive, "
                                f"resetting timer")
                    continue

                self._close_session_v2(s, db, reason=f"stuck in LOGIN for "
                                             f"{SESSION_V2_LOGIN_TIMEOUT_MINUTES} min")
                s.status = "FAILED"
                s.closed_at = now
                closed += 1

        if closed:
            db.commit()
            logger.warning(f"SessionSweeper closed {closed} stale Session V2(s)")

        return closed

    def _close_session_v2(self, s: SessionV2, db, reason: str = "") -> None:
        """安全关闭一个 V2 Session：
        1. 经 Grid REST 删除 Grid 端会话（释放节点槽位）
        2. 关闭并移除本地 live driver（如果存在）
        3. 将绑定 Account 标记为 WAIT_LOGIN（未完成的登录回退）
        """
        logger.warning(f"SessionSweeper: closing session V2 {s.id} ({s.name}) — {reason}")

        # 1. 释放 Grid 节点槽位
        if s.grid_session_id and s.node:
            GridService.delete_session(s.node.hub_url, s.grid_session_id)

        # 2. 关闭本地 driver（如果还活着）
        live_drivers = _resolve_live_drivers()
        if live_drivers is not None:
            driver = live_drivers.pop(s.id, None)
            if driver is not None:
                GridService.close_driver(driver)
                logger.debug(f"SessionSweeper: closed live driver for session {s.id}")

        # 3. 绑定 Account 回退到 WAIT_LOGIN（登录未完成）
        #    直接赋值，由外层 sweep_once 统一 commit，避免嵌套事务
        now = datetime.now(timezone.utc)
        for sa in s.accounts:
            acc = sa.account
            if acc and acc.status in ("ACTIVE", "IN_USE", "LOGIN_EXPIRED") and acc.status != "WAIT_LOGIN":
                acc.status = "WAIT_LOGIN"
                acc.updated_at = now
                logger.info(f"Account {acc.id} ({acc.name}) → WAIT_LOGIN "
                            f"(session V2 {s.id} swept)")


    def _sweep_grid_zombies(self, db) -> int:
        """扫描所有 Grid 节点，清理并未被 DB 记录的僵尸 session。
        
        僵尸定义：Grid 上有 session 在运行，但 sessions_v2 表中没有对应 ACTIVE/LOGIN 状态的记录。
        这类 session 可能是：app 重启后 driver 丢失但 Grid 未清理、cleanup 失败残留等。
        """
        from services.grid_service import GridService
        from models import GridInstance

        cleaned = 0
        nodes = db.query(GridInstance).all()
        for node in nodes:
            # 收集该节点上 DB 已知的活跃 session ID
            known_ids = set()
            db_sessions = db.query(SessionV2).filter(
                SessionV2.node_id == node.id,
                SessionV2.status.in_(["ACTIVE", "LOGIN", "CREATING", "READY"]),
                SessionV2.grid_session_id.isnot(None),
            ).all()
            for s in db_sessions:
                if s.grid_session_id:
                    known_ids.add(s.grid_session_id)

            # 清理僵尸
            try:
                removed = GridService.cleanup_orphan_sessions(node.hub_url, known_ids)
                if removed:
                    cleaned += removed
                    logger.warning(
                        f"SessionSweeper: cleaned {removed} zombie session(s) from node '{node.name}'"
                    )
            except Exception as e:
                logger.warning(f"SessionSweeper: zombie scan failed for node '{node.name}': {e}")

        return cleaned


# 进程级单例：api 层入队、main lifespan 启停均使用此实例
worker = TaskWorker()
sweeper = SessionSweeper()
