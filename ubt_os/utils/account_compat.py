"""
ubt_os/utils/account_compat.py

FIX #5: несоответствие id vs account_id между таблицей `accounts`
(deploy/01_schema_sot.sql — первичный ключ называется `id`, см. строка 11)
и Risk Engine (ubt_os/core/risk_engine.py), который читал acc["account_id"]
и падал с KeyError при работе со строками из accounts.

get_account_id() — безопасно достаёт идентификатор аккаунта независимо
от того, какой ключ присутствует в словаре (id или account_id).

normalize_account() — добавляет ОБА ключа в словарь, чтобы его можно было
безопасно передавать между агентами/таблицами, где исторически
использовались разные имена колонки.
"""

from __future__ import annotations


def get_account_id(acc: dict) -> str:
    """Возвращает идентификатор аккаунта, принимая оба варианта ключа."""
    account_id = acc.get("account_id") or acc.get("id")
    if account_id is None:
        raise KeyError(
            "Запись аккаунта не содержит ни 'id', ни 'account_id': "
            f"{list(acc.keys())}"
        )
    return account_id


def normalize_account(acc: dict) -> dict:
    """Возвращает копию acc с гарантированными ключами id и account_id."""
    account_id = get_account_id(acc)
    normalized = dict(acc)
    normalized["id"] = account_id
    normalized["account_id"] = account_id
    return normalized
