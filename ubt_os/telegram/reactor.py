"""
T4 — REACTOR: лайки и реакции на посты в Telegram.

Мягкое вовлечение — безопаснее комментариев.
Лимиты: 8–15 реакций/день/аккаунт.
"""
from __future__ import annotations
import asyncio
import random
import logging
from datetime import datetime, timezone

logger = logging.getLogger("ubt_os.telegram.reactor")

MAX_REACTIONS_PER_DAY = 12

REACTIONS_BY_VERTICAL = {
    "nutra":   ["👍", "❤️", "🔥", "💪", "✅"],
    "betting": ["🔥", "💰", "⚽", "🏆", "👏"],
    "neutral": ["👍", "❤️", "🔥", "👏", "😍"],
}


class TelegramReactor:
    """T4 — реакции на посты."""

    def __init__(self, session_manager, tg_client=None):
        self.sm     = session_manager
        self.client = tg_client

    async def run(self, account_id: str, target_channels: list[str]) -> dict:
        account = self.sm.get_account(account_id)
        if not account:
            return {"ok": False, "error": "account not found"}

        if account.status == "banned":
            return {"ok": False, "error": "banned"}

        daily = self.sm.get_daily(account_id, "reactions")
        if daily >= MAX_REACTIONS_PER_DAY:
            return {"ok": False, "error": f"daily limit reached ({daily}/{MAX_REACTIONS_PER_DAY})"}

        reacted = 0
        errors  = []
        reactions = REACTIONS_BY_VERTICAL.get(account.vertical, REACTIONS_BY_VERTICAL["neutral"])

        for channel in target_channels:
            if daily + reacted >= MAX_REACTIONS_PER_DAY:
                break
            try:
                n = await self._react_to_channel(account, channel, reactions, MAX_REACTIONS_PER_DAY - daily - reacted)
                reacted += n
                for _ in range(n):
                    self.sm.increment_daily(account_id, "reactions")
                await asyncio.sleep(random.uniform(20, 60))
            except Exception as e:
                logger.warning(f"[T4] {account.phone} error in {channel}: {e}")
                errors.append(str(e))

        self.sm.update_account(account_id,
            last_action_at=datetime.now(timezone.utc).isoformat()
        )
        return {"ok": True, "reacted": reacted, "errors": errors, "daily_total": daily + reacted}

    async def _react_to_channel(self, account, channel: str, reactions: list[str], max_n: int) -> int:
        if not self.client:
            logger.info(f"[T4] simulated {max_n} reactions in {channel}")
            return min(max_n, 3)

        try:
            msgs = await self.client.get_messages(channel, limit=5)
            reacted = 0
            for msg in msgs[:max_n]:
                reaction = random.choice(reactions)
                try:
                    await self.client.send_reaction(channel, msg.id, reaction)
                    reacted += 1
                    logger.debug(f"[T4] {reaction} on {channel}/{msg.id}")
                    await asyncio.sleep(random.uniform(5, 15))
                except Exception as e:
                    logger.warning(f"[T4] single reaction error: {e}")
            return reacted
        except Exception as e:
            logger.warning(f"[T4] channel error {channel}: {e}")
            raise
