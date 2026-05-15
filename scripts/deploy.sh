#!/bin/bash
# Docker 安装 + 项目部署脚本
set -e

echo "=== 1. 安装 Docker ==="
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

echo "✅ Docker 已安装"

echo ""
echo "=== 2. 构建并启动容器 ==="
cd /home/jckchen/project
docker compose -f docker-compose.local.yml up -d --build

echo "✅ 部署完成"
echo ""
echo "========== 服务地址 =========="
echo "  API:      http://localhost:8000"
echo "  Docs:     http://localhost:8000/docs"
echo "  Dashboard: http://localhost:8501"
echo "================================"
echo "注意: newgrp docker 后需重新打开终端才能免 sudo 用 docker"
