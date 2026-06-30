"""
FIX #11: Blotato — Dead Letter Queue + Retry
=============================================
Проблема: если публикация через Blotato упала (API timeout,
неверный формат) — задача теряется молча. Нет retry, нет уведомления.

Решение:
  - 3 попытки с нарастающей задержкой (15 мин, 1ч, 1ч)
  - После 3 провалов → Dead Letter Queue → ручной ревью
  - Telegram алерт при попадании в DLQ
  - Суточный отчёт по DLQ
"""

from __future__ import annotations
import logging
import os
from datetime import datetime, timezone, timedelta
import httpx

logger = logging.getLogger("publishing.dlq")

# Задержки между попытками
RETRY_DELAYS = [
    15 * 60,    # 15 минут
    60 * 60,    # 1 час
    60 * 60,    # 1 час (финальная)
]
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1   # 3 задержки = 4 попытки (1 + 3)


# ══════════════════════════════════════════════════════════
# 1. PUBLISHER С DLQ
# ══════════════════════════════════════════════════════════

class BlotatoPublisher:
    """
    Публикатор с retry и Dead Letter Queue.
    Работает поверх Blotato API.
    """

    def __init__(self, db_client, blotato_api_key: str):
        self.db         = db_client
        self.api_key    = blotato_api_key
        self.base_url   = "https://app.blotato.com/api"

    async def publish(self, pub_id: str) -> dict:
        """
        Главный метод публикации.
        Загружает publication из БД, пытается опубликовать с retry.
        """
        pub = (
            self.db.table("publications")
            .select("*")
            .eq("id", pub_id)
            .single()
            .execute()
            .data
        )
        if not pub:
            raise ValueError(f"Publication {pub_id} не найдена")

        if pub["status"] == "dead_letter":
            logger.warning(f"[DLQ] {pub_id[:8]}: уже в Dead Letter, пропускаем")
            return {"status": "dead_letter"}

        if pub["status"] == "published":
            logger.info(f"[DLQ] {pub_id[:8]}: уже опубликовано")
            return {"status": "already_published"}

        attempt  = pub.get("attempt_count", 0) + 1
        max_att  = MAX_ATTEMPTS

        logger.info(f"[Publisher] {pub_id[:8]}: попытка {attempt}/{max_att}")

        try:
            result = await self._call_blotato(pub)

            # Успех
            self.db.table("publications").update({
                "status":           "published",
                "published_at":     datetime.now(timezone.utc).isoformat(),
                "platform_post_id": result.get("post_id"),
                "attempt_count":    attempt,
            }).eq("id", pub_id).execute()

            logger.info(f"[Publisher] ✅ {pub_id[:8]}: опубликовано")
            return {"status": "published", "attempt": attempt}

        except PublishError as e:
            return await self._handle_failure(pub, attempt, str(e))

    async def _call_blotato(self, pub: dict) -> dict:
        """Вызывает Blotato API."""
        video  = (
            self.db.table("videos")
            .select("storage_url,duration_sec")
            .eq("id", pub["video_id"])
            .single()
            .execute()
            .data
        )
        account = (
            self.db.table("accounts")
            .select("platform,gologin_profile_id")
            .eq("id", pub["account_id"])
            .single()
            .execute()
            .data
        )

        if not video or not video.get("storage_url"):
            raise PublishError("Видео не найдено или нет URL")

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/posts",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "platform":    account["platform"],
                    "video_url":   video["storage_url"],
                    "profile_id":  account.get("gologin_profile_id"),
                    "scheduled_at": pub["scheduled_at"],
                }
            )
            if resp.status_code >= 400:
                raise PublishError(
                    f"Blotato API ошибка {resp.status_code}: {resp.text[:200]}"
                )
            return resp.json()

    async def _handle_failure(self, pub: dict, attempt: int, error: str) -> dict:
        """Обрабатывает провал попытки."""
        pub_id = pub["id"]

        if attempt >= MAX_ATTEMPTS:
            # Все попытки исчерпаны → Dead Letter
            self.db.table("publications").update({
                "status":       "dead_letter",
                "attempt_count": attempt,
                "last_error":   error,
            }).eq("id", pub_id).execute()

            logger.error(f"[DLQ] ❌ {pub_id[:8]}: в Dead Letter после {attempt} попыток")
            await self._alert_dead_letter(pub, attempt, error)
            return {"status": "dead_letter", "attempt": attempt, "error": error}

        # Планируем следующую попытку
        delay = RETRY_DELAYS[attempt - 1]   # 0-indexed
        next_try = (
            datetime.now(timezone.utc) + timedelta(seconds=delay)
        ).isoformat()

        self.db.table("publications").update({
            "status":        "failed",
            "attempt_count": attempt,
            "last_error":    error,
            "scheduled_at":  next_try,       # перепланируем
        }).eq("id", pub_id).execute()

        logger.warning(
            f"[Publisher] ⚠️ {pub_id[:8]}: провал #{attempt}. "
            f"Следующая попытка через {delay//60} мин"
        )
        return {
            "status":    "retry_scheduled",
            "attempt":   attempt,
            "next_try":  next_try,
            "error":     error,
        }

    async def _alert_dead_letter(self, pub: dict, attempt: int, error: str):
        """Telegram алерт при попадании в DLQ."""
        account = (
            self.db.table("accounts")
            .select("platform,username")
            .eq("id", pub["account_id"])
            .maybe_single()
            .execute()
            .data or {}
        )
        await _send_telegram_alert(
            f"🚨 ПУБЛИКАЦИЯ В DEAD LETTER\n"
            f"ID: {pub['id'][:8]}\n"
            f"Платформа: {account.get('platform', '?')}\n"
            f"Аккаунт: @{account.get('username', '?')}\n"
            f"Попыток: {attempt}/{MAX_ATTEMPTS}\n"
            f"Ошибка: {error[:200]}\n\n"
            f"Требуется ручная публикация или переприоритизация."
        )


# ══════════════════════════════════════════════════════════
# 2. DLQ МЕНЕДЖЕР — просмотр и ручное управление
# ══════════════════════════════════════════════════════════

class DeadLetterQueueManager:

    def __init__(self, db_client):
        self.db = db_client

    def get_all(self) -> list[dict]:
        """Все публикации в Dead Letter."""
        return (
            self.db.table("publications")
            .select("*, accounts(platform,username), videos(storage_url)")
            .eq("status", "dead_letter")
            .order("updated_at", desc=True)
            .execute()
            .data
        )

    def retry_manual(self, pub_id: str) -> dict:
        """Ручной перезапуск из DLQ."""
        return (
            self.db.table("publications")
            .update({
                "status":        "scheduled",
                "attempt_count": 0,
                "last_error":    None,
                "scheduled_at":  datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", pub_id)
            .execute()
            .data
        )

    def archive(self, pub_id: str) -> dict:
        """Архивирует задачу из DLQ (осознанно отказываемся)."""
        return (
            self.db.table("publications")
            .update({"status": "archived"})
            .eq("id", pub_id)
            .execute()
            .data
        )

    async def daily_report(self):
        """Суточный отчёт по DLQ (вызывать из n8n daily-report)."""
        items = self.get_all()
        if not items:
            return

        platforms = {}
        for item in items:
            p = item.get("accounts", {}).get("platform", "?")
            platforms[p] = platforms.get(p, 0) + 1

        breakdown = "\n".join(f"  {p}: {c}" for p, c in platforms.items())
        await _send_telegram_alert(
            f"📋 СУТОЧНЫЙ ОТЧЁТ DLQ\n"
            f"Публикаций в Dead Letter: {len(items)}\n\n"
            f"По платформам:\n{breakdown}\n\n"
            f"Просмотреть: /dlq в боте"
        )


# ══════════════════════════════════════════════════════════
# 3. SQL для DLQ таблицы (дополнение к Fix #1 схеме)
# ══════════════════════════════════════════════════════════

DLQ_VIEW_SQL = """
-- Удобное представление для мониторинга
CREATE OR REPLACE VIEW v_dead_letter_publications AS
SELECT
    p.id,
    p.attempt_count,
    p.last_error,
    p.updated_at AS last_attempt,
    a.platform,
    a.username,
    v.storage_url,
    cp.title AS content_title
FROM publications p
JOIN accounts      a  ON a.id = p.account_id
JOIN videos        v  ON v.id = p.video_id
JOIN content_plans cp ON cp.id = v.content_plan_id
WHERE p.status = 'dead_letter'
ORDER BY p.updated_at DESC;
"""


# ══════════════════════════════════════════════════════════
# УТИЛИТА
# ══════════════════════════════════════════════════════════

class PublishError(Exception):
    pass


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
