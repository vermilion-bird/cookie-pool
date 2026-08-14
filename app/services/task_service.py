import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import Task
from services.account_service import AccountService
from executors.registry import get_executor, ExecutorError, resolve_grid_url

logger = logging.getLogger(__name__)


class TaskService:
    TASK_STATUSES = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}

    @staticmethod
    def get_all(db: Session) -> list[Task]:
        return db.query(Task).order_by(Task.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, task_id: int) -> Task | None:
        return db.query(Task).filter(Task.id == task_id).first()

    @staticmethod
    def create(db: Session, account_id: int, task_type: str, params: str = "{}") -> Task:
        task = Task(
            account_id=account_id,
            type=task_type,
            params=params,
            status="PENDING",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        logger.info(f"Task {task.id} created: {task_type} (account {account_id})")
        return task

    @staticmethod
    def run(db: Session, task: Task, executor_cls=None) -> Task:
        """执行任务。executor_cls 为按 task.type 注册的执行器类（worker 传入）。
        若为 None 则按 task.type 从注册表查找。"""
        if task.status != "PENDING":
            return task

        try:
            executor_cls = executor_cls or get_executor(task.type)
        except ExecutorError as e:
            task.status = "FAILED"
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.warning(f"Task {task.id} failed: {e}")
            return task

        account = AccountService.acquire_lock(db, task.account_id)
        if not account:
            task.status = "FAILED"
            task.error = "Account not available (not ACTIVE)"
            task.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.warning(f"Task {task.id} failed: account {task.account_id} not available")
            return task

        task.status = "RUNNING"
        task.started_at = datetime.now(timezone.utc)
        db.commit()

        executor = executor_cls(account)
        browser = None
        try:
            grid_url = resolve_grid_url(account)
            browser = executor.setup_browser(account, grid_url=grid_url)
            result = executor.execute(db, browser, task)
            task.status = "COMPLETED"
            task.result = json.dumps(result, ensure_ascii=False) if result else "{}"
            task.completed_at = datetime.now(timezone.utc)
            logger.info(f"Task {task.id} completed")
        except Exception as e:
            task.status = "FAILED"
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)
            logger.error(f"Task {task.id} failed: {e}")
        finally:
            try:
                if browser is not None:
                    executor.teardown_browser(browser)
            except Exception:
                logger.exception(f"Teardown error for task {task.id}")
            AccountService.release_lock(db, task.account_id)
            db.commit()

        return task

    @staticmethod
    def cancel(db: Session, task_id: int) -> bool:
        task = TaskService.get_by_id(db, task_id)
        if not task or task.status in ("COMPLETED", "CANCELLED"):
            return False
        task.status = "CANCELLED"
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Task {task.id} cancelled")
        return True
