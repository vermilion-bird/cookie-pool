"""Session V2 login flow tests."""
from database import SessionLocal
from models import Session as SessionV2, GridInstance
from services.grid_service import GridService
from services.browser_service import BrowserService


class FakeDriver:
    session_id = "fake-session-v2-1"


def _ensure_session(db, name="test-session"):
    g = db.query(GridInstance).first()
    if not g:
        g = GridInstance(name="test-grid", hub_url="http://grid:4444", status="ONLINE")
        db.add(g)
        db.commit()
    s = SessionV2(
        name=name, node_id=g.id, status="IDLE",
        profile_path="/tmp/test-session-profile"
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _patch_driver(monkeypatch):
    """Patch GridService to return a fake driver instead of hitting a real Grid."""
    def fake_create(profile_path, grid_url=None):
        return FakeDriver()
    monkeypatch.setattr(GridService, "create_driver", staticmethod(fake_create))
    monkeypatch.setattr(GridService, "close_driver", staticmethod(lambda d: None))
    # Also stub capacity check
    monkeypatch.setattr(GridService, "check_capacity",
                        staticmethod(lambda node, live_drivers: {
                            "available": True, "active_sessions": 0,
                            "max_sessions": 1, "message": "0/1"
                        }))
    monkeypatch.setattr(GridService, "get_active_session_count",
                        staticmethod(lambda grid_url: 0))


def test_session_v2_start_login(client, auth_headers, monkeypatch):
    """POST /api/sessions/{id}/login 应启动浏览器并返回 LOGIN 状态。"""
    _patch_driver(monkeypatch)
    db = SessionLocal()
    s = _ensure_session(db, name="login-test")
    sid = s.id
    db.close()

    r = client.post(f"/api/sessions/{sid}/login", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["status"] == "LOGIN"
    assert body["session"]["grid_session_id"] == "fake-session-v2-1"
    assert "novnc_url" in body


def test_session_v2_complete_login(client, auth_headers, monkeypatch):
    """POST /api/sessions/{id}/login/complete 应将 LOGIN → ACTIVE。"""
    _patch_driver(monkeypatch)
    db = SessionLocal()
    s = _ensure_session(db, name="complete-test")
    sid = s.id
    db.close()

    # Start login first
    client.post(f"/api/sessions/{sid}/login", headers=auth_headers)

    # Complete
    r = client.post(f"/api/sessions/{sid}/login/complete", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # Verify
    r2 = client.get(f"/api/sessions/{sid}", headers=auth_headers)
    assert r2.json()["session"]["status"] == "ACTIVE"


def test_session_v2_cancel_login(client, auth_headers, monkeypatch):
    """POST /api/sessions/{id}/login/cancel 应关闭 session。"""
    _patch_driver(monkeypatch)
    db = SessionLocal()
    s = _ensure_session(db, name="cancel-test")
    sid = s.id
    db.close()

    client.post(f"/api/sessions/{sid}/login", headers=auth_headers)
    r = client.post(f"/api/sessions/{sid}/login/cancel", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_session_v2_complete_without_login(client, auth_headers):
    """不应允许在非 LOGIN 状态下 complete。"""
    db = SessionLocal()
    s = _ensure_session(db, name="idle-test")
    sid = s.id
    db.close()

    r = client.post(f"/api/sessions/{sid}/login/complete", headers=auth_headers)
    assert r.status_code == 400


def test_session_v2_restart(client, auth_headers, monkeypatch):
    """POST /api/sessions/{id}/restart 应重启浏览器并保留 profile。"""
    _patch_driver(monkeypatch)
    db = SessionLocal()
    s = _ensure_session(db, name="restart-test")
    sid = s.id
    db.close()

    # First login
    client.post(f"/api/sessions/{sid}/login", headers=auth_headers)
    client.post(f"/api/sessions/{sid}/login/complete", headers=auth_headers)

    # Restart
    r = client.post(f"/api/sessions/{sid}/restart", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["status"] == "LOGIN"
    assert "restarted" in body["message"].lower() or "Browser restarted" in body["message"]
