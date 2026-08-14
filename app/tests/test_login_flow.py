from conftest import create_account
from services.grid_service import GridService
from services.browser_service import BrowserService


class FakeDriver:
    session_id = "fake-session-1"


def _patch_browser(monkeypatch):
    def fake_create_session(self, grid_url=None):
        self.driver = FakeDriver()
    monkeypatch.setattr(BrowserService, "create_session", fake_create_session)


def test_start_login_creates_session(client, auth_headers, monkeypatch):
    _patch_browser(monkeypatch)
    acc = create_account(client, auth_headers, name="acc")
    r = client.post(f"/api/accounts/{acc['id']}/login", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["status"] == "LOGIN"
    assert body["session"]["grid_session_id"] == "fake-session-1"
    assert "novnc_url" in body


def test_complete_login_ok_via_url(client, auth_headers, monkeypatch):
    _patch_browser(monkeypatch)
    monkeypatch.setattr(GridService, "session_url",
                        staticmethod(lambda grid_url, session_id: "https://example.com/dashboard"))
    acc = create_account(client, auth_headers, name="acc")
    client.post(f"/api/accounts/{acc['id']}/login", headers=auth_headers)
    r = client.post(f"/api/accounts/{acc['id']}/login/complete", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    updated = client.get(f"/api/accounts/{acc['id']}", headers=auth_headers).json()["account"]
    assert updated["status"] == "ACTIVE"
    assert updated["last_login_at"] is not None


def test_complete_login_retry_on_login_url(client, auth_headers, monkeypatch):
    _patch_browser(monkeypatch)
    monkeypatch.setattr(GridService, "session_url",
                        staticmethod(lambda grid_url, session_id: "https://example.com/signin"))
    acc = create_account(client, auth_headers, name="acc")
    client.post(f"/api/accounts/{acc['id']}/login", headers=auth_headers)
    r = client.post(f"/api/accounts/{acc['id']}/login/complete", headers=auth_headers)
    assert r.json()["status"] == "retry"
    updated = client.get(f"/api/accounts/{acc['id']}", headers=auth_headers).json()["account"]
    assert updated["status"] == "WAIT_LOGIN"


def test_complete_login_uses_indicator(client, auth_headers, monkeypatch):
    _patch_browser(monkeypatch)
    monkeypatch.setattr(GridService, "session_has_selector",
                        staticmethod(lambda grid_url, session_id, sel: True))
    acc = create_account(client, auth_headers, name="acc", login_indicator=".avatar")
    client.post(f"/api/accounts/{acc['id']}/login", headers=auth_headers)
    r = client.post(f"/api/accounts/{acc['id']}/login/complete", headers=auth_headers)
    assert r.json()["status"] == "ok"


def test_complete_login_without_session(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    r = client.post(f"/api/accounts/{acc['id']}/login/complete", headers=auth_headers)
    assert r.status_code == 400
