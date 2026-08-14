import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Account, BrowserSession, GridInstance
from services.account_service import AccountService
from services.grid_service import GridService
from services.browser_service import BrowserService
from config import HOST_ADDRESS, NOVNC_PORT

logger = logging.getLogger(__name__)
router = APIRouter()
grid_service = GridService()

LOGIN_KEYWORDS = ["login", "signin", "auth", "sign_in", "log_in"]


class AccountCreate(BaseModel):
    name: str
    platform: str
    notes: str = ""
    grid_id: int | None = None
    login_indicator: str | None = None


class AccountUpdate(BaseModel):
    name: str = None
    platform: str = None
    notes: str = None
    grid_id: int | None = None
    login_indicator: str | None = None


def _resolve_novnc_url(account: Account) -> str:
    """根据账号绑定的 Grid 确定 noVNC URL。
    优先使用 grid.novnc_base_url，否则回退到全局 NOVNC_PUBLIC_URL。"""
    if account.grid_id:
        grid = account.grid
        if grid and grid.novnc_base_url:
            return grid.novnc_base_url
    return f"http://{HOST_ADDRESS}:{NOVNC_PORT}/vnc.html"


def _resolve_grid_url(account: Account) -> str:
    """根据账号绑定的 Grid 确定 hub URL。"""
    if account.grid_id and account.grid:
        return account.grid.hub_url
    from config import GRID_URL
    return GRID_URL


@router.get("")
def list_accounts(db: Session = Depends(get_db)):
    accounts = AccountService.get_all(db)
    return {"accounts": [a.to_dict(include_grid=True) for a in accounts]}


