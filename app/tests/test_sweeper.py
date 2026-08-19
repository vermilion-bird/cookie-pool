from datetime import datetime, timedelta, timezone

from database import SessionLocal
from models import Session as SessionV2, GridInstance
from services import grid_service
from services.grid_service import GridService


def _stub_rest(monkeypatch):
    monkeypatch.setattr(GridService, "delete_session",
                        staticmethod(lambda grid_url, session_id: None))
    monkeypatch.setattr(GridService, "close_driver",
                        staticmethod(lambda driver: None))


def _ensure_grid(db):
    g = db.query(GridInstance).first()
    if not g:
        g = GridInstance(name="test-grid", hub_url="http://grid:4444", status="ONLINE")
        db.add(g)
        db.commit()
    return g


def test_sweeper_sessions_v2_closes_stale_creating(client, auth_headers, monkeypatch):
    """CREATING 超过 5 分钟的 V2 Session 应被回收为 FAILED。"""
    _stub_rest(monkeypatch)
    db = SessionLocal()
    g = _ensure_grid(db)
    s = SessionV2(
        name="stale-creating",
        node_id=g.id,
        status="CREATING",
        profile_path="/tmp/test-profile",
        grid_session_id="s1",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    db.add(s)
    db.commit()
    sid = s.id
    db.close()

    from worker import SessionSweeper
    closed = SessionSweeper().sweep_once()
    assert closed >= 1  # may also include stale locks

    db = SessionLocal()
    s2 = db.query(SessionV2).filter(SessionV2.id == sid).first()
    assert s2 is not None
    assert s2.status == "FAILED"
    assert s2.closed_at is not None
    db.close()


def test_sweeper_sessions_v2_closes_stale_login(client, auth_headers, monkeypatch):
    """LOGIN 超时 + driver 不存在 → 回收为 FAILED。"""
    _stub_rest(monkeypatch)
    db = SessionLocal()
    g = _ensure_grid(db)
    s = SessionV2(
        name="stale-login",
        node_id=g.id,
        status="LOGIN",
        profile_path="/tmp/test-profile2",
        grid_session_id="s2",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=130),
    )
    db.add(s)
    db.commit()
    sid = s.id
    db.close()

    # 清理任何可能泄漏的 driver
    from api import sessions_v2
    sessions_v2._live_drivers.clear()

    from worker import SessionSweeper
    SessionSweeper().sweep_once()

    db = SessionLocal()
    s2 = db.query(SessionV2).filter(SessionV2.id == sid).first()
    assert s2.status == "FAILED", f"Expected FAILED, got {s2.status}"
    db.close()


def test_sweeper_skips_alive_login_driver(client, auth_headers, monkeypatch):
    """LOGIN 超时但 driver 还活着 → 跳过不关，重置 created_at 防止循环。"""
    _stub_rest(monkeypatch)
    from api import sessions_v2
    sessions_v2._live_drivers.clear()
    db = SessionLocal()
    g = _ensure_grid(db)
    old_time = datetime.now(timezone.utc) - timedelta(minutes=130)
    s = SessionV2(
        name="stale-but-alive",
        node_id=g.id,
        status="LOGIN",
        profile_path="/tmp/test-profile4",
        grid_session_id="s4",
        created_at=old_time,
    )
    db.add(s)
    db.commit()
    sid = s.id
    db.close()

    # 注入一个 fake driver 到 _live_drivers
    from api import sessions_v2
    class FakeDriver:
        def execute_script(self, script):
            return 1
    sessions_v2._live_drivers[sid] = FakeDriver()

    from worker import SessionSweeper
    SessionSweeper().sweep_once()

    db = SessionLocal()
    s2 = db.query(SessionV2).filter(SessionV2.id == sid).first()
    assert s2.status == "LOGIN", f"Expected LOGIN (alive driver skipped), got {s2.status}"
    # created_at should be refreshed (within last minute)
    now = datetime.now(timezone.utc)
    diff = (now - s2.created_at.replace(tzinfo=timezone.utc)).total_seconds()
    assert diff < 60, f"created_at should be refreshed, diff={diff}s"
    db.close()


def test_sweeper_keeps_fresh_session(client, auth_headers, monkeypatch):
    """刚创建的 V2 Session 不应被回收。"""
    _stub_rest(monkeypatch)
    db = SessionLocal()
    g = _ensure_grid(db)
    s = SessionV2(
        name="fresh-login",
        node_id=g.id,
        status="LOGIN",
        profile_path="/tmp/test-profile3",
        created_at=datetime.now(timezone.utc),
    )
    db.add(s)
    db.commit()
    db.close()

    from worker import SessionSweeper
    assert SessionSweeper().sweep_once() == 0
