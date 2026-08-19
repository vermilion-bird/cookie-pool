from __future__ import annotations
"""Session v2 API — 常驻浏览器 + 多平台 Account 绑定 + Cookie 提取。"""
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import Session, SessionAccount, Account, GridInstance
from services.account_service import AccountService
from services.grid_service import GridService
from config import HOST_ADDRESS, NOVNC_PORT, PROFILES_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions-v2"])

_live_drivers: dict[int, object] = {}
_session_locks: dict[int, object] = {}  # threading.Lock per session — prevent concurrent driver creation
_import_lock = __import__("threading").Lock()

grid_service = GridService()


def _get_session_lock(session_id: int):
    """获取 session 级别的互斥锁（按需创建，线程安全）。"""
    if session_id not in _session_locks:
        with _import_lock:
            if session_id not in _session_locks:
                _session_locks[session_id] = __import__("threading").Lock()
    return _session_locks[session_id]


# ── Pydantic models ──

class SessionCreate(BaseModel):
    name: str
    node_id: int


class BindAccount(BaseModel):
    account_id: int


# ── Helpers ──

def _resolve_novnc_url(node: GridInstance) -> str:
    """解析 noVNC URL。
    
    优先使用全局 HOST_ADDRESS + NOVNC_PORT 配置（保证一致性），
    仅当 Grid 是远程外部节点时才使用其自定义 novnc_base_url。
    """
    # 远程外部 Grid（非内部 Default）使用自定义 URL
    if node and node.novnc_base_url and node.name != "Default Internal Grid":
        url = node.novnc_base_url.strip()
        if url and url.startswith("http"):
            return url
    # 内部 Grid 和兜底：使用全局配置
    host = HOST_ADDRESS or "127.0.0.1"
    port = NOVNC_PORT or "7901"
    return f"http://{host}:{port}/vnc.html"


