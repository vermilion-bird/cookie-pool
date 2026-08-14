def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_api_requires_key(client):
    assert client.get("/api/accounts").status_code == 401
    assert client.get("/api/accounts", headers={"X-API-Key": "wrong"}).status_code == 401


def test_api_accepts_valid_key(client, auth_headers):
    r = client.get("/api/accounts", headers=auth_headers)
    assert r.status_code == 200


def test_docs_require_key(client):
    assert client.get("/docs").status_code == 401


def test_health_reports_version_and_db(client):
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["version"]
