"""Session v2 API — 常驻浏览器 + 多平台 Account 绑定 + Cookie 提取。"""
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import Session, SessionAccount, Account, GridInstance, BrowserSession
from services.account_service import AccountService
from services.grid_service import GridService
from config import HOST_ADDRESS, NOVNC_PORT, PROFILES_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions-v2"])

_live_drivers: dict[int, object] = {}

grid_service = GridService()


# ── Pydantic models ──

class SessionCreate(BaseModel):
    name: str
    node_id: int


class BindAccount(BaseModel):
    account_id: int


# ── Helpers ──

def _resolve_novnc_url(node: GridInstance) -> str:
    if node and node.novnc_base_url:
        return node.novnc_base_url
    return f"http://{HOST_ADDRESS}:{NOVNC_PORT}/vnc.html"


def _close_driver(session_id: int) -> None:
    driver = _live_drivers.pop(session_id, None)
    if driver is not None:
        GridService.close_driver(driver)


# ── CRUD ──

@router.post("")
def create_session(data: SessionCreate, db: DBSession = Depends(get_db)):
    """创建常驻 Session（不启动浏览器，仅 DB 记录）。"""
    node = db.query(GridInstance).filter(GridInstance.id == data.node_id).first()
    if not node:
        raise HTTPException(status_code=400, detail=f"Node {data.node_id} not found")

    existing = db.query(Session).filter(Session.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Session '{data.name}' already exists")

    profile_name = f"session_{data.name.strip().lower().replace(' ', '_')}"
    profile_path = os.path.join(PROFILES_DIR, profile_name)

    s = Session(
        name=data.name,
        node_id=data.node_id,
        status="IDLE",
        profile_path=profile_path,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    logger.info(f"Session {s.id} created: {data.name} (node={data.node_id})")
    return {"session": s.to_dict()}


@router.get("")
def list_sessions(db: DBSession = Depends(get_db)):
    sessions = db.query(Session).order_by(Session.created_at.desc()).all()
    return {"sessions": [s.to_dict() for s in sessions]}


@router.get("/{session_id}")
def get_session(session_id: int, db: DBSession = Depends(get_db)):
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": s.to_dict()}


@router.delete("/{session_id}")
def delete_session(session_id: int, db: DBSession = Depends(get_db)):
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    _close_driver(session_id)
    db.delete(s)
    db.commit()
    return {"status": "deleted"}


# ── Account 绑定 / 解绑 ──

@router.post("/{session_id}/accounts")
def bind_account(session_id: int, data: BindAccount, db: DBSession = Depends(get_db)):
    """绑定 Account 到 Session。同一 Session 内同 Platform 不能重复。"""
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    account = AccountService.get_by_id(db, data.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # 检查同 platform 约束
    existing = db.query(SessionAccount).filter(
        SessionAccount.session_id == session_id,
        SessionAccount.platform == account.platform,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Session already has an account for platform '{account.platform}': account #{existing.account_id}"
        )

    sa = SessionAccount(
        session_id=session_id,
        account_id=data.account_id,
        platform=account.platform,
    )
    db.add(sa)
    db.commit()
    db.refresh(sa)
    logger.info(f"Bound account {account.id} ({account.platform}) to session {session_id}")
    return {"session_account": sa.to_dict()}


@router.delete("/{session_id}/accounts/{account_id}")
def unbind_account(session_id: int, account_id: int, db: DBSession = Depends(get_db)):
    sa = db.query(SessionAccount).filter(
        SessionAccount.session_id == session_id,
        SessionAccount.account_id == account_id,
    ).first()
    if not sa:
        raise HTTPException(status_code=404, detail="Binding not found")
    db.delete(sa)
    db.commit()
    return {"status": "unbound"}


# ── Login 流程 ──

@router.post("/{session_id}/login")
def start_login(session_id: int, db: DBSession = Depends(get_db)):
    """启动常驻浏览器，返回 noVNC URL。复用已存活的 driver。"""
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    # 复用已存活 driver
    if session_id in _live_drivers and s.status == "ACTIVE":
        return {
            "session": s.to_dict(),
            "novnc_url": s.novnc_url,
            "message": "Browser already running",
        }

    # 关闭旧残留
    _close_driver(session_id)
    old = db.query(BrowserSession).filter(
        BrowserSession.status.in_(["CREATING", "READY", "LOGIN"]),
    ).all()
    for o in old:
        o.status = "CLOSED"; o.closed_at = datetime.now(timezone.utc)
    db.commit()

    s.status = "CREATING"
    db.commit()

    node = db.query(GridInstance).filter(GridInstance.id == s.node_id).first()
    try:
        os.makedirs(s.profile_path, exist_ok=True)
        os.chmod(s.profile_path, 0o777)

        driver = grid_service.create_driver(s.profile_path, grid_url=node.hub_url)
        _live_drivers[session_id] = driver

        s.grid_session_id = driver.session_id
        s.novnc_url = _resolve_novnc_url(node)
        s.status = "LOGIN"
        db.commit()
        logger.info(f"Session {session_id} login started (node={node.hub_url})")
    except Exception as e:
        _close_driver(session_id)
        s.status = "FAILED"
        s.closed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start browser: {e}")

    return {
        "session": s.to_dict(),
        "novnc_url": s.novnc_url,
        "message": "Open noVNC, log in to all bound platforms, then click Complete",
    }


@router.post("/{session_id}/login/complete")
def complete_login(session_id: int, db: DBSession = Depends(get_db)):
    """确认登录完成，标记 Session 为 ACTIVE。"""
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.status != "LOGIN":
        raise HTTPException(status_code=400, detail=f"Session is {s.status}, not in LOGIN")

    s.status = "ACTIVE"
    db.commit()

    # 标记所有绑定的 Account 为 ACTIVE
    for sa in s.accounts:
        acc = sa.account
        if acc and acc.status == "WAIT_LOGIN":
            AccountService.mark_logged_in(db, acc)

    return {"status": "ok", "message": "Session is now ACTIVE"}


@router.post("/{session_id}/login/cancel")
def cancel_login(session_id: int, db: DBSession = Depends(get_db)):
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    _close_driver(session_id)
    s.status = "CLOSED"
    s.closed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "cancelled"}


# ── Cookie 提取 ──

def _extract_session_cookies(s: Session, platform_filter: str = None) -> dict:
    """从存活的 session driver 提取 cookie，按 platform 过滤。"""
    driver = _live_drivers.get(s.id)
    if driver is None:
        raise HTTPException(status_code=400, detail="Session browser is not running. Start login first.")

    try:
        # CDP 全量获取
        result = driver.execute_cdp_cmd("Network.getAllCookies", {})
        cookies = result.get("cookies", [])
    except Exception:
        cookies = driver.get_cookies()

    if platform_filter:
        cookies = [c for c in cookies
                   if platform_filter.lower() in (c.get("domain") or "").lower()]

    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    return {
        "count": len(cookies),
        "cookie_string": cookie_str,
        "cookies": [
            {"name": c["name"], "value": c["value"], "domain": c.get("domain")}
            for c in cookies
        ],
    }


@router.get("/{session_id}/cookies/plain")
def get_cookies_plain(
    session_id: int,
    platform: str = Query(None, description="e.g. tiktok.com or google.com"),
    db: DBSession = Depends(get_db),
):
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    result = _extract_session_cookies(s, platform_filter=platform)
    return PlainTextResponse(result["cookie_string"])


@router.get("/{session_id}/cookies")
def get_cookies_json(
    session_id: int,
    platform: str = Query(None, description="e.g. tiktok.com or google.com"),
    db: DBSession = Depends(get_db),
):
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return _extract_session_cookies(s, platform_filter=platform)