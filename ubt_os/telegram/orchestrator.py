"""
Telegram Orchestrator — запускает T2/T3/T4 для всех активных аккаунтов.

Вызывается из main.py через роуты:
  POST /telegram/warmup      — T2 прогрев всех warming-аккаунтов
  POST /telegram/comment     — T3 комментарии (день 6+)
  POST /telegram/react       — T4 реакции
  POST /telegram/status      — статус всех tg_accounts
"""
from __future__ import annotations
import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger("ubt_os.telegram.orchestrator")

# Каналы по вертикали для T3/T4 (публичные, активные)
TARGET_CHANNELS = {
    "nutra": [
        "@zdorovye_secrets", "@dietadnia", "@fitnesspro_ru",
        "@hudeemvmeste", "@zdorovoe_pitanie_official",
    ],
    "betting": [
        "@stavki_sport", "@prognozy_football",
        "@sports_bets_free", "@football_bets_today",
    ],
}


def _get_redis():
    import redis as redis_lib
    return redis_lib.from_url(os.environ["REDIS_URL"], decode_responses=False)


def _get_db():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


async def _with_client(acc, sm, coro_fn):
    """Запускает coro_fn(client) с реальным Telethon клиентом если есть сессия, иначе None."""
    session = sm.load_session(acc.id)
    if not session:
        return await coro_fn(None)
    try:
        from ubt_os.telegram.client import get_connected_client
        client = await get_connected_client(acc, sm)
        try:
            return await coro_fn(client)
        finally:
            await client.disconnect()
    except Exception as e:
        logger.warning(f"[client] {acc.phone} connection error: {e} — falling back to simulate")
        return await coro_fn(None)


async def run_warmup(body: dict) -> dict:
    """T2 — прогрев всех warming/idle аккаунтов."""
    from ubt_os.telegram.session_manager import TelegramSessionManager
    from ubt_os.telegram.warmer import TelegramWarmer

    db    = _get_db()
    redis = _get_redis()
    sm    = TelegramSessionManager(db, redis)

    account_id = body.get("account_id")
    if account_id:
        accounts = [sm.get_account(account_id)] if sm.get_account(account_id) else []
    else:
        accounts = sm.load_accounts(status="warming") + sm.load_accounts(status="idle")

    if not accounts:
        return {"ok": True, "message": "нет аккаунтов для прогрева", "processed": 0}

    results = []
    for acc in accounts:
        async def do_warmup(client):
            warmer = TelegramWarmer(sm, tg_client=client)
            return await warmer.run_daily_warmup(acc.id)
        result = await _with_client(acc, sm, do_warmup)
        results.append({"account": acc.phone[-4:].rjust(len(acc.phone),"*"), **result})

    return {"ok": True, "processed": len(results), "results": results}


async def run_comment(body: dict) -> dict:
    """T3 — комментарии от всех аккаунтов день 6+."""
    from ubt_os.telegram.session_manager import TelegramSessionManager
    from ubt_os.telegram.commenter import TelegramCommenter

    db    = _get_db()
    redis = _get_redis()
    sm    = TelegramSessionManager(db, redis)

    accounts = sm.load_accounts(status="active") + sm.load_accounts(status="warming")
    accounts = [a for a in accounts if a.warming_day >= 6]

    if not accounts:
        return {"ok": True, "message": "нет аккаунтов для комментирования", "processed": 0}

    results = []
    for acc in accounts:
        channels = TARGET_CHANNELS.get(acc.vertical, [])
        async def do_comment(client):
            commenter = TelegramCommenter(sm, tg_client=client)
            return await commenter.run(acc.id, channels)
        result = await _with_client(acc, sm, do_comment)
        results.append({"account": acc.phone[-4:].rjust(len(acc.phone),"*"), **result})

    return {"ok": True, "processed": len(results), "results": results}


async def run_react(body: dict) -> dict:
    """T4 — реакции от всех аккаунтов."""
    from ubt_os.telegram.session_manager import TelegramSessionManager
    from ubt_os.telegram.reactor import TelegramReactor

    db    = _get_db()
    redis = _get_redis()
    sm    = TelegramSessionManager(db, redis)

    accounts = sm.load_accounts(status="active") + sm.load_accounts(status="warming")

    if not accounts:
        return {"ok": True, "message": "нет аккаунтов", "processed": 0}

    results = []
    for acc in accounts:
        channels = TARGET_CHANNELS.get(acc.vertical, [])
        async def do_react(client):
            reactor = TelegramReactor(sm, tg_client=client)
            return await reactor.run(acc.id, channels)
        result = await _with_client(acc, sm, do_react)
        results.append({"account": acc.phone[-4:].rjust(len(acc.phone),"*"), **result})

    return {"ok": True, "processed": len(results), "results": results}


async def get_status(body: dict) -> dict:
    """Статус всех tg_accounts из Supabase."""
    from ubt_os.telegram.session_manager import TelegramSessionManager

    db    = _get_db()
    redis = _get_redis()
    sm    = TelegramSessionManager(db, redis)
    accounts = sm.load_accounts()

    return {
        "ok": True,
        "total": len(accounts),
        "by_status": _count_by(accounts, "status"),
        "by_vertical": _count_by(accounts, "vertical"),
        "accounts": [
            {
                "id": a.id,
                "phone": a.phone[-4:].rjust(len(a.phone), "*"),  # маскируем
                "status": a.status,
                "warming_day": a.warming_day,
                "vertical": a.vertical,
                "geo": a.geo,
            }
            for a in accounts
        ],
    }


def _count_by(accounts, field: str) -> dict:
    result: dict = {}
    for a in accounts:
        val = getattr(a, field, "unknown")
        result[val] = result.get(val, 0) + 1
    return result
