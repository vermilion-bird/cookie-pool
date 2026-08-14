from conftest import create_account, set_account_active
from database import SessionLocal
from models import Task
from services.task_service import TaskService


class FlakyExecutor:
    task_type = "flaky"

    def __init__(self, account):
        self.account = account

    @staticmethod
    def setup_browser(account, grid_url=None):
        return object()

    @staticmethod
    def teardown_browser(browser):
        pass

    def execute(self, db, browser, task):
        raise RuntimeError("always fails")


def _run(client, auth_headers, task_id, executor):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    TaskService.run(db, task, executor)
    db.refresh(task)
    result = (task.status, task.retry_count, task.error)
    db.close()
    return result


def test_retry_escalates_to_pending_then_failed(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])

    db = SessionLocal()
    task = TaskService.create(db, acc["id"], "flaky", "{}")
    task.max_retries = 2
    task.retry_delay_seconds = 1
    task_id = task.id
    db.commit()
    db.close()

    # 第 1 次失败 → PENDING (1/2)
    status, count, error = _run(client, auth_headers, task_id, FlakyExecutor)
    assert status == "PENDING"
    assert count == 1
    assert "will retry 1/2" in error

    # 第 2 次失败 → PENDING (2/2)
    status, count, error = _run(client, auth_headers, task_id, FlakyExecutor)
    assert status == "PENDING"
    assert count == 2
    assert "will retry 2/2" in error

    # 第 3 次失败 → 重试耗尽 → FAILED
    status, count, error = _run(client, auth_headers, task_id, FlakyExecutor)
    assert status == "FAILED"
    assert count == 2
    assert "will retry" not in error


def test_no_retry_without_config(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    db = SessionLocal()
    task = TaskService.create(db, acc["id"], "flaky", "{}")  # max_retries=0
    task_id = task.id
    db.close()

    status, count, error = _run(client, auth_headers, task_id, FlakyExecutor)
    assert status == "FAILED"
    assert count == 0


def test_retry_releases_account_lock(client, auth_headers):
    acc = create_account(client, auth_headers, name="acc")
    set_account_active(acc["id"])
    db = SessionLocal()
    task = TaskService.create(db, acc["id"], "flaky", "{}")
    task.max_retries = 1
    task_id = task.id
    db.commit()
    db.close()

    _run(client, auth_headers, task_id, FlakyExecutor)  # → PENDING

    from models import Account
    db = SessionLocal()
    account = db.query(Account).filter(Account.id == acc["id"]).first()
    assert account.status == "ACTIVE"  # 锁已释放，可再次重试
    db.close()
