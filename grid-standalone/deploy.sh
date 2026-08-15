#!/usr/bin/env bash
# ============================================================
# Selenium Standalone Grid — 一键部署
# ============================================================
# 用法:
#   ./deploy.sh                       # 默认端口 4444/7900
#   ./deploy.sh --port 4445 --novnc 7901
#   ./deploy.sh --name my-grid        # 自定义容器名
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERR]${NC}   $*"; }

# ── 参数解析 ──
NAME="${CONTAINER_NAME:-selenium-grid}"
GRID_PORT="${GRID_PORT:-4444}"
NOVNC_PORT="${NOVNC_PORT:-7900}"
VNC_PORT="${VNC_PORT:-5900}"
MAX_SESSIONS="${GRID_MAX_SESSIONS:-1}"
VNC_PASSWORD="${VNC_PASSWORD:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --name)    NAME="$2"; shift 2 ;;
        --port)    GRID_PORT="$2"; shift 2 ;;
        --novnc)   NOVNC_PORT="$2"; shift 2 ;;
        --vnc)     VNC_PORT="$2"; shift 2 ;;
        --sessions) MAX_SESSIONS="$2"; shift 2 ;;
        --password) VNC_PASSWORD="$2"; shift 2 ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo "  --name NAME        容器名 (默认 selenium-grid)"
            echo "  --port PORT        Grid 端口 (默认 4444)"
            echo "  --novnc PORT       noVNC 端口 (默认 7900)"
            echo "  --vnc PORT         VNC 端口 (默认 5900)"
            echo "  --sessions N       最大会话数 (默认 1)"
            echo "  --password PASS    VNC 密码 (默认无密码)"
            exit 0 ;;
        *) err "未知参数: $1"; exit 1 ;;
    esac
done

# ── 1. 预检 ──
echo ""
echo "============================================"
echo " Selenium Grid 部署"
echo "============================================"
echo ""

info "检查 Docker ..."
docker --version >/dev/null 2>&1 || { err "Docker 未安装"; exit 1; }
ok "$(docker --version)"

info "检查 Docker Compose ..."
docker compose version >/dev/null 2>&1 || { err "需要 Docker Compose v2"; exit 1; }
ok "Compose v2"

info "检查内存 ..."
MEM_MB=$(awk '/MemAvailable/{printf "%d",$2/1024}' /proc/meminfo 2>/dev/null || echo "0")
[ "${MEM_MB:-0}" -lt 1024 ] 2>/dev/null && warn "内存 ${MEM_MB}MB，建议 2GB+" || ok "内存 ${MEM_MB}MB"

# ── 2. 生成 .env ──
if [ ! -f .env ]; then
    info "生成 .env ..."
    cat > .env << EOF
CONTAINER_NAME=${NAME}
GRID_PORT=${GRID_PORT}
NOVNC_PORT=${NOVNC_PORT}
VNC_PORT=${VNC_PORT}
GRID_MAX_SESSIONS=${MAX_SESSIONS}
GRID_SESSION_TIMEOUT=300
VNC_PASSWORD=${VNC_PASSWORD}
SHM_SIZE=2gb
GRID_IMAGE=selenium/standalone-chromium:latest
PROFILES_DIR=./profiles
TZ=Asia/Shanghai
EOF
    ok ".env 已生成"
else
    info ".env 已存在，使用现有配置"
fi

# ── 3. 目录 ──
mkdir -p profiles
ok "profiles 目录就绪"

# ── 4. 拉取 & 启动 ──
echo ""
info "拉取镜像 ..."
docker compose pull 2>&1 || warn "拉取部分失败"

info "启动容器 ..."
docker compose up -d 2>&1
ok "容器启动完成"

# ── 5. 等待就绪 ──
echo ""
info "等待 Grid 就绪 ..."
for i in $(seq 1 45); do
    if curl -fsS "http://localhost:${GRID_PORT}/status" 2>/dev/null | grep -q '"ready": *true'; then
        ok "Grid 就绪 (${i}s)"
        break
    fi
    sleep 2
done

# ── 6. 验证 VNC（不应有 -viewonly）──
VNC_ARGS=$(docker exec "${NAME}" sh -c "ps aux | grep x11vnc | grep -v grep" 2>/dev/null || echo "")
if echo "$VNC_ARGS" | grep -q "viewonly"; then
    err "VNC 处于 view-only 模式！需删除 SE_VNC_VIEW_ONLY 环境变量"
else
    ok "VNC 可读写（无 viewonly 标志）"
fi

# ── 7. 输出 ──
GRID_STATUS=$(curl -s "http://localhost:${GRID_PORT}/status" | python3 -c "
import sys,json
try:
  d=json.load(sys.stdin)['value']
  print(f'ready={d[\"ready\"]}, nodes={len(d.get(\"nodes\",[]))}, chrome={d[\"nodes\"][0][\"slots\"][0][\"stereotype\"][\"browserVersion\"]}')
except: print('parse error')
" 2>/dev/null || echo "unknown")

echo ""
echo "============================================"
echo " ✅ Grid 部署完成"
echo "============================================"
echo ""
echo "  容器:        ${NAME}"
echo "  状态:        ${GRID_STATUS}"
echo ""
echo "  Grid API:    http://localhost:${GRID_PORT}/wd/hub"
echo "  Grid 状态:   http://localhost:${GRID_PORT}/status"
echo "  noVNC:       http://localhost:${NOVNC_PORT}/vnc.html"
if [ -n "$VNC_PASSWORD" ]; then
echo "  VNC 密码:    ${VNC_PASSWORD}"
fi
echo ""
echo "  Python 客户端:"
echo "    from selenium import webdriver"
echo "    driver = webdriver.Remote("
echo "        command_executor='http://localhost:${GRID_PORT}/wd/hub',"
echo "        options=chrome_options)"
echo ""
echo "  常用命令:"
echo "    docker compose logs -f        # 日志"
echo "    docker compose restart        # 重启"
echo "    docker compose down           # 停止"
echo "    docker exec -it ${NAME} bash  # 进入容器"
echo ""