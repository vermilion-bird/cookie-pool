import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import get_db
from models import BrowserSession

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(BrowserSession).filter(BrowserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session.to_dict()}


@router.delete("/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(BrowserSession).filter(BrowserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "CLOSED"
    session.closed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "closed"}