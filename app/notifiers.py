"""通知渠道：任务完成/失败等事件投递到 Webhook。

任何渠道失败仅记日志，绝不影响主流程。
"""
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

EVENT_TASK_COMPLETED = "task.completed"
EVENT_TASK_FAILED = "task.failed"
EVENT_SCHEDULE_TRIGGERED = "schedule.triggered"


def notify(event: str, payload: dict) -> None:
    """将事件投递到所有已配置渠道。"""
    from config import NOTIFY_WEBHOOK_URL
    if NOTIFY_WEBHOOK_URL:
        _post_webhook(NOTIFY_WEBHOOK_URL, {"event": event, **payload})


def _post_webhook(url: str, body: dict) -> None:
    try:
        data = json.dumps(body, ensure_ascii=False).encode()
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info(f"Webhook notified ({resp.status}): {body.get('event')}")
    except Exception as e:
        logger.warning(f"Webhook notify failed for {url}: {e}")
