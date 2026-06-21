"""
FIX #3: Идемпотентность пайплайна — Redis Distributed Lock
===========================================================
Проблема: n8n cron запускает второй инстанс пайплайна до завершения первого.
Результат: дублирующиеся видео → теневой бан аккаунта.

Решение: Redis SET NX EX lock перед запуском пайплайна.
Если lock занят → пропустить итерацию, залогировать.
"""

from __future__ import annotations
import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger("pipeline.lock")


# ══════════════════════════════════════════════════════════
# 1. REDIS CLIENT
# ══════════════════════════════════════════════════════════

_redis: Optional[aioredis.Redis] = None
_redis_loop = None

async def get_redis() -> aioredis.Redis:
    global _redis, _redis_loop
    current_loop = asyncio.get_running_loop()
    if _redis is None or _redis_loop is not current_loop:
        if _redis is not None:
            try:
                await _redis.close()
            except Exception:
                pass
        _redis = await aioredis.from_url(
            os.environ["REDIS_URL"],
            encoding="utf-8",
            decode_responses=True,
        )
        _redis_loop = current_loop
    return _redis


# ══════════════════════════════════════════════════════════
# 2. DISTRIBUTED LOCK
# ══════════════════════════════════════════════════════════

class PipelineLock:
    """
    Распределённый Redis-lock для пайплайна.
    Использует уникальный token — только тот, кто захватил lock, может его снять.
    """

    def __init__(
        self,
        name: str,
        ttl_seconds: int = 600,   # 10 минут — максимальное время пайплайна
    ):
        self.key        = f"pipeline_lock:{name}"
        self.ttl        = ttl_seconds
        self.token      = str(uuid.uuid4())
        self._acquired  = False

    async def acquire(self) -> bool:
        """
        Пытается захватить lock.
        Возвращает True если успешно, False если lock уже занят.
        """
        r = await get_redis()
        result = await r.set(
            self.key,
            self.token,
            ex=self.ttl,
            nx=True   # только если не существует
        )
        self._acquired = result is not None
        if self._acquired:
            logger.info(f"[Lock] ✅ Захвачен: {self.key} (TTL={self.ttl}s, token={self.token[:8]})")
        else:
            # Читаем, кто держит lock (для диагностики)
            owner = await r.get(self.key)
            ttl_left = await r.ttl(self.key)
            logger.warning(
                f"[Lock] 🔒 Занят: {self.key} "
                f"(владелец: {str(owner)[:8]}..., "
                f"осталось: {ttl_left}s) — пропускаем итерацию"
            )
        return self._acquired

    async def release(self):
        """
        Освобождает lock ТОЛЬКО если token совпадает.
        Защита от случайного снятия чужого lock.
        """
        if not self._acquired:
            return
        r = await get_redis()
        # Lua script — атомарная проверка + удаление
        lua = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await r.eval(lua, 1, self.key, self.token)
        if result == 1:
            logger.info(f"[Lock] 🔓 Освобождён: {self.key}")
        else:
            logger.warning(f"[Lock] ⚠️ Lock {self.key} уже истёк или захвачен другим процессом")
        self._acquired = False

    async def extend(self, extra_seconds: int = 300):
        """Продлевает TTL если пайплайн занимает больше времени."""
        if not self._acquired:
            return
        r = await get_redis()
        current = await r.get(self.key)
        if current == self.token:
            await r.expire(self.key, extra_seconds)
            logger.info(f"[Lock] ⏱ Продлён: {self.key} на {extra_seconds}s")


# ══════════════════════════════════════════════════════════
# 3. CONTEXT MANAGER (удобный способ использования)
# ══════════════════════════════════════════════════════════

@asynccontextmanager
async def pipeline_lock(name: str, ttl_seconds: int = 600):
    """
    Использование:
        async with pipeline_lock("nutra") as acquired:
            if not acquired:
                return  # другой инстанс уже работает
            # ... пайплайн код ...
    """
    lock = PipelineLock(name, ttl_seconds)
    acquired = await lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            await lock.release()


