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
    def session_url(grid_url: str, session_id: str) -> str | None:
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
    def session_has_selector(grid_url: str, session_id: str, css_selector: str) -> bool | None:
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
        探测 Grid 实例是否健康。
        Hub 用 /wd/hub/status，Node/Standalone 用 /status，自动回退。
        返回 {"status": "ONLINE"|"OFFLINE"|"ERROR", "nodes": int, "ready": bool, "message": str}
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
                nodes_list = value.get("value", {}).get("nodes", [])
                node_count = len(nodes_list) if isinstance(nodes_list, list) else 0
                if ready:
                    return {"status": "ONLINE", "nodes": node_count, "ready": True,
                            "message": "Ready"}
                else:
                    return {"status": "ERROR", "nodes": node_count, "ready": False,
                            "message": "Grid not ready"}
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
                    # Standalone mode: check if there's a session
                    ready = value.get("ready", False)
                    nodes_list = value.get("nodes", [])
                    if nodes_list:
                        return len([n for n in nodes_list if n.get("session")])
                    return 0 if ready else -1
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