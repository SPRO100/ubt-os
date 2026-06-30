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
            "/agents/run":            self._run_agent,
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

        agent_catalog = (
            "\n\nДОСТУПНЫЕ АГЕНТЫ (предлагай когда они помогут задаче):\n"
            "- A19 text_humanizer: очистка текста от AI-маркеров и шаблонности\n"
            "- A20 trend_scraper: анализ трендов и конкурентов по URL или вертикали\n"
            "- A21 content_creator: генерация before/after, хуков, UGC по Brand Voice\n"
            "- A22 ads_auditor: аудит TikTok/Meta/YouTube аккаунтов, Health Score 0–100\n"
            "- A23 youtube_creator: сценарии Shorts/Long-form, хуки, metadata, thumbnail\n"
            "- A24 obsidian_brain: запрос или добавление знаний в Obsidian Vault\n"
            "- A25 compliance_gate: проверка текста на запрещённые заявления перед публикацией\n"
            "- A26 publer_publisher: публикация в TikTok/Facebook/Instagram через Publer API\n"
            "- A27 spy_analyzer: анализ крипов конкурентов из PiPiAds/AdHeart, паттерны хуков и brief для A21\n"
            "- A28 warmup_manager: трекер 14-дневного прогрева аккаунтов, GEO-инфраструктура, лимиты активности\n"
            "- A29 prelanding_generator: генерация HTML прелендингов (quiz/story/article/vsl) для воронки\n"
            "- A30 higgsfield_agent: генерация UGC-видео 9:16, Shorts 15–60с и каруселей через Higgsfield AI\n\n"
            "Если задача пользователя явно подходит для одного из агентов — добавь в КОНЕЦ ответа строку:\n"
            "[AGENT_SUGGEST: agent_id|Что именно агент сделает для этой задачи]\n"
            "Пример: [AGENT_SUGGEST: content_creator|Создать 3 варианта hook для нутра GEO US]\n"
            "Добавляй не более 2 предложений. Если агент не нужен — ничего не добавляй.\n\n"
            "Если в ответе уместна ссылка на внешний сервис (PiPiAds, AdHeart, Publer, Higgsfield, Keitaro и т.д.) — "
            "добавь в конец ответа: [QUICK_LINK: Название|https://url]\n"
            "Примеры: [QUICK_LINK: PiPiAds|https://www.pipiads.com] или [QUICK_LINK: Publer|https://app.publer.io]\n"
            "Не более 3 ссылок. Только если они реально помогут пользователю прямо сейчас."
        )

        system_prompt = (
            f"Ты — ORCHESTRATOR проекта «{project['name']}» в системе UBT OS.\n"
            f"Конфигурация проекта: {project['config_yaml']}\n\n"
            f"Последние записи базы знаний этого проекта:\n"
            + ("\n".join(f"- [{k['type']}] {k['content'][:200]}" for k in knowledge) if knowledge else "пока нет записей")
            + "\n\nОтвечай по-русски, кратко и по делу, в контексте именно этого проекта."
            + agent_catalog
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
        raw_reply = resp.content[0].text

        import re as _re
        suggestions = []
        quick_links = []

        def _extract_markers(text):
            for m in _re.finditer(r"\[AGENT_SUGGEST:\s*([^\|]+)\|([^\]]+)\]", text):
                suggestions.append({"agent": m.group(1).strip(), "description": m.group(2).strip()})
            for m in _re.finditer(r"\[QUICK_LINK:\s*([^\|]+)\|([^\]]+)\]", text):
                quick_links.append({"label": m.group(1).strip(), "url": m.group(2).strip()})
            text = _re.sub(r"\[AGENT_SUGGEST:[^\]]+\]", "", text)
            text = _re.sub(r"\[QUICK_LINK:[^\]]+\]", "", text)
            return text.strip()

        reply = _extract_markers(raw_reply)

        # Auto-add agent launch quick_links from suggestions
        _agent_links = {
            "spy_analyzer":         [
                {"label": "PiPiAds", "url": "https://www.pipiads.com"},
                {"label": "AdHeart", "url": "https://adheart.me"},
            ],
            "publer_publisher":     [{"label": "Publer", "url": "https://app.publer.io"}],
            "higgsfield_agent":     [{"label": "Higgsfield", "url": "https://higgsfield.ai"}],
            "prelanding_generator": [{"label": "Keitaro", "url": "https://keitaro.io"}],
            "warmup_manager":       [
                {"label": "IPRoyal", "url": "https://iproyal.com"},
                {"label": "Airalo", "url": "https://www.airalo.com"},
            ],
        }
        existing_urls = {ql["url"] for ql in quick_links}
        for s in suggestions:
            for link in _agent_links.get(s["agent"], []):
                if link["url"] not in existing_urls and len(quick_links) < 4:
                    quick_links.append(link)
                    existing_urls.add(link["url"])

        db.table("chat_messages").insert({"vertical_id": vertical_id, "role": "user", "content": message}).execute()
        db.table("chat_messages").insert({"vertical_id": vertical_id, "role": "assistant", "content": reply}).execute()

        return {
            "reply": reply,
            "vertical_id": vertical_id,
            "agent_suggestions": suggestions,
            "quick_links": quick_links,
        }

    async def _run_agent(self, body: dict):
        """POST /agents/run — запуск A19–A24 напрямую из браузера."""
        agent  = body.get("agent", "")
        params = body.get("params", {})

        try:
            if agent == "content_creator":
                from ubt_os.agents import ContentCreator, ContentFormat
                creator = ContentCreator()
                fmt     = ContentFormat(params.get("format", "hook_problem"))
                result  = await creator.create(
                    fmt,
                    params.get("vertical", "nutra"),
                    params.get("geo", "US"),
                    params.get("offer", ""),
                )
                return {"result": result.humanized_text, "score": result.score, "passed": result.passed_quality}

            elif agent == "text_humanizer":
                from ubt_os.agents import TextHumanizer
                h      = TextHumanizer()
                result = await h.humanize(
                    params.get("text", ""),
                    params.get("geo", "US"),
                    params.get("vertical", "nutra"),
                )
                return {"result": result.humanized_text, "score": result.total_score, "passed": result.passed}

            elif agent == "trend_scraper":
                from ubt_os.agents import TrendScraper
                scraper = TrendScraper()
                if params.get("url"):
                    r = await scraper.analyze_url(params["url"])
                else:
                    r = await scraper.find_trends(params.get("vertical", "nutra"), params.get("geo", "US"))
                return {"hooks": r.hooks, "pains": r.pains, "action_items": r.action_items, "trend_score": r.trend_score}

            elif agent == "ads_auditor":
                from ubt_os.agents import AdsAuditor
                auditor = AdsAuditor()
                result  = await auditor.audit(
                    params.get("platform", "tiktok"),
                    params.get("vertical", "nutra"),
                    params.get("account_data", {}),
                    params.get("geo", "US"),
                )
                return {"health_score": result.health_score, "grade": result.grade,
                        "critical_issues": result.critical_issues, "quick_wins": result.quick_wins}

            elif agent == "youtube_creator":
                from ubt_os.agents import YoutubeCreator, YTFormat
                creator = YoutubeCreator()
                fmt     = YTFormat(params.get("format", "shorts"))
                result  = await creator.create(
                    fmt,
                    params.get("vertical", "nutra"),
                    params.get("geo", "US"),
                    params.get("topic", ""),
                    params.get("offer", ""),
                )
                return {"content": result.content}

            elif agent == "obsidian_brain":
                from ubt_os.agents import ObsidianBrain
                brain  = ObsidianBrain()
                action = params.get("action", "query")
                if action == "ingest":
                    r = await brain.ingest(params.get("text", ""), params.get("source_name", "dashboard"))
                    return {"pages_created": r.pages_created, "filenames": r.filenames, "summary": r.summary}
                elif action == "health":
                    r = await brain.health_check()
                    return {"health_score": r.health_score, "dead_links": len(r.dead_links), "action_items": r.action_items}
                else:
                    r = await brain.query(params.get("question", ""))
                    return {"answer": r.answer, "sources": r.sources, "confidence": r.confidence}

            elif agent == "compliance_gate":
                from ubt_os.agents import ComplianceGate
                gate   = ComplianceGate()
                result = await gate.check(
                    params.get("text", ""),
                    params.get("vertical", "nutra"),
                    params.get("geo", "US"),
                )
                return {
                    "risk_level": result.risk_level.value,
                    "score": result.score,
                    "passed": result.passed,
                    "violations": result.violations,
                    "suggestions": result.suggestions,
                    "clean_version": result.clean_version,
                    "reason": result.reason,
                }

            elif agent in ("blotato_publisher", "publer_publisher"):
                from ubt_os.agents import PubelerPublisher, PublishPlatform
                publisher = PubelerPublisher()
                result    = await publisher.publish(
                    params.get("text", ""),
                    PublishPlatform(params.get("platform", "tiktok")),
                    params.get("vertical", "nutra"),
                    params.get("geo", "US"),
                    params.get("affiliate_url", ""),
                    params.get("media_url", ""),
                    profile_ids=params.get("profile_ids") or None,
                    dry_run=params.get("dry_run", True),
                )
                return {
                    "status": result.status,
                    "platform": result.platform,
                    "compliance_score": result.compliance_score,
                    "compliance_risk": result.compliance_risk,
                    "url": result.url,
                    "error": result.error,
                }

            elif agent == "spy_analyzer":
                from ubt_os.agents import SpyAnalyzer
                analyzer = SpyAnalyzer()
                creatives = params.get("creatives", [])
                if isinstance(creatives, str):
                    creatives = [creatives]
                action = params.get("action", "analyze")
                if action == "compare_hooks":
                    result = await analyzer.compare_hooks(
                        params.get("hooks", []),
                        params.get("vertical", "nutra"),
                        params.get("geo", "US"),
                    )
                    return result
                result = await analyzer.analyze(
                    creatives,
                    params.get("vertical", "nutra"),
                    params.get("geo", "US"),
                    params.get("platform", "tiktok"),
                    params.get("focus", "all"),
                )
                return {
                    "hook_patterns": result.hook_patterns,
                    "content_structures": result.content_structures,
                    "key_phrases": result.key_phrases,
                    "forbidden_phrases": result.forbidden_phrases,
                    "winning_formats": result.winning_formats,
                    "creative_brief": result.creative_brief,
                    "a21_prompt_extension": result.a21_prompt_extension,
                    "creatives_analyzed": result.creatives_analyzed,
                }

            elif agent == "warmup_manager":
                from ubt_os.agents import WarmupManager
                mgr    = WarmupManager()
                action = params.get("action", "check")
                account_id = params.get("account_id", "")
                if action == "register":
                    result = mgr.register(
                        account_id,
                        geo=params.get("geo", "US"),
                        account_type=params.get("account_type", "new"),
                        platform=params.get("platform", "tiktok"),
                        device_type=params.get("device_type", "GLOBAL"),
                        proxy_type=params.get("proxy_type", "mobile"),
                        has_local_sim=params.get("has_local_sim", False),
                        notes=params.get("notes", ""),
                    )
                elif action == "list":
                    return {"accounts": mgr.list_accounts()}
                elif action == "enable_bio_link":
                    return mgr.enable_bio_link(account_id)
                elif action == "reset":
                    return mgr.reset(account_id)
                elif action == "validate_infra":
                    return mgr.validate_infra(
                        account_id,
                        params.get("device_type", "GLOBAL"),
                        params.get("proxy_type", "mobile"),
                        params.get("has_local_sim", False),
                        params.get("geo", "US"),
                    )
                else:
                    result = mgr.check(account_id)
                from dataclasses import asdict
                return {
                    "account_id": result.account_id,
                    "status": result.status,
                    "current_day": result.current_day,
                    "total_days": result.total_days,
                    "progress_pct": result.progress_pct,
                    "today_limits": result.today_limits,
                    "content_split": result.content_split,
                    "bio_link_allowed": result.bio_link_allowed,
                    "infra_issues": result.infra_issues,
                    "ready_to_publish": result.ready_to_publish,
                    "next_action": result.next_action,
                    "message": result.message,
                }

            elif agent == "prelanding_generator":
                from ubt_os.agents import PrelandingGenerator
                gen    = PrelandingGenerator()
                action = params.get("action", "generate")
                if action == "generate_variants":
                    results = await gen.generate_variants(
                        params.get("offer_name", "Product"),
                        params.get("vertical", "nutra"),
                        params.get("geo", "US"),
                        params.get("billing_model", "COD"),
                        params.get("formats", ["story", "native_article"]),
                    )
                    return {
                        "variants": [
                            {"format": r.format, "language": r.language,
                             "estimated_cr": r.estimated_cr, "word_count": r.word_count,
                             "html_content": r.html_content, "funnel_tips": r.funnel_tips}
                            for r in results
                        ]
                    }
                result = await gen.generate(
                    params.get("offer_name", "Product"),
                    params.get("vertical", "nutra"),
                    params.get("geo", "US"),
                    params.get("billing_model", "COD"),
                    params.get("format", "story"),
                    params.get("language"),
                    params.get("product_benefits", []),
                    params.get("target_audience", ""),
                    params.get("lander_url", "LANDER_URL"),
                )
                return {
                    "offer_name": result.offer_name,
                    "format": result.format,
                    "language": result.language,
                    "estimated_cr": result.estimated_cr,
                    "word_count": result.word_count,
                    "html_content": result.html_content,
                    "compliance_notes": result.compliance_notes,
                    "funnel_tips": result.funnel_tips,
                }

            elif agent == "higgsfield_agent":
                from ubt_os.agents import HiggsFieldAgent, VideoFormat
                hf     = HiggsFieldAgent()
                fmt    = params.get("format", "ugc")

                if fmt == "check_status":
                    r = await hf.check_status(params.get("job_id", ""))
                    return {"format": r.format, "status": r.status,
                            "video_url": r.video_url, "job_id": r.job_id, "error": r.error}

                if fmt == "carousel":
                    r = await hf.generate_carousel(
                        params.get("offer_name", "Product"),
                        params.get("benefits", []),
                        params.get("carousel_style", "minimal"),
                        params.get("vertical", "nutra"),
                        params.get("slide_count", 5),
                        params.get("aspect_ratio", "1:1"),
                    )
                    return {"format": r.format, "status": r.status,
                            "slides": r.slides, "slide_count": len(r.slides), "error": r.error}

                if fmt == "shorts":
                    script = " ".join(filter(None, [
                        params.get("hook", ""), params.get("story", ""), params.get("cta", ""),
                    ]))
                    r = await hf.generate_shorts(
                        script,
                        params.get("style", "dynamic"),
                        params.get("vertical", "nutra"),
                        params.get("geo", "US"),
                        params.get("aspect_ratio", "9:16"),
                    )
                else:  # ugc
                    r = await hf.generate_ugc(
                        params.get("hook", ""),
                        params.get("story", ""),
                        params.get("cta", ""),
                        params.get("vertical", "nutra"),
                        params.get("geo", "US"),
                        params.get("avatar_style", "authentic"),
                        params.get("aspect_ratio", "9:16"),
                    )
                return {
                    "format": r.format, "status": r.status,
                    "video_url": r.video_url, "thumbnail_url": r.thumbnail_url,
                    "duration_sec": r.duration_sec, "job_id": r.job_id,
                    "prompt_used": r.prompt_used, "error": r.error,
                }

            else:
                return {"error": f"Неизвестный агент: {agent}"}

        except Exception as exc:
            logger.exception("agents/run: agent=%s error=%s", agent, exc)
            return {"error": str(exc)}

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
