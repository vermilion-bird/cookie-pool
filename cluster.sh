#!/usr/bin/env bash
# ============================================================
# 集群模式 — 启动 + 自动注册 GridInstance
# ============================================================
# 用法:
#   ./cluster.sh up                  # 启动 2 节点
#   ./cluster.sh up --full           # 启动 3 节点
#   ./cluster.sh register            # 注册 node URL 到 DB
#   ./cluster.sh down
set -euo pipefail

CMD="${1:-up}"
PROFILE=""
[[ "${2:-}" == "--full" ]] && PROFILE="--profile full"

case "$CMD" in
  up)
    echo "=== 启动集群 ==="
    docker compose -f docker-compose.cluster.yml $PROFILE up -d --build
    echo "等待就绪..."
    sleep 10
    echo ""
    echo "节点 noVNC 地址:"
    echo "  Node 1: http://localhost:7901/vnc.html"
    echo "  Node 2: http://localhost:7902/vnc.html"
    [ -n "$PROFILE" ] && echo "  Node 3: http://localhost:7903/vnc.html"
    echo ""
    echo "下一步: ./cluster.sh register"
    ;;

  register)
    echo "=== 注册 GridInstance 到 DB ==="
    docker exec cp-app python3 -c "
from database import SessionLocal
from models import GridInstance
db = SessionLocal()

nodes = [
    ('Node 1', 'http://node-1:5555', 'http://localhost:7901/vnc.html'),
    ('Node 2', 'http://node-2:5555', 'http://localhost:7902/vnc.html'),
    ('Node 3', 'http://node-3:5555', 'http://localhost:7903/vnc.html'),
]

for name, hub_url, novnc in nodes:
    existing = db.query(GridInstance).filter(GridInstance.name == name).first()
    if existing:
        existing.hub_url = hub_url
        existing.novnc_base_url = novnc
        print(f'  Updated: {name} -> {hub_url}')
    else:
        g = GridInstance(name=name, hub_url=hub_url, novnc_base_url=novnc,
                         status='UNKNOWN', max_sessions=1)
        db.add(g)
        print(f'  Created: {name} -> {hub_url}')
db.commit()
db.close()
print('Done. 现在 Web UI 中可为 Account 选择 Node 1/2/3 了。')
"
    ;;

  down)
    docker compose -f docker-compose.cluster.yml down
    ;;

  *)
    echo "用法: $0 {up|register|down} [--full]"
    exit 1
    ;;
esac