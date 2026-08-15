import os
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import DB_PATH

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """WAL 提升多线程并发读写；busy_timeout 缓解写锁竞争；外键保证级联删除。"""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


class Base(DeclarativeBase):
    pass


def init_db():
    """Initialize database: create tables if not exist, run migrations."""
    from models import GridInstance, Account, BrowserSession, Session, SessionAccount, Task  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # ── Schema migrations ──
    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns("accounts")}

    # Add grid_id if missing (migration from v0.1.0)
    if "grid_id" not in existing_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE accounts ADD COLUMN grid_id INTEGER REFERENCES grid_instances(id)"))
            conn.commit()

    # Add login_indicator if missing (migration to v0.3.0)
    columns_now = {col["name"] for col in inspector.get_columns("accounts")}
    if "login_indicator" not in columns_now:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE accounts ADD COLUMN login_indicator VARCHAR(512)"))
            conn.commit()

    # Add Task retry/artifact columns (migration to v0.4.0)
    task_cols = {col["name"] for col in inspector.get_columns("tasks")}
    task_adds = {
        "retry_count": "INTEGER DEFAULT 0",
        "max_retries": "INTEGER DEFAULT 0",
        "retry_delay_seconds": "INTEGER DEFAULT 30",
        "artifact_paths": "TEXT DEFAULT '[]'",
    }
    for col, ddl in task_adds.items():
        if col not in task_cols:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {col} {ddl}"))
                conn.commit()

    # Auto-create default grid instance if the grid table is empty
    with SessionLocal() as db:
        from models import GridInstance as GI
        from config import GRID_URL, NOVNC_PUBLIC_URL, DEFAULT_GRID_NAME
        count = db.query(GI).count()
        if count == 0:
            default = GI(
                name=DEFAULT_GRID_NAME,
                hub_url=GRID_URL,
                novnc_base_url=NOVNC_PUBLIC_URL,
                status="UNKNOWN",
                max_sessions=1,
                notes="Auto-created default grid. Accounts without an explicit grid_id use this one.",
            )
            db.add(default)
            db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()