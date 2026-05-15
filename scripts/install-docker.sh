#!/bin/bash
# Docker 安装脚本 —— 手动执行
set -e

echo "=== 安装 Docker ==="
sudo apt update -qq
sudo apt install -y docker.io docker-compose-plugin

echo "=== 将当前用户加入 docker 组 ==="
sudo usermod -aG docker $USER

echo "=== 启动 docker 服务 ==="
sudo systemctl enable --now docker

echo "✅ Docker 安装完成"
echo "⚠️  请重新登录终端或执行: newgrp docker"
echo ""
echo "=== 部署项目 ==="
cd "$(dirname "$0")/.."
docker compose up -d --build
echo "✅ 部署完成"
echo "  API:      http://localhost:8000"
echo "  Dashboard: http://localhost:8501"
