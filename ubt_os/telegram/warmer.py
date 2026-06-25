"""
T2 — WARMER: прогрев Telegram-аккаунта по протоколу Days 1–8+.

Протокол (из CLAUDE.md):
  Дни 1–3: просмотры и лайки, ноль постов
  Дни 4–5: 2 нейтральных поста, без CTA
  Дни 6–7: 2 нишевых поста, без ссылок
  День 8+: монетизация

Лимиты безопасности:
  - views:    20–30 в день
  - reactions: 10–15 в день
  - channels: только крупные (>1000 подписчиков)
  - jitter: случайная задержка 30–180 сек между действиями
"""
from __future__ import annotations
import asyncio
import random
import logging
from datetime import datetime, timezone

logger = logging.getLogger("ubt_os.telegram.warmer")

# Лимиты по фазам (day → limits)
WARMING_LIMITS = {
    "views_only":      {"views": 25, "reactions": 12, "comments": 0, "posts": 0},
    "neutral_content": {"views": 20, "reactions": 10, "comments": 2, "posts": 1},
    "niche_content":   {"views": 20, "reactions": 10, "comments": 3, "posts": 1},
    "monetization":    {"views": 15, "reactions": 8,  "comments": 4, "posts": 2},
}

def _phase_for_day(day: int) -> str:
    if day <= 3: return "views_only"
    if day <= 5: return "neutral_content"
    if day <= 7: return "niche_content"
    return "monetization"

async def _jitter(min_s: int = 30, max_s: int = 180):
    """Случайная задержка между действиями — антибот защита."""
    await asyncio.sleep(random.uniform(min_s, max_s))


class TelegramWarmer:
    """T2 — прогрев аккаунта."""

    # Каналы для просмотра по вертикали (публичные, >100K подписчиков)
    WARMUP_CHANNELS = {
        "nutra": [
            "@zdorovye_secrets", "@dietadnia", "@fitnesspro_ru",
            "@hudeemvmeste", "@zdorovoe_pitanie_official",
        ],
        "betting": [
            "@stavki_sport", "@prognozy_football", "@betting_analytics_ru",
            "@sports_bets_free", "@football_bets_today",
        ],
        "neutral": [
            "@durov", "@telegram", "@tginfo", "@ru_travel", "@memes_ru",
        ],
    }

    def __init__(self, session_manager, tg_client=None):
        self.sm     = session_manager
        self.client = tg_client  # Telethon AsyncTelegramClient, передаётся снаружи

    async def run_daily_warmup(self, account_id: str) -> dict:
        """Запускает одну итерацию дневного прогрева для аккаунта."""
        account = self.sm.get_account(account_id)
        if not account:
            return {"ok": False, "error": f"account {account_id} not found"}

        if account.status == "banned":
            return {"ok": False, "error": "account banned"}

        if account.status == "flood_wait":
            return {"ok": False, "error": "flood_wait active"}

        day   = account.warming_day + 1
        phase = _phase_for_day(day)
        limits = WARMING_LIMITS[phase]

        logger.info(f"[T2] {account.phone} day={day} phase={phase}")

        results = {"views": 0, "reactions": 0, "comments": 0, "posts": 0, "phase": phase, "day": day}

        try:
            # 1. Просмотры каналов
            if limits["views"] > 0:
                results["views"] = await self._do_views(account, limits["views"])
                await _jitter(60, 120)

            # 2. Реакции
            if limits["reactions"] > 0:
                results["reactions"] = await self._do_reactions(account, limits["reactions"])
                await _jitter(30, 90)

            # Обновляем день и статус
            self.sm.update_account(account_id,
                warming_day=day,
                warming_phase=phase,
                status="warming" if day < 8 else "active",
                last_action_at=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:
            logger.error(f"[T2] {account.phone} warmup error: {e}")
            results["error"] = str(e)

        logger.info(f"[T2] {account.phone} done: {results}")
        return {"ok": True, **results}

    async def _do_views(self, account, target: int) -> int:
        """Открываем сообщения в каналах — имитируем просмотры."""
        if not self.client:
            logger.info(f"[T2] views simulated (no client): {target}")
            return target

        channels = (
            self.WARMUP_CHANNELS.get(account.vertical, []) +
            self.WARMUP_CHANNELS["neutral"]
        )
        random.shuffle(channels)
        viewed = 0

        for ch in channels[:5]:
            if viewed >= target:
                break
            try:
                msgs = await self.client.get_messages(ch, limit=5)
                await self.client.send_read_acknowledge(ch, msgs)
                viewed += len(msgs)
                logger.debug(f"[T2] viewed {len(msgs)} in {ch}")
                await _jitter(10, 30)
            except Exception as e:
                logger.warning(f"[T2] view error {ch}: {e}")

        self.sm.increment_daily(account.id, "views")
        return viewed

    async def _do_reactions(self, account, target: int) -> int:
        """Ставим реакции на посты в каналах."""
        if not self.client:
            logger.info(f"[T2] reactions simulated (no client): {target}")
            return target

        channels = self.WARMUP_CHANNELS.get(account.vertical, [])
        random.shuffle(channels)
        reacted = 0
        REACTIONS = ["👍", "❤️", "🔥", "👏", "😍"]

        for ch in channels[:3]:
            if reacted >= target:
                break
            try:
                msgs = await self.client.get_messages(ch, limit=3)
                for msg in msgs:
                    if reacted >= target:
                        break
                    reaction = random.choice(REACTIONS)
                    await self.client.send_reaction(ch, msg.id, reaction)
                    reacted += 1
                    daily = self.sm.increment_daily(account.id, "reactions")
                    if daily > 15:
                        logger.info(f"[T2] daily reaction limit hit for {account.phone}")
                        return reacted
                    await _jitter(15, 45)
            except Exception as e:
                logger.warning(f"[T2] reaction error {ch}: {e}")

        return reacted