# ══════════════════════════════════════════════════════════
# 4. LOCK-КЛЮЧИ ДЛЯ ВСЕХ ПАЙПЛАЙНОВ
# ══════════════════════════════════════════════════════════

PIPELINE_LOCKS = {
    "nutra":          ("video-pipeline-nutra",     600),   # 10 мин
    "ubt":            ("video-pipeline-ubt",       600),   # 10 мин
    "publisher":      ("publisher-main",           300),   # 5 мин
    "tg_commenter":   ("tg-commenter",             180),   # 3 мин
    "tg_reactor":     ("tg-reactor",               120),   # 2 мин
    "account_check":  ("account-checker",          360),   # 6 мин
    "obsidian_sync":  ("obsidian-sync",            60),    # 1 мин
    "daily_report":   ("daily-report",             120),   # 2 мин
}


# ══════════════════════════════════════════════════════════
# 5. ПРИМЕР: защищённый пайплайн NUTRA
# ══════════════════════════════════════════════════════════

async def run_nutra_pipeline():
    """
    Пример использования lock в пайплайне.
    Этот код вставить в n8n Execute Code ноду.
    """
    lock_name, ttl = PIPELINE_LOCKS["nutra"]

    async with pipeline_lock(lock_name, ttl) as acquired:
        if not acquired:
            logger.info(
                "NUTRA pipeline уже запущен другим инстансом. "
                "Эта итерация пропущена."
            )
            return {"status": "skipped", "reason": "lock_busy"}

        logger.info("NUTRA pipeline: старт")

        try:
            # Шаг 1: СЦЕНАРИСТ генерирует скрипт
            # script = await content_creator_agent(...)

            # Шаг 2: РЕЖИССЁР рендерит видео
            # video_path = await video_director_agent(script)

            # Шаг 3: ДИКТОР озвучивает
            # audio_path = await elevenlabs_agent(script)

            # Шаг 4: МОНТАЖЁР собирает
            # final_video = await ffmpeg_agent(video_path, audio_path)

            # Шаг 5: ДИСТРИБЬЮТОР публикует
            # result = await publisher_agent(final_video)

            logger.info("NUTRA pipeline: завершён ✅")
            return {"status": "success"}

        except Exception as e:
            logger.error(f"NUTRA pipeline: ошибка ❌ {e}")
            return {"status": "error", "error": str(e)}
            # lock освобождается автоматически в finally блоке


# ══════════════════════════════════════════════════════════
# 6. n8n JAVASCRIPT ВЕРСИЯ (для Execute Code ноды)
# ══════════════════════════════════════════════════════════
N8N_LOCK_CODE = """
// Вставить в начало каждого n8n пайплайна
// Requires: n8n с Redis credentials

const LOCK_KEY = 'pipeline_lock:nutra';
const LOCK_TTL = 600; // секунд
const LOCK_TOKEN = Date.now().toString();

// Попытка захватить lock
const acquired = await $redis.set(LOCK_KEY, LOCK_TOKEN, 'EX', LOCK_TTL, 'NX');

if (!acquired) {
  const ttlLeft = await $redis.ttl(LOCK_KEY);
  console.log(`Pipeline уже запущен. Осталось ${ttlLeft}s. Пропускаем.`);
  return [{ json: { status: 'skipped', reason: 'lock_busy', ttl_left: ttlLeft } }];
}

// Сохраняем token для освобождения
$execution.customData.set('lock_token', LOCK_TOKEN);

// --- ПАЙПЛАЙН КОД ЗДЕСЬ ---

// В конце пайплайна (Success node):
// const token = $execution.customData.get('lock_token');
// const currentToken = await $redis.get('pipeline_lock:nutra');
// if (currentToken === token) await $redis.del('pipeline_lock:nutra');
"""
