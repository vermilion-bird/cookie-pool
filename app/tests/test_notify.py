from conftest import create_account, set_account_active
from database import SessionLocal
from models import Task
from services.task_service import TaskService
from notifiers import notify, EVENT_TASK_COMPLETED, EVENT_TASK_FAILED


def test_notify_noop_without_webhook(monkeypatch):
    monkeypatch.setattr("config.NOTIFY_WEBHOOK_URL", "")
    calls = []
    monkeypatch.setattr("notifiers._post_webhook", lambda url, body: calls.append(body))
    notify(EVENT_TASK_COMPLETED, {"task_id": 1})
    assert calls == []


def test_notify_posts_to_webhook(monkeypatch):
    monkeypatch.setattr("config.NOTIFY_WEBHOOK_URL", "https://hooks.example.com/x")
    calls = []
    monkeypatch.setattr("notifiers._post_webhook", lambda url, body: calls.append((url, body)))
    notify(EVENT_TASK_FAILED, {"task_id": 7, "error": "boom"})
    assert len(calls) == 1
    url, body = calls[0]
    assert url == "https://hooks.example.com/x"
    assert body["event"] == "task.failed"
    assert body["task_id"] == 7


def test_webhook_network_error_suppressed(monkeypatch):
    monkeypatch.setattr("config.NOTIFY_WEBHOOK_URL", "http://127.0.0.1:1/x")
    notify(EVENT_TASK_COMPLETED, {"task_id": 1})  # 不抛异常


def test_task_completion_triggers_notify(client, auth_headers, monkeypatch):
    monkeypatch.setattr("config.NOTIFY_WEBHOOK_URL", "https://hooks.example.com/x")
    events = []
    monkeypatch.setattr("notifiers._post_webhook", lambda url, body: events.append(body))
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])

    class OkExecutor:
        task_type = "ok"

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

    db = SessionLocal()
    task = TaskService.create(db, acc["id"], "ok", "{}")
    task_id = task.id
    db.close()

    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    TaskService.run(db, task, OkExecutor)
    db.close()

    assert any(e["event"] == "task.completed" and e["task_id"] == task_id for e in events)
