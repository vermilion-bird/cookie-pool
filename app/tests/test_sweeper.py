from datetime import datetime, timedelta, timezone

from conftest import create_account
from database import SessionLocal
from models import BrowserSession, Account
from worker import SessionSweeper
from services import grid_service


def _stub_rest(monkeypatch):
    monkeypatch.setattr(grid_service.GridService, "delete_session",
                        staticmethod(lambda grid_url, session_id: None))


def test_sweeper_closes_stale_session(client, auth_headers, monkeypatch):
    _stub_rest(monkeypatch)
    acc = create_account(client, auth_headers, name="acc")

    db = SessionLocal()
    s = BrowserSession(
        account_id=acc["id"],
        status="LOGIN",
        grid_session_id="s1",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db.add(s)
    db.commit()
    sid = s.id
    db.close()

    closed = SessionSweeper().sweep_once()
    assert closed == 1

    db = SessionLocal()
    s2 = db.query(BrowserSession).filter(BrowserSession.id == sid).first()
    assert s2.status == "CLOSED"
    assert s2.closed_at is not None
    db.close()


def test_sweeper_keeps_fresh_session(client, auth_headers, monkeypatch):
    _stub_rest(monkeypatch)
    acc = create_account(client, auth_headers, name="acc")
    db = SessionLocal()
    db.add(BrowserSession(account_id=acc["id"], status="LOGIN",
                          created_at=datetime.now(timezone.utc)))
    db.commit()
    db.close()
    assert SessionSweeper().sweep_once() == 0
