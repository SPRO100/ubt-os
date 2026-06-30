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
import hashlib
import hmac
import logging
import os
import signal
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

from ubt_os.core.logging_config import setup_logging, set_request_id

setup_logging()
logger = logging.getLogger("ubt_os.main")

# Простые in-memory счётчики для Prometheus-совместимого /metrics
_METRICS: dict[str, int] = {
    "webhook_requests_total": 0,
    "webhook_requests_ok": 0,
    "webhook_requests_error": 0,
    "webhook_requests_unauthorized": 0,
}


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

    def _verify_signature(self, raw_body: bytes) -> bool:
        """HMAC-SHA256 проверка подписи вебхука. Пропускает если секрет не задан."""
        secret = os.getenv("WEBHOOK_SECRET")
        if not secret:
            return True
        sig_header = self.headers.get("X-Webhook-Signature", "")
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig_header, expected)

    def do_POST(self):
        length   = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b""

        _METRICS["webhook_requests_total"] += 1

        if not self._verify_signature(raw_body):
            _METRICS["webhook_requests_unauthorized"] += 1
            self._respond(403, {"error": "invalid signature"})
            logger.warning("Webhook: отклонён — неверная подпись", extra={"path": self.path})
            return

        # Correlation ID: берём из заголовка n8n или генерируем
        request_id = self.headers.get("X-Request-Id") or str(uuid.uuid4())[:8]
        set_request_id(request_id)

        body   = json.loads(raw_body) if raw_body else {}
        action = body.get("action", "unknown")

        logger.info("Webhook received", extra={"path": self.path, "action": action, "request_id": request_id})

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
            "/orchestrator/chat":     self._run_orchestrator_chat,
            # DOHOO-inspired: A14 + прямая публикация + транскрипция
            "/competitor/analyze":    self._run_competitor_analyze,
            "/publish/direct":        self._run_publish_direct,
            "/publish/bulk":          self._run_publish_bulk,
            "/transcribe":            self._run_transcribe,
            "/hooks/top":             self._run_hooks_top,
        }

        handler = routes.get(self.path)
        if handler:
            result = asyncio.run(handler(body))
            _METRICS["webhook_requests_ok"] += 1
            self._respond(200, result if isinstance(result, dict) else {"status": "accepted"})
        else:
            _METRICS["webhook_requests_error"] += 1
            self._respond(404, {"error": "unknown route"})

    def do_GET(self):
        # FIX #1 — health-check маршрут, который дёргает n8n / Railway
        if self.path == "/health/check-all":
            asyncio.run(self._run_health_check())
            return
        if self.path == "/metrics":
            self._serve_metrics()
            return
        self._respond(404, {"error": "unknown route"})

    def _respond(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *_):
        pass  # подавляем стандартные логи HTTPServer

    def do_OPTIONS(self):
        """PATCH: CORS preflight для POST-запросов с Content-Type: application/json."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

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
        if not target.is_relative_to(vault):
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

    async def _run_orchestrator_chat(self, body: dict):
        """PATCH: чат с оркестратором, со контекстом конкретного проекта (vertical)."""
        from anthropic import AsyncAnthropic

        vertical_id = body.get("vertical_id")
        message = (body.get("message") or "").strip()
        if not vertical_id or not message:
            return {"error": "vertical_id и message обязательны"}

        db = _get_db()

        vconf = db.table("vertical_configs").select("id,name,config_yaml").eq("id", vertical_id).limit(1).execute()
        if not vconf.data:
            return {"error": f"проект '{vertical_id}' не найден"}
        project = vconf.data[0]

        knowledge = (
            db.table("knowledge_entries")
            .select("type,content,created_at")
            .eq("vertical", vertical_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        ).data

        history = (
            db.table("chat_messages")
            .select("role,content")
            .eq("vertical_id", vertical_id)
            .order("created_at", desc=False)
            .limit(20)
            .execute()
        ).data

        system_prompt = (
            f"Ты — ORCHESTRATOR проекта «{project['name']}» в системе UBT OS.\n"
            f"Конфигурация проекта: {project['config_yaml']}\n\n"
            f"Последние записи базы знаний этого проекта:\n"
            + ("\n".join(f"- [{k['type']}] {k['content'][:200]}" for k in knowledge) if knowledge else "пока нет записей")
            + "\n\nОтвечай по-русски, кратко и по делу, в контексте именно этого проекта."
        )

        messages = [{"role": h["role"], "content": h["content"]} for h in history]
        messages.append({"role": "user", "content": message})

        client = AsyncAnthropic()
        resp = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )
        reply = resp.content[0].text

        db.table("chat_messages").insert({"vertical_id": vertical_id, "role": "user", "content": message}).execute()
        db.table("chat_messages").insert({"vertical_id": vertical_id, "role": "assistant", "content": reply}).execute()

        return {"reply": reply, "vertical_id": vertical_id}

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
            logger.info(f"strategy/collect завершён: brief_id={result.get('brief_id')}")
            return result
        return {"status": "skipped", "reason": "lock_busy"}

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

    # ── DOHOO-inspired роуты ──────────────────────────────────

    async def _run_competitor_analyze(self, body: dict):
        """A14 COMPETITOR_ANALYST: анализ хуков конкурентов."""
        from ubt_os.core import pipeline_lock
        from ubt_os.agents.competitor_analyst import run_competitor_analyst
        vertical     = body.get("vertical", "nutra")
        lookback     = int(body.get("lookback_days", 3))
        async with pipeline_lock(f"competitor-analyze-{vertical}", 600) as acquired:
            if not acquired:
                return {"status": "skipped", "reason": "lock_busy"}
            return await run_competitor_analyst(vertical=vertical, lookback_days=lookback)

    async def _run_publish_direct(self, body: dict):
        """Прямая публикация в соцсеть без лимитов аккаунтов."""
        from ubt_os.pipelines.social_publisher import create_and_publish
        platform     = body.get("platform")
        account_id   = body.get("account_id")
        media_url    = body.get("media_url", "")
        if not platform or not account_id:
            return {"error": "platform и account_id обязательны"}
        return await create_and_publish(
            platform=platform,
            account_id=account_id,
            media_url=media_url,
            caption=body.get("caption", ""),
            hashtags=body.get("hashtags", []),
            content_type=body.get("content_type", "video"),
            extra=body.get("extra", {}),
        )

    async def _run_publish_bulk(self, body: dict):
        """Массовая публикация: список джобов без ограничений."""
        from ubt_os.pipelines.social_publisher import bulk_publish
        jobs = body.get("jobs", [])
        if not jobs:
            return {"error": "jobs[] обязателен"}
        return {"results": await bulk_publish(jobs)}

    async def _run_transcribe(self, body: dict):
        """AI-транскрипция видео + извлечение хука."""
        from ubt_os.agents.transcription_agent import run_transcription, run_batch_transcription
        urls = body.get("video_urls") or ([body.get("video_url")] if body.get("video_url") else [])
        if not urls:
            return {"error": "video_url или video_urls обязателен"}
        kwargs = {
            "source":   body.get("source", "competitor"),
            "vertical": body.get("vertical", "nutra"),
            "platform": body.get("platform", "tiktok"),
            "geo":      body.get("geo", "RU"),
            "language": body.get("language", "ru"),
        }
        if len(urls) == 1:
            return await run_transcription(urls[0], **kwargs)
        return {"results": await run_batch_transcription(urls, **kwargs)}

    async def _run_hooks_top(self, body: dict):
        """Возвращает топ хуков из библиотеки hook_templates."""
        db       = _get_db()
        vertical = body.get("vertical", "nutra")
        platform = body.get("platform")
        limit    = int(body.get("limit", 20))
        q = (
            db.table("hook_templates")
            .select("hook_type,hook_text,visual_style,platform,geo,views_at_capture,er_at_capture,created_at")
            .eq("vertical", vertical)
            .eq("is_active", True)
            .order("er_at_capture", desc=True)
            .limit(limit)
        )
        if platform:
            q = q.eq("platform", platform)
        return {"hooks": q.execute().data}

    def _serve_metrics(self):
        """GET /metrics — Prometheus-совместимый текстовый формат."""
        lines = ["# HELP ubt_os_webhook UBT OS webhook counters", "# TYPE ubt_os_webhook counter"]
        for name, value in _METRICS.items():
            lines.append(f"{name} {value}")
        body = "\n".join(lines).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(body)

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
    server = ThreadingHTTPServer(("0.0.0.0", port), WebhookHandler)

    def _shutdown(signum, frame):
        logger.info("UBT OS: получен сигнал завершения, останавливаем сервер...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    server.serve_forever()


if __name__ == "__main__":
    main()
