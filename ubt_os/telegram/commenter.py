"""
T3 — COMMENTER: нативные комментарии к постам.

Жёсткие ограничения:
  - max 3–5 комментариев/день/аккаунт
  - только аккаунты в фазе niche_content или monetization (день 6+)
  - Claude Haiku генерирует текст комментария
  - стиль: нативный, без ссылок, без упоминания продукта напрямую
  - jitter 5–20 мин между комментариями
"""
from __future__ import annotations
import asyncio
import random
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("ubt_os.telegram.commenter")

MAX_COMMENTS_PER_DAY = 4  # консервативно, не 5

# Промпты для генерации комментариев по вертикали
COMMENT_PROMPTS = {
    "nutra": """\
Ты — реальный пользователь Telegram, оставляешь нативный комментарий к посту о здоровье/похудении/питании.
Пост: {post_text}

Требования:
- 1–2 предложения максимум
- звучит как живой человек, не как реклама
- можно поделиться своим опытом или задать вопрос
- без ссылок, без упоминания брендов, без CTA
- на языке поста ({lang})

Ответь только текстом комментария, без кавычек и пояснений.""",

    "betting": """\
Ты — реальный пользователь Telegram, оставляешь нативный комментарий к посту о спорте/ставках/прогнозах.
Пост: {post_text}

Требования:
- 1–2 предложения максимум
- звучит как живой болельщик или любитель ставок
- без ссылок, без рекламы, без CTA
- на языке поста ({lang})

Ответь только текстом комментария, без кавычек и пояснений.""",
}


class TelegramCommenter:
    """T3 — генерация и публикация нативных комментариев."""

    def __init__(self, session_manager, tg_client=None):
        self.sm     = session_manager
        self.client = tg_client

    async def run(self, account_id: str, target_channels: list[str]) -> dict:
        """Публикует комментарии от имени аккаунта в указанных каналах."""
        account = self.sm.get_account(account_id)
        if not account:
            return {"ok": False, "error": "account not found"}

        # Только аккаунты с прогревом день 6+
        if account.warming_day < 6:
            return {"ok": False, "error": f"too early — day {account.warming_day}, need 6+"}

        if account.status == "banned":
            return {"ok": False, "error": "banned"}

        daily = self.sm.get_daily(account_id, "comments")
        if daily >= MAX_COMMENTS_PER_DAY:
            return {"ok": False, "error": f"daily limit reached ({daily}/{MAX_COMMENTS_PER_DAY})"}

        posted = 0
        errors = []

        for channel in target_channels:
            if daily + posted >= MAX_COMMENTS_PER_DAY:
                break
            try:
                result = await self._comment_on_latest(account, channel)
                if result:
                    posted += 1
                    self.sm.increment_daily(account_id, "comments")
                    logger.info(f"[T3] {account.phone} commented in {channel}")
                    # Jitter 5–20 мин между комментариями
                    await asyncio.sleep(random.uniform(300, 1200))
            except Exception as e:
                logger.warning(f"[T3] {account.phone} error in {channel}: {e}")
                errors.append(str(e))

        self.sm.update_account(account_id,
            last_action_at=datetime.now(timezone.utc).isoformat()
        )

        return {"ok": True, "posted": posted, "errors": errors, "daily_total": daily + posted}

    async def _comment_on_latest(self, account, channel: str) -> bool:
        """Берёт последний пост из канала, генерирует и публикует комментарий."""
        if not self.client:
            text = await self._generate_comment(account.vertical, "Sample post text", "ru")
            logger.info(f"[T3] simulated comment: {text}")
            return True

        try:
            msgs = await self.client.get_messages(channel, limit=3)
            if not msgs:
                return False

            # Берём случайный пост из последних 3
            msg = random.choice(msgs)
            post_text = msg.text or msg.caption or ""
            if not post_text:
                return False

            lang = _detect_lang(post_text)
            comment_text = await self._generate_comment(account.vertical, post_text[:300], lang)

            if not comment_text:
                return False

            await self.client.send_message(
                entity=channel,
                message=comment_text,
                comment_to=msg.id,
            )
            return True

        except Exception as e:
            logger.warning(f"[T3] _comment_on_latest error: {e}")
            raise

    async def _generate_comment(self, vertical: str, post_text: str, lang: str) -> str:
        """Генерирует нативный комментарий через Claude Haiku."""
        try:
            from anthropic import AsyncAnthropic
            prompt_tpl = COMMENT_PROMPTS.get(vertical, COMMENT_PROMPTS["nutra"])
            prompt = prompt_tpl.format(post_text=post_text, lang=lang)

            client = AsyncAnthropic()
            resp = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip().strip('"').strip("'")
            return text
        except Exception as e:
            logger.warning(f"[T3] generate_comment error: {e}")
            return ""


def _detect_lang(text: str) -> str:
    """Простое определение языка по символам."""
    cyrillic = sum(1 for c in text if 'Ѐ' <= c <= 'ӿ')
    if cyrillic > len(text) * 0.3:
        return "ru"
    polish = sum(1 for c in text if c in "ąćęłńóśźż")
    if polish > 2:
        return "pl"
    return "en"
