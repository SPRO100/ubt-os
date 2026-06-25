"""
T1 — ACCOUNT_MANAGER: управление Telegram-сессиями.

Хранит сессии в Redis (ключ tg:session:{account_id}).
Состояние аккаунта пишется в Supabase таблицу tg_accounts.
"""
from __future__ import annotations
import os
import json
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger("ubt_os.telegram.session_manager")


@dataclass
class TgAccount:
    id: str
    phone: str
    api_id: int
    api_hash: str
    proxy: Optional[dict] = None        # {"host": ..., "port": ..., "type": "socks5"}
    warming_day: int = 0
    status: str = "idle"               # idle | warming | active | banned | flood_wait
    daily_comments: int = 0
    daily_reactions: int = 0
    last_action_at: Optional[str] = None
    vertical: str = "nutra"
    geo: str = "PL"


class TelegramSessionManager:
    """T1 — управление аккаунтами и сессиями."""

    SESSION_PREFIX = "tg:session:"
    STATE_PREFIX   = "tg:state:"

    def __init__(self, db_client, redis_client):
        self.db    = db_client
        self.redis = redis_client

    # ── Загрузка аккаунтов из Supabase ──────────────────────

    def load_accounts(self, status: str | None = None) -> list[TgAccount]:
        q = self.db.table("tg_accounts").select("*")
        if status:
            q = q.eq("status", status)
        rows = q.execute().data
        return [self._row_to_account(r) for r in rows]

    def get_account(self, account_id: str) -> TgAccount | None:
        r = self.db.table("tg_accounts").select("*").eq("id", account_id).maybe_single().execute()
        return self._row_to_account(r.data) if r.data else None

    def update_account(self, account_id: str, **kwargs) -> None:
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.db.table("tg_accounts").update(kwargs).eq("id", account_id).execute()
        logger.info(f"TG account {account_id} updated: {kwargs}")

    def set_banned(self, account_id: str, reason: str = "") -> None:
        self.update_account(account_id, status="banned", ban_reason=reason)
        self._clear_session(account_id)
        logger.warning(f"TG account {account_id} BANNED: {reason}")

    def set_flood_wait(self, account_id: str, seconds: int) -> None:
        self.update_account(account_id, status="flood_wait", flood_wait_until=seconds)

    # ── Сессии в Redis ───────────────────────────────────────

    def save_session(self, account_id: str, session_string: str) -> None:
        key = self.SESSION_PREFIX + account_id
        self.redis.set(key, session_string)
        logger.info(f"Session saved for {account_id}")

    def load_session(self, account_id: str) -> str | None:
        key = self.SESSION_PREFIX + account_id
        val = self.redis.get(key)
        return val.decode() if val else None

    def _clear_session(self, account_id: str) -> None:
        self.redis.delete(self.SESSION_PREFIX + account_id)

    # ── Счётчики дневных действий ────────────────────────────

    def increment_daily(self, account_id: str, action: str) -> int:
        """action: 'comments' | 'reactions' | 'views'. Возвращает новое значение."""
        from datetime import date
        key = f"tg:daily:{account_id}:{action}:{date.today().isoformat()}"
        val = self.redis.incr(key)
        self.redis.expire(key, 86400 * 2)
        return int(val)

    def get_daily(self, account_id: str, action: str) -> int:
        from datetime import date
        key = f"tg:daily:{account_id}:{action}:{date.today().isoformat()}"
        val = self.redis.get(key)
        return int(val) if val else 0

    def reset_daily_counters(self, account_id: str) -> None:
        from datetime import date
        for action in ("comments", "reactions", "views"):
            key = f"tg:daily:{account_id}:{action}:{date.today().isoformat()}"
            self.redis.delete(key)

    # ── Хелперы ──────────────────────────────────────────────

    @staticmethod
    def _row_to_account(r: dict) -> TgAccount:
        return TgAccount(
            id            = r["id"],
            phone         = r["phone"],
            api_id        = int(r.get("api_id", 0)),
            api_hash      = r.get("api_hash", ""),
            proxy         = r.get("proxy"),
            warming_day   = int(r.get("warming_day", 0)),
            status        = r.get("status", "idle"),
            daily_comments= int(r.get("daily_comments", 0)),
            daily_reactions=int(r.get("daily_reactions", 0)),
            last_action_at= r.get("last_action_at"),
            vertical      = r.get("vertical", "nutra"),
            geo           = r.get("geo", "PL"),
        )
