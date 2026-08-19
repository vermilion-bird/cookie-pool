from __future__ import annotations
import logging
import os

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.grid_service import GridService
from config import PROFILES_DIR, BROWSER_TIMEOUT

logger = logging.getLogger(__name__)


class BrowserService:
    """统一浏览器管理。业务层通过此服务操作浏览器，不直接调用 Selenium。"""

    def __init__(self, account, grid_service: GridService = None):
        self.account = account
        self.driver: WebDriver | None = None
        self.grid_service = grid_service or GridService()

    def create_session(self, grid_url: str = None) -> WebDriver:
        """
        创建浏览器 session，加载账号对应的 Profile。
        可指定 grid_url（多 Grid 场景），否则由 GridService 根据配置决定。
        """
        profile_path = self.account.profile_path
        os.makedirs(profile_path, exist_ok=True)
        # Chrome 节点可能以不同 uid 运行，放宽权限
        os.chmod(profile_path, 0o777)

        self.driver = self.grid_service.create_driver(profile_path, grid_url=grid_url)
        logger.info(f"Browser session created for account {self.account.id} "
                     f"(profile: {profile_path}, grid_url: {grid_url})")
        return self.driver

    def close_session(self) -> None:
        """关闭浏览器 session。"""
        if self.driver:
            try:
                self.grid_service.close_driver(self.driver)
            finally:
                self.driver = None

    def get_driver(self) -> WebDriver | None:
        return self.driver

    def navigate(self, url: str) -> None:
        if not self.driver:
            raise RuntimeError("Browser session not created")
        self.driver.get(url)
        logger.info(f"Navigated to {url}")

    def check_login(self, login_indicator: str = None) -> bool:
        if not self.driver:
            return False
        if login_indicator:
            try:
                WebDriverWait(self.driver, BROWSER_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, login_indicator))
                )
                logger.info(f"Login check passed for account {self.account.id}")
                return True
            except (TimeoutException, WebDriverException):
                logger.info(f"Login check failed for account {self.account.id}")
                return False
        current_url = self.driver.current_url.lower()
        login_keywords = ["login", "signin", "auth", "sign_in", "log_in"]
        is_logged_in = not any(kw in current_url for kw in login_keywords)
        logger.info(f"Login check for account {self.account.id}: "
                     f"{'passed' if is_logged_in else 'failed'} (url: {current_url})")
        return is_logged_in

    def execute(self, task_type: str, params: dict = None) -> dict:
        raise NotImplementedError("Subclasses must implement execute()")

    def screenshot(self, path: str = None) -> bytes:
        if not self.driver:
            raise RuntimeError("Browser session not created")
        if path:
            self.driver.save_screenshot(path)
        return self.driver.get_screenshot_as_png()