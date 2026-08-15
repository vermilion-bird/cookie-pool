import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from services.task_service import TaskService
from services.browser_service import BrowserService
from services.grid_service import GridService

logger = logging.getLogger(__name__)
router = APIRouter()

grid_service = GridService()


class TaskCreate(BaseModel):
    account_id: int
    type: str
    params: str = "{}"


class DefaultTaskExecutor:
    """默认任务执行器 — 打开目标 URL 后截图返回。实际使用时子类化 BrowserService 重写 execute()。"""

    @staticmethod
    def setup_browser(account):
        browser = BrowserService(account, grid_service)
        browser.create_session()
        return browser

    @staticmethod
    def execute(db, browser, task) -> dict:
        params = json.loads(task.params) if task.params else {}
        target_url = params.get("url", "")
        if target_url:
            browser.navigate(target_url)
        return {"screenshot": "taken"}

    @staticmethod
    def teardown_browser(browser):
        browser.close_session()


task_executor = DefaultTaskExecutor()


@router.post("")
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    task = TaskService.create(db, data.account_id, data.type, data.params)
    return {"task": task.to_dict()}


@router.get("")
def list_tasks(db: Session = Depends(get_db)):
    tasks = TaskService.get_all(db)
    return {"tasks": [t.to_dict() for t in tasks]}


@router.get("/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = TaskService.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task.to_dict()}


@router.post("/{task_id}/run")
def run_task(task_id: int, db: Session = Depends(get_db)):
    """手动触发执行 PENDING 任务。"""
    task = TaskService.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task = TaskService.run(db, task, task_executor)
    return {"task": task.to_dict()}


@router.post("/{task_id}/cancel")
def cancel_task(task_id: int, db: Session = Depends(get_db)):
    ok = TaskService.cancel(db, task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")
    return {"status": "cancelled"}