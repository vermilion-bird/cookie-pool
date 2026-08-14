#!/bin/bash
# Cookie Pool — 初始化脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Cookie Pool Init"
echo "===================="

# 创建数据目录
mkdir -p "$PROJECT_DIR/data/profiles"
echo "📁 Created data directories"

# Docker Compose 构建启动
cd "$PROJECT_DIR"
echo "🐳 Building and starting services..."
docker compose up -d --build

echo ""
echo "✅ Cookie Pool is running!"
echo "   Web UI: http://localhost:8080/"
echo "   API:    http://localhost:8080/api/accounts"
echo "   Health: http://localhost:8080/health"
echo ""
echo "📝 Quick start:"
echo "   1. Open http://localhost:8080/accounts"
echo "   2. Create an account"
echo "   3. Click 'Login' to open noVNC browser"
echo "   4. Log in to target platform manually"
echo "   5. Click 'Login Complete'"
echo "   6. Account status → ACTIVE, ready for tasks"