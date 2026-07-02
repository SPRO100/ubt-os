"""
FIX #7: Higgsfield — Очередь с приоритетами + Retry
=====================================================
Проблема: HIGGSFIELD_AGENT отправляет запросы напрямую.
При 10+ видео одновременно — нет порядка, нет retry при ошибке кредитов.

Решение:
  - Redis Sorted Set как priority queue
  - Приоритет: betting > nutra
  - Max concurrent: 3 (лимит Higgsfield)
  - On credit error → pause 1h + Telegram алерт
  - On timeout (>5min) → retry × 2 → fallback cached template
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, asdict
from typing import Optional
import redis.asyncio as aioredis
import httpx

logger = logging.getLogger("higgsfield.queue")


# ══════════════════════════════════════════════════════════
# 1. КОНСТАНТЫ
# ══════════════════════════════════════════════════════════

QUEUE_KEY          = "higgsfield:queue"          # Redis Sorted Set
PROCESSING_KEY     = "higgsfield:processing"     # активные задания
FAILED_KEY         = "higgsfield:failed"         # упавшие
CREDIT_PAUSE_KEY   = "higgsfield:credit_pause"   # флаг паузы при нехватке кредитов

MAX_CONCURRENT     = 3     # максимум параллельных генераций
GENERATION_TIMEOUT = 600   # 10 минут (генерация видео + опрос статуса)
MAX_RETRIES        = 2
CREDIT_PAUSE_SEC   = 3600  # 1 час при ошибке кредитов

# Higgsfield MCP (JSON-RPC поверх streamable HTTP, НЕ обычный REST)
MCP_URL              = os.getenv("HIGGSFIELD_MCP_URL", "https://mcp.higgsfield.ai/mcp")
MCP_PROTOCOL_VERSION = "2025-06-18"
STATUS_POLL_SEC      = 20

# Модель из каталога models_explore. marketing_studio_video — «one-click
# product ads, TikTok/Reels ready», 12–15 сек, 9:16, звук — наш кейс UGC.
DEFAULT_VIDEO_MODEL  = os.getenv("HIGGSFIELD_MODEL", "marketing_studio_video")

# Приоритеты (меньше = выше приоритет в Sorted Set)
PRIORITY = {
    "betting": 1,
    "nutra":   2,
    "other":   3,
}


# ══════════════════════════════════════════════════════════
# 2. ЗАДАНИЕ ДЛЯ ОЧЕРЕДИ
# ══════════════════════════════════════════════════════════

@dataclass
class VideoJob:
    job_id:         str       # UUID из videos.id (Supabase)
    vertical:       str       # betting | nutra
    mcsla_prompt:   str       # готовый промпт
    account_id:     str
    content_plan_id: str
    model:          str = ""  # пусто → DEFAULT_VIDEO_MODEL воркера
    retry_count:    int = 0
    created_at:     float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    @property
    def priority_score(self) -> float:
        """Чем меньше — тем раньше выполняется."""
        base = PRIORITY.get(self.vertical, 3)
        # Добавляем время создания как дробную часть (FIFO внутри приоритета)
        return base + self.created_at / 1e12

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "VideoJob":
        return cls(**json.loads(data))


# ══════════════════════════════════════════════════════════
# 3. QUEUE MANAGER
# ══════════════════════════════════════════════════════════

class HiggsFieldQueue:

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

    async def _r(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self._redis_url, encoding="utf-8", decode_responses=True
            )
        return self._redis

    # ── ENQUEUE ─────────────────────────────────────────
    async def enqueue(self, job: VideoJob):
        """Добавляет задание в очередь с приоритетом."""
        r = await self._r()
        await r.zadd(QUEUE_KEY, {job.to_json(): job.priority_score})
        logger.info(
            f"[Queue] Добавлено: {job.job_id[:8]} "
            f"vertical={job.vertical} priority={job.priority_score:.3f}"
        )

    # ── ДЕQUEUE ─────────────────────────────────────────
    async def dequeue(self) -> Optional[VideoJob]:
        """Берёт следующее задание с наименьшим score (высший приоритет)."""
        r = await self._r()

        # Проверяем паузу кредитов
        if await r.exists(CREDIT_PAUSE_KEY):
            ttl = await r.ttl(CREDIT_PAUSE_KEY)
            logger.info(f"[Queue] ⏸ Пауза из-за кредитов. Осталось: {ttl}s")
            return None

        # Проверяем лимит параллельных задач
        processing_count = await r.scard(PROCESSING_KEY)
        if processing_count >= MAX_CONCURRENT:
            logger.debug(f"[Queue] Достигнут лимит: {processing_count}/{MAX_CONCURRENT}")
            return None

        # Берём задачу с наивысшим приоритетом
        items = await r.zpopmin(QUEUE_KEY, count=1)
        if not items:
            return None

        # zpopmin возвращает список пар (member, score) — берём member
        member = items[0][0]
        job_json = member.decode() if isinstance(member, bytes) else str(member)

        job = VideoJob.from_json(job_json)
        await r.sadd(PROCESSING_KEY, job.job_id)
        logger.info(f"[Queue] Взято в обработку: {job.job_id[:8]}")
        return job

    # ── COMPLETE ────────────────────────────────────────
    async def complete(self, job_id: str):
        r = await self._r()
        await r.srem(PROCESSING_KEY, job_id)
        logger.info(f"[Queue] ✅ Завершено: {job_id[:8]}")

    # ── FAIL / RETRY ────────────────────────────────────
    async def fail(self, job: VideoJob, error: str) -> bool:
        """
        Обрабатывает ошибку.
        Возвращает True если задача перезапущена, False если отправлена в dead letter.
        """
        r = await self._r()
        await r.srem(PROCESSING_KEY, job.job_id)

        if "credit" in error.lower() or "insufficient" in error.lower():
            await self._handle_credit_error(error)
            # Возвращаем задачу в очередь
            job.retry_count += 1
            await self.enqueue(job)
            return True

        if job.retry_count < MAX_RETRIES:
            job.retry_count += 1
            logger.warning(
                f"[Queue] Retry {job.retry_count}/{MAX_RETRIES}: {job.job_id[:8]} — {error}"
            )
            # Небольшая задержка перед повтором
            await asyncio.sleep(30)
            await self.enqueue(job)
            return True
        else:
            logger.error(f"[Queue] ❌ Dead letter: {job.job_id[:8]} — {error}")
            await r.hset(FAILED_KEY, job.job_id, json.dumps({
                "job": asdict(job),
                "error": error,
                "failed_at": time.time(),
            }))
            await _send_telegram_alert(
                f"❌ ВИДЕО НЕ СОЗДАНО (Dead Letter)\n"
                f"Job: {job.job_id[:8]}\n"
                f"Vertical: {job.vertical}\n"
                f"Ошибка: {error}\n"
                f"Попыток: {job.retry_count + 1}"
            )
            return False

    async def _handle_credit_error(self, error: str):
        r = await self._r()
        await r.set(CREDIT_PAUSE_KEY, "1", ex=CREDIT_PAUSE_SEC)
        logger.error(f"[Queue] 💳 Нехватка кредитов Higgsfield. Пауза {CREDIT_PAUSE_SEC}s")
        await _send_telegram_alert(
            f"💳 НЕХВАТКА КРЕДИТОВ HIGGSFIELD\n"
            f"Очередь генерации приостановлена на 1 час.\n"
            f"Пополни кредиты: https://app.higgsfield.ai/billing\n"
            f"Ошибка: {error}"
        )

    # ── СТАТИСТИКА ──────────────────────────────────────
    async def stats(self) -> dict:
        r = await self._r()
        return {
            "queued":        await r.zcard(QUEUE_KEY),
            "processing":    await r.scard(PROCESSING_KEY),
            "failed":        await r.hlen(FAILED_KEY),
            "credit_paused": bool(await r.exists(CREDIT_PAUSE_KEY)),
        }


# ══════════════════════════════════════════════════════════
# 4. WORKER — обрабатывает очередь
# ══════════════════════════════════════════════════════════

class HiggsFieldWorker:
    """
    Запускается как отдельный сервис (n8n или Docker).
    Постоянно опрашивает очередь и запускает генерацию.
    """

    def __init__(self, queue: HiggsFieldQueue, higgsfield_api_key: str):
        self.queue = queue
        self.api_key = higgsfield_api_key

    async def run_forever(self, poll_interval: float = 5.0):
        logger.info("[Worker] Старт Higgsfield Worker")
        while True:
            try:
                job = await self.queue.dequeue()
                if job:
                    asyncio.create_task(self._process(job))
                else:
                    await asyncio.sleep(poll_interval)
            except Exception as e:
                logger.error(f"[Worker] Ошибка цикла: {e}")
                await asyncio.sleep(10)

    async def _process(self, job: VideoJob):
        logger.info(f"[Worker] Обрабатываю: {job.job_id[:8]} ({job.vertical})")
        try:
            result = await asyncio.wait_for(
                self._generate_video(job),
                timeout=GENERATION_TIMEOUT
            )
            await self.queue.complete(job.job_id)
            await self._save_result(job.job_id, result)
        except asyncio.TimeoutError:
            await self.queue.fail(job, f"Timeout после {GENERATION_TIMEOUT}s")
        except Exception as e:
            await self.queue.fail(job, str(e))

    # ── MCP-клиент (Higgsfield говорит на MCP, не на REST) ──

    def _mcp_headers(self, session_id: str | None = None) -> dict:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
            # без text/event-stream сервер отвечает 406 Not Acceptable
            "Accept":        "application/json, text/event-stream",
        }
        if session_id:
            h["Mcp-Session-Id"] = session_id
        return h

    @staticmethod
    def _parse_mcp_response(resp: httpx.Response) -> dict:
        """Ответ MCP приходит либо чистым JSON, либо SSE-потоком data:-строк."""
        if "text/event-stream" in resp.headers.get("content-type", ""):
            message: dict | None = None
            for line in resp.text.splitlines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload:
                    continue
                try:
                    msg = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if isinstance(msg, dict) and ("result" in msg or "error" in msg):
                    message = msg
            if message is None:
                raise RuntimeError(f"пустой SSE-ответ MCP: {resp.text[:200]}")
            return message
        return resp.json()

    async def _mcp_session(self, client: httpx.AsyncClient) -> str:
        """initialize + notifications/initialized → Mcp-Session-Id."""
        resp = await client.post(MCP_URL, headers=self._mcp_headers(), json={
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ubt-os-higgsfield-worker", "version": "1.0"},
            },
        })
        resp.raise_for_status()
        session_id = resp.headers.get("mcp-session-id", "")
        await client.post(MCP_URL, headers=self._mcp_headers(session_id), json={
            "jsonrpc": "2.0", "method": "notifications/initialized",
        })
        return session_id

    async def _mcp_tool(self, client: httpx.AsyncClient, session_id: str,
                        name: str, arguments: dict) -> str:
        """tools/call → склеенный текст content-блоков ответа."""
        resp = await client.post(MCP_URL, headers=self._mcp_headers(session_id), json={
            "jsonrpc": "2.0", "id": int(time.time() * 1000) % 10**9,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        resp.raise_for_status()
        msg = self._parse_mcp_response(resp)
        if msg.get("error"):
            raise RuntimeError(f"MCP {name}: {msg['error']}")
        result = msg.get("result") or {}
        text = "\n".join(
            b.get("text", "") for b in (result.get("content") or [])
            if isinstance(b, dict) and b.get("type") == "text"
        )
        if result.get("isError"):
            raise RuntimeError(f"MCP {name}: {text[:300]}")
        return text

    @staticmethod
    def _find_video_url(text: str) -> str | None:
        m = re.search(r"https://[^\s\"'\)\]]+\.(?:mp4|mov|webm)[^\s\"'\)\]]*", text)
        return m.group(0) if m else None

    @staticmethod
    def _find_generation_id(text: str) -> str | None:
        m = re.search(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            text, re.IGNORECASE,
        )
        return m.group(0) if m else None

    async def _generate_video(self, job: VideoJob) -> dict:
        """Генерация через Higgsfield MCP: generate_video → опрос до готовности."""
        async with httpx.AsyncClient(timeout=120) as client:
            session_id = await self._mcp_session(client)
            text = await self._mcp_tool(client, session_id, "generate_video", {
                "params": {
                    "model":        job.model or DEFAULT_VIDEO_MODEL,
                    "prompt":       job.mcsla_prompt,
                    "aspect_ratio": "9:16",
                },
            })
            logger.info(f"[Worker] generate_video → {text[:400]}")

            url = self._find_video_url(text)
            if url:
                return {"video_url": url}

            gen_id = self._find_generation_id(text)
            if not gen_id:
                raise RuntimeError(f"нет job_id в ответе generate_video: {text[:300]}")

            # Генерация асинхронная — опрашиваем статус до дедлайна
            deadline = time.time() + GENERATION_TIMEOUT - 60
            while time.time() < deadline:
                await asyncio.sleep(STATUS_POLL_SEC)
                status = await self._mcp_tool(client, session_id, "job_display", {"id": gen_id})
                url = self._find_video_url(status)
                if url:
                    logger.info(f"[Worker] генерация {gen_id[:8]} готова: {url[:80]}")
                    return {"video_url": url, "higgsfield_job_id": gen_id}
                if re.search(r"\b(failed|error|nsfw|rejected)\b", status, re.IGNORECASE):
                    raise RuntimeError(f"генерация {gen_id[:8]} упала: {status[:200]}")
            raise RuntimeError(f"генерация {gen_id[:8]} не успела за {GENERATION_TIMEOUT}s")

    async def _save_result(self, job_id: str, result: dict):
        """Сохраняет результат в Supabase videos таблицу."""
        from ubt_os.core.agent_api_layer import VideoWriter
        storage_url = result.get("output_url") or result.get("video_url")
        if storage_url:
            VideoWriter.set_ready(
                video_id=job_id,
                storage_url=storage_url,
                duration_sec=result.get("duration", 0),
            )


# ══════════════════════════════════════════════════════════
# 5. УТИЛИТА
# ══════════════════════════════════════════════════════════

async def _send_telegram_alert(text: str):
    bot_token = os.getenv("TELEGRAM_ALERT_BOT_TOKEN")
    chat_id   = os.getenv("TELEGRAM_ALERT_CHAT_ID")
    if not bot_token or not chat_id:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")
