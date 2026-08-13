import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import Account, GridInstance
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
               grid_id: int = None) -> Account:
        profile_name = f"account_{name.strip().lower().replace(' ', '_')}"
        profile_path = os.path.join(PROFILES_DIR, profile_name)

        account = Account(
            name=name,
            platform=platform,
            profile_path=profile_path,
            status="WAIT_LOGIN",
            notes=notes,
            grid_id=grid_id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        logger.info(f"Created account {account.id}: {name} ({platform}) grid_id={grid_id}")
        return account

    @staticmethod
    def update(db: Session, account_id: int, **kwargs) -> Account | None:
        """Update account fields. Accepted: name, platform, notes, grid_id."""
        account = AccountService.get_by_id(db, account_id)
        if not account:
            return None
        for key in ("name", "platform", "notes", "grid_id"):
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
        db.delete(account)
        db.commit()
        logger.info(f"Deleted account {account_id}")
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
    def mark_logged_in(db: Session, account: Account) -> None:
        AccountService.set_status(db, account, "ACTIVE")
        account.last_login_at = datetime.now(timezone.utc)
        account.last_check_at = datetime.now(timezone.utc)
        db.commit()