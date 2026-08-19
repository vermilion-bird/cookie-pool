from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import Account, GridInstance
from services.grid_service import GridService
from config import PROFILES_DIR

logger = logging.getLogger(__name__)


class AccountService:
    ACCOUNT_STATUSES = {"WAIT_LOGIN", "ACTIVE", "IN_USE", "LOGIN_EXPIRED", "DISABLED", "ERROR"}

    @staticmethod
    def get_all(db: Session) -> list[Account]:
        return db.query(Account).order_by(Account.id).all()

    @staticmethod
    def get_by_id(db: Session, account_id: int) -> Account | None:
        return db.query(Account).filter(Account.id == account_id).first()

    @staticmethod
    def create(db: Session, name: str, platform: str, notes: str = "",
               grid_id: int = None, login_indicator: str = None) -> Account:
        profile_name = f"account_{name.strip().lower().replace(' ', '_')}"
        profile_path = os.path.join(PROFILES_DIR, profile_name)

        account = Account(
            name=name,
            platform=platform,
            profile_path=profile_path,
            status="WAIT_LOGIN",
            notes=notes,
            grid_id=grid_id,
            login_indicator=login_indicator,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        logger.info(f"Created account {account.id}: {name} ({platform}) grid_id={grid_id}")
        from services import audit_service
        audit_service.log(db, "account.created", "account", account.id, {"name": name, "platform": platform})
        return account

    @staticmethod
    def update(db: Session, account_id: int, **kwargs) -> Account | None:
        """Update account fields. Accepted: name, platform, notes, grid_id, login_indicator."""
        account = AccountService.get_by_id(db, account_id)
        if not account:
            return None
        for key in ("name", "platform", "notes", "grid_id", "login_indicator", "status"):
            if key in kwargs:
                setattr(account, key, kwargs[key])
        account.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(account)
        logger.info(f"Updated account {account_id}")
        return account

    @staticmethod
    def delete(db: Session, account_id: int) -> bool:
        account = AccountService.get_by_id(db, account_id)
        if not account:
            return False
        profile_path = account.profile_path

        # 清理关联数据：SessionAccount / Task / Schedule
        from models import SessionAccount, Task, Schedule
        db.query(SessionAccount).filter(SessionAccount.account_id == account_id).delete()
        db.query(Task).filter(Task.account_id == account_id).delete()
        db.query(Schedule).filter(Schedule.account_id == account_id).delete()

        db.delete(account)
        db.commit()
        logger.info(f"Deleted account {account_id}")
        from services import audit_service
        audit_service.log(db, "account.deleted", "account", account_id, {"name": account.name})

        # 清理磁盘上的 Profile（级联删除会话/任务后）
        if profile_path and os.path.isdir(profile_path):
            try:
                import shutil
                shutil.rmtree(profile_path, ignore_errors=True)
                logger.info(f"Removed profile directory: {profile_path}")
            except Exception as e:
                logger.warning(f"Failed to remove profile directory {profile_path}: {e}")
        return True

    @staticmethod
    def set_status(db: Session, account: Account, status: str) -> None:
        if status not in AccountService.ACCOUNT_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        account.status = status
        account.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Account {account.id} status → {status}")

    @staticmethod
    def acquire_lock(db: Session, account_id: int) -> Account | None:
        account = db.query(Account).filter(
            Account.id == account_id,
            Account.status == "ACTIVE",
        ).with_for_update().first()
        if account:
            AccountService.set_status(db, account, "IN_USE")
            account.last_used_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Account {account_id} acquired (IN_USE)")
        else:
            logger.warning(f"Account {account_id} not available for lock")
        return account

    @staticmethod
    def release_lock(db: Session, account_id: int) -> None:
        account = AccountService.get_by_id(db, account_id)
        if account and account.status == "IN_USE":
            AccountService.set_status(db, account, "ACTIVE")
            logger.info(f"Account {account_id} released (ACTIVE)")

    @staticmethod
    def mark_login_expired(db: Session, account_id: int) -> None:
        account = AccountService.get_by_id(db, account_id)
        if account:
            AccountService.set_status(db, account, "LOGIN_EXPIRED")
            account.last_check_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def release_stale_locks(db: Session, timeout_minutes: int = 15) -> int:
        """Release accounts stuck in IN_USE for too long (e.g. process crash)."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        stale = db.query(Account).filter(
            Account.status == "IN_USE",
            Account.last_used_at < cutoff,
        ).all()
        for acc in stale:
            AccountService.set_status(db, acc, "ACTIVE")
            logger.warning(f"Released stale IN_USE lock on account {acc.id} ({acc.name})")
        if stale:
            logger.info(f"Released {len(stale)} stale IN_USE lock(s)")
        return len(stale)

    @staticmethod
    def mark_logged_in(db: Session, account: Account) -> None:
        AccountService.set_status(db, account, "ACTIVE")
        account.last_login_at = datetime.now(timezone.utc)
        account.last_check_at = datetime.now(timezone.utc)
        db.commit()
        from services import audit_service
        audit_service.log(db, "account.login", "account", account.id, {"platform": account.platform})