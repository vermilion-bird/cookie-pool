import os

from conftest import create_account


def test_create_and_list(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc1")
    assert acc["status"] == "WAIT_LOGIN"
    assert acc["login_indicator"] is None
    assert acc["profile_path"].endswith("account_acc1")

    lst = client.get("/api/accounts", headers=auth_headers).json()["accounts"]
    assert len(lst) == 1


def test_create_duplicate_name(client, auth_headers):
    create_account(client, auth_headers, name="dup")
    r = client.post("/api/accounts", json={"name": "dup", "platform": "x"}, headers=auth_headers)
    assert r.status_code == 400


def test_create_invalid_grid(client, auth_headers):
    r = client.post("/api/accounts", json={"name": "a", "platform": "x", "grid_id": 999},
                    headers=auth_headers)
    assert r.status_code == 400


def test_update_account_fields(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    r = client.put(f"/api/accounts/{acc['id']}",
                   json={"notes": "hi", "login_indicator": ".avatar", "name": "renamed"},
                   headers=auth_headers)
    assert r.status_code == 200
    body = r.json()["account"]
    assert body["name"] == "renamed"
    assert body["notes"] == "hi"
    assert body["login_indicator"] == ".avatar"


def test_update_clear_login_indicator(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc", login_indicator=".x")
    r = client.put(f"/api/accounts/{acc['id']}", json={"login_indicator": None}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["account"]["login_indicator"] is None


def test_delete_removes_profile_dir(client, auth_headers):
    acc = create_account(client, auth_headers, name="gone")
    os.makedirs(acc["profile_path"], exist_ok=True)
    marker = os.path.join(acc["profile_path"], "marker.txt")
    with open(marker, "w") as f:
        f.write("x")

    r = client.delete(f"/api/accounts/{acc['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert not os.path.exists(acc["profile_path"])
    assert client.get("/api/accounts", headers=auth_headers).json()["accounts"] == []
