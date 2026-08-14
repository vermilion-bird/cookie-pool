def test_health(client):
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["version"]
