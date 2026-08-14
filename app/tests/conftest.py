import os
import sys
import tempfile

# 在导入任何 app 模块前设置测试环境
_tmp = tempfile.mkdtemp(prefix="cookie-pool-test-")
os.environ["DATA_DIR"] = _tmp
os.environ["API_KEY"] = "test-key"
os.environ.setdefault("GRID_URL", "http://test-hub:4444")
os.environ["CP_DISABLE_BACKGROUND"] = "1"  # 测试中不启动 worker/sweeper 线程

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # app/

import pytest
from fastapi.testclient import TestClient

from database import Base, engine
import models  # noqa: F401 — register models

TEST_API_KEY = "test-key"


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    from main import app
    with TestClient(app) as c:  # lifespan -> init_db + default grid
        yield c


@pytest.fixture()
def auth_headers():
    return {"X-API-Key": TEST_API_KEY}


def create_account(client, auth_headers, name="acc", platform="google", **extra):
    payload = {"name": name, "platform": platform, **extra}
    r = client.post("/api/accounts", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["account"]


def set_account_active(account_id):
    from database import SessionLocal
    from models import Account
    from services.account_service import AccountService
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        AccountService.mark_logged_in(db, account)
    finally:
        db.close()
