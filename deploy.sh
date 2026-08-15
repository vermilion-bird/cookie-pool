#!/usr/bin/env bash
# ============================================================
# Cookie Pool — 一键部署脚本
# ============================================================
# 用法:
#   chmod +x deploy.sh
#   ./deploy.sh                        # 交互式部署
#   ./deploy.sh --host 1.2.3.4        # 指定公网 IP
#   ./deploy.sh --host 1.2.3.4 --port 8080 --novnc 7901
#
# 前置条件:
#   - Docker 20.10+
#   - Docker Compose v2 (docker compose 命令可用)
#   - 2GB+ 可用内存
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERR]${NC}   $*"; }

# ── 参数解析 ──
HOST_ADDRESS=""
APP_PORT="8080"
NOVNC_PORT="7901"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)   HOST_ADDRESS="$2"; shift 2 ;;
        --port)   APP_PORT="$2"; shift 2 ;;
        --novnc)  NOVNC_PORT="$2"; shift 2 ;;
        --help|-h)
            echo "用法: $0 [--host IP] [--port 8080] [--novnc 7901]"
            exit 0 ;;
        *) err "未知参数: $1"; exit 1 ;;
    esac
done

# ── 1. 检查前置条件 ──
echo ""
echo "============================================"
echo " Cookie Pool — 部署检查"
echo "============================================"
echo ""

info "检查 Docker ..."
if ! docker --version >/dev/null 2>&1; then
    err "Docker 未安装。请先安装: https://docs.docker.com/engine/install/"
    exit 1
fi
ok "Docker: $(docker --version)"

info "检查 Docker Compose ..."
if ! docker compose version >/dev/null 2>&1; then
    err "Docker Compose v2 未安装。请先安装: https://docs.docker.com/compose/install/"
    exit 1
fi
ok "Docker Compose: $(docker compose version --short 2>/dev/null || echo 'v2')"

info "检查可用内存 ..."
MEM_MB=$(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo "0")
if [ "$MEM_MB" -lt 1024 ] 2>/dev/null && [ "$MEM_MB" != "0" ]; then
    warn "可用内存 ${MEM_MB}MB，建议至少 2GB。Chrome 可能不稳定。"
else
    ok "可用内存: ${MEM_MB}MB"
fi

info "检查磁盘空间 ..."
DISK_GB=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "${DISK_GB:-0}" -lt 5 ] 2>/dev/null; then
    warn "磁盘剩余 ${DISK_GB}GB，建议至少 5GB（Chrome profiles 占用较大）"
else
    ok "磁盘剩余: ${DISK_GB}GB"
fi

# ── 2. 获取主机地址 ──
if [ -z "$HOST_ADDRESS" ]; then
    # 尝试自动检测
    AUTO_IP=$(curl -s --connect-timeout 3 ifconfig.me 2>/dev/null || \
              curl -s --connect-timeout 3 ipinfo.io/ip 2>/dev/null || \
              hostname -I 2>/dev/null | awk '{print $1}' || echo "")
    if [ -n "$AUTO_IP" ]; then
        read -p "公网 IP [${AUTO_IP}]: " USER_IP
        HOST_ADDRESS="${USER_IP:-$AUTO_IP}"
    else
        read -p "请输入主机公网 IP 或域名: " HOST_ADDRESS
    fi
fi
info "主机地址: ${HOST_ADDRESS}"

# ── 3. 生成 .env ──
if [ ! -f .env ]; then
    info "生成 .env ..."
    API_KEY=$(LC_ALL=C tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 24)
    cat > .env << EOF
HOST_ADDRESS=${HOST_ADDRESS}
APP_PORT=${APP_PORT}
NOVNC_PORT=${NOVNC_PORT}
API_KEY=${API_KEY}
VNC_PASSWORD=
GRID_MAX_SESSIONS=1
GRID_SESSION_TIMEOUT=300
GRID_IMAGE=selenium/standalone-chromium:latest
DATA_DIR=./data
EOF
    ok ".env 已生成 (API_KEY=${API_KEY})"
else
    info ".env 已存在，跳过生成"
    # 更新 HOST_ADDRESS 如果提供了参数
    if [ -n "$HOST_ADDRESS" ]; then
        sed -i "s/^HOST_ADDRESS=.*/HOST_ADDRESS=${HOST_ADDRESS}/" .env
        ok "已更新 HOST_ADDRESS=${HOST_ADDRESS}"
    fi
fi

# ── 4. 创建数据目录 ──
info "创建数据目录 ..."
mkdir -p data/profiles
ok "数据目录: $(pwd)/data/"

# ── 5. 拉取镜像 + 构建 ──
echo ""
echo "============================================"
echo " 构建 & 启动"
echo "============================================"
echo ""

info "拉取 Grid 镜像 ..."
docker compose pull grid 2>&1 || warn "镜像拉取部分失败，将尝试在线构建"

info "构建 & 启动所有服务 ..."
docker compose up -d --build 2>&1
ok "容器启动完成"

# ── 6. 等待就绪 ──
echo ""
info "等待服务就绪 (最多 60s) ..."
for i in $(seq 1 30); do
    if curl -fsS "http://localhost:${APP_PORT}/health" >/dev/null 2>&1; then
        ok "服务就绪 (${i}s)"
        break
    fi
    sleep 2
done

# ── 7. 健康检查 ──
echo ""
echo "============================================"
echo " 健康检查"
echo "============================================"
echo ""

APP_HEALTH=$(curl -s "http://localhost:${APP_PORT}/health" 2>/dev/null || echo '{"status":"DOWN"}')
GRID_STATUS=$(curl -s "http://localhost:4444/status" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'ready={d[\"value\"][\"ready\"]}, nodes={len(d[\"value\"].get(\"nodes\",[]))}')
" 2>/dev/null || echo "DOWN")

echo "  App:   ${APP_HEALTH}"
echo "  Grid:  ${GRID_STATUS}"
echo ""

# ── 8. 输出总结 ──
echo "============================================"
echo " ✅ 部署完成"
echo "============================================"
echo ""
echo "  Web UI:         http://${HOST_ADDRESS}:${APP_PORT}/"
echo "  API:            http://${HOST_ADDRESS}:${APP_PORT}/api/accounts"
echo "  noVNC 浏览器:   http://${HOST_ADDRESS}:${NOVNC_PORT}/vnc.html"
echo "  Health:         http://${HOST_ADDRESS}:${APP_PORT}/health"
echo ""
echo "  常用命令:"
echo "    docker compose logs -f        # 查看日志"
echo "    docker compose ps             # 查看容器状态"
echo "    docker compose restart        # 重启服务"
echo "    docker compose down           # 停止并清除容器"
echo "    docker compose up -d --build  # 重新构建并启动"
echo ""
echo "  Cookie 提取:"
echo "    curl http://${HOST_ADDRESS}:${APP_PORT}/api/accounts/{id}/cookies/plain"
echo ""
echo "  快速开始:"
echo "    1. 打开 Web UI 创建 Account"
echo "    2. 点击 Login → 在 noVNC 中登录平台"
echo "    3. 点击 Login Complete → 账号状态变为 ACTIVE"
echo "    4. 通过 /api/accounts/{id}/cookies/plain 提取 cookie"
echo ""