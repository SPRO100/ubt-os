#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# UBT OS — полный деплой одной командой: dashboard + backend-агенты.
# Запускать НА СЕРВЕРЕ из папки репозитория:
#     bash scripts/deploy-all.sh
#
# Путь к репозиторию НЕ захардкожен — определяется по расположению
# самого скрипта (он лежит в <repo>/scripts/), поэтому работает
# независимо от того, куда склонирован проект.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"
echo "==> Репозиторий: $REPO_DIR"

# docker compose (новый) vs docker-compose (старый)
if docker compose version >/dev/null 2>&1; then DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then DC="docker-compose"
else DC=""; fi

# ── 1. git pull ──────────────────────────────────────────────
echo "==> [1/5] git pull origin main"
git fetch origin main
git checkout main
git pull --ff-only origin main

# ── 2. dashboard: сборка ─────────────────────────────────────
echo "==> [2/5] dashboard: npm ci + build"
cd "$REPO_DIR/dashboard"
npm ci                 # нужны devDeps (vite) — без --omit=dev!
npm run build
cd "$REPO_DIR"

# ── 3. dashboard: перезапуск ─────────────────────────────────
echo "==> [3/5] restart dashboard"
if systemctl list-unit-files 2>/dev/null | grep -q '^ubt-dashboard'; then
  sudo systemctl restart ubt-dashboard
  sleep 2
  systemctl is-active --quiet ubt-dashboard \
    && echo "   ✅ dashboard активен" \
    || echo "   ⚠ dashboard не активен — journalctl -u ubt-dashboard -n 30"
else
  echo "   ⚠ systemd-сервис ubt-dashboard не найден — пропускаю."
  echo "     (проверь, как у тебя запущен дашборд: systemctl list-units | grep -i dash)"
fi

# ── 4. backend-агенты (docker) ───────────────────────────────
echo "==> [4/5] rebuild + restart агентов (docker)"
if [ -n "$DC" ] && [ -f "$REPO_DIR/docker-compose.yml" ]; then
  $DC build agents higgsfield_worker
  $DC up -d
else
  echo "   ⚠ docker compose не найден или нет docker-compose.yml — пропускаю backend."
fi

# ── 5. healthcheck ───────────────────────────────────────────
echo "==> [5/5] healthcheck"
[ -n "$DC" ] && $DC ps || true
sleep 3
if curl -fsS http://127.0.0.1:8080/health/check-all >/dev/null 2>&1; then
  echo "   ✅ agents API отвечает (:8080/health/check-all)"
else
  echo "   ⚠ agents API не ответил — смотри логи: ${DC:-docker compose} logs -f agents"
fi

echo "✅ Деплой завершён."
