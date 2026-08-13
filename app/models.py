from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


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

    grid_id = Column(Integer, ForeignKey("grid_instances.id"), nullable=True)

    last_login_at = Column(DateTime, nullable=True)
    last_check_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    sessions = relationship("BrowserSession", back_populates="account", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="account", cascade="all, delete-orphan")
    grid = relationship("GridInstance", back_populates="accounts")

    def to_dict(self, include_grid=False):
        d = {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "profile_path": self.profile_path,
            "status": self.status,
            "notes": self.notes,
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


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    type = Column(String(128), nullable=False)
    params = Column(Text, default="{}")
    status = Column(String(32), nullable=False, default="PENDING")
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }