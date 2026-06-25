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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("ubt_os.main")

# AgentOps — трекинг LiteLLM расходов (регистрирует callback один раз при старте)
try:
    from ubt_os.core.agentops_tracker import setup_agentops
    setup_agentops()
except Exception as _ao_err:
    logger.warning(f"AgentOps init skipped: {_ao_err}")


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
        raw     = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as e:
            logger.warning(f"Bad JSON body: {e}")
            self._respond(400, {"error": "invalid JSON body"})
            return
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
            "/orchestrator/chat":     self._run_orchestrator_chat,
            # Sprint 2
            "/compliance/check":      self._run_compliance_check,
            "/keitaro/postback":      self._run_keitaro_postback,
            "/usage/summary":         self._run_usage_summary,
            # Phase 7 — Telegram
            "/telegram/warmup":       self._run_tg_warmup,
            "/telegram/comment":      self._run_tg_comment,
            "/telegram/react":        self._run_tg_react,
            "/telegram/status":       self._run_tg_status,
            "/telegram/login/send-code":    self._run_tg_send_code,
            "/telegram/login/confirm-code": self._run_tg_confirm_code,
            "/telegram/login/confirm-2fa":  self._run_tg_confirm_2fa,
            "/telegram/account/add":        self._run_tg_add_account,
            "/telegram/comment/log":        self._run_tg_comment_log,
            "/telegram/channels/parse":     self._run_tg_parse_channels,
            "/telegram/channels/targets":   self._run_tg_channel_targets,
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
        from ubt_os.core.compliance_gate import get_gate
        async with pipeline_lock("video-pipeline-nutra", 600) as acquired:
            if not acquired:
                logger.info("NUTRA: lock занят, пропускаем")
                return
            text = body.get("caption") or body.get("text") or body.get("description", "")
            geo  = body.get("geo", "PL")
            if text:
                result = get_gate().check(text, vertical="nutra", geo=geo)
                if result.verdict == "block":
                    logger.warning(f"NUTRA compliance BLOCK [{geo}]: {result.reason}")
                    return
                if result.verdict == "warn":
                    logger.warning(f"NUTRA compliance WARN [{geo}]: {result.reason}")
            logger.info("NUTRA pipeline: запуск ✅")

    async def _run_ubt(self, body: dict):
        from ubt_os.core import pipeline_lock
        from ubt_os.core.compliance_gate import get_gate
        async with pipeline_lock("video-pipeline-ubt", 600) as acquired:
            if not acquired:
                logger.info("UBT: lock занят, пропускаем")
                return
            text = body.get("caption") or body.get("text") or body.get("description", "")
            geo  = body.get("geo", "RU")
            if text:
                result = get_gate().check(text, vertical="betting", geo=geo)
                if result.verdict == "block":
                    logger.warning(f"UBT compliance BLOCK [{geo}]: {result.reason}")
                    return
                if result.verdict == "warn":
                    logger.warning(f"UBT compliance WARN [{geo}]: {result.reason}")
            logger.info("UBT pipeline: запуск ✅")

    async def _run_compliance_check(self, body: dict):
        """Прямая проверка текста — для n8n и ручного тестирования."""
        from ubt_os.core.compliance_gate import get_gate
        text     = body.get("text", "")
        vertical = body.get("vertical", "nutra")
        geo      = body.get("geo", "PL")
        result   = get_gate().check(text, vertical=vertical, geo=geo)
        self._respond(200, {
            "verdict":  result.verdict,
            "reason":   result.reason,
            "matched":  result.matched,
            "geo":      result.geo,
            "vertical": result.vertical,
        })

    async def _run_keitaro_postback(self, body: dict):
        """Приём S2S postback от Keitaro — запись revenue_event в Supabase."""
        from ubt_os.utils.attribution import KeitaroPostbackHandler
        handler = KeitaroPostbackHandler(db_client=_get_db())
        result  = handler.handle(body)
        status  = 200 if result.get("ok") else 400
        self._respond(status, result)

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

    # ── Phase 7 — Telegram ────────────────────────────────────

    async def _run_tg_warmup(self, body: dict):
        from ubt_os.telegram.orchestrator import run_warmup
        return await run_warmup(body)

    async def _run_tg_comment(self, body: dict):
        from ubt_os.telegram.orchestrator import run_comment
        return await run_comment(body)

    async def _run_tg_react(self, body: dict):
        from ubt_os.telegram.orchestrator import run_react
        return await run_react(body)

    async def _run_tg_status(self, body: dict):
        from ubt_os.telegram.orchestrator import get_status
        return await get_status(body)

    async def _run_tg_add_account(self, body: dict):
        """Регистрирует новый аккаунт в tg_accounts."""
        required = ["phone", "api_id", "api_hash"]
        for f in required:
            if not body.get(f):
                return {"ok": False, "error": f"missing field: {f}"}
        db = _get_db()
        row = {
            "phone":    body["phone"],
            "api_id":   int(body["api_id"]),
            "api_hash": body["api_hash"],
            "vertical": body.get("vertical", "nutra"),
            "geo":      body.get("geo", "PL"),
            "proxy":    body.get("proxy"),
            "status":   "idle",
        }
        result = db.table("tg_accounts").insert(row).execute()
        account_id = result.data[0]["id"] if result.data else None
        logger.info(f"TG account added: {body['phone']} id={account_id}")
        return {"ok": True, "account_id": account_id, "phone": body["phone"]}

    async def _run_tg_send_code(self, body: dict):
        """Шаг 1 авторизации: отправить SMS-код на номер."""
        import redis as redis_lib
        from ubt_os.telegram.session_manager import TelegramSessionManager, TgAccount
        from ubt_os.telegram.client import login_send_code
        db    = _get_db()
        redis = redis_lib.from_url(os.environ["REDIS_URL"])
        sm    = TelegramSessionManager(db, redis)
        account_id = body.get("account_id")
        acc = sm.get_account(account_id) if account_id else None
        if not acc:
            return {"ok": False, "error": "account not found"}
        result = await login_send_code(acc)
        # Сохраняем phone_code_hash в Redis на 10 минут
        redis.set(f"tg:pch:{account_id}", result["phone_code_hash"], ex=600)
        return result

    async def _run_tg_confirm_code(self, body: dict):
        """Шаг 2 авторизации: подтвердить SMS-код."""
        import redis as redis_lib
        from ubt_os.telegram.session_manager import TelegramSessionManager
        from ubt_os.telegram.client import login_confirm_code
        db    = _get_db()
        redis = redis_lib.from_url(os.environ["REDIS_URL"])
        sm    = TelegramSessionManager(db, redis)
        account_id = body.get("account_id")
        code       = body.get("code", "")
        acc = sm.get_account(account_id) if account_id else None
        if not acc:
            return {"ok": False, "error": "account not found"}
        pch = redis.get(f"tg:pch:{account_id}")
        if not pch:
            return {"ok": False, "error": "phone_code_hash expired — send code again"}
        result = await login_confirm_code(acc, code, pch.decode(), sm)
        if result.get("ok"):
            sm.update_account(account_id, status="warming", warming_day=0)
        return result

    async def _run_tg_confirm_2fa(self, body: dict):
        """Шаг 3 авторизации: подтвердить 2FA пароль."""
        import redis as redis_lib
        from ubt_os.telegram.session_manager import TelegramSessionManager
        from ubt_os.telegram.client import login_confirm_2fa
        db    = _get_db()
        redis = redis_lib.from_url(os.environ["REDIS_URL"])
        sm    = TelegramSessionManager(db, redis)
        account_id = body.get("account_id")
        password   = body.get("password", "")
        acc = sm.get_account(account_id) if account_id else None
        if not acc:
            return {"ok": False, "error": "account not found"}
        result = await login_confirm_2fa(acc, password, sm)
        if result.get("ok"):
            sm.update_account(account_id, status="warming", warming_day=0)
        return result

    async def _run_tg_comment_log(self, body: dict):
        """GET /telegram/comment/log — последние N комментариев из Supabase."""
        import urllib.request as _ur, json as _j
        supa_url = os.environ.get("SUPABASE_URL", "")
        supa_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        limit = int(body.get("limit", 50))
        vertical = body.get("vertical")
        qs = f"select=id,account_id,phone,channel,text,vertical,posted_at&order=posted_at.desc&limit={limit}"
        if vertical:
            qs += f"&vertical=eq.{vertical}"
        try:
            req = _ur.Request(f"{supa_url}/rest/v1/comment_log?{qs}")
            req.add_header("apikey", supa_key)
            req.add_header("Authorization", f"Bearer {supa_key}")
            with _ur.urlopen(req, timeout=5) as r:
                return {"ok": True, "log": _j.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e), "log": []}

    async def _run_tg_parse_channels(self, body: dict):
        """POST /telegram/channels/parse — парсим каналы по ключевому слову."""
        from ubt_os.telegram.channel_parser import TelegramChannelParser
        keyword  = body.get("keyword", "")
        vertical = body.get("vertical", "nutra")
        limit    = int(body.get("limit", 20))
        if not keyword:
            return {"ok": False, "error": "keyword required"}
        parser = TelegramChannelParser()
        return await parser.parse_by_keyword(keyword, vertical, limit)

    async def _run_tg_channel_targets(self, body: dict):
        """POST /telegram/channels/targets — список сохранённых target-каналов."""
        from ubt_os.telegram.channel_parser import TelegramChannelParser
        vertical = body.get("vertical")
        parser = TelegramChannelParser()
        targets = await parser.get_targets(vertical)
        return {"ok": True, "targets": targets}

    async def _run_usage_summary(self, body: dict):
        """GET/POST /usage/summary — агрегат расходов LiteLLM за N дней."""
        from ubt_os.core.agentops_tracker import get_usage_summary
        days = int(body.get("days", 7))
        return get_usage_summary(days=days)

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
    server.serve_forever()


if __name__ == "__main__":
    main()
