from __future__ import annotations
"""Node Heartbeat Service — 周期性探测所有 Grid 节点健康状态，更新 DB 状态。

职责：
1. 每 HEARTBEAT_INTERVAL 秒探测所有 Grid 节点
2. 更新节点状态（ONLINE/OFFLINE/DEGRADED）
3. 连续失败达到阈值触发 Webhook 告警
4. 记录心跳历史（最近一次成功/失败时间 + 连续失败计数）
"""
import logging
import threading
import time
from datetime import datetime, timezone

from database import SessionLocal
from models import GridInstance
from services.grid_service import GridService

logger = logging.getLogger(__name__)

# 默认心跳间隔（秒）
DEFAULT_INTERVAL = 30
# 连续失败多少次触发告警
ALERT_CONSECUTIVE_FAILURES = 3


class NodeHeartbeat:
    """周期性探测所有 Grid 节点，维护在线状态。"""

    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL):
        self.interval_seconds = interval_seconds
        self._running = False
        self._thread = None  # type: threading.Thread | None
        # 追踪每个节点的连续失败次数（node_id → count）
        self._failure_counts: dict[int, int] = {}

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="node-heartbeat", daemon=True)
        self._thread.start()
        logger.info(f"NodeHeartbeat started (interval={self.interval_seconds}s)")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("NodeHeartbeat stopped")

    def _loop(self) -> None:
        # 启动后立即执行一轮
        try:
            self.beat_once()
        except Exception:
            logger.exception("NodeHeartbeat initial beat error")
        while self._running:
            for _ in range(self.interval_seconds):
                if not self._running:
                    return
                time.sleep(1)
            try:
                self.beat_once()
            except Exception:
                logger.exception("NodeHeartbeat beat error")

    def beat_once(self) -> dict[int, dict]:
        """探测所有 Grid 节点一次，返回 {node_id: probe_result}。"""
        db = SessionLocal()
        try:
            nodes = db.query(GridInstance).all()
            results = {}
            for node in nodes:
                result = GridService.probe(node.hub_url)
                results[node.id] = result

                old_status = node.status
                if result["status"] == "ONLINE":
                    node.status = "ONLINE"
                    self._failure_counts[node.id] = 0
                else:
                    # 累计失败次数
                    self._failure_counts[node.id] = self._failure_counts.get(node.id, 0) + 1
                    fail_count = self._failure_counts[node.id]
                    if fail_count >= ALERT_CONSECUTIVE_FAILURES:
                        # 连续失败达到阈值：标记 OFFLINE + 告警
                        if node.status != "OFFLINE":
                            node.status = "OFFLINE"
                            logger.warning(
                                f"Node '{node.name}' ({node.hub_url}) OFFLINE "
                                f"after {fail_count} consecutive failures"
                            )
                            self._alert_node_down(node, result)
                    else:
                        # 偶发失败：标记 DEGRADED
                        node.status = "DEGRADED"
                node.updated_at = datetime.now(timezone.utc)

                if old_status != node.status:
                    logger.info(
                        f"Node '{node.name}': {old_status} → {node.status} "
                        f"({result.get('message', '')})"
                    )
            db.commit()
            return results
        finally:
            db.close()

    def _alert_node_down(self, node: GridInstance, result: dict) -> None:
        """节点离线告警：通过 Webhook 通知。"""
        try:
            from notifiers import notify
            notify("node.offline", {
                "node_id": node.id,
                "node_name": node.name,
                "hub_url": node.hub_url,
                "message": result.get("message", "No response"),
                "consecutive_failures": self._failure_counts.get(node.id, 0),
            })
        except Exception as e:
            logger.warning(f"Failed to send node offline alert: {e}")

    def get_node_health(self, node_id: int):  # -> Optional[dict]
        """获取单个节点的健康信息（含失败计数）。"""
        db = SessionLocal()
        try:
            node = db.query(GridInstance).filter(GridInstance.id == node_id).first()
            if not node:
                return None
            return {
                "node_id": node.id,
                "name": node.name,
                "hub_url": node.hub_url,
                "status": node.status,
                "consecutive_failures": self._failure_counts.get(node.id, 0),
                "last_updated": node.updated_at.isoformat() if node.updated_at else None,
            }
        finally:
            db.close()


# 进程级单例
heartbeat = NodeHeartbeat()
