"""
Telethon клиент с поддержкой прокси и StringSession.
Сессия хранится в Redis, не на диске.
"""
from __future__ import annotations
import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger("ubt_os.telegram.client")


def build_client(account, session_string: str | None = None):
    """
    Создаёт Telethon AsyncTelegramClient для аккаунта.
    Возвращает (client, StringSession) — сессию нужно сохранить после авторизации.
    """
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        raise RuntimeError("telethon не установлен: pip install telethon")

    session = StringSession(session_string or "")

    proxy = None
    if account.proxy:
        import socks
        ptype = {"socks5": socks.SOCKS5, "socks4": socks.SOCKS4, "http": socks.HTTP}.get(
            account.proxy.get("type", "socks5"), socks.SOCKS5
        )
        proxy = (
            ptype,
            account.proxy["host"],
            int(account.proxy["port"]),
            True,
            account.proxy.get("user"),
            account.proxy.get("pass"),
        )

    client = TelegramClient(
        session,
        api_id=account.api_id,
        api_hash=account.api_hash,
        proxy=proxy,
        device_model="Samsung Galaxy S23",
        system_version="Android 14",
        app_version="10.3.2",
        lang_code="ru",
        system_lang_code="ru-RU",
    )
    return client


async def get_connected_client(account, session_manager):
    """Получает подключённый клиент. Сессия берётся из Redis."""
    session_string = session_manager.load_session(account.id)
    client = build_client(account, session_string)

    await client.connect()

    if not await client.is_user_authorized():
        raise RuntimeError(f"Account {account.phone} not authorized — need login first")

    # Сохраняем актуальную сессию обратно
    from telethon.sessions import StringSession
    session_manager.save_session(account.id, client.session.save())

    return client


async def login_send_code(account) -> dict:
    """
    Шаг 1 авторизации: отправить код на номер телефона.
    Возвращает phone_code_hash для шага 2.
    """
    client = build_client(account)
    await client.connect()

    result = await client.send_code_request(account.phone)
    logger.info(f"Code sent to {account.phone}")

    return {
        "ok": True,
        "phone_code_hash": result.phone_code_hash,
        "phone": account.phone,
    }


async def login_confirm_code(account, code: str, phone_code_hash: str, session_manager) -> dict:
    """
    Шаг 2 авторизации: подтвердить код и сохранить сессию.
    """
    client = build_client(account)
    await client.connect()

    try:
        await client.sign_in(account.phone, code, phone_code_hash=phone_code_hash)
    except Exception as e:
        if "2FA" in str(e) or "password" in str(e).lower():
            return {"ok": False, "error": "2fa_required", "detail": str(e)}
        raise

    session_str = client.session.save()
    session_manager.save_session(account.id, session_str)

    await client.disconnect()
    logger.info(f"Account {account.phone} authorized and session saved")
    return {"ok": True, "phone": account.phone}


async def login_confirm_2fa(account, password: str, session_manager) -> dict:
    """
    Шаг 3 (если 2FA): подтвердить пароль.
    """
    client = build_client(account)
    await client.connect()

    await client.sign_in(password=password)

    session_str = client.session.save()
    session_manager.save_session(account.id, session_str)

    await client.disconnect()
    logger.info(f"Account {account.phone} 2FA confirmed")
    return {"ok": True, "phone": account.phone}
