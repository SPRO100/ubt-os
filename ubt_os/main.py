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
            "/strategy/collect":      self._run_strategy_collect,
            "/risk/run":              self._run_risk,
            "/knowledge/synthesize":  self._run_knowledge_synthesize,
            "/obsidian/write":        self._run_obsidian_write,
            "/obsidian/append":       self._run_obsidian_append,
            "/orchestrator/chat":     self._run_orchestrator_chat,
            # Управление аккаунтами
            "/accounts/add":          self._accounts_add,
            "/accounts/import":       self._accounts_import,
            "/accounts/checker/run":  self._accounts_checker_run,
            # Управление проектами
            "/projects/add":          self._projects_add,
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
        if self.path == "/health/check-all":
            asyncio.run(self._run_health_check())
            return
        if self.path == "/metrics":
            self._serve_metrics()
            return
        if self.path.startswith("/accounts/list"):
            asyncio.run(self._accounts_list())
            return
        self._respond(404, {"error": "unknown route"})

    async def _accounts_list(self):
        """GET /accounts/list?platform=tiktok&vertical_id=betting_ru&status=active"""
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        db = _get_db()
        q = db.table("accounts").select(
            "id,platform,username,status,warming_phase,warming_day,geo,niche,partner_program,vertical_id,created_at"
        )
        if qs.get("platform"):
            q = q.eq("platform", qs["platform"][0])
        if qs.get("vertical_id"):
            q = q.eq("vertical_id", qs["vertical_id"][0])
        if qs.get("status"):
            q = q.eq("status", qs["status"][0])
        rows = q.order("created_at", desc=True).limit(200).execute().data
        self._respond(200, {"accounts": rows, "total": len(rows)})

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

        # Авто-саммари каждые 10 сообщений
        count_res = db.table("chat_messages").select("id", count="exact").eq("vertical_id", vertical_id).execute()
        total = count_res.count or 0
        if total > 0 and total % 10 == 0:
            await self._auto_summarize_chat(vertical_id, project["name"], db)

        return {"reply": reply, "vertical_id": vertical_id}

    async def _auto_summarize_chat(self, vertical_id: str, project_name: str, db):
        """Каждые 10 сообщений сжимает чат в инсайт и кладёт в базу знаний проекта."""
        from anthropic import AsyncAnthropic
        recent = (
            db.table("chat_messages")
            .select("role,content")
            .eq("vertical_id", vertical_id)
            .order("created_at", desc=False)
            .limit(20)
            .execute()
        ).data
        if len(recent) < 5:
            return
        history_text = "\n".join(
            f"{h['role'].upper()}: {h['content'][:400]}" for h in recent
        )
        client = AsyncAnthropic()
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content":
                f"Переписка с оркестратором проекта «{project_name}»:\n\n{history_text}\n\n"
                "Выдели 3-7 ключевых инсайтов, решений и договорённостей пунктами. "
                "Только суть, без лишних слов. Это сохранится в базу знаний."}],
        )
        summary = resp.content[0].text
        db.table("knowledge_entries").insert({
            "type": "insight",
            "subtype": "chat_summary",
            "vertical": vertical_id,
            "content": f"[Авто-саммари чата]\n{summary}",
            "metadata": {"source": "auto_chat_summarizer", "msg_count": len(recent)},
        }).execute()
        logger.info(f"auto_summarize_chat: сохранён инсайт для {vertical_id} ({len(recent)} сообщений)")

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


    # ── Управление аккаунтами ────────────────────────────

    async def _accounts_add(self, body: dict):
        """POST /accounts/add — добавить один аккаунт."""
        ALLOWED_PLATFORMS = {"tiktok", "youtube", "instagram", "telegram"}
        platform = (body.get("platform") or "").lower()
        if platform not in ALLOWED_PLATFORMS:
            return {"error": f"platform должен быть одним из: {', '.join(sorted(ALLOWED_PLATFORMS))}"}
        username = (body.get("username") or "").strip()
        if not username:
            return {"error": "username обязателен"}
        row = {
            "platform":           platform,
            "username":           username,
            "niche":              body.get("niche"),
            "geo":                body.get("geo"),
            "partner_program":    body.get("partner_program"),
            "gologin_profile_id": body.get("gologin_profile_id"),
            "vertical_id":        body.get("vertical_id"),
            "status":             "new",
        }
        # убираем None-поля чтобы не перебить дефолты БД
        row = {k: v for k, v in row.items() if v is not None}
        db = _get_db()
        result = db.table("accounts").insert(row).execute()
        inserted = result.data[0] if result.data else {}
        logger.info(f"accounts/add: добавлен {platform}/@{username} id={inserted.get('id','?')}")
        return {"status": "ok", "account": inserted}

    async def _accounts_import(self, body: dict):
        """POST /accounts/import — массовый импорт списка аккаунтов.

        Body: { "accounts": [ {platform, username, geo?, niche?, ...}, ... ] }
        Принимает до 200 аккаунтов за раз.
        """
        ALLOWED_PLATFORMS = {"tiktok", "youtube", "instagram", "telegram"}
        raw = body.get("accounts")
        if not isinstance(raw, list) or not raw:
            return {"error": "accounts должен быть непустым массивом"}
        if len(raw) > 200:
            return {"error": "максимум 200 аккаунтов за один запрос"}

        rows, skipped = [], []
        for i, item in enumerate(raw):
            platform = (item.get("platform") or "").lower()
            username = (item.get("username") or "").strip()
            if platform not in ALLOWED_PLATFORMS or not username:
                skipped.append({"index": i, "reason": "пустой username или неверная платформа", "item": item})
                continue
            rows.append({
                "platform":           platform,
                "username":           username,
                "niche":              item.get("niche"),
                "geo":                item.get("geo"),
                "partner_program":    item.get("partner_program"),
                "gologin_profile_id": item.get("gologin_profile_id"),
                "status":             "new",
            })
            rows[-1] = {k: v for k, v in rows[-1].items() if v is not None}

        if not rows:
            return {"error": "все записи не прошли валидацию", "skipped": skipped}

        db = _get_db()
        result = db.table("accounts").insert(rows).execute()
        inserted_count = len(result.data) if result.data else 0
        logger.info(f"accounts/import: вставлено {inserted_count}, пропущено {len(skipped)}")
        return {
            "status":   "ok",
            "inserted": inserted_count,
            "skipped":  len(skipped),
            "skipped_details": skipped,
        }

    async def _accounts_checker_run(self, body: dict):
        """POST /accounts/checker/run — запустить чекер с фильтрами."""
        from ubt_os.agents import AccountChecker
        db = _get_db()
        checker = AccountChecker(db_client=db)
        results = await checker.check_all(
            platform=body.get("platform") or None,
            status_filter=body.get("status_filter") or None,
            days=body.get("days") or None,
            vertical_id=body.get("vertical_id") or None,
        )
        summary = {"ok": 0, "warn": 0, "stop": 0}
        for r in results:
            v = r.get("verdict", "ok")
            summary[v] = summary.get(v, 0) + 1
        logger.info(f"accounts/checker/run: проверено {len(results)}, summary={summary}")
        return {"status": "ok", "total": len(results), "summary": summary, "results": results}


    async def _projects_add(self, body: dict):
        """POST /projects/add — создать новый проект (vertical_configs)."""
        pid  = (body.get("id") or "").strip().lower()
        name = (body.get("name") or "").strip()
        if not pid or not name:
            return {"error": "id и name обязательны"}
        import re
        pid = re.sub(r"[^a-z0-9_]", "_", pid)
        category = body.get("category", "ecommerce")
        geo      = body.get("geo") or []
        primary  = body.get("primary_platform", "instagram")
        model    = body.get("monetization_model", "lead_gen")
        config   = {
            "vertical":     {"id": pid, "name": name, "category": category},
            "audience":     {"geo": geo if isinstance(geo, list) else [geo], "language": ["ru"]},
            "content":      {"tone": "", "cta_style": ""},
            "platforms":    {"allowed": ["instagram", "telegram", "tiktok", "youtube"], "primary": primary},
            "monetization": {"model": model, "client_type": "white"},
        }
        db = _get_db()
        result = db.table("vertical_configs").insert({
            "id": pid, "name": name, "category": category, "config_yaml": config
        }).execute()
        inserted = result.data[0] if result.data else {}
        logger.info(f"projects/add: создан проект {pid} / {name}")
        return {"status": "ok", "project": inserted}


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
