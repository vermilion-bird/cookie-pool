from pathlib import Path

from conftest import create_account, set_account_active
from database import SessionLocal
from models import Task
from services.task_service import TaskService


class FakeDriver:
    def save_screenshot(self, path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fake-png-bytes")


class FakeExecutor:
    task_type = "fake"

    def __init__(self, account):
        self.account = account

    @staticmethod
    def setup_browser(account, grid_url=None):
        return type("Browser", (), {"driver": FakeDriver()})()

    @staticmethod
    def teardown_browser(browser):
        pass

    def execute(self, db, browser, task):
        from executors.registry import save_screenshot
        shot = save_screenshot(browser, task)
        return {"screenshot": shot}


def test_artifacts_collected_and_served(client, auth_headers):
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
    assert task.artifact_list() == ["screenshot.png"]
    db.close()

    # 列表接口
    lst = client.get(f"/api/tasks/{task_id}/artifacts", headers=auth_headers).json()
    assert lst["artifacts"] == ["screenshot.png"]

    # 下载接口
    r = client.get(f"/api/tasks/{task_id}/artifacts/screenshot.png", headers=auth_headers)
    assert r.status_code == 200
    assert r.content == b"fake-png-bytes"

    # 路径穿越防护
    r2 = client.get(f"/api/tasks/{task_id}/artifacts/..%2F..%2Fetc%2Fpasswd", headers=auth_headers)
    assert r2.status_code in (404, 422)


def test_artifacts_empty_for_no_files(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    db = SessionLocal()
    task = TaskService.create(db, acc["id"], "fake", "{}")
    task_id = task.id
    db.close()
    r = client.get(f"/api/tasks/{task_id}/artifacts", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["artifacts"] == []
