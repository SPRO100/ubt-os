#!/usr/bin/env bash
# Деплой React dashboard на сервер
# Запускать ПРЯМО НА СЕРВЕРЕ: bash scripts/deploy-dashboard.sh
set -e

REPO_DIR="/home/user/ubt-os"
DASHBOARD_DIR="$REPO_DIR/dashboard"
SERVICE="ubt-dashboard"

echo "==> [1/5] git pull"
cd "$REPO_DIR"
git fetch origin main
git checkout main
git pull origin main

echo "==> [2/5] npm install"
cd "$DASHBOARD_DIR"
npm ci --omit=dev

echo "==> [3/5] npm run build"
npm run build

echo "==> [4/5] systemctl restart $SERVICE"
sudo systemctl restart "$SERVICE"

echo "==> [5/5] проверка статуса"
sleep 2
sudo systemctl is-active "$SERVICE" && echo "OK — dashboard запущен" || echo "ОШИБКА — проверь: journalctl -u $SERVICE -n 30"
