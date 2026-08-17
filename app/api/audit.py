"""审计日志 API。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit_logs(
    entity_type: str = Query(None),
    entity_id: int = Query(None),
    event: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """查询审计日志（分页）。"""
    offset = (page - 1) * page_size
    logs = audit_service.query(db, entity_type=entity_type, entity_id=entity_id,
                               event=event, limit=page_size, offset=offset)
    # Count total for matching query
    from models import AuditLog
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.filter(AuditLog.entity_id == entity_id)
    if event:
        q = q.filter(AuditLog.event == event)
    total = q.count()
    return {
        "logs": [l.to_dict() for l in logs],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }
