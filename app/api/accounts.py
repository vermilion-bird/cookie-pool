import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from selenium.webdriver.remote.webdriver import WebDriver
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

# ---------------------------------------------------------------------------
# Login-session driver cache
# Keep the WebDriver alive while the user logs in through noVNC.
# Without this the driver goes out of scope after start_login() returns,
# its __del__ calls quit(), and the Grid browser disappears instantly.
# ---------------------------------------------------------------------------
_login_drivers: dict[int, WebDriver] = {}

def _close_login_driver(account_id: int) -> None:
    """Close and forget the login-session driver for *account_id*, if any."""
    driver = _login_drivers.pop(account_id, None)
    if driver is not None:
        GridService.close_driver(driver)
        logger.info(f"Login driver closed for account {account_id}")


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
def list_accounts(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    platform: str = None,
    db: Session = Depends(get_db),
):
    query = db.query(Account)
    if status:
        query = query.filter(Account.status == status)
    if platform:
        query = query.filter(Account.platform.ilike(f"%{platform}%"))
    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    accounts = query.order_by(Account.id.desc()).offset(offset).limit(page_size).all()
    return {
        "accounts": [a.to_dict(include_grid=True) for a in accounts],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


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

    # Reuse existing LOGIN session if its driver is still alive
    existing_session = db.query(BrowserSession).filter(
        BrowserSession.account_id == account_id,
        BrowserSession.status == "LOGIN",
    ).order_by(BrowserSession.id.desc()).first()

    if existing_session and account_id in _login_drivers:
        logger.info(f"Reusing existing login session {existing_session.id} for account {account_id}")
        return {
            "session": existing_session.to_dict(),
            "novnc_url": existing_session.novnc_url,
            "instructions": "Browser already open. Log in to the target platform, then click 'Complete'.",
        }

    # Close stale login sessions — also kill any orphaned driver
    old_sessions = db.query(BrowserSession).filter(
        BrowserSession.account_id == account_id,
        BrowserSession.status.in_(["CREATING", "READY", "LOGIN"]),
    ).all()
    for s in old_sessions:
        s.status = "CLOSED"
        s.closed_at = datetime.now(timezone.utc)
    _close_login_driver(account_id)
    db.commit()

    session = BrowserSession(account_id=account_id, status="CREATING")
    db.add(session)
    db.commit()
    db.refresh(session)

    try:
        grid_url = _resolve_grid_url(account)
        browser = BrowserService(account, grid_service)
        browser.create_session(grid_url=grid_url)

        # Persist the driver so it survives after this function returns —
        # otherwise the WebDriver.__del__ calls quit() and kills the browser.
        _login_drivers[account_id] = browser.driver

        session.grid_session_id = browser.driver.session_id
        session.status = "READY"
        session.novnc_url = _resolve_novnc_url(account)
        session.status = "LOGIN"
        db.commit()
        logger.info(f"Login session {session.id} created for account {account_id} (grid_url={grid_url})")
    except Exception as e:
        _close_login_driver(account_id)
        session.status = "FAILED"
        session.closed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(f"Login session creation failed for account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create browser: {e}")

    return {
        "session": session.to_dict(),
        "novnc_url": session.novnc_url,
        "instructions": "Open the noVNC URL in a new tab, log in to the target platform, then click 'Complete'.",
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

    try:
        # Reuse the existing login session driver (kept alive in _login_drivers)
        # instead of creating a brand-new driver that would conflict on the same
        # Chrome user-data-dir profile.
        driver = _login_drivers.get(account_id)
        if driver is None:
            raise HTTPException(
                status_code=400,
                detail="Login session driver not found — it may have timed out. Please restart login.",
            )
        browser = BrowserService(account, grid_service)
        browser.driver = driver
        is_logged_in = browser.check_login()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login check failed: {e}")
        is_logged_in = False

    if is_logged_in:
        _close_login_driver(account_id)
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

    _close_login_driver(account_id)
    session.status = "CLOSED"
    session.closed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "cancelled"}


# ── Cookie Extraction ──

def _extract_cookies(account: Account, domain: str = None) -> dict:
    """打开账号 profile 浏览器，提取所有 cookie。导航失败时通过 CDP 全量获取。"""
    grid_url = _resolve_grid_url(account)
    browser = BrowserService(account, grid_service)
    cookies = []
    try:
        browser.create_session(grid_url=grid_url)
        # 防止页面加载过慢导致长时间阻塞
        browser.driver.set_page_load_timeout(15)
        import time
        # 尝试导航到平台首页；无效 URL 或网络错误时回退到 CDP 全量获取
        platform = account.platform
        if not platform.startswith("http://") and not platform.startswith("https://"):
            platform = f"https://{platform}"
        try:
            browser.navigate(platform)
            time.sleep(1)
            cookies = browser.driver.get_cookies()
        except Exception:
            logger.warning(f"Navigate to {platform} failed, falling back to CDP Network.getAllCookies")
            try:
                result = browser.driver.execute_cdp_cmd("Network.getAllCookies", {})
                cookies = result.get("cookies", [])
            except Exception:
                cookies = browser.driver.get_cookies()

        if domain:
            cookies = [c for c in cookies if domain in (c.get("domain") or "")]
    finally:
        browser.close_session()

    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    return {
        "count": len(cookies),
        "cookie_string": cookie_str,
        "cookies": [
            {"name": c["name"], "value": c["value"], "domain": c.get("domain")}
            for c in cookies
        ],
    }


@router.get("/{account_id}/cookies/plain")
def get_cookies_plain(account_id: int, domain: str = None, db: Session = Depends(get_db)):
    """返回纯文本 cookie 字符串，可直接作为 HTTP Cookie header。"""
    from fastapi.responses import PlainTextResponse
    account = AccountService.get_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status not in ("ACTIVE", "IN_USE"):
        raise HTTPException(status_code=400, detail=f"Account status is {account.status}, not logged in")

    result = _extract_cookies(account, domain=domain)
    return PlainTextResponse(result["cookie_string"])


@router.get("/{account_id}/cookies")
def get_cookies(account_id: int, domain: str = None, db: Session = Depends(get_db)):
    """返回 JSON 格式的 cookie 列表。"""
    account = AccountService.get_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status not in ("ACTIVE", "IN_USE"):
        raise HTTPException(status_code=400, detail=f"Account status is {account.status}, not logged in")

    return _extract_cookies(account, domain=domain)