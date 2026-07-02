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
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
import json

from ubt_os.core.logging_config import setup_logging, set_request_id

setup_logging()
logger = logging.getLogger("ubt_os.main")

# Origin, которому разрешён CORS. По умолчанию "*" (dev), в проде задать домен dashboard.
CORS_ALLOW_ORIGIN = os.getenv("CORS_ALLOW_ORIGIN", "*")

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


# ── Парсер файлов аккаунтов (/accounts/parse-file) ───────────────────────────

_ACC_PLATFORMS = {'tiktok', 'facebook', 'instagram', 'pinterest', 'youtube', 'threads'}
_ACC_GEOS = {
    'US','BR','MX','DE','PL','TR','IN','NG','RU','KZ','UA',
    'FR','GB','ES','IT','AU','CA','JP','TH','VN','ID','PH',
}
_DATE_RE = None  # инициализируется лениво

def _is_date_like(s: str) -> bool:
    import re as _re
    global _DATE_RE
    if _DATE_RE is None:
        _DATE_RE = _re.compile(
            r'^\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}$|^\d{4}[./\-]\d{2}[./\-]\d{2}$'
        )
    return bool(_DATE_RE.match(s.strip()))


def _platform_from_filename(name: str) -> str | None:
    n = name.lower()
    if 'tiktok' in n or 'tok' in n: return 'tiktok'
    if 'facebook' in n or '/fb' in n or n.startswith('fb'): return 'facebook'
    if 'instagram' in n or 'insta' in n or '/ig' in n: return 'instagram'
    if 'pinterest' in n or 'pin' in n: return 'pinterest'
    if 'youtube' in n or 'yt' in n: return 'youtube'
    return None


def _detect_delim(line: str) -> str:
    # Запятая/pipe/tab/точка-с-запятой имеют приоритет — стандартные CSV-разделители
    for d in [',', '|', '\t', ';']:
        if d in line:
            return d
    # Двоеточие — формат продавца (login:pass или login:pass:email:...)
    if ':' in line:
        return ':'
    return ','


def _parse_account_line(line: str, platform_hint: str | None) -> dict | None:
    """Парсит одну строку файла аккаунта в dict или None при ошибке."""
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    delim = _detect_delim(line)
    parts = [p.strip() for p in line.split(delim)]

    account_id = parts[0]
    if not account_id:
        return None

    # Стандартный CSV нашего формата: id,platform,geo,proxy,publer_id,type
    if delim == ',' and len(parts) >= 2 and parts[1].lower() in _ACC_PLATFORMS:
        geo = parts[2].upper() if len(parts) > 2 else 'US'
        geo = geo if geo in _ACC_GEOS else 'US'
        return {
            'id': account_id,
            'platform': parts[1].lower(),
            'geo': geo,
            'proxy': parts[3] or None if len(parts) > 3 else None,
            'publer_profile_id': parts[4] or None if len(parts) > 4 else None,
            'account_type': (parts[5] or 'aged') if len(parts) > 5 else 'aged',
            'status': 'new',
        }

    # Формат продавца: login:password:email:phone:proxy или login|password|geo...
    platform = platform_hint or 'tiktok'
    geo = 'US'
    proxy = None

    for field in parts[1:]:
        f = field.strip()
        if not f or _is_date_like(f):
            continue
        fu = f.upper()
        if fu in _ACC_GEOS:
            geo = fu
        elif f.lower() in _ACC_PLATFORMS:
            platform = f.lower()
        elif ':' in f and len(f.split(':')) >= 2 and not _is_date_like(f):
            # выглядит как прокси (host:port или type:host:port)
            parts_p = f.split(':')
            if parts_p[0].lower() in ('http','https','socks5','mobile','residential','dc','static'):
                proxy = f
            elif all(c.isdigit() or c == '.' for c in parts_p[-1]):
                proxy = f  # host:port

    return {
        'id': account_id,
        'platform': platform,
        'geo': geo,
        'proxy': proxy,
        'publer_profile_id': None,
        'account_type': 'aged',
        'status': 'new',
    }


def _parse_file_bytes(raw_bytes: bytes, filename: str,
                      platform_hint: str | None) -> dict:
    """Разбирает байты файла (.txt/.csv/.zip) в список аккаунтов."""
    import zipfile, io

    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    lines_with_meta: list[tuple[str, str | None, str]] = []  # (line, platform, src)

    if ext == 'zip':
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                for name in sorted(zf.namelist()):
                    if name.lower().endswith(('.txt', '.csv')) and '__MACOSX' not in name:
                        plat = _platform_from_filename(name) or platform_hint
                        text = zf.read(name).decode('utf-8', errors='ignore')
                        for ln in text.splitlines():
                            ln = ln.strip()
                            if ln and not ln.startswith('#'):
                                lines_with_meta.append((ln, plat, name))
        except zipfile.BadZipFile:
            return {'error': 'Не удалось открыть ZIP-архив'}
    else:
        text = raw_bytes.decode('utf-8', errors='ignore')
        plat = _platform_from_filename(filename) or platform_hint
        for ln in text.splitlines():
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                lines_with_meta.append((ln, plat, filename))

    # Пропустить заголовок CSV если он есть
    if lines_with_meta and lines_with_meta[0][0].lower().startswith(('id,', 'id|', 'login', 'username', 'account')):
        lines_with_meta = lines_with_meta[1:]

    accounts: list[dict] = []
    errors: list[str] = []
    seen_ids: set[str] = set()

    for i, (ln, plat, src) in enumerate(lines_with_meta, 1):
        rec = _parse_account_line(ln, plat)
        if rec is None:
            if ln:
                errors.append(f'{src} стр.{i}: не распознано — {ln[:60]}')
        elif rec['id'] in seen_ids:
            errors.append(f'{src} стр.{i}: дубль ID {rec["id"]}')
        else:
            seen_ids.add(rec['id'])
            accounts.append(rec)
        if len(accounts) >= 1000:
            errors.append('⚠ Достигнут лимит 1000 аккаунтов за один импорт')
            break

    return {
        'accounts': accounts,
        'errors': errors[:60],
        'raw_lines': len(lines_with_meta),
        'parsed': len(accounts),
    }


class WebhookHandler(BaseHTTPRequestHandler):
    """Принимает POST-запросы от n8n и запускает нужный пайплайн."""

    def _authorized(self, raw_body: bytes) -> bool:
        """Двойная аутентификация POST-запросов:

        - n8n / серверные вызовы → HMAC-SHA256 подпись (заголовок X-Webhook-Signature, ключ WEBHOOK_SECRET)
        - dashboard / браузер     → Bearer-токен (заголовок Authorization, ключ AGENTS_API_TOKEN)

        Достаточно пройти любой из путей. Если ни WEBHOOK_SECRET, ни
        AGENTS_API_TOKEN не заданы — пропускаем (dev-режим) с предупреждением.
        """
        secret = os.getenv("WEBHOOK_SECRET")
        token  = os.getenv("AGENTS_API_TOKEN")

        if not secret and not token:
            logger.warning(
                "ВНИМАНИЕ: ни WEBHOOK_SECRET, ни AGENTS_API_TOKEN не заданы — "
                "сервер принимает запросы без аутентификации (dev-режим)."
            )
            return True

        # Путь 1 — HMAC-подпись (n8n)
        if secret:
            sig_header = self.headers.get("X-Webhook-Signature", "")
            if sig_header:
                expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
                if hmac.compare_digest(sig_header, expected):
                    return True

        # Путь 2 — Bearer-токен (dashboard)
        if token:
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                if hmac.compare_digest(auth[7:], token):
                    return True

        return False

    def do_POST(self):
        length   = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b""

        _METRICS["webhook_requests_total"] += 1

        if not self._authorized(raw_body):
            _METRICS["webhook_requests_unauthorized"] += 1
            self._respond(403, {"error": "unauthorized"})
            logger.warning("Webhook: отклонён — провал аутентификации", extra={"path": self.path})
            return

        # Correlation ID: берём из заголовка n8n или генерируем
        request_id = self.headers.get("X-Request-Id") or str(uuid.uuid4())[:8]
        set_request_id(request_id)

        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            _METRICS["webhook_requests_error"] += 1
            self._respond(400, {"error": "invalid JSON body"})
            return
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
            # Новые агенты: анализ конкурентов, прямая публикация, транскрипция
            "/competitor/analyze":    self._run_competitor_analyze,
            "/publish/direct":        self._run_publish_direct,
            "/publish/bulk":          self._run_publish_bulk,
            "/transcribe":            self._run_transcribe,
            "/hooks/top":             self._run_hooks_top,
            # A32/A33: тренды + авто-сбор крипов
            "/trends/radar":          self._run_trends_radar,
            "/competitor/scrape":     self._run_competitor_scrape,
            # A34/A35: субтитры + озвучка
            "/caption":               self._run_caption,
            "/tts":                   self._run_tts,
            # A36: синхронизация нативных метрик постов
            "/analytics/sync":        self._run_analytics_sync,
            # Бесплатный стоковый видео-конвейер (Pexels + edge-tts + ffmpeg)
            "/video/stock":           self._run_video_stock,
            # Структурированная база знаний по таксономии
            "/knowledge/kb":          self._run_kb_search,
            # Парсинг файлов аккаунтов (txt/csv/zip → список записей)
            "/accounts/parse-file":   self._run_parse_file,
            # Health check (POST для совместимости с n8n — делает то же что GET)
            "/health/check-all":      self._run_health_check_post,
            # Экстренная пауза всех активных аккаунтов (n8n health-monitor)
            "/system/emergency-pause": self._run_emergency_pause,
            # Пауза конкретных аккаунтов по risk_level=stop (n8n risk-engine-monitor)
            "/risk/pause-accounts":   self._run_risk_pause_accounts,
        }

        handler = routes.get(self.path)
        if handler:
            try:
                result = asyncio.run(handler(body))
            except Exception as exc:
                _METRICS["webhook_requests_error"] += 1
                logger.exception("Webhook: ошибка обработчика %s", self.path)
                self._respond(500, {"error": str(exc)})
                return
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
        if self.path == "/health/env":
            self._serve_env_check()
            return
        self._respond(404, {"error": "unknown route"})

    def _respond(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", CORS_ALLOW_ORIGIN)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *_):
        pass  # подавляем стандартные логи HTTPServer

    def do_OPTIONS(self):
        """PATCH: CORS preflight для POST-запросов с Content-Type: application/json."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", CORS_ALLOW_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Webhook-Signature")
        self.end_headers()

    # ── Обработчики пайплайнов ────────────────────────────

    async def _run_nutra(self, body: dict):
        from ubt_os.core import pipeline_lock
        from ubt_os.pipelines.video_pipeline import run_video_pipeline
        async with pipeline_lock("video-pipeline-nutra", 600) as acquired:
            if not acquired:
                logger.info("NUTRA: lock занят, пропускаем")
                return {"status": "skipped", "reason": "lock_busy"}
            logger.info("NUTRA pipeline: запуск ✅")
            return await run_video_pipeline(
                "nutra",
                geo=body.get("geo", "US"),
                offer=body.get("offer", ""),
                count=int(body.get("count", 1)),
                account_id=body.get("account_id"),
                provider=body.get("provider", ""),
            )

    async def _run_ubt(self, body: dict):
        from ubt_os.core import pipeline_lock
        from ubt_os.pipelines.video_pipeline import run_video_pipeline
        async with pipeline_lock("video-pipeline-ubt", 600) as acquired:
            if not acquired:
                logger.info("UBT: lock занят, пропускаем")
                return {"status": "skipped", "reason": "lock_busy"}
            logger.info("UBT pipeline: запуск ✅")
            return await run_video_pipeline(
                "betting",
                geo=body.get("geo", "BR"),
                offer=body.get("offer", ""),
                count=int(body.get("count", 1)),
                account_id=body.get("account_id"),
                provider=body.get("provider", ""),
            )

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

        # Структурированная база знаний — релевантные записи по вертикали + ключевым словам сообщения
        from ubt_os.core.kb_context import load_kb_context as _load_kb
        from ubt_os.core.knowledge_taxonomy import PLATFORMS, PROCESSES, SCHEMES
        _msg_lower = message.lower()
        _detected_platform = next((p for p in PLATFORMS if p != "any" and p in _msg_lower), None)
        _detected_process   = next((p for p in PROCESSES if p in _msg_lower), None)
        _detected_scheme    = next((s for s in SCHEMES   if s in _msg_lower), None)
        # Вертикаль из vertical_id: "nutra_joints_pl" → "nutra", "betting_ru" → "betting"
        from ubt_os.core.knowledge_taxonomy import VERTICALS as _VERTS
        _proj_vertical = next(
            (v for v in _VERTS if v not in ("both", "any") and v in vertical_id.lower()),
            None
        )
        kb_learnings = _load_kb(
            db,
            process=_detected_process,
            platform=_detected_platform,
            vertical=_proj_vertical,
            scheme=_detected_scheme,
            limit=8,
        )

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
            "- A30 higgsfield_agent: генерация UGC-видео 9:16, Shorts 15–60с и каруселей через Higgsfield AI\n"
            "- A31 competitor_analyst: проактивный анализ хуков конкурентов из competitor_signals → тренды\n"
            "- A32 trend_radar: ранжирование трендовых звуков/хэштегов под vertical/GEO — «на чём ехать сейчас»\n"
            "- A33 competitor_scraper: авто-сбор крипов конкурентов по хэштегу/ключу в competitor_signals (кормит A31)\n"
            "- A34 caption_agent: стилизованные субтитры (ASS/SRT, TikTok-style) для видео + ffmpeg burn\n"
            "- A35 tts_agent: озвучка faceless-видео (self-hosted TTS → ElevenLabs)\n"
            "- transcription_agent: транскрипция видео (Deepgram → Whisper) + извлечение хука\n"
            "- social_publisher: прямая публикация на 8 платформ через нативные API (без лимитов Publer)\n"
            "- A36 post_analytics_agent: синхронизация нативных метрик постов (impressions/reach/likes/comments/shares)\n\n"
            "Если задача пользователя явно подходит для одного из агентов — добавь в КОНЕЦ ответа строку:\n"
            "[AGENT_SUGGEST: agent_id|Что именно агент сделает для этой задачи]\n"
            "Пример: [AGENT_SUGGEST: content_creator|Создать 3 варианта hook для нутра GEO US]\n"
            "Добавляй не более 2 предложений. Если агент не нужен — ничего не добавляй.\n\n"
            "Если в ответе уместна ссылка на внешний сервис (PiPiAds, AdHeart, Publer, Higgsfield, Keitaro и т.д.) — "
            "добавь в конец ответа: [QUICK_LINK: Название|https://url]\n"
            "Примеры: [QUICK_LINK: PiPiAds|https://www.pipiads.com] или [QUICK_LINK: Publer|https://app.publer.io]\n"
            "Не более 3 ссылок. Только если они реально помогут пользователю прямо сейчас.\n\n"
            "СИНХРОНИЗАЦИЯ С БАЗОЙ ЗНАНИЙ. Если в диалоге появилось новое устойчивое "
            "знание, применимое в будущем (рабочая схема залива, лимиты прогрева, "
            "мастер-промт, антибан-приём, находка по площадке) — зафиксируй его "
            "маркером в конце ответа:\n"
            "[LEARN: entry_key|Заголовок|Суть знания в 1-3 предложениях]\n"
            "entry_key строится как <процесс>.<площадка>.<вертикаль>.<схема>, где\n"
            "  процесс: zaliv|warmup|master_prompt|content|prelanding|publishing|antiban|analytics|scaling|infra\n"
            "  площадка: tiktok|facebook|instagram|youtube|pinterest|threads|any\n"
            "  вертикаль: nutra|betting|both|any\n"
            "  схема: white|grey|black\n"
            "Пример: [LEARN: warmup.tiktok.nutra.grey|Прогрев TikTok 7 дней|"
            "Первые 3 дня только просмотры FYP 20-30 мин, посты с 4 дня, био-ссылка с 8].\n"
            "Фиксируй только реально новое и проверяемое знание, максимум 2 маркера. "
            "Не фиксируй общие фразы и то, что уже есть в записях выше."
        )

        kb_section = f"\n\n{kb_learnings}" if kb_learnings else ""

        system_prompt = (
            f"Ты — ORCHESTRATOR проекта «{project['name']}» в системе UBT OS.\n"
            f"Конфигурация проекта: {project['config_yaml']}\n\n"
            f"Последние записи синтезатора знаний этого проекта:\n"
            + ("\n".join(f"- [{k['type']}] {k['content'][:200]}" for k in knowledge) if knowledge else "пока нет записей")
            + kb_section
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
            messages=messages,  # type: ignore[arg-type]  # роли валидируются на стороне БД
        )
        raw_reply = getattr(resp.content[0], "text", "")

        import re as _re
        suggestions = []
        quick_links = []
        learnings = []

        def _extract_markers(text):
            for m in _re.finditer(r"\[AGENT_SUGGEST:\s*([^\|]+)\|([^\]]+)\]", text):
                suggestions.append({"agent": m.group(1).strip(), "description": m.group(2).strip()})
            for m in _re.finditer(r"\[QUICK_LINK:\s*([^\|]+)\|([^\]]+)\]", text):
                quick_links.append({"label": m.group(1).strip(), "url": m.group(2).strip()})
            # [LEARN: entry_key|заголовок|суть знания] — фиксируем в базу знаний
            for m in _re.finditer(r"\[LEARN:\s*([^\|]+)\|([^\|]+)\|([^\]]+)\]", text):
                learnings.append({
                    "entry_key": m.group(1).strip(),
                    "title":     m.group(2).strip(),
                    "content":   m.group(3).strip(),
                })
            text = _re.sub(r"\[AGENT_SUGGEST:[^\]]+\]", "", text)
            text = _re.sub(r"\[QUICK_LINK:[^\]]+\]", "", text)
            text = _re.sub(r"\[LEARN:[^\]]+\]", "", text)
            return text.strip()

        reply = _extract_markers(raw_reply)

        # Синхронизация чат → база знаний: изученное сразу пишем в knowledge_entries
        saved_learnings = self._persist_learnings(db, vertical_id, learnings)

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
            "competitor_analyst":   [{"label": "TikTok Creative Center", "url": "https://ads.tiktok.com/business/creativecenter"}],
            "trend_radar":          [{"label": "TikTok Creative Center", "url": "https://ads.tiktok.com/business/creativecenter"}],
            "tts_agent":            [{"label": "ElevenLabs", "url": "https://elevenlabs.io"}],
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
            "learnings_saved": saved_learnings,
        }

    @staticmethod
    def _persist_learnings(db, vertical_id: str, learnings: list) -> list:
        """Пишет извлечённые из чата знания в knowledge_entries (append-only,
        версионируемо через KnowledgeBase) + зеркалит в Obsidian-vault."""
        from ubt_os.core.knowledge_base import KnowledgeBase
        from ubt_os.core.knowledge_taxonomy import (
            parse_entry_key, vault_path_for, page_template,
        )
        if not learnings:
            return []
        kb = KnowledgeBase(db)
        saved = []
        for item in learnings:
            key = item.get("entry_key", "").strip()
            title = item.get("title", "").strip() or key
            content = item.get("content", "").strip()
            if not key or not content:
                continue
            ax = parse_entry_key(key)
            try:
                existing = kb.get_current(key)
                if existing:
                    kb.update(
                        entry_key=key, content=content, title=title,
                        changed_by="orchestrator",
                        change_reason=f"чат-инсайт (vertical={vertical_id})",
                    )
                else:
                    kb.create(
                        entry_key=key, category=ax["process"], vertical=ax["vertical"],
                        title=title, content=content,
                        tags=[ax["process"], ax["platform"], ax["scheme"]],
                        changed_by="orchestrator",
                    )
                saved.append(key)
                # Зеркало в vault (best-effort, не роняет ответ)
                try:
                    target = WebhookHandler._safe_vault_path(vault_path_for(key))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(page_template(key, title, content), encoding="utf-8")
                except Exception as ve:
                    logger.warning("LEARN: зеркало в vault не удалось (%s): %s", key, ve)
            except Exception as e:
                logger.warning("LEARN: не сохранил '%s': %s", key, e)
        if saved:
            logger.info("orchestrator: записано в базу знаний %d записей: %s",
                        len(saved), ", ".join(saved))
        return saved

    async def _run_agent(self, body: dict):
        """POST /agents/run — запуск A19–A24 напрямую из браузера."""
        agent  = body.get("agent", "")
        params = body.get("params", {})

        # ── Загрузка KB контекста для агента ─────────────────────────────────
        from ubt_os.core.kb_context import load_kb_context as _load_kb_agent
        from ubt_os.core.knowledge_taxonomy import AGENT_PROCESS, VERTICALS as _AVERTS
        from ubt_os.core.kb_writer import save_learnings, scan_and_strip, LEARN_INSTRUCTION
        _agent_process  = AGENT_PROCESS.get(agent)
        _agent_vertical = params.get("vertical")
        if _agent_vertical and _agent_vertical not in _AVERTS:
            _agent_vertical = None
        _agent_platform = params.get("platform")
        try:
            _kb_ctx = _load_kb_agent(
                _get_db(),
                process=_agent_process,
                platform=_agent_platform,
                vertical=_agent_vertical,
                limit=5,
            ) if _agent_process else ""
        except Exception:
            _kb_ctx = ""
        # ─────────────────────────────────────────────────────────────────────

        # Диспетчер возвращает разнородные dataclass-результаты — типы динамические.
        result:  Any
        r:       Any
        creator: Any
        fmt:     Any

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
                    kb_context=_kb_ctx + LEARN_INSTRUCTION if _kb_ctx else LEARN_INSTRUCTION,
                )
                _out = {"result": result.humanized_text, "score": result.score, "passed": result.passed_quality}
                _out, _ll = scan_and_strip(_out)
                if _ll:
                    try:
                        save_learnings(_get_db(), _ll, params.get("vertical", "any"))
                    except Exception as _le:
                        logger.warning("kb_writer: %s", _le)
                return _out

            elif agent == "text_humanizer":
                from ubt_os.agents import TextHumanizer
                h      = TextHumanizer()
                result = await h.humanize(
                    params.get("text", ""),
                    params.get("geo", "US"),
                    params.get("vertical", "nutra"),
                    kb_context=_kb_ctx,
                )
                return {"result": result.humanized_text, "score": result.total_score, "passed": result.passed}

            elif agent == "trend_scraper":
                from ubt_os.agents import TrendScraper
                scraper = TrendScraper()
                if params.get("url"):
                    r = await scraper.analyze_url(params["url"], kb_context=_kb_ctx)
                else:
                    r = await scraper.find_trends(params.get("vertical", "nutra"), params.get("geo", "US"),
                                                  kb_context=_kb_ctx)
                return {"hooks": r.hooks, "pains": r.pains, "action_items": r.action_items, "trend_score": r.trend_score}

            elif agent == "ads_auditor":
                from ubt_os.agents import AdsAuditor
                auditor = AdsAuditor()
                result  = await auditor.audit(
                    params.get("platform", "tiktok"),
                    params.get("vertical", "nutra"),
                    params.get("account_data", {}),
                    params.get("geo", "US"),
                    kb_context=_kb_ctx,
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
                    kb_context=_kb_ctx + LEARN_INSTRUCTION if _kb_ctx else LEARN_INSTRUCTION,
                )
                _out = {"content": result.content}
                _out, _ll = scan_and_strip(_out)
                if _ll:
                    try:
                        save_learnings(_get_db(), _ll, params.get("vertical", "any"))
                    except Exception as _le:
                        logger.warning("kb_writer: %s", _le)
                return _out

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
                    kb_context=_kb_ctx,
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
                    kb_context=_kb_ctx + LEARN_INSTRUCTION if _kb_ctx else LEARN_INSTRUCTION,
                )
                _out = {
                    "hook_patterns": result.hook_patterns,
                    "content_structures": result.content_structures,
                    "key_phrases": result.key_phrases,
                    "forbidden_phrases": result.forbidden_phrases,
                    "winning_formats": result.winning_formats,
                    "creative_brief": result.creative_brief,
                    "a21_prompt_extension": result.a21_prompt_extension,
                    "creatives_analyzed": result.creatives_analyzed,
                }
                _out, _ll = scan_and_strip(_out)
                if _ll:
                    try:
                        save_learnings(_get_db(), _ll, params.get("vertical", "any"))
                    except Exception as _le:
                        logger.warning("kb_writer: %s", _le)
                return _out

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
                        kb_context=_kb_ctx,
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
                    kb_context=_kb_ctx,
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
                from ubt_os.agents import HiggsFieldAgent
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

            # ── Доп. агенты A31–A35 (свои run_-функции возвращают dict) ──
            elif agent == "competitor_analyst":
                from ubt_os.agents import run_competitor_analyst
                return await run_competitor_analyst(
                    params.get("vertical", "nutra"),
                    int(params.get("lookback_days", 3)),
                    kb_context=_kb_ctx)

            elif agent == "trend_radar":
                from ubt_os.agents import run_trend_radar
                return await run_trend_radar(
                    vertical=params.get("vertical", "nutra"),
                    geo=params.get("geo", "US"),
                    platform=params.get("platform", "tiktok"),
                    hashtags=params.get("hashtags"),
                    sounds=params.get("sounds"),
                    kb_context=_kb_ctx,
                )

            elif agent == "competitor_scraper":
                from ubt_os.agents import run_competitor_scrape
                return await run_competitor_scrape(
                    query=params.get("query", ""),
                    vertical=params.get("vertical", "nutra"),
                    geo=params.get("geo", "US"),
                    platform=params.get("platform", "tiktok"),
                    limit=int(params.get("limit", 20)),
                )

            elif agent == "caption_agent":
                from ubt_os.agents import run_caption
                return await run_caption(
                    video_url=params.get("video_url", ""),
                    words=params.get("words"),
                    language=params.get("language", "ru"),
                    style=params.get("style", "tiktok"),
                    burn=params.get("burn", False),
                )

            elif agent == "tts_agent":
                from ubt_os.agents import run_tts
                return await run_tts(
                    text=params.get("text", ""),
                    voice=params.get("voice"),
                    provider=params.get("provider"),
                )

            elif agent == "transcription_agent":
                from ubt_os.agents import run_transcription
                return await run_transcription(
                    params.get("video_url", ""),
                    vertical=params.get("vertical", "nutra"),
                    platform=params.get("platform", "tiktok"),
                    geo=params.get("geo", "US"),
                    language=params.get("language", "ru"),
                )

            elif agent == "post_analytics":
                from ubt_os.agents import run_post_analytics
                return await run_post_analytics(
                    platform=params.get("platform"),
                    limit=int(params.get("limit", 100)),
                )

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
            db = _get_db()
            await DeadLetterQueueManager(db).daily_report()

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

    async def _run_video_stock(self, body: dict):
        """Бесплатное faceless-видео: стоковые клипы Pexels + озвучка + ffmpeg."""
        from ubt_os.pipelines.stock_video import run_stock_video
        return await run_stock_video(
            script=body.get("script", ""),
            vertical=body.get("vertical", "nutra"),
            geo=body.get("geo", "US"),
            voice=body.get("voice"),
            max_clips=int(body.get("max_clips", 4)),
            keywords=body.get("keywords"),
        )

    async def _run_kb_search(self, body: dict):
        """Поиск по структурированной базе знаний kb_entries (таксономия)."""
        from ubt_os.core.knowledge_base import KnowledgeBase
        db = _get_db()
        kb = KnowledgeBase(db)
        entry_key = (body.get("entry_key") or "").strip()
        if entry_key:
            entry = kb.get_current(entry_key)
            return {"entry": entry}
        results = kb.search(
            category=body.get("process") or body.get("category"),
            vertical=body.get("vertical"),
            tags=body.get("tags"),
        )
        return {"entries": results, "count": len(results)}

    async def _run_analytics_sync(self, body: dict):
        """A36 POST_ANALYTICS: синхронизация нативных метрик опубликованных постов."""
        from ubt_os.core import pipeline_lock
        from ubt_os.agents import run_post_analytics
        platform = body.get("platform")
        limit    = int(body.get("limit", 100))
        async with pipeline_lock("post-analytics-sync", 300) as acquired:
            if not acquired:
                return {"status": "skipped", "reason": "lock_busy"}
            return await run_post_analytics(platform=platform, limit=limit)

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

    async def _run_trends_radar(self, body: dict):
        """A32 TREND_RADAR — ранжирование трендовых звуков/хэштегов под vertical/GEO."""
        from ubt_os.agents.trend_radar import run_trend_radar
        return await run_trend_radar(
            vertical=body.get("vertical", "nutra"),
            geo=body.get("geo", "US"),
            platform=body.get("platform", "tiktok"),
            hashtags=body.get("hashtags"),
            sounds=body.get("sounds"),
            persist=body.get("persist", True),
        )

    async def _run_competitor_scrape(self, body: dict):
        """A33 COMPETITOR_SCRAPER — авто-сбор крипов в competitor_signals (для A31)."""
        from ubt_os.agents.competitor_scraper import run_competitor_scrape
        return await run_competitor_scrape(
            query=body.get("query", ""),
            vertical=body.get("vertical", "nutra"),
            geo=body.get("geo", "US"),
            platform=body.get("platform", "tiktok"),
            limit=int(body.get("limit", 20)),
            persist=body.get("persist", True),
        )

    async def _run_caption(self, body: dict):
        """A34 CAPTION_AGENT — стилизованные субтитры (ASS/SRT) + ffmpeg burn."""
        from ubt_os.agents.caption_agent import run_caption
        return await run_caption(
            video_url=body.get("video_url", ""),
            words=body.get("words"),
            language=body.get("language", "ru"),
            style=body.get("style", "tiktok"),
            max_words=int(body.get("max_words", 4)),
            burn=body.get("burn", False),
        )

    async def _run_tts(self, body: dict):
        """A35 TTS_AGENT — озвучка скрипта (self-hosted → ElevenLabs)."""
        from ubt_os.agents.tts_agent import run_tts
        return await run_tts(
            text=body.get("text", ""),
            voice=body.get("voice"),
            provider=body.get("provider"),
            upload=body.get("upload", True),
        )

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

    async def _run_health_check_post(self, body: dict) -> dict:
        """POST /health/check-all — POST-обёртка для совместимости с n8n.
        GET-версия по-прежнему работает для браузеров/curl."""
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
        return status

    async def _run_emergency_pause(self, body: dict) -> dict:
        """POST /system/emergency-pause — ставит все активные аккаунты на паузу.
        Вызывается n8n health-monitor при critical_degradation."""
        reason = body.get("reason", "manual")
        level  = body.get("level", "unknown")
        logger.warning("ЭКСТРЕННАЯ ПАУЗА: reason=%s level=%s", reason, level)
        try:
            db = _get_db()
            # Ставим на паузу все аккаунты кроме уже заблокированных/banned
            res = (
                db.table("accounts")
                .update({"status": "paused"})
                .not_.in_("status", ["banned", "paused"])
                .execute()
            )
            paused = len(res.data or [])
            # Telegram-алерт (если настроен)
            bot   = os.getenv("TELEGRAM_ALERT_BOT_TOKEN")
            chat  = os.getenv("TELEGRAM_ALERT_CHAT_ID")
            if bot and chat:
                import urllib.request as _ur, urllib.parse as _up
                msg = f"⛔ EMERGENCY PAUSE\nПричина: {reason}\nУровень: {level}\nАккаунтов приостановлено: {paused}"
                _ur.urlopen(
                    f"https://api.telegram.org/bot{bot}/sendMessage"
                    f"?chat_id={chat}&text={_up.quote(msg)}",
                    timeout=5,
                )
            return {"status": "paused", "accounts_paused": paused, "reason": reason}
        except Exception as exc:
            logger.exception("emergency_pause: ошибка")
            return {"error": str(exc)}

    async def _run_risk_pause_accounts(self, body: dict) -> dict:
        """POST /risk/pause-accounts — пауза конкретных аккаунтов по risk_level=stop.
        Вызывается n8n risk-engine-monitor."""
        accounts = body.get("accounts", [])
        if not accounts:
            return {"status": "ok", "paused": 0, "note": "список пуст"}
        if not isinstance(accounts, list):
            return {"error": "accounts должен быть списком строк"}
        try:
            db = _get_db()
            res = (
                db.table("accounts")
                .update({"status": "paused"})
                .in_("id", accounts[:200])  # защита от слишком большого списка
                .execute()
            )
            paused = len(res.data or [])
            logger.info("risk_pause_accounts: приостановлено %d аккаунтов", paused)
            return {"status": "ok", "paused": paused, "requested": len(accounts)}
        except Exception as exc:
            logger.exception("risk_pause_accounts: ошибка")
            return {"error": str(exc)}

    async def _run_parse_file(self, body: dict) -> dict:
        """POST /accounts/parse-file — парсинг файла аккаунтов.

        Тело запроса:
          { "filename": "accounts.zip", "content": "<base64>", "platform": "tiktok" }
        Ответ:
          { "accounts": [...], "errors": [...], "raw_lines": N, "parsed": N }
        """
        import base64
        filename = body.get("filename", "file.txt")
        content_b64 = body.get("content", "")
        platform_hint = body.get("platform") or None
        if platform_hint:
            platform_hint = platform_hint.lower().strip()
            if platform_hint not in _ACC_PLATFORMS:
                platform_hint = None
        if not content_b64:
            return {"error": "content обязателен (base64)"}
        try:
            raw_bytes = base64.b64decode(content_b64)
        except Exception:
            return {"error": "Не удалось декодировать base64"}
        if len(raw_bytes) > 10 * 1024 * 1024:
            return {"error": "Файл слишком большой (макс. 10 МБ)"}
        return _parse_file_bytes(raw_bytes, filename, platform_hint)

    def _serve_env_check(self):
        """GET /health/env — какие API-ключи прописаны (наличие, не значения)."""
        keys = [
            "ANTHROPIC_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
            "REDIS_URL", "FIRECRAWL_API_KEY", "HIGGSFIELD_API_KEY",
            "PUBLER_API_KEY", "TIKTOK_SCRAPER_URL", "ELEVENLABS_API_KEY",
            "WEBHOOK_SECRET", "AGENTS_API_TOKEN", "TELEGRAM_ALERT_TOKEN",
            "KEITARO_URL", "LITELLM_BASE_URL",
        ]
        result = {k: bool(os.environ.get(k)) for k in keys}
        self._respond(200, result)


def main():
    port = int(os.getenv("AGENTS_PORT", "8080"))
    # По умолчанию слушаем все интерфейсы (нужно в контейнере за nginx).
    # В проде за reverse-proxy можно ограничить до 127.0.0.1 через AGENTS_HOST.
    host = os.getenv("AGENTS_HOST", "0.0.0.0")  # nosec B104 — доступ ограничен nginx + firewall + auth
    logger.info(f"UBT OS запущен на {host}:{port}")
    server = ThreadingHTTPServer((host, port), WebhookHandler)

    def _shutdown(signum, frame):
        logger.info("UBT OS: получен сигнал завершения, останавливаем сервер...")
        # shutdown() нельзя вызывать из потока serve_forever (обработчик сигнала
        # исполняется в главном потоке) — это дедлок; останавливаем из отдельного
        import threading
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    server.serve_forever()
    logger.info("UBT OS: сервер остановлен")


if __name__ == "__main__":
    main()
