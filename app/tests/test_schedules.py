from datetime import datetime, timezone

from conftest import create_account, set_account_active
from scheduler import SchedulerThread


def _create_schedule(client, auth_headers, cron="0 9 * * *", name="daily",
                     task_type="visit_url", params="{}", account_id=None):
    payload = {"name": name, "cron": cron, "task_type": task_type, "params": params}
    if account_id is not None:
        payload["account_id"] = account_id
    r = client.post("/api/schedules", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["schedule"]


def test_schedule_crud(client, auth_headers):
    s = _create_schedule(client, auth_headers)
    assert s["enabled"] is True
    assert s["next_run_at"] is not None

    lst = client.get("/api/schedules", headers=auth_headers).json()["schedules"]
    assert len(lst) == 1

    r = client.put(f"/api/schedules/{s['id']}",
                   json={"enabled": False, "cron": "0 10 * * *"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()["schedule"]
    assert body["enabled"] is False
    assert body["cron"] == "0 10 * * *"

    r = client.delete(f"/api/schedules/{s['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert client.get("/api/schedules", headers=auth_headers).json()["schedules"] == []


def test_schedule_invalid_cron_rejected(client, auth_headers):
    r = client.post("/api/schedules",
                    json={"name": "bad", "cron": "0 9 * *", "task_type": "visit_url"},
                    headers=auth_headers)
    assert r.status_code == 400


def test_schedule_invalid_type_rejected(client, auth_headers):
    r = client.post("/api/schedules",
                    json={"name": "bad", "cron": "0 9 * * *", "task_type": "nope"},
                    headers=auth_headers)
    assert r.status_code == 400


def test_schedule_unknown_account_rejected(client, auth_headers):
    r = client.post("/api/schedules",
                    json={"name": "bad", "cron": "0 9 * * *", "task_type": "visit_url",
                          "account_id": 999},
                    headers=auth_headers)
    assert r.status_code == 400


def test_schedule_trigger_creates_tasks(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    s = _create_schedule(client, auth_headers, account_id=acc["id"])
    r = client.post(f"/api/schedules/{s['id']}/trigger", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["triggered"] == 1
    tasks = client.get("/api/tasks", headers=auth_headers).json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["account_id"] == acc["id"]


def test_scheduler_tick_triggers_matching(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    _create_schedule(client, auth_headers, cron="* * * * *", name="everymin")
    created = SchedulerThread(tick_seconds=1).tick_once()
    assert created >= 1
    tasks = client.get("/api/tasks", headers=auth_headers).json()["tasks"]
    assert len(tasks) >= 1


def test_scheduler_tick_respects_enabled(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    s = _create_schedule(client, auth_headers, cron="* * * * *", name="disabled")
    client.put(f"/api/schedules/{s['id']}", json={"enabled": False}, headers=auth_headers)
    assert SchedulerThread(tick_seconds=1).tick_once() == 0


def test_scheduler_tick_no_accounts(client, auth_headers):
    """无 ACTIVE 账号且 schedule 未绑定账号 → 不创建任务。"""
    _create_schedule(client, auth_headers, cron="* * * * *", name="global")
    assert SchedulerThread(tick_seconds=1).tick_once() == 0
