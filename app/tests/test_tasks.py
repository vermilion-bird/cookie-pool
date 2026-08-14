import json

from conftest import create_account, set_account_active
from database import SessionLocal
from models import Account, Task
from services.task_service import TaskService
from executors.registry import get_executor, registered_types, ExecutorError
import pytest


def _create_task(client, auth_headers, account_id, task_type="visit_url", params=None):
    r = client.post("/api/tasks", json={
        "account_id": account_id,
        "type": task_type,
        "params": params or "{}",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["task"]


class FakeExecutor:
    """测试用假执行器。"""
    task_type = "fake"

    def __init__(self, account):
        self.account = account

    @staticmethod
    def setup_browser(account, grid_url=None):
        return object()

    @staticmethod
    def teardown_browser(browser):
        pass

    def execute(self, db, browser, task):
        return {"ok": True}


class RaisingExecutor(FakeExecutor):
    task_type = "raising"

    def execute(self, db, browser, task):
        raise RuntimeError("boom")


def test_registry_has_builtin_executors():
    types = registered_types()
    assert "visit_url" in types
    assert "check_login_status" in types
    with pytest.raises(ExecutorError):
        get_executor("does_not_exist")


def test_create_task_validates_type(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    r = client.post("/api/tasks", json={"account_id": acc["id"], "type": "nope", "params": "{}"},
                    headers=auth_headers)
    assert r.status_code == 400
    assert "No executor" in r.json()["detail"]


def test_create_task_validates_json(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    r = client.post("/api/tasks", json={"account_id": acc["id"], "type": "visit_url", "params": "not-json"},
                    headers=auth_headers)
    assert r.status_code == 400


def test_run_task_queues_and_returns_fast(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    task = _create_task(client, auth_headers, acc["id"])
    r = client.post(f"/api/tasks/{task['id']}/run", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["queued"] is True
    # 仍为 PENDING（worker 未启动，测试环境不消费队列）
    fetched = client.get(f"/api/tasks/{task['id']}", headers=auth_headers).json()["task"]
    assert fetched["status"] == "PENDING"


def test_run_non_pending_rejected(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    task = _create_task(client, auth_headers, acc["id"])
    db = SessionLocal()
    t = db.query(Task).filter(Task.id == task["id"]).first()
    t.status = "COMPLETED"
    db.commit()
    db.close()
    r = client.post(f"/api/tasks/{task['id']}/run", headers=auth_headers)
    assert r.status_code == 400


def test_run_success_completes_and_releases_lock(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])

    db = SessionLocal()
    task = TaskService.create(db, acc["id"], "fake", "{}")
    task_id = task.id
    db.close()

    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    TaskService.run(db, task, FakeExecutor)
    db.refresh(task)
    assert task.status == "COMPLETED"
    assert json.loads(task.result) == {"ok": True}
    db.close()

    db = SessionLocal()
    account = db.query(Account).filter(Account.id == acc["id"]).first()
    assert account.status == "ACTIVE"
    db.close()


def test_run_executor_error_fails_task(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    db = SessionLocal()
    task = TaskService.create(db, acc["id"], "fake", "{}")
    task_id = task.id
    db.close()

    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    TaskService.run(db, task, RaisingExecutor)
    db.refresh(task)
    assert task.status == "FAILED"
    assert "boom" in task.error
    db.close()


def test_run_unknown_type_fails(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    db = SessionLocal()
    task = TaskService.create(db, acc["id"], "ghost_type", "{}")
    task_id = task.id
    db.close()

    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    TaskService.run(db, task)  # executor_cls=None -> registry lookup
    db.refresh(task)
    assert task.status == "FAILED"
    assert "No executor" in task.error
    db.close()


def test_run_account_not_active_fails(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")  # WAIT_LOGIN
    db = SessionLocal()
    task = TaskService.create(db, acc["id"], "fake", "{}")
    task_id = task.id
    db.close()

    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    TaskService.run(db, task, FakeExecutor)
    db.refresh(task)
    assert task.status == "FAILED"
    assert "not available" in task.error
    db.close()


def test_cancel_pending_task(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    task = _create_task(client, auth_headers, acc["id"])
    r = client.post(f"/api/tasks/{task['id']}/cancel", headers=auth_headers)
    assert r.status_code == 200
    fetched = client.get(f"/api/tasks/{task['id']}", headers=auth_headers).json()["task"]
    assert fetched["status"] == "CANCELLED"
