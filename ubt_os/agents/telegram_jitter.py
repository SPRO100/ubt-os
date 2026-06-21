"""
FIX #8: Telegram Commenter — Human Jitter
==========================================
Проблема: регулярные интервалы (каждые 2ч ровно) легко
детектируются Telegram как бот → спамблок.

Решение:
  - Случайный разброс ±30 минут к базовому интервалу
  - Случайная задержка перед каждым действием (typing simulation)
  - Разные паттерны активности по времени суток
  - Лимиты по дням недели
"""

from __future__ import annotations
import asyncio
import logging
import random
from datetime import datetime, timezone, time as dt_time
from typing import Optional

logger = logging.getLogger("telegram.jitter")


# ══════════════════════════════════════════════════════════
# 1. КОНФИГУРАЦИЯ ЧЕЛОВЕКОПОДОБНОГО ПОВЕДЕНИЯ
# ══════════════════════════════════════════════════════════

# Активность по часам (0-23): вес = вероятность действия
HOURLY_ACTIVITY_WEIGHTS = {
    0:  0.1,  1:  0.05, 2:  0.0,  3:  0.0,  4:  0.0,  5:  0.1,
    6:  0.3,  7:  0.5,  8:  0.8,  9:  0.9,  10: 1.0,  11: 0.9,
    12: 0.7,  13: 0.8,  14: 0.9,  15: 0.9,  16: 0.8,  17: 0.9,
    18: 1.0,  19: 0.9,  20: 0.8,  21: 0.6,  22: 0.4,  23: 0.2,
}

# Лимиты действий в день на аккаунт
DAILY_LIMITS = {
    "comment":  {"min": 1, "max": 5},
    "reaction": {"min": 3, "max": 15},
    "view":     {"min": 10, "max": 50},
}

# Задержки (в секундах) — имитация human timing
DELAYS = {
    "before_open_chat":      (2.0,  8.0),   # до открытия чата
    "reading_time_per_char": (0.02, 0.05),  # время "чтения" сообщения
    "typing_preparation":    (1.5,  5.0),   # пауза перед набором
    "between_actions":       (30,   180),   # между действиями одного акк
    "between_accounts":      (60,   300),   # между аккаунтами
    "after_comment":         (120,  600),   # после комментария
}


# ══════════════════════════════════════════════════════════
# 2. JITTER ENGINE
# ══════════════════════════════════════════════════════════

class HumanJitter:
    """
    Генератор задержек имитирующих человеческое поведение.
    Используется в T2-WARMER, T3-COMMENTER, T4-REACTOR.
    """

    @staticmethod
    def delay(action: str) -> float:
        """Случайная задержка для действия в секундах."""
        lo, hi = DELAYS.get(action, (1.0, 3.0))
        # Используем betavariate для более реалистичного распределения
        # (пики у меньших значений, длинный хвост)
        t = random.betavariate(1.5, 4.0)
        return lo + t * (hi - lo)

    @staticmethod
    def reading_delay(text: str) -> float:
        """Задержка имитирующая чтение текста."""
        lo, hi = DELAYS["reading_time_per_char"]
        per_char = random.uniform(lo, hi)
        return min(len(text) * per_char, 15.0)  # максимум 15 сек

    @staticmethod
    def base_interval_with_jitter(
        base_seconds: int = 7200,
        jitter_seconds: int = 1800
    ) -> float:
        """
        Базовый интервал с ±jitter.
        По умолчанию: 2ч ± 30 мин → от 1.5ч до 2.5ч
        """
        return base_seconds + random.randint(-jitter_seconds, jitter_seconds)

    @staticmethod
    def should_act_now() -> bool:
        """
        Проверяет, стоит ли действовать в текущий час.
        Ночью (2-5 UTC) — почти не действуем.
        """
        hour = datetime.now(timezone.utc).hour
        weight = HOURLY_ACTIVITY_WEIGHTS.get(hour, 0.5)
        return random.random() < weight

    @staticmethod
    def daily_action_count(action: str) -> int:
        """Случайное количество действий на день."""
        limits = DAILY_LIMITS.get(action, {"min": 1, "max": 3})
        # Нормальное распределение внутри диапазона
        mean  = (limits["min"] + limits["max"]) / 2
        sigma = (limits["max"] - limits["min"]) / 4
        count = int(random.gauss(mean, sigma))
        return max(limits["min"], min(limits["max"], count))

    @staticmethod
    async def sleep(action: str):
        """Асинхронный sleep с jitter для действия."""
        d = HumanJitter.delay(action)
        logger.debug(f"[Jitter] {action}: sleep {d:.1f}s")
        await asyncio.sleep(d)


