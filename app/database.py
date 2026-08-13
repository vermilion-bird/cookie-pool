import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import DB_PATH

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def init_db():
    """Initialize database: create tables if not exist, run migrations."""
    from models import GridInstance, Account, BrowserSession, Task  # noqa: F401 — register models
    Base.metadata.create_all(bind=engine)

    # ── Schema migrations ──
    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns("accounts")}

    # Add grid_id if missing (migration from v0.1.0)
    if "grid_id" not in existing_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE accounts ADD COLUMN grid_id INTEGER REFERENCES grid_instances(id)"))
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