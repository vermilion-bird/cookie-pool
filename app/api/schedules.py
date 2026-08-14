import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Schedule, Account
from services.cron import parse_cron
from executors.registry import get_executor, ExecutorError
from services.task_service import TaskService
from worker import worker

logger = logging.getLogger(__name__)
router = APIRouter()


class ScheduleCreate(BaseModel):
    name: str
    cron: str
    task_type: str
    params: str = "{}"
    account_id: int | None = None
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: str = None
    cron: str = None
    task_type: str = None
    params: str = None
    account_id: int | None = None
    enabled: bool = None


def _validate(data) -> None:
    if data.cron is not None:
        try:
            parse_cron(data.cron)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid cron: {e}")
    if data.task_type is not None:
        try:
            get_executor(data.task_type)
        except ExecutorError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if data.params is not None:
        try:
            json.loads(data.params or "{}")
        except ValueError:
            raise HTTPException(status_code=400, detail="params must be valid JSON")


def _check_account(db: Session, account_id: int | None) -> None:
    if account_id is not None and not db.query(Account).filter(Account.id == account_id).first():
        raise HTTPException(status_code=400, detail=f"Account {account_id} not found")


@router.get("")
def list_schedules(db: Session = Depends(get_db)):
    schedules = db.query(Schedule).order_by(Schedule.id).all()
    return {"schedules": [s.to_dict() for s in schedules]}


@router.post("")
def create_schedule(data: ScheduleCreate, db: Session = Depends(get_db)):
    _validate(data)
    _check_account(db, data.account_id)
    s = Schedule(name=data.name, cron=data.cron, task_type=data.task_type,
                 params=data.params, account_id=data.account_id, enabled=data.enabled)
    db.add(s)
    db.commit()
    db.refresh(s)
    logger.info(f"Created schedule {s.id}: {s.name} ({s.cron})")
    return {"schedule": s.to_dict()}


@router.get("/{schedule_id}")
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"schedule": s.to_dict()}


@router.put("/{schedule_id}")
def update_schedule(schedule_id: int, data: ScheduleUpdate, db: Session = Depends(get_db)):
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    _validate(data)
    _check_account(db, data.account_id)
    if data.name is not None:
        s.name = data.name
    if data.cron is not None:
        s.cron = data.cron
    if data.task_type is not None:
        s.task_type = data.task_type
    if data.params is not None:
        s.params = data.params
    if data.enabled is not None:
        s.enabled = data.enabled
    if data.account_id is not None:
        s.account_id = data.account_id
    db.commit()
    db.refresh(s)
    return {"schedule": s.to_dict()}


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(s)
    db.commit()
    return {"status": "deleted"}


@router.post("/{schedule_id}/trigger")
def trigger_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """立即触发一次调度（手动运行，忽略 cron）。"""
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    from scheduler import SchedulerThread
    accounts = SchedulerThread._target_accounts(db, s)
    created = 0
    for acc in accounts:
        task = TaskService.create(db, acc.id, s.task_type, s.params)
        worker.submit(task.id)
        created += 1
    s.last_run_at = datetime.now(timezone.utc)
    db.commit()
    return {"triggered": created, "schedule": s.to_dict()}
