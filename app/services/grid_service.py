from __future__ import annotations
import logging
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException

from config import GRID_URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Realistic User-Agent pool — rotated per session to avoid fingerprinting
# ---------------------------------------------------------------------------
_USER_AGENTS = [
    # Windows 10 / Chrome 130+
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # macOS / Chrome 130+
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Windows 11 / Edge (Chromium)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
]

# ---------------------------------------------------------------------------
# CDP script injected into every page to override WebDriver detection markers.
# Runs before any page JS, so navigator.webdriver is patched before site scripts see it.
# ---------------------------------------------------------------------------
_CDP_OVERRIDE_SCRIPT = """
(function() {
    'use strict';
    // ── 1. Hide webdriver flag ──
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // ── 2. Fake plugins ──
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const arr = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
            ];
            arr.item = (i) => arr[i] || null;
            arr.namedItem = (n) => arr.find(p => p.name === n) || null;
            arr.refresh = () => {};
            Object.setPrototypeOf(arr, PluginArray.prototype);
            return arr;
        }
    });

    // ── 3. Fake languages ──
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });

    // ── 4. Fake chrome object ──
    window.chrome = {
        runtime: { connect: () => {}, onConnect: { addListener: () => {} } },
        loadTimes: () => {},
        csi: () => {},
        app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } },
    };

    // ── 5. Fake permissions.query ──
    const _query = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) => {
        if (params && params.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission, onchange: null });
        }
        return _query.call(window.navigator.permissions, params);
    };

    // ── 6. Fake hardware concurrency ──
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

    // ── 7. Fake WebGL vendor ──
    try {
        const proto = WebGLRenderingContext.prototype;
        const getParam = proto.getParameter;
        proto.getParameter = function(p) {
            if (p === 37445) return 'Google Inc. (Intel)';       // UNMASKED_VENDOR_WEBGL
            if (p === 37446) return 'ANGLE (Intel, Intel(R) Iris(R) Xe Graphics (0x000046A8) Direct3D11 vs_5_0 ps_5_0, D3D11)';  // UNMASKED_RENDERER_WEBGL
            return getParam.call(this, p);
        };
    } catch(e) {}

    // ── 8. Remove "enable-automation" info bar side-effects ──
    delete document.__webdriver_evaluate;
    delete document.__webdriver_script_function;
    delete document.__webdriver_script_func;
    delete document.__webdriver_script_fn;
})();
"""


