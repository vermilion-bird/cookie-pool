from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class Schedule(Base):
    """cron 定时调度：按计划为目标账号创建任务。account_id 为空 = 所有 ACTIVE 账号。"""

    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    cron = Column(String(64), nullable=False, comment="5 段 cron: 分 时 日 月 周(1-7)")
    task_type = Column(String(128), nullable=False)
    params = Column(Text, default="{}")
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True,
                        comment="null = 所有 ACTIVE 账号")
    enabled = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    account = relationship("Account", back_populates="schedules")

    def next_run_at(self):
        """下一个匹配时间（UTC ISO 字符串）。"""
        from services.cron import next_run
        nxt = next_run(self.cron, datetime.now(timezone.utc))
        return nxt.isoformat() if nxt else None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "cron": self.cron,
            "task_type": self.task_type,
            "params": self.params,
            "account_id": self.account_id,
            "enabled": self.enabled,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at() if self.enabled else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class GridInstance(Base):
    __tablename__ = "grid_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True, comment="Human-readable label")
    hub_url = Column(String(512), nullable=False, comment="Grid hub URL, e.g. http://selenium-hub:4444")
    novnc_base_url = Column(String(512), nullable=True, comment="noVNC access URL template, e.g. http://host:7901/vnc.html")
    status = Column(String(32), nullable=False, default="UNKNOWN")
    max_sessions = Column(Integer, nullable=False, default=1)
    notes = Column(Text, default="")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    accounts = relationship("Account", back_populates="grid", cascade="")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "hub_url": self.hub_url,
            "novnc_base_url": self.novnc_base_url,
            "status": self.status,
            "max_sessions": self.max_sessions,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    platform = Column(String(128), nullable=False)
    profile_path = Column(String(512), nullable=False)
    status = Column(String(32), nullable=False, default="WAIT_LOGIN")
    notes = Column(Text, default="")
    login_indicator = Column(String(512), nullable=True,
                             comment="Optional CSS selector used to verify login state")

    grid_id = Column(Integer, ForeignKey("grid_instances.id"), nullable=True)

    last_login_at = Column(DateTime, nullable=True)
    last_check_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    sessions = relationship("BrowserSession", back_populates="account", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="account", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="account", cascade="all, delete-orphan")
    grid = relationship("GridInstance", back_populates="accounts")

    def to_dict(self, include_grid=False):
        d = {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "profile_path": self.profile_path,
            "status": self.status,
            "notes": self.notes,
            "login_indicator": self.login_indicator,
            "grid_id": self.grid_id,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "last_check_at": self.last_check_at.isoformat() if self.last_check_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_grid and self.grid:
            d["grid"] = self.grid.to_dict()
        return d


class BrowserSession(Base):
    __tablename__ = "browser_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    grid_session_id = Column(String(128), nullable=True)
    novnc_url = Column(String(512), nullable=True)
    status = Column(String(32), nullable=False, default="CREATING")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="sessions")

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "grid_session_id": self.grid_session_id,
            "novnc_url": self.novnc_url,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }


# ── 新版常驻 Session：一个 Chrome 浏览器承载多个不同平台的 Account ──

class Session(Base):
    """常驻浏览器会话。启动后保持 Chrome 存活，可绑定多个不同平台的 Account，
    通过 noVNC 统一登录，按平台提取 cookie。"""

    __tablename__ = "sessions_v2"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, comment="Human label")
    node_id = Column(Integer, ForeignKey("grid_instances.id"), nullable=False,
                     comment="Chrome 运行在哪个 Grid 节点")
    grid_session_id = Column(String(128), nullable=True, comment="Selenium Grid session id")
    status = Column(String(32), nullable=False, default="IDLE",
                   comment="IDLE|CREATING|READY|LOGIN|ACTIVE|CLOSED|FAILED")
    profile_path = Column(String(512), nullable=False, comment="Chrome --user-data-dir")
    novnc_url = Column(String(512), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime, nullable=True)

    node = relationship("GridInstance")
    accounts = relationship("SessionAccount", back_populates="session",
                            cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "node_id": self.node_id,
            "grid_session_id": self.grid_session_id,
            "status": self.status,
            "profile_path": self.profile_path,
            "novnc_url": self.novnc_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "accounts": [sa.to_dict() for sa in self.accounts] if self.accounts else [],
        }


class SessionAccount(Base):
    """N:N join：Session 绑定的 Account，同一 Session 内同平台唯一。"""

    __tablename__ = "session_accounts_v2"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions_v2.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    platform = Column(String(128), nullable=False,
                      comment="冗余字段：用于 UNIQUE 约束和快速查询")

    bound_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("Session", back_populates="accounts")
    account = relationship("Account")

    # 业务约束：同一 Session 同一 Platform 只能有一个 Account
    __table_args__ = (
        UniqueConstraint("session_id", "platform", name="uq_session_platform"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "account_id": self.account_id,
            "platform": self.platform,
            "bound_at": self.bound_at.isoformat() if self.bound_at else None,
            "account": self.account.to_dict() if self.account else None,
        }


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    type = Column(String(128), nullable=False)
    params = Column(Text, default="{}")
    status = Column(String(32), nullable=False, default="PENDING")
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=0)
    retry_delay_seconds = Column(Integer, nullable=False, default=30)
    artifact_paths = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "type": self.type,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "artifact_paths": self.artifact_list(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def artifact_list(self) -> list:
        import json
        try:
            return json.loads(self.artifact_paths or "[]")
        except (ValueError, TypeError):
            return []