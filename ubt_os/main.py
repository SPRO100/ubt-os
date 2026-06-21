"""
UBT OS — Main Entry Point
Запускает HTTP-сервер для приёма webhook-вызовов от n8n.

FIXES в этом файле (Sprint 1):
  FIX #1 — добавлены маршруты, которые вызывает n8n, но которых не было:
           /strategy/collect, /risk/run, /knowledge/synthesize,
           /health/check-all, /obsidian/write
  FIX #6 — AccountChecker теперь получает db_client (раньше падал с TypeError)
"""
from __future__ import annotations
import asyncio
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("ubt_os.main")


def _get_db():
    """Ленивый Supabase-клиент. Создаётся только при обработке запроса,
    а не при старте сервера (FIX #6)."""
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


class WebhookHandler(BaseHTTPRequestHandler):
    """Принимает POST-запросы от n8n и запускает нужный пайплайн."""

    def do_POST(self):
        length  = int(self.headers.get("Content-Length", 0))
        body    = json.loads(self.rfile.read(length)) if length else {}
        action  = body.get("action", "unknown")

        logger.info(f"Webhook: {self.path} action={action}")

        routes = {
            "/run/nutra":          self._run_nutra,
            "/run/ubt":            self._run_ubt,
            "/run/account-check":  self._run_checker,
            "/run/obsidian-sync":  self._run_obsidian,
            "/run/daily-report":   self._run_report,
            # FIX #1 — маршруты, которые n8n уже вызывал, но сервер не знал о них:
            "/strategy/collect":      self._run_strategy_collect,
            "/risk/run":              self._run_risk,
            "/knowledge/synthesize":  self._run_knowledge_synthesize,
            "/obsidian/write":        self._run_obsidian_write,
            "/obsidian/append":       self._run_obsidian_append,
        }

        handler = routes.get(self.path)
        if handler:
            result = asyncio.run(handler(body))
            self._respond(200, result if isinstance(result, dict) else {"status": "accepted"})
        else:
            self._respond(404, {"error": "unknown route"})

    def do_GET(self):
        # FIX #1 — health-check маршрут, который дёргает n8n / Railway
        if self.path == "/health/check-all":
            asyncio.run(self._run_health_check())
            return
        self._respond(404, {"error": "unknown route"})

    def _respond(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *_):
        pass  # подавляем стандартные логи HTTPServer

    # ── Обработчики пайплайнов ────────────────────────────

    async def _run_nutra(self, body: dict):
        from ubt_os.core import pipeline_lock
        async with pipeline_lock("video-pipeline-nutra", 600) as acquired:
            if not acquired:
                logger.info("NUTRA: lock занят, пропускаем")
                return
            logger.info("NUTRA pipeline: запуск ✅")
            # TODO: подключить агентов после FIX #1 применения

    async def _run_ubt(self, body: dict):
        from ubt_os.core import pipeline_lock
        async with pipeline_lock("video-pipeline-ubt", 600) as acquired:
            if not acquired:
                logger.info("UBT: lock занят, пропускаем")
                return
            logger.info("UBT pipeline: запуск ✅")

    async def _run_checker(self, body: dict):
        from ubt_os.core import pipeline_lock
        from ubt_os.agents import AccountChecker
        async with pipeline_lock("account-checker", 360) as acquired:
            if not acquired:
                return
            # FIX #6 — БЫЛО: AccountChecker()              ← TypeError
            #          СТАЛО: AccountChecker(db_client=db)
            db = _get_db()
            checker = AccountChecker(db_client=db)
            await checker.check_all()

    async def _run_obsidian(self, body: dict):
        from ubt_os.core import pipeline_lock
        from ubt_os.utils import ObsidianSync
        async with pipeline_lock("obsidian-sync", 60) as acquired:
            if not acquired:
                return
            sync = ObsidianSync()
            await sync.sync()

    @staticmethod
    def _safe_vault_path(rel_path: str):
        from pathlib import Path
        vault = Path(os.getenv("OBSIDIAN_VAULT_PATH", "/opt/ubt-os/obsidian-vault")).resolve()
        target = (vault / rel_path).resolve()
        if not str(target).startswith(str(vault)):
            raise ValueError(f"Path escapes vault: {rel_path}")
        return target

    async def _run_obsidian_write(self, body: dict):
        """PATCH: реальная запись файла в vault (path+content из тела запроса)."""
        rel_path = body.get("path")
        content  = body.get("content", "")
        append   = bool(body.get("append", False))
        if not rel_path:
            logger.warning("obsidian/write: пустой path, пропускаем")
            return
        target = self._safe_vault_path(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)
        logger.info(f"obsidian/write: записано {target} (append={append})")

    async def _run_obsidian_append(self, body: dict):
        """PATCH: алиас append=true для /obsidian/append."""
        body = dict(body)
        body["append"] = True
        await self._run_obsidian_write(body)

    async def _run_report(self, body: dict):
        from ubt_os.core import pipeline_lock
        from ubt_os.pipelines import DeadLetterQueueManager
        async with pipeline_lock("daily-report", 120) as acquired:
            if not acquired:
                return
            await DeadLetterQueueManager.daily_report()

    # ── FIX #1: новые обработчики ──────────────────────────

    async def _run_strategy_collect(self, body: dict):
        """A15 STRATEGY_ENGINE: собирает данные за период и пишет анализ в vault."""
        from ubt_os.core import pipeline_lock
        from ubt_os.agents.strategy_engine import run_strategy_engine
        async with pipeline_lock("strategy-collect", 600) as acquired:
            if not acquired:
                logger.info("strategy/collect: lock занят, пропускаем")
                return
            lookback_days = int(body.get("lookback_days", 7))
            result = await run_strategy_engine(lookback_days=lookback_days)
            logger.info(f"strategy/collect завершён: {result}")

    async def _run_risk(self, body: dict):
        """Risk Engine: пересчитывает риск-скор всех активных аккаунтов."""
        from ubt_os.core import pipeline_lock
        from ubt_os.core.risk_engine import RiskEngine
        async with pipeline_lock("risk-run", 300) as acquired:
            if not acquired:
                logger.info("risk/run: lock занят, пропускаем")
                return
            db = _get_db()
            engine = RiskEngine(db)
            await engine.run_all()

    async def _run_knowledge_synthesize(self, body: dict):
        """A18 KNOWLEDGE_SYNTHESIZER: daily или weekly синтез знаний."""
        from ubt_os.core import pipeline_lock
        from ubt_os.agents.knowledge_synthesizer import (
            run_daily_synthesis, run_weekly_synthesis,
        )
        mode = body.get("mode", "daily")
        async with pipeline_lock(f"knowledge-synthesize-{mode}", 600) as acquired:
            if not acquired:
                logger.info("knowledge/synthesize: lock занят, пропускаем")
                return
            result = (
                await run_weekly_synthesis()
                if mode == "weekly"
                else await run_daily_synthesis()
            )
            logger.info(f"knowledge/synthesize ({mode}) завершён")
            return result
        return {"status": "skipped", "reason": "lock_busy"}

    async def _run_health_check(self):
        """GET /health/check-all — проверка доступности Supabase и Redis."""
        status = {"supabase": "unknown", "redis": "unknown"}
        try:
            db = _get_db()
            db.table("accounts").select("id").limit(1).execute()
            status["supabase"] = "ok"
        except Exception as e:
            status["supabase"] = f"error: {e}"

        try:
            import redis
            r = redis.from_url(os.environ["REDIS_URL"])
            r.ping()
            status["redis"] = "ok"
        except Exception as e:
            status["redis"] = f"error: {e}"

        self._respond(200, status)


def main():
    port = int(os.getenv("AGENTS_PORT", "8080"))
    logger.info(f"UBT OS запущен на порту {port}")
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
