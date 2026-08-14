import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException

from config import GRID_URL

logger = logging.getLogger(__name__)


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
        """在指定 Grid 上创建一个新 Chrome session，加载指定 Profile。"""
        effective_url = grid_url or GRID_URL

        chrome_options = Options()

        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-search-engine-choice-screen")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--remote-allow-origins=*")

        chrome_options.add_argument("--lang=zh-CN")
        chrome_options.add_experimental_option("prefs", {
            "intl.accept_languages": "zh-CN,zh",
        })

        driver = webdriver.Remote(
            command_executor=f"{effective_url}/wd/hub",
            options=chrome_options,
        )
        driver.implicitly_wait(10)
        logger.info(f"Grid session created ({effective_url}): {driver.session_id}")
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
        返回 {"status": "ONLINE"|"OFFLINE"|"ERROR", "nodes": int, "ready": bool, "message": str}
        """
        import urllib.request
        import json
        try:
            status_url = f"{grid_url}/wd/hub/status"
            resp = urllib.request.urlopen(status_url, timeout=10)
            if resp.status != 200:
                return {"status": "ERROR", "nodes": 0, "ready": False,
                        "message": f"HTTP {resp.status}"}

            data = json.loads(resp.read().decode())
            value = data.get("value", {})
            ready = value.get("ready", False)
            nodes = value.get("value", {}).get("nodes", [])
            node_count = len(nodes) if isinstance(nodes, list) else 0

            if ready:
                return {"status": "ONLINE", "nodes": node_count, "ready": True,
                        "message": "Ready"}
            else:
                return {"status": "ERROR", "nodes": node_count, "ready": False,
                        "message": "Grid not ready"}
        except Exception as e:
            return {"status": "OFFLINE", "nodes": 0, "ready": False,
                    "message": str(e)}