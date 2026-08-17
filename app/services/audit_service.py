"""审计日志服务。记录关键操作，支持查询。"""
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import AuditLog

logger = logging.getLogger(__name__)


def log(db: Session, event: str, entity_type: str, entity_id: int = None, detail: dict = None) -> AuditLog:
    """记录一条审计日志。不抛异常，失败仅记 warning。"""
    try:
        entry = AuditLog(
            event=event,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=json.dumps(detail, ensure_ascii=False) if detail else "",
        )
        db.add(entry)
        db.commit()
        return entry
    except Exception as e:
        logger.warning(f"Audit log failed ({event} {entity_type}#{entity_id}): {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def query(db: Session, entity_type: str = None, entity_id: int = None,
          event: str = None, limit: int = 100, offset: int = 0) -> list:
    """查询审计日志，支持按实体类型/ID/事件过滤。"""
    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.filter(AuditLog.entity_id == entity_id)
    if event:
        q = q.filter(AuditLog.event == event)
    return q.offset(offset).limit(limit).all()
