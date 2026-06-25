"""
T3 — COMMENTER: нативные комментарии к постам.

Жёсткие ограничения:
  - max 3–5 комментариев/день/аккаунт
  - только аккаунты в фазе niche_content или monetization (день 6+)
  - Claude Haiku генерирует текст комментария
  - двухэтапный постинг: эмодзи → 45 сек → edit на полный текст (имитирует живого человека)
  - jitter 5–20 мин между комментариями
"""
from __future__ import annotations
import asyncio
import random
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("ubt_os.telegram.commenter")

MAX_COMMENTS_PER_DAY = 4

# Эмодзи-реакции для первого этапа постинга (выглядит как живая реакция)
FIRST_STAGE_EMOJIS = {
    "nutra":   ["👍", "💪", "🔥", "❤️", "✅"],
    "betting": ["🔥", "💯", "⚽", "🏆", "👏"],
}

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

    def __init__(self, session_manager, tg_client=None, supabase_url: str = "", supabase_key: str = ""):
        self.sm          = session_manager
        self.client      = tg_client
        self._supa_url   = supabase_url or os.getenv("SUPABASE_URL", "")
        self._supa_key   = supabase_key or os.getenv("SUPABASE_SERVICE_KEY", "")

    async def run(self, account_id: str, target_channels: list[str]) -> dict:
        """Публикует комментарии от имени аккаунта в указанных каналах."""
        account = self.sm.get_account(account_id)
        if not account:
            return {"ok": False, "error": "account not found"}

        if account.warming_day < 6:
            return {"ok": False, "error": f"too early — day {account.warming_day}, need 6+"}

        if account.status == "banned":
            return {"ok": False, "error": "banned"}

        daily = self.sm.get_daily(account_id, "comments")
        if daily >= MAX_COMMENTS_PER_DAY:
            return {"ok": False, "error": f"daily limit reached ({daily}/{MAX_COMMENTS_PER_DAY})"}

        posted = 0
        errors = []
        log_entries = []

        for channel in target_channels:
            if daily + posted >= MAX_COMMENTS_PER_DAY:
                break
            try:
                result = await self._comment_on_latest(account, channel)
                if result:
                    posted += 1
                    self.sm.increment_daily(account_id, "comments")
                    log_entries.append({
                        "account_id": account_id,
                        "phone": account.phone,
                        "channel": channel,
                        "text": result.get("text", ""),
                        "msg_id": result.get("msg_id"),
                        "vertical": account.vertical,
                        "posted_at": datetime.now(timezone.utc).isoformat(),
                    })
                    logger.info(f"[T3] {account.phone} → {channel}: {result.get('text','')[:60]}")
                    await asyncio.sleep(random.uniform(300, 1200))
            except Exception as e:
                logger.warning(f"[T3] {account.phone} error in {channel}: {e}")
                errors.append(str(e))

        self.sm.update_account(account_id, last_action_at=datetime.now(timezone.utc).isoformat())

        # Сохраняем лог в Supabase
        if log_entries:
            await self._save_comment_log(log_entries)

        return {"ok": True, "posted": posted, "errors": errors, "daily_total": daily + posted, "log": log_entries}

    async def _comment_on_latest(self, account, channel: str) -> dict | None:
        """Двухэтапный постинг: эмодзи → 45 сек → edit на полный текст."""
        if not self.client:
            text = await self._generate_comment(account.vertical, "Sample post text", "ru")
            logger.info(f"[T3] simulated 2-stage comment: {text}")
            return {"text": text, "msg_id": None}

        try:
            msgs = await self.client.get_messages(channel, limit=3)
            if not msgs:
                return None

            msg = random.choice(msgs)
            post_text = msg.text or msg.caption or ""
            if not post_text:
                return None

            lang = _detect_lang(post_text)
            full_text = await self._generate_comment(account.vertical, post_text[:300], lang)
            if not full_text:
                return None

            # Этап 1: постим эмодзи-реакцию
            emojis = FIRST_STAGE_EMOJIS.get(account.vertical, ["👍", "🔥"])
            emoji = random.choice(emojis)
            sent = await self.client.send_message(
                entity=channel,
                message=emoji,
                comment_to=msg.id,
            )
            logger.info(f"[T3] stage1 emoji '{emoji}' → {channel}")

            # Пауза 40–55 секунд (имитация набора текста)
            await asyncio.sleep(random.uniform(40, 55))

            # Этап 2: редактируем на полный текст
            await self.client.edit_message(entity=channel, message=sent.id, text=full_text)
            logger.info(f"[T3] stage2 edit → full text: {full_text[:60]}")

            return {"text": full_text, "msg_id": sent.id}

        except Exception as e:
            logger.warning(f"[T3] _comment_on_latest error: {e}")
            raise

    async def _generate_comment(self, vertical: str, post_text: str, lang: str) -> str:
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
            return resp.content[0].text.strip().strip('"').strip("'")
        except Exception as e:
            logger.warning(f"[T3] generate_comment error: {e}")
            return ""

    async def _save_comment_log(self, entries: list[dict]):
        """Сохраняем лог комментариев в Supabase (таблица comment_log)."""
        if not self._supa_url or not self._supa_key:
            return
        try:
            import urllib.request
            import json as _json
            url = f"{self._supa_url}/rest/v1/comment_log"
            data = _json.dumps(entries).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("apikey", self._supa_key)
            req.add_header("Authorization", f"Bearer {self._supa_key}")
            req.add_header("Content-Type", "application/json")
            req.add_header("Prefer", "return=minimal")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.warning(f"[T3] save_comment_log error: {e}")


def _detect_lang(text: str) -> str:
    cyrillic = sum(1 for c in text if 'Ѐ' <= c <= 'ӿ')
    if cyrillic > len(text) * 0.3:
        return "ru"
    polish = sum(1 for c in text if c in "ąćęłńóśźż")
    if polish > 2:
        return "pl"
    return "en"
