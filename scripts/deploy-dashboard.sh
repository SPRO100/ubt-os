#!/usr/bin/env bash
# Деплой только React dashboard. Запускать НА СЕРВЕРЕ из папки репозитория:
#     bash scripts/deploy-dashboard.sh
# Путь к репозиторию определяется по расположению скрипта (не захардкожен).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE="ubt-dashboard"

echo "==> [1/5] git pull"
cd "$REPO_DIR"
git fetch origin main
git checkout main
git pull --ff-only origin main

echo "==> [2/5] npm ci"
cd "$REPO_DIR/dashboard"
npm ci                 # нужны devDeps (vite) для сборки — без --omit=dev!

echo "==> [3/5] npm run build"
npm run build

echo "==> [4/5] systemctl restart $SERVICE"
sudo systemctl restart "$SERVICE"

echo "==> [5/5] проверка статуса"
sleep 2
systemctl is-active --quiet "$SERVICE" \
  && echo "OK — dashboard запущен" \
  || echo "ОШИБКА — проверь: journalctl -u $SERVICE -n 30"
