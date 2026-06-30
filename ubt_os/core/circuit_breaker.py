"""
FIX #2: ORCHESTRATOR — Circuit Breaker + Timeout + Fallback
============================================================
Проблема: если Anthropic API падает или rate-limit → вся система стоит.
Решение:
  1. Timeout 30s на каждый вызов агента
  2. Retry × 3 с exponential backoff
  3. Circuit Breaker: после 5 ошибок подряд → OPEN (не звоним 2 мин)
  4. Fallback: PUBLISHING продолжает по последнему контент-плану
  5. Telegram-алерт при переходе в OPEN
"""

from __future__ import annotations
import asyncio
import time
import logging
import os
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass, field
import anthropic
import httpx

logger = logging.getLogger("orchestrator.circuit_breaker")


# ══════════════════════════════════════════════════════════
# 1. CIRCUIT BREAKER
# ══════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED  = "closed"   # норма, запросы проходят
    OPEN    = "open"     # авария, запросы блокируются
    HALF    = "half"     # проверка — пробуем один запрос


@dataclass
class CircuitBreaker:
    name:               str
    failure_threshold:  int   = 5      # сколько ошибок подряд → OPEN
    recovery_timeout:   float = 120.0  # секунд в OPEN перед HALF
    success_threshold:  int   = 2      # успехов в HALF → CLOSED

    _state:             CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count:     int          = field(default=0, init=False)
    _success_count:     int          = field(default=0, init=False)
    _last_failure_time: float        = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                logger.info(f"[{self.name}] Circuit → HALF_OPEN (recovery timeout passed)")
                self._state = CircuitState.HALF
        return self._state

    def record_success(self):
        if self.state == CircuitState.HALF:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                logger.info(f"[{self.name}] Circuit → CLOSED ✅")
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        else:
            self._failure_count = 0

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        self._success_count = 0
        if self._failure_count >= self.failure_threshold:
            if self._state != CircuitState.OPEN:
                logger.error(
                    f"[{self.name}] Circuit → OPEN 🔴 "
                    f"({self._failure_count} failures). "
                    f"Recovery in {self.recovery_timeout}s"
                )
                self._state = CircuitState.OPEN
                # уведомление в Telegram
                asyncio.create_task(_send_telegram_alert(
                    f"🔴 ORCHESTRATOR Circuit OPEN\n"
                    f"Агент: {self.name}\n"
                    f"Ошибок подряд: {self._failure_count}\n"
                    f"Система переключилась на fallback-режим.\n"
                    f"Восстановление через {int(self.recovery_timeout)}s"
                ))

    def allow_request(self) -> bool:
        s = self.state
        if s == CircuitState.CLOSED:
            return True
        if s == CircuitState.HALF:
            return True   # пробуем один запрос
        return False      # OPEN — блокируем


# ══════════════════════════════════════════════════════════
# 2. RETRY + TIMEOUT WRAPPER
# ══════════════════════════════════════════════════════════

async def call_agent_with_retry(
    agent_fn: Callable,
    *args,
    breaker: CircuitBreaker,
    timeout_sec: float = 30.0,
    max_retries: int = 3,
    **kwargs
) -> Any:
    """
    Вызывает агента с:
    - Circuit Breaker проверкой
    - Timeout 30s
    - Retry × 3 с exponential backoff (2s, 4s, 8s)
    """
    if not breaker.allow_request():
        raise CircuitOpenError(
            f"Circuit OPEN для {breaker.name}. "
            f"Используется fallback-режим."
        )

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            result = await asyncio.wait_for(
                agent_fn(*args, **kwargs),
                timeout=timeout_sec
            )
            breaker.record_success()
            return result

        except asyncio.TimeoutError:
            last_exc = TimeoutError(
                f"Agent {breaker.name} timeout после {timeout_sec}s "
                f"(попытка {attempt}/{max_retries})"
            )
            logger.warning(str(last_exc))
            breaker.record_failure()

        except anthropic.RateLimitError as e:
            last_exc = e
            wait = 2 ** attempt * 5  # 10s, 20s, 40s для rate limit
            logger.warning(f"Rate limit. Ожидаем {wait}s (попытка {attempt})")
            breaker.record_failure()
            await asyncio.sleep(wait)
            continue

        except (anthropic.APIConnectionError, anthropic.InternalServerError) as e:
            last_exc = e
            breaker.record_failure()

        except Exception as e:
            # Неизвестная ошибка — не засчитываем в breaker, пробрасываем
            logger.error(f"Неожиданная ошибка в {breaker.name}: {e}")
            raise

        if attempt < max_retries:
            wait = 2 ** attempt  # 2s, 4s, 8s
            logger.info(f"Retry через {wait}s...")
            await asyncio.sleep(wait)

    raise MaxRetriesExceeded(
        f"Agent {breaker.name} не ответил после {max_retries} попыток. "
        f"Последняя ошибка: {last_exc}"
    )


# ══════════════════════════════════════════════════════════
# 3. FALLBACK РЕЖИМ
# ══════════════════════════════════════════════════════════

class FallbackMode:
    """
    Когда ORCHESTRATOR недоступен — PUBLISHING продолжает
    по последнему утверждённому контент-плану из БД.
    """

    @staticmethod
    async def get_last_approved_plans(limit: int = 10) -> list[dict]:
        """
        Берём последние approved планы из Supabase.
        PUBLISHING использует их без ORCHESTRATOR.
        """
        from ubt_os.core.agent_api_layer import ContentPlanReader
        plans = ContentPlanReader.get_approved()
        logger.info(
            f"[FallbackMode] Загружено {len(plans)} планов "
            f"для автономной публикации"
        )
        return plans[:limit]

    @staticmethod
    async def notify_fallback_active():
        await _send_telegram_alert(
            "⚠️ ORCHESTRATOR FALLBACK ACTIVE\n"
            "Публикация идёт по сохранённым планам.\n"
            "Новый контент не генерируется до восстановления API."
        )


# ══════════════════════════════════════════════════════════
# 4. TELEGRAM ALERT
# ══════════════════════════════════════════════════════════

async def _send_telegram_alert(text: str):
    """Отправляет алерт в Telegram бот."""
    bot_token = os.getenv("TELEGRAM_ALERT_BOT_TOKEN")
    chat_id   = os.getenv("TELEGRAM_ALERT_CHAT_ID")
    if not bot_token or not chat_id:
        logger.warning("TELEGRAM_ALERT_* не настроены, алерт пропущен")
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            )
    except Exception as e:
        logger.error(f"Не удалось отправить Telegram алерт: {e}")


# ══════════════════════════════════════════════════════════
# 5. ИНСТАНСЫ BREAKER-ОВ ПО АГЕНТАМ
# ══════════════════════════════════════════════════════════

BREAKERS: dict[str, CircuitBreaker] = {
    "ORCHESTRATOR":    CircuitBreaker("ORCHESTRATOR",    failure_threshold=5, recovery_timeout=120),
    "CONTENT_CREATOR": CircuitBreaker("CONTENT_CREATOR", failure_threshold=5, recovery_timeout=60),
    "RESEARCH":        CircuitBreaker("RESEARCH",        failure_threshold=3, recovery_timeout=60),
    "HIGGSFIELD":      CircuitBreaker("HIGGSFIELD",      failure_threshold=3, recovery_timeout=300),
    "PUBLISHING":      CircuitBreaker("PUBLISHING",      failure_threshold=5, recovery_timeout=60),
}


# ══════════════════════════════════════════════════════════
# 6. КАСТОМНЫЕ ИСКЛЮЧЕНИЯ
# ══════════════════════════════════════════════════════════

class CircuitOpenError(Exception):
    """Выбрасывается когда circuit в состоянии OPEN."""

class MaxRetriesExceeded(Exception):
    """Выбрасывается после исчерпания всех retry-попыток."""


# ══════════════════════════════════════════════════════════
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ══════════════════════════════════════════════════════════
# async def run_content_creator(prompt: str) -> str:
#     return await call_agent_with_retry(
#         _actual_content_creator_call,
#         prompt,
#         breaker=BREAKERS["CONTENT_CREATOR"],
#         timeout_sec=30,
#         max_retries=3,
#     )
