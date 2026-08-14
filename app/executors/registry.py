"""任务执行器注册表：业务任务按 task.type 注册执行器，worker 依注册表调度。"""
import json
import logging

from services.browser_service import BrowserService
from services.grid_service import GridService

logger = logging.getLogger(__name__)

_registry: dict[str, type] = {}


class ExecutorError(Exception):
    pass


def resolve_grid_url(account) -> str:
    """根据账号绑定的 Grid 确定 hub URL。"""
    if account.grid_id and account.grid:
        return account.grid.hub_url
    from config import GRID_URL
    return GRID_URL


class BaseExecutor:
    """执行器基类：子类定义 task_type 并实现 execute()。"""

    task_type = "base"

    def __init__(self, account, grid_service: GridService | None = None):
        self.account = account
        self.grid_service = grid_service or GridService()

    @staticmethod
    def setup_browser(account, grid_url: str | None = None):
        browser = BrowserService(account, GridService())
        browser.create_session(grid_url=grid_url)
        return browser

    @staticmethod
    def teardown_browser(browser) -> None:
        browser.close_session()

    def execute(self, db, browser, task) -> dict:
        raise NotImplementedError(f"{type(self).__name__} must implement execute()")


class VisitUrlExecutor(BaseExecutor):
    """打开目标 URL 并截图。"""

    task_type = "visit_url"

    def execute(self, db, browser, task) -> dict:
        params = json.loads(task.params) if task.params else {}
        target_url = params.get("url", "")
        if target_url:
            browser.navigate(target_url)
        return {"url": target_url, "screenshot": "taken"}


class CheckLoginStatusExecutor(BaseExecutor):
    """校验账号登录状态（URL 启发式或 login_indicator 选择器）。"""

    task_type = "check_login_status"

    def execute(self, db, browser, task) -> dict:
        params = json.loads(task.params) if task.params else {}
        indicator = params.get("login_indicator") or self.account.login_indicator
        logged_in = browser.check_login(login_indicator=indicator or None)
        return {"logged_in": logged_in}


def register_executor(executor_cls: type) -> type:
    task_type = getattr(executor_cls, "task_type", None)
    if not task_type:
        raise ExecutorError(f"Executor {executor_cls.__name__} must define task_type")
    _registry[task_type] = executor_cls
    logger.info(f"Registered executor: {task_type}")
    return executor_cls


def get_executor(task_type: str) -> type:
    cls = _registry.get(task_type)
    if not cls:
        raise ExecutorError(
            f"No executor registered for task type '{task_type}'. "
            f"Registered: {', '.join(registered_types()) or 'none'}"
        )
    return cls


def registered_types() -> list[str]:
    return sorted(_registry)


# 注册内置执行器
register_executor(VisitUrlExecutor)
register_executor(CheckLoginStatusExecutor)