@router.post("")
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    existing = db.query(Account).filter(Account.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account '{data.name}' already exists")

    # 验证 grid_id 存在（如果指定了）
    if data.grid_id is not None:
        grid = db.query(GridInstance).filter(GridInstance.id == data.grid_id).first()
        if not grid:
            raise HTTPException(status_code=400, detail=f"Grid {data.grid_id} not found")

    account = AccountService.create(db, name=data.name, platform=data.platform,
                                     notes=data.notes, grid_id=data.grid_id,
                                     login_indicator=data.login_indicator)
    return {"account": account.to_dict(include_grid=True)}


@router.post("/import")
async def import_accounts(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """CSV 批量导入账号。列：name, platform, notes, grid, login_indicator。"""
    import csv
    import io
    content = await file.read()
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    created, skipped = [], []
    for row in reader:
        name = (row.get("name") or "").strip()
        platform = (row.get("platform") or "").strip()
        if not name or not platform:
            skipped.append({"name": name, "reason": "missing name/platform"})
            continue
        if db.query(Account).filter(Account.name == name).first():
            skipped.append({"name": name, "reason": "already exists"})
            continue
        grid_id = None
        grid_name = (row.get("grid") or "").strip()
        if grid_name and grid_name.lower() != "default":
            grid = db.query(GridInstance).filter(GridInstance.name == grid_name).first()
            if not grid:
                skipped.append({"name": name, "reason": f"grid '{grid_name}' not found"})
                continue
            grid_id = grid.id
        account = AccountService.create(
            db, name=name, platform=platform,
            notes=(row.get("notes") or ""),
            grid_id=grid_id,
            login_indicator=((row.get("login_indicator") or "").strip() or None),
        )
        created.append(account.id)
    logger.info(f"CSV import: created {len(created)}, skipped {len(skipped)}")
    return {"created": len(created), "skipped": skipped}


@router.get("/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)):
    account = AccountService.get_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"account": account.to_dict(include_grid=True)}


@router.put("/{account_id}")
def update_account(account_id: int, data: AccountUpdate, db: Session = Depends(get_db)):
    """更新账号字段，包括 grid_id（关联到不同 Grid 实例）与 login_indicator。"""
    account = AccountService.get_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    kwargs = {}
    if data.name is not None:
        existing = db.query(Account).filter(
            Account.name == data.name, Account.id != account_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Account name '{data.name}' already exists")
        kwargs["name"] = data.name
    if data.platform is not None:
        kwargs["platform"] = data.platform
    if data.notes is not None:
        kwargs["notes"] = data.notes
    if data.grid_id is not None:
        grid = db.query(GridInstance).filter(GridInstance.id == data.grid_id).first()
        if not grid:
            raise HTTPException(status_code=400, detail=f"Grid {data.grid_id} not found")
        kwargs["grid_id"] = data.grid_id
    if data.grid_id is None and "grid_id" not in kwargs:
        # explicit set to None allowed
        kwargs["grid_id"] = None
    if data.login_indicator is not None:
        kwargs["login_indicator"] = data.login_indicator
    if data.login_indicator is None and "login_indicator" not in kwargs:
        kwargs["login_indicator"] = None

    updated = AccountService.update(db, account_id, **kwargs)
    return {"account": updated.to_dict(include_grid=True)}


@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    ok = AccountService.delete(db, account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "deleted"}


# ── Login Flow ──

@router.post("/{account_id}/login")
def start_login(account_id: int, db: Session = Depends(get_db)):
    account = AccountService.get_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status == "IN_USE":
        raise HTTPException(status_code=409, detail="Account is in use")

    # Close stale login sessions
    old_sessions = db.query(BrowserSession).filter(
        BrowserSession.account_id == account_id,
        BrowserSession.status.in_(["CREATING", "READY", "LOGIN"]),
    ).all()
    for s in old_sessions:
        s.status = "CLOSED"
        s.closed_at = datetime.now(timezone.utc)
    db.commit()

    session = BrowserSession(account_id=account_id, status="CREATING")
    db.add(session)
    db.commit()
    db.refresh(session)

    try:
        grid_url = _resolve_grid_url(account)
        browser = BrowserService(account, grid_service)
        browser.create_session(grid_url=grid_url)

        session.grid_session_id = browser.driver.session_id
        session.status = "READY"
        session.novnc_url = _resolve_novnc_url(account)
        session.status = "LOGIN"
        db.commit()
        logger.info(f"Login session {session.id} created for account {account_id} (grid_url={grid_url})")
    except Exception as e:
        session.status = "FAILED"
        session.closed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(f"Login session creation failed for account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create browser: {e}")

    return {
        "session": session.to_dict(),
        "novnc_url": session.novnc_url,
        "instructions": "Open the noVNC URL, log in to the target platform, then click 'Complete'.",
    }


@router.post("/{account_id}/login/complete")
def complete_login(account_id: int, db: Session = Depends(get_db)):
    """校验登录：不新建 driver，直接经 Grid REST 检查现有登录会话（避免 Profile 锁竞争）。"""
    account = AccountService.get_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    session = db.query(BrowserSession).filter(
        BrowserSession.account_id == account_id,
        BrowserSession.status == "LOGIN",
    ).order_by(BrowserSession.id.desc()).first()

    if not session:
        raise HTTPException(status_code=400, detail="No active login session found")

    is_logged_in = False
    if session.grid_session_id:
        grid_url = _resolve_grid_url(account)
        indicator = (account.login_indicator or "").strip()
        checked = False
        if indicator:
            found = GridService.session_has_selector(grid_url, session.grid_session_id, indicator)
            if found is not None:
                is_logged_in = found
                checked = True
            else:
                logger.warning(f"Selector check failed for account {account_id}; falling back to URL heuristic")
        if not checked:
            current_url = GridService.session_url(grid_url, session.grid_session_id)
            if current_url is None:
                logger.error(f"Cannot reach login session {session.grid_session_id} for account {account_id}")
                return {"status": "retry",
                        "message": "Cannot reach the login browser session. Please keep the browser open and try again."}
            lowered = current_url.lower()
            is_logged_in = not any(kw in lowered for kw in LOGIN_KEYWORDS)

    if is_logged_in:
        # 校验通过：关闭 Grid 会话释放资源，账号标记 ACTIVE
        if session.grid_session_id:
            GridService.delete_session(_resolve_grid_url(account), session.grid_session_id)
        AccountService.mark_logged_in(db, account)
        session.status = "COMPLETED"
        session.closed_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "ok", "message": "Login confirmed, account is now ACTIVE"}
    else:
        return {"status": "retry", "message": "Not logged in yet. Please complete login in the browser."}


@router.post("/{account_id}/login/cancel")
def cancel_login(account_id: int, db: Session = Depends(get_db)):
    session = db.query(BrowserSession).filter(
        BrowserSession.account_id == account_id,
        BrowserSession.status.in_(["CREATING", "READY", "LOGIN"]),
    ).order_by(BrowserSession.id.desc()).first()

    if not session:
        raise HTTPException(status_code=400, detail="No active login session")

    session.status = "CLOSED"
    session.closed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "cancelled"}