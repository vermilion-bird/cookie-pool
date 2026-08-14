import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Account
from services.task_service import TaskService
from executors.registry import get_executor, ExecutorError
from worker import worker

logger = logging.getLogger(__name__)
router = APIRouter()


class TaskCreate(BaseModel):
    account_id: int
    type: str
    params: str = "{}"


def _validate_payload(task_type: str, params: str) -> None:
    try:
        get_executor(task_type)
    except ExecutorError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        json.loads(params or "{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="params must be valid JSON")


@router.post("")
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == data.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {data.account_id} not found")
    _validate_payload(data.type, data.params)
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
    """把 PENDING 任务放入后台执行队列，立即返回。"""
    task = TaskService.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Task is {task.status}; only PENDING tasks can be queued")
    _validate_payload(task.type, task.params)
    worker.submit(task.id)
    logger.info(f"Task {task.id} queued for background execution")
    return {"task": task.to_dict(), "queued": True, "message": "Task queued for background execution"}


@router.post("/{task_id}/cancel")
def cancel_task(task_id: int, db: Session = Depends(get_db)):
    ok = TaskService.cancel(db, task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")
    return {"status": "cancelled"}