# ══════════════════════════════════════════════════════════
# 3. COMMENTER С JITTER
# ══════════════════════════════════════════════════════════

class TelegramCommenterScheduler:
    """
    Планировщик комментариев с human-like задержками.
    Вызывается из n8n tg-commenter воркфлоу (каждые 2ч).
    """

    def __init__(self, db_client, telethon_client):
        self.db     = db_client
        self.tg     = telethon_client
        self.jitter = HumanJitter()

    async def run_for_account(self, account_id: str, target_channels: list[str]):
        """
        Выполняет комментирование для одного аккаунта.
        Количество комментариев — случайное (1-5).
        """
        # Проверяем время суток
        if not self.jitter.should_act_now():
            logger.info(f"[Commenter] {account_id[:8]}: пропуск (неактивный час)")
            return

        count_today = self.jitter.daily_action_count("comment")
        logger.info(f"[Commenter] {account_id[:8]}: план {count_today} комментариев")

        for i, channel in enumerate(target_channels[:count_today]):
            try:
                # Задержка перед открытием чата
                await self.jitter.sleep("before_open_chat")

                # Получаем последние сообщения
                messages = await self._get_recent_messages(channel, limit=5)
                if not messages:
                    continue

                # Выбираем случайное сообщение
                message = random.choice(messages)

                # Имитируем чтение
                read_time = self.jitter.reading_delay(message.get("text", ""))
                await asyncio.sleep(read_time)

                # Генерируем комментарий через Claude Haiku
                comment = await self._generate_comment(message)

                # Задержка имитирующая набор
                await self.jitter.sleep("typing_preparation")

                # Отправляем комментарий
                await self._post_comment(channel, message["id"], comment)

                logger.info(
                    f"[Commenter] {account_id[:8]}: "
                    f"✅ Прокомментировал {channel}"
                )

                # Задержка после комментария
                await self.jitter.sleep("after_comment")

                # Задержка между аккаунтами если несколько
                if i < count_today - 1:
                    await self.jitter.sleep("between_actions")

            except Exception as e:
                logger.error(
                    f"[Commenter] {account_id[:8]}: "
                    f"❌ Ошибка в {channel}: {e}"
                )

    async def _get_recent_messages(self, channel: str, limit: int) -> list[dict]:
        """Получает последние сообщения из канала."""
        # Реализация через Telethon
        # messages = await self.tg.get_messages(channel, limit=limit)
        return []  # placeholder

    async def _generate_comment(self, message: dict) -> str:
        """Генерирует релевантный комментарий через Claude Haiku."""
        # Реализация через LiteLLM
        return ""  # placeholder

    async def _post_comment(self, channel: str, message_id: int, text: str):
        """Публикует комментарий."""
        # await self.tg.send_message(channel, text, reply_to=message_id)
        pass


# ══════════════════════════════════════════════════════════
# 4. REACTOR С JITTER
# ══════════════════════════════════════════════════════════

class TelegramReactorScheduler:
    """T4-REACTOR: расставляет реакции с human jitter."""

    REACTION_EMOJIS = ["👍", "🔥", "❤️", "👏", "🎯", "💪", "✅"]

    def __init__(self, db_client, telethon_client):
        self.db     = db_client
        self.tg     = telethon_client
        self.jitter = HumanJitter()

    async def run_for_account(self, account_id: str, target_channels: list[str]):
        if not self.jitter.should_act_now():
            return

        count = self.jitter.daily_action_count("reaction")
        for channel in target_channels[:count]:
            await self.jitter.sleep("before_open_chat")
            emoji = random.choice(self.REACTION_EMOJIS)
            # await self._react(channel, emoji)
            await self.jitter.sleep("between_actions")


# ══════════════════════════════════════════════════════════
# 5. n8n CRON ИНТЕРВАЛ С JITTER (JavaScript)
# ══════════════════════════════════════════════════════════

N8N_JITTER_CODE = """
// Вставить в n8n перед вызовом tg-commenter
// Добавляет случайную задержку ±30 минут

const BASE_INTERVAL_MS  = 2 * 60 * 60 * 1000; // 2 часа
const JITTER_MS         = 30 * 60 * 1000;      // ±30 минут

const jitter     = Math.floor(Math.random() * JITTER_MS * 2) - JITTER_MS;
const actualWait = BASE_INTERVAL_MS + jitter;

// Проверяем время суток (не работаем 2-5 UTC)
const hour = new Date().getUTCHours();
if (hour >= 2 && hour <= 5) {
  return [{ json: { status: 'skipped', reason: 'inactive_hours', hour } }];
}

// Ждём с jitter
await new Promise(r => setTimeout(r, Math.max(0, jitter)));

return [{ json: { status: 'running', jitter_ms: jitter } }];
"""