class GridService:
    """封装 Selenium Grid 交互。支持多 Grid 实例，通过 grid_url 区分。"""

    @staticmethod
    def resolve_grid_url(grid_instance=None) -> str:
        """根据 GridInstance 对象或配置返回 hub URL。"""
        if grid_instance:
            return grid_instance.hub_url
        return GRID_URL

    @staticmethod
    def create_driver(profile_path: str, grid_url: str = None) -> WebDriver:
        """在指定 Grid 上创建一个新 Chrome session（包含反检测配置），加载指定 Profile。"""
        effective_url = grid_url or GRID_URL

        chrome_options = Options()

        # ── Profile & display ──
        chrome_options.add_argument(f"--user-data-dir={profile_path}")

        # ── Anti-automation flags ──
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-automation")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # ── Misc ──
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--disable-search-engine-choice-screen")
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-prompt-on-repost")

        # ── Container / headless-server safety ──
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--remote-allow-origins=*")

        # ── Language ──
        chrome_options.add_argument("--lang=zh-CN")
        chrome_options.add_experimental_option("prefs", {
            "intl.accept_languages": "zh-CN,zh",
        })

        # ── Realistic random User-Agent ──
        ua = random.choice(_USER_AGENTS)
        chrome_options.add_argument(f"--user-agent={ua}")
        logger.debug(f"Using UA: {ua}")

        driver = webdriver.Remote(
            command_executor=f"{effective_url}/wd/hub",
            options=chrome_options,
        )
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        logger.info(f"Grid session created ({effective_url}): {driver.session_id}")

        # ── CDP injection: override JS detection markers before every page load ──
        try:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": _CDP_OVERRIDE_SCRIPT,
            })
            logger.debug("CDP anti-detection script injected")
        except Exception as e:
            logger.warning(f"CDP injection failed (non-fatal): {e}")

        return driver

    @staticmethod
    def close_driver(driver: WebDriver) -> None:
        """安全关闭 Grid session。"""
        if driver is None:
            return
        try:
            session_id = driver.session_id
            driver.quit()
            logger.info(f"Grid session closed: {session_id}")
        except WebDriverException as e:
            logger.warning(f"Error closing Grid session: {e}")

    @staticmethod
    def session_url(grid_url: str, session_id: str):  # -> Optional[str]
        """经 Grid REST 获取现有 session 的当前 URL（不新建 driver，避免 Profile 锁竞争）。"""
        import urllib.request
        import json
        if not session_id:
            return None
        try:
            req = urllib.request.Request(f"{grid_url}/wd/hub/session/{session_id}/url")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return data.get("value")
        except Exception as e:
            logger.warning(f"Failed to get session URL {session_id}: {e}")
            return None

    @staticmethod
    def session_has_selector(grid_url: str, session_id: str, css_selector: str):  # -> Optional[bool]
        """经 Grid REST 在现有 session 中执行 JS 判断选择器是否存在；失败返回 None。"""
        import urllib.request
        import json
        if not session_id or not css_selector:
            return None
        try:
            body = json.dumps({
                "script": "return !!document.querySelector(arguments[0]);",
                "args": [css_selector],
            }).encode()
            req = urllib.request.Request(
                f"{grid_url}/wd/hub/session/{session_id}/execute/sync",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return bool(data.get("value"))
        except Exception as e:
            logger.warning(f"Failed to execute selector check on session {session_id}: {e}")
            return None

    @staticmethod
    def delete_session(grid_url: str, session_id: str) -> None:
        """经 Grid REST 关闭现有 session（释放 Profile 与节点资源）。"""
        import urllib.request
        if not session_id:
            return
        try:
            req = urllib.request.Request(f"{grid_url}/wd/hub/session/{session_id}", method="DELETE")
            urllib.request.urlopen(req, timeout=10)
            logger.info(f"Grid session deleted via REST: {session_id}")
        except Exception as e:
            logger.warning(f"Failed to delete grid session {session_id}: {e}")

    @staticmethod
    def get_session_info(driver: WebDriver) -> dict:
        """获取 session 的节点信息（用于提取 noVNC 等）。"""
        try:
            info = driver.execute("GET", f"/session/{driver.session_id}/se/grid/node/owner")
            return info or {}
        except Exception:
            return {}

    @staticmethod
    def probe(grid_url: str) -> dict:
        """
        探测 Grid 实例是否可达。
        ready=True 表示有空闲 slot 可接收新会话；ready=False 表示可达但 slot 已满。
        返回 {"status": "ONLINE"|"OFFLINE", "nodes": int, "ready": bool, "message": str}
        """
        import urllib.request
        import json
        for endpoint in ("/wd/hub/status", "/status"):
            try:
                status_url = f"{grid_url}{endpoint}"
                resp = urllib.request.urlopen(status_url, timeout=10)
                if resp.status != 200:
                    continue
                data = json.loads(resp.read().decode())
                value = data.get("value", {})
                ready = value.get("ready", False)
                # Standalone: nodes 在 value 顶层；Hub: nodes 在 value.value 内
                nodes_list = value.get("nodes", [])
                if not nodes_list:
                    nodes_list = value.get("value", {}).get("nodes", [])
                node_count = len(nodes_list) if isinstance(nodes_list, list) else 0
                # Grid 可达即 ONLINE；ready 反映是否有空闲 slot
                return {
                    "status": "ONLINE",
                    "nodes": node_count,
                    "ready": ready,
                    "message": "Ready" if ready else f"Online (no free slots, {node_count} node(s))",
                }
            except Exception:
                continue
        return {"status": "OFFLINE", "nodes": 0, "ready": False,
                "message": "No status endpoint reachable"}

    @staticmethod
    def get_active_session_count(grid_url: str) -> int:
        """Query Grid status API for current active session count. Returns -1 on failure."""
        import urllib.request
        import json
        try:
            for endpoint in ("/wd/hub/status", "/status"):
                try:
                    resp = urllib.request.urlopen(f"{grid_url}{endpoint}", timeout=5)
                    if resp.status != 200:
                        continue
                    data = json.loads(resp.read().decode())
                    value = data.get("value", {})
                    nodes = value.get("value", {}).get("nodes", [])
                    if isinstance(nodes, list):
                        total = 0
                        for n in nodes:
                            slots = n.get("slots", [])
                            for slot in slots:
                                if slot.get("session"):
                                    total += 1
                        return total
                    # Standalone mode: check slot occupancy
                    nodes_list = value.get("nodes", [])
                    if nodes_list:
                        occupied = 0
                        for n in nodes_list:
                            slots = n.get("slots", [])
                            for slot in slots:
                                if slot.get("session"):
                                    occupied += 1
                        return occupied
                    return 0
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Failed to query session count for {grid_url}: {e}")
        return -1

    @staticmethod
    def check_capacity(node, live_drivers: dict) -> dict:
        """Check if a Grid node has available capacity.
        
        Returns:
            {"available": bool, "active_sessions": int, "max_sessions": int, "message": str}
        """
        if node is None:
            return {"available": False, "active_sessions": 0, "max_sessions": 0,
                    "message": "Node not found"}
        
        max_sessions = node.max_sessions or 1
        
        # Count local live drivers targeting this node's URL
        local_count = 0
        for driver in live_drivers.values():
            try:
                if driver and driver.command_executor._url and node.hub_url in driver.command_executor._url:
                    local_count += 1
            except Exception:
                pass
        
        # Query Grid for actual session count
        grid_count = GridService.get_active_session_count(node.hub_url)
        effective_count = max(local_count, grid_count) if grid_count >= 0 else local_count
        
        available = effective_count < max_sessions
        return {
            "available": available,
            "active_sessions": effective_count,
            "max_sessions": max_sessions,
            "message": f"{effective_count}/{max_sessions} sessions" if available else f"Full ({max_sessions}/{max_sessions})",
        }

    @staticmethod
    def list_active_grid_sessions(grid_url: str):  # -> list[str]
        """Query Grid for all active session IDs on this node.
        Returns a list of session_id strings. Returns empty list on failure.
        """
        import urllib.request
        import json
        try:
            for endpoint in ("/wd/hub/status", "/status"):
                try:
                    resp = urllib.request.urlopen(f"{grid_url}{endpoint}", timeout=5)
                    if resp.status != 200:
                        continue
                    data = json.loads(resp.read().decode())
                    value = data.get("value", {})
                    session_ids = []
                    # Hub mode: nodes[].slots[].session.sessionId
                    nodes = value.get("value", {}).get("nodes", [])
                    if not nodes:
                        nodes = value.get("nodes", [])
                    for n in (nodes or []):
                        for slot in n.get("slots", []):
                            sess = slot.get("session")
                            if sess and sess.get("sessionId"):
                                session_ids.append(sess["sessionId"])
                    return session_ids
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Failed to list active sessions for {grid_url}: {e}")
        return []

    @staticmethod
    def cleanup_orphan_sessions(grid_url: str, known_session_ids):  # known_session_ids: set[str]
        """Delete Grid sessions that are NOT in the known set (zombie cleanup).
        
        Args:
            grid_url: The Grid hub URL.
            known_session_ids: Set of session IDs that should be kept alive.
        Returns:
            Number of orphan sessions cleaned up.
        """
        active = GridService.list_active_grid_sessions(grid_url)
        cleaned = 0
        for sid in active:
            if sid not in known_session_ids:
                try:
                    GridService.delete_session(grid_url, sid)
                    cleaned += 1
                    logger.info(f"Cleaned up orphan Grid session: {sid} (node={grid_url})")
                except Exception as e:
                    logger.warning(f"Failed to clean orphan session {sid}: {e}")
        if cleaned:
            logger.info(f"Orphan cleanup: removed {cleaned} zombie sessions from {grid_url}")
        return cleaned

    @staticmethod
    def force_cleanup_node(grid_url: str, max_retries: int = 2) -> int:
        """Force-delete ALL active sessions on a Grid node (used for emergency cleanup).
        Returns count of sessions deleted.
        """
        import time
        active = GridService.list_active_grid_sessions(grid_url)
        cleaned = 0
        for sid in active:
            for attempt in range(max_retries):
                try:
                    GridService.delete_session(grid_url, sid)
                    cleaned += 1
                    logger.info(f"Force-cleaned session {sid} from {grid_url}")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        logger.warning(f"Failed force-clean session {sid} after {max_retries} attempts: {e}")
        return cleaned