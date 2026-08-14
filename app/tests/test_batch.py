from conftest import create_account, set_account_active


def test_task_types_meta(client, auth_headers):
    r = client.get("/api/tasks/meta/types", headers=auth_headers)
    assert r.status_code == 200
    types = r.json()["types"]
    names = [t["type"] for t in types]
    assert "visit_url" in names
    assert "check_login_status" in names
    vt = [t for t in types if t["type"] == "visit_url"][0]
    assert "url" in vt["params_template"]
    assert vt["description"]


def test_create_task_with_retry_params(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    r = client.post("/api/tasks", json={
        "account_id": acc["id"], "type": "visit_url", "params": "{}",
        "max_retries": 3, "retry_delay_seconds": 60,
    }, headers=auth_headers)
    assert r.status_code == 200
    t = r.json()["task"]
    assert t["max_retries"] == 3
    assert t["retry_delay_seconds"] == 60


def test_batch_run_and_cancel(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    ids = []
    for _ in range(3):
        r = client.post("/api/tasks", json={"account_id": acc["id"], "type": "visit_url", "params": "{}"},
                        headers=auth_headers)
        ids.append(r.json()["task"]["id"])

    r = client.post("/api/tasks/batch-run", json={"task_ids": ids}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["queued"] == 3
    assert r.json()["skipped"] == []

    r = client.post("/api/tasks/batch-cancel", json={"task_ids": ids}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["cancelled"] == 3


def test_csv_import(client, auth_headers):
    csv_data = (
        "name,platform,notes,grid,login_indicator\n"
        "imp1,google,note1,Default,.avatar\n"
        "imp2,tiktok,,,\n"
    )
    r = client.post("/api/accounts/import",
                    files={"file": ("accounts.csv", csv_data, "text/csv")},
                    headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 2
    assert body["skipped"] == []

    accounts = client.get("/api/accounts", headers=auth_headers).json()["accounts"]
    by_name = {a["name"]: a for a in accounts}
    assert "imp1" in by_name and "imp2" in by_name
    assert by_name["imp1"]["login_indicator"] == ".avatar"
    assert by_name["imp1"]["notes"] == "note1"


def test_csv_import_skips_duplicates_and_bad_grid(client, auth_headers):
    csv_data = (
        "name,platform,grid\n"
        "imp1,google,Default\n"
        "imp1,google,Default\n"
        "imp3,tiktok,NoSuchGrid\n"
    )
    r = client.post("/api/accounts/import",
                    files={"file": ("accounts.csv", csv_data, "text/csv")},
                    headers=auth_headers)
    body = r.json()
    assert body["created"] == 1
    assert len(body["skipped"]) == 2