def _close_driver(session_id: int) -> None:
    """安全关闭 session driver，清理 _live_drivers 和 Grid 侧 session。
    
    确保：
    1. 从 _live_drivers 移除
    2. Selenium driver.quit()（释放本地连接）
    3. Grid REST DELETE（释放节点槽位）一 driver.quit 失败时作为兜底
    """
    driver = _live_drivers.pop(session_id, None)
    if driver is not None:
        try:
            GridService.close_driver(driver)
        except Exception as e:
            logger.warning(f"Error closing driver for session {session_id}: {e}")
    # 同时清理 session 锁
    _session_locks.pop(session_id, None)


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

    # 如果 Session 已经是 ACTIVE，绑定 Account 自动标记为已登录
    if s.status == "ACTIVE" and account.status == "WAIT_LOGIN":
        AccountService.mark_logged_in(db, account)
        logger.info(f"Account {account.id} ({account.name}) auto-promoted to ACTIVE (session {session_id} is ACTIVE)")

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
    """启动常驻浏览器，返回 noVNC URL。复用已存活的 driver；死 driver 自动重启。"""
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    node = db.query(GridInstance).filter(GridInstance.id == s.node_id).first()
    if not node:
        raise HTTPException(status_code=500, detail=f"Grid node {s.node_id} not found")

    # ── 检查已有 driver 是否存活 ──
    existing = _live_drivers.get(session_id)
    if existing is not None and _ping_driver(existing):
        # Driver 存活 → 直接复用（同时刷新 noVNC URL 防止端口变化）
        if s.status not in ("LOGIN", "ACTIVE"):
            s.status = "LOGIN"
        fresh_novnc = _resolve_novnc_url(node)
        if s.novnc_url != fresh_novnc:
            s.novnc_url = fresh_novnc
            logger.info(f"Session {session_id}: updated novnc_url → {fresh_novnc}")
        db.commit()
        return {
            "session": s.to_dict(),
            "novnc_url": fresh_novnc,
            "message": "Browser already running",
        }

    # ── Driver 已死或不存在 → 关闭残留 + 重建（复用 profile 保留登录态）─
    _close_driver(session_id)

    # 强制清理 Grid 侧孤儿 session（driver 不在内存时 _close_driver 无法清理）
    if s.grid_session_id:
        try:
            grid_service.delete_session(node.hub_url, s.grid_session_id)
            logger.info(f"Cleared orphan Grid session {s.grid_session_id} before login")
        except Exception:
            logger.debug(f"No orphan to clear or delete failed: {s.grid_session_id}")

    s.status = "CREATING"
    db.commit()

    # ── 容量检查：Grid 是否还有空闲 session 槽位 ──
    cap = grid_service.check_capacity(node, _live_drivers)
    if not cap["available"]:
        s.status = "FAILED"
        s.closed_at = datetime.now(timezone.utc)
        db.commit()
        # 查找可用的替代 Grid
        alt_nodes = db.query(GridInstance).filter(
            GridInstance.id != s.node_id,
        ).all()
        alt_info = ""
        for alt in alt_nodes:
            alt_cap = grid_service.check_capacity(alt, _live_drivers)
            if alt_cap["available"]:
                alt_info += f"  {alt.name} ({alt.hub_url}): {alt_cap['message']}\n"
        suggestion = f"\nAvailable alternatives:\n{alt_info}" if alt_info else " No other nodes available."
        raise HTTPException(
            status_code=503,
            detail=f"Grid node '{node.name}' is at capacity ({cap['message']}).{suggestion}",
        )

    # ── Session 锁：防止并发创建 driver 导致 Profile 损坏 ──
    lock = _get_session_lock(session_id)
    acquired = lock.acquire(timeout=30)  # 最多等 30s，超时说明另一个操作卡住了
    if not acquired:
        raise HTTPException(
            status_code=409,
            detail="Another operation is in progress for this session. Please wait and retry.",
        )
    try:
        # 双重检查：获取锁后再次确认没有并发创建了 driver
        existing = _live_drivers.get(session_id)
        if existing is not None and _ping_driver(existing):
            if s.status not in ("LOGIN", "ACTIVE"):
                s.status = "LOGIN"
                db.commit()
            return {
                "session": s.to_dict(),
                "novnc_url": s.novnc_url or _resolve_novnc_url(node),
                "message": "Browser already running (race condition resolved)",
            }

        os.makedirs(s.profile_path, exist_ok=True)
        os.chmod(s.profile_path, 0o777)

        driver = grid_service.create_driver(s.profile_path, grid_url=node.hub_url)
        _live_drivers[session_id] = driver

        s.grid_session_id = driver.session_id
        s.novnc_url = _resolve_novnc_url(node)
        s.status = "LOGIN"
        s.closed_at = None
        db.commit()
        logger.info(f"Session {session_id} login started (node={node.hub_url}, profile={s.profile_path})")
    except Exception as e:
        _close_driver(session_id)
        s.status = "FAILED"
        s.closed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start browser: {e}")
    finally:
        lock.release()

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

    # 标记所有绑定的 Account 为 ACTIVE（含之前被 sweeper 标记的 LOGIN_EXPIRED）
    for sa in s.accounts:
        acc = sa.account
        if acc and acc.status in ("WAIT_LOGIN", "LOGIN_EXPIRED", "IN_USE"):
            AccountService.mark_logged_in(db, acc)
            logger.info(f"Account {acc.id} ({acc.name}) → ACTIVE (session {session_id} completed)")

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


# ── Health ──

def _ping_driver(driver) -> bool:
    """轻量 ping：执行 return 1，成功即存活。"""
    try:
        return driver.execute_script("return 1") == 1
    except Exception:
        return False


def _get_grid_status(hub_url: str, timeout: int = 5) -> dict | None:
    """获取 Grid /status 响应。"""
    try:
        import urllib.request, json as _json
        resp = urllib.request.urlopen(f"{hub_url}/status", timeout=timeout)
        return _json.loads(resp.read())
    except Exception:
        return None


def _find_active_grid_session_id(hub_url: str) -> str | None:
    """从 Grid /status 端点查找当前活跃的 session ID。"""
    data = _get_grid_status(hub_url)
    if not data:
        return None
    for node in data.get("value", {}).get("nodes", []):
        for slot in node.get("slots", []):
            sess = slot.get("session")
            if sess and sess.get("sessionId"):
                return sess["sessionId"]
    return None


def _reconnect_via_grid(s: Session):  # -> Optional[Any]
    """通过已存储的 grid_session_id 尝试重新连接到已有的 Grid session。"""
    if not s.grid_session_id:
        return None
    node = s.node
    if not node:
        return None
    return _attach_driver_to_session(node.hub_url, s.grid_session_id)


def _attach_driver_to_session(hub_url: str, grid_session_id: str):  # -> Optional[Any]
    """挂载 WebDriver 到已有 Grid session，不创建新 session、不消耗 Grid 槽位。
    
    策略：
    1. 先尝试创建 Remote driver（需要空闲 slot）→ 成功则 swap session ID
    2. 若无空闲 slot → 直接构造 driver 对象，手动设置 session_id"""
    try:
        from selenium import webdriver
        from selenium.webdriver.remote.remote_connection import RemoteConnection
        chrome_options = webdriver.ChromeOptions()
        executor = RemoteConnection(hub_url)
        executor.set_timeout(10)
        driver = webdriver.Remote(
            command_executor=executor,
            options=chrome_options,
        )
        temp_sid = driver.session_id
        driver.session_id = grid_session_id
        try:
            grid_service.delete_session(hub_url, temp_sid)
        except Exception:
            logger.debug(f"Failed to clean up temp session {temp_sid}")
        driver.execute_script("return 1")
        logger.info(f"Attached driver to Grid session {grid_session_id}")
        return driver
    except Exception as e:
        logger.debug(f"Cannot attach driver to session {grid_session_id}: {e}")
        return None


@router.get("/{session_id}/health")
def session_health(session_id: int, db: DBSession = Depends(get_db)):
    """检查 session 浏览器是否存活（仅检查内存 driver）。"""
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    driver = _live_drivers.get(session_id)
    alive = driver is not None and _ping_driver(driver)

    return {
        "session_id": session_id,
        "status": s.status,
        "alive": alive,
        "driver_exists": driver is not None,
        "grid_session_id": s.grid_session_id,
    }


@router.post("/{session_id}/restart")
def restart_session(session_id: int, db: DBSession = Depends(get_db)):
    """重启 session 浏览器（复用同一 profile，保留登录态）。"""
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if s.status not in ("LOGIN", "ACTIVE", "FAILED", "CLOSED"):
        raise HTTPException(status_code=400,
                            detail=f"Session is {s.status}; only LOGIN/ACTIVE/FAILED/CLOSED can be restarted")

    # ── Session 锁：防止并发操作导致 Profile 损坏 ──
    lock = _get_session_lock(session_id)
    acquired = lock.acquire(timeout=30)
    if not acquired:
        raise HTTPException(
            status_code=409,
            detail="Another operation is in progress for this session. Please wait and retry.",
        )
    try:
        # 关闭旧 driver
        _close_driver(session_id)

        node = db.query(GridInstance).filter(GridInstance.id == s.node_id).first()
        if not node:
            raise HTTPException(status_code=500, detail=f"Grid node {s.node_id} not found")

        # 强制清理 Grid 侧孤儿 session（driver 不在内存时 _close_driver 无法清理）
        if s.grid_session_id:
            try:
                grid_service.delete_session(node.hub_url, s.grid_session_id)
                logger.info(f"Cleared orphan Grid session {s.grid_session_id} before restart")
            except Exception:
                logger.debug(f"No orphan to clear or delete failed: {s.grid_session_id}")

        os.makedirs(s.profile_path, exist_ok=True)
        os.chmod(s.profile_path, 0o777)

        driver = grid_service.create_driver(s.profile_path, grid_url=node.hub_url)
        _live_drivers[session_id] = driver

        s.grid_session_id = driver.session_id
        s.novnc_url = _resolve_novnc_url(node)
        s.status = "LOGIN"
        s.closed_at = None
        db.commit()

        # 重启后浏览器需要重新确认登录 → 绑定 account 退回 WAIT_LOGIN
        for sa in s.accounts:
            acc = sa.account
            if acc and acc.status in ("ACTIVE", "IN_USE"):
                AccountService.set_status(db, acc, "WAIT_LOGIN")
                logger.info(f"Account {acc.id} ({acc.name}) → WAIT_LOGIN (session {session_id} restarted)")

        logger.info(f"Session {session_id} restarted (profile={s.profile_path})")
    except Exception as e:
        _close_driver(session_id)
        s.status = "FAILED"
        s.closed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to restart browser: {e}")
    finally:
        lock.release()

    return {
        "session": s.to_dict(),
        "novnc_url": s.novnc_url,
        "message": "Browser restarted with same profile. Open noVNC to verify login state, then click Complete.",
    }


# ── Cookie 提取 ──

def _extract_session_cookies(s: Session, platform_filter: str = None) -> dict:
    """从存活的 session driver 提取 cookie，按 platform 过滤。

    稳定性增强：
    - 最多 3 次重试（指数退避：1s / 2s / 4s）
    - CDP 优先（全量 cookie），失败回退到 Selenium get_cookies()
    - driver 死时自动尝试 Grid 重连
    - 所有尝试均失败后返回明确错误
    """
    import time

    max_attempts = 3
    last_error = None

    for attempt in range(max_attempts):
        driver = _live_drivers.get(s.id)

        # 检查 liveness；driver 对象存在但已死时尝试 Grid 重连
        if driver is not None and not _ping_driver(driver):
            logger.warning(
                f"Session {s.id} driver is dead (attempt {attempt+1}/{max_attempts}), "
                f"attempting Grid reconnect"
            )
            reconnected = _reconnect_via_grid(s)
            if reconnected:
                _live_drivers[s.id] = reconnected
                driver = reconnected
            else:
                driver = None

        if driver is None:
            last_error = "Session browser is not running. Call POST /sessions/{id}/restart to revive it."
            if attempt < max_attempts - 1:
                delay = 2 ** attempt  # 1s, 2s, 4s
                logger.info(f"Session {s.id} no driver, retrying in {delay}s (attempt {attempt+1}/{max_attempts})")
                time.sleep(delay)
                continue
            break

        try:
            # CDP 全量获取（Network.getAllCookies 返回所有域名的 cookie）
            result = driver.execute_cdp_cmd("Network.getAllCookies", {})
            cookies = result.get("cookies", [])
            logger.debug(f"Session {s.id}: CDP returned {len(cookies)} cookies")
        except Exception as cdp_err:
            logger.warning(
                f"Session {s.id} CDP cookie fetch failed (attempt {attempt+1}/{max_attempts}): "
                f"{cdp_err}, falling back to Selenium"
            )
            try:
                cookies = driver.get_cookies()
                logger.debug(f"Session {s.id}: Selenium fallback returned {len(cookies)} cookies")
            except Exception as sel_err:
                last_error = f"Cookie extraction failed: {sel_err}"
                if attempt < max_attempts - 1:
                    delay = 2 ** attempt
                    logger.warning(
                        f"Session {s.id} cookie extraction failed (attempt {attempt+1}/{max_attempts}), "
                        f"retrying in {delay}s"
                    )
                    time.sleep(delay)
                    continue
                break

        # Success — filter and return
        if platform_filter:
            cookies = [c for c in cookies
                       if platform_filter.lower() in (c.get("domain") or "").lower()]
            if not cookies:
                logger.warning(
                    f"Session {s.id}: no cookies matched platform filter '{platform_filter}' "
                    f"(total cookies before filter: {len(cookies)})"
                )

        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        return {
            "count": len(cookies),
            "cookie_string": cookie_str,
            "cookies": [
                {"name": c["name"], "value": c["value"], "domain": c.get("domain")}
                for c in cookies
            ],
        }

    # All attempts exhausted
    raise HTTPException(
        status_code=503,
        detail=last_error or "Cookie extraction failed after {max_attempts} attempts. "
                          "The session browser may need to be restarted.",
    )


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