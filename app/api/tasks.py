import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Account, Task
from services.task_service import TaskService
from executors.registry import get_executor, ExecutorError, list_task_types
from config import ARTIFACTS_DIR
from worker import worker

logger = logging.getLogger(__name__)
router = APIRouter()


class TaskCreate(BaseModel):
    account_id: int
    type: str
    params: str = "{}"
    max_retries: int = 0
    retry_delay_seconds: int = 30


class BatchTaskRequest(BaseModel):
    task_ids: list[int]


def _validate_payload(task_type: str, params: str) -> None:
    try:
        get_executor(task_type)
    except ExecutorError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        json.loads(params or "{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="params must be valid JSON")


# ── 静态路径需先于 /{task_id} 注册 ──

@router.get("/meta/types")
def get_task_types():
    """任务类型元数据（前端模板下拉）。"""
    return {"types": list_task_types()}


@router.post("/batch-run")
def batch_run_tasks(data: BatchTaskRequest, db: Session = Depends(get_db)):
    """批量入队 PENDING 任务。"""
    queued, skipped = 0, []
    for tid in data.task_ids:
        task = TaskService.get_by_id(db, tid)
        if not task or task.status != "PENDING":
            skipped.append(tid)
            continue
        try:
            get_executor(task.type)
        except ExecutorError:
            skipped.append(tid)
            continue
        worker.submit(tid)
        queued += 1
    logger.info(f"Batch run: queued {queued}, skipped {skipped}")
    return {"queued": queued, "skipped": skipped}


@router.post("/batch-cancel")
def batch_cancel_tasks(data: BatchTaskRequest, db: Session = Depends(get_db)):
    """批量取消 PENDING/RUNNING 任务。"""
    cancelled = 0
    for tid in data.task_ids:
        try:
            if TaskService.cancel(db, tid):
                cancelled += 1
        except Exception:
            pass
    return {"cancelled": cancelled}


@router.post("")
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == data.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {data.account_id} not found")
    _validate_payload(data.type, data.params)
    task = TaskService.create(db, data.account_id, data.type, data.params)
    task.max_retries = max(0, data.max_retries)
    task.retry_delay_seconds = max(1, data.retry_delay_seconds)
    db.commit()
    return {"task": task.to_dict()}


@router.get("")
def list_tasks(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    type: str = None,
    account_id: int = None,
    db: Session = Depends(get_db),
):
    query = db.query(Task)
    if status:
        query = query.filter(Task.status == status)
    if type:
        query = query.filter(Task.type == type)
    if account_id is not None:
        query = query.filter(Task.account_id == account_id)
    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    tasks = query.order_by(Task.created_at.desc()).offset(offset).limit(page_size).all()
    return {
        "tasks": [t.to_dict() for t in tasks],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


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


@router.get("/{task_id}/artifacts")
def list_artifacts(task_id: int, db: Session = Depends(get_db)):
    task = TaskService.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, "artifacts": task.artifact_list()}


@router.get("/{task_id}/artifacts/{artifact_name}")
def get_artifact(task_id: int, artifact_name: str, db: Session = Depends(get_db)):
    """下载任务产物（截图等），带路径穿越防护。"""
    task = TaskService.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    base = (Path(ARTIFACTS_DIR) / f"task_{task_id}").resolve()
    target = (base / artifact_name).resolve()
    if not str(target).startswith(str(base) + "/") or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(str(target))