"""
FIX #6: LiteLLM Budget Guard — защита от бесконечных циклов
============================================================
Дополнение к litellm_config.yaml:
- Программная проверка бюджета перед каждым вызовом
- Лимит итераций в цепочках агентов
- Алерт при приближении к лимиту
"""

from __future__ import annotations
import logging
import os
from typing import Optional
import httpx

logger = logging.getLogger("litellm.budget_guard")

DAILY_BUDGET_USD   = float(os.getenv("LITELLM_DAILY_BUDGET", "20.0"))
ALERT_THRESHOLD    = 0.80   # алерт при 80% использования
MAX_CHAIN_DEPTH    = 10     # максимум итераций в одной цепочке агентов


class BudgetGuard:
    """
    Проверяет использование бюджета перед вызовом агента.
    Останавливает цепочку если превышен лимит итераций.
    """

    def __init__(self, litellm_base_url: str, master_key: str):
        self.base_url   = litellm_base_url.rstrip("/")
        self.master_key = master_key
        self._headers   = {"Authorization": f"Bearer {master_key}"}

    async def get_usage_today(self) -> dict:
        """Получает текущий расход бюджета из LiteLLM."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/spend/logs",
                headers=self._headers,
                params={"start_date": "today"}
            )
            resp.raise_for_status()
            data = resp.json()
            total_spent = sum(item.get("spend", 0) for item in data)
            return {
                "spent_usd":    round(total_spent, 4),
                "budget_usd":   DAILY_BUDGET_USD,
                "remaining":    round(DAILY_BUDGET_USD - total_spent, 4),
                "percent_used": round(total_spent / DAILY_BUDGET_USD * 100, 1),
            }

    async def check_before_call(
        self,
        agent_name: str,
        estimated_tokens: int = 1000,
        chain_depth: int = 0,
    ) -> bool:
        """
        Проверяет можно ли делать вызов.
        Возвращает True = ок, False = заблокировано.
        """
        # 1. Проверка глубины цепочки
        if chain_depth >= MAX_CHAIN_DEPTH:
            logger.error(
                f"[BudgetGuard] {agent_name}: превышена глубина цепочки "
                f"({chain_depth}/{MAX_CHAIN_DEPTH}). Вызов заблокирован."
            )
            await _send_alert(
                f"🔴 ЦИКЛ АГЕНТОВ ОСТАНОВЛЕН\n"
                f"Агент: {agent_name}\n"
                f"Глубина: {chain_depth}/{MAX_CHAIN_DEPTH}\n"
                f"Возможный бесконечный цикл. Проверь логи."
            )
            return False

        # 2. Проверка бюджета
        try:
            usage = await self.get_usage_today()
        except Exception as e:
            logger.warning(f"[BudgetGuard] Не удалось проверить бюджет: {e}. Разрешаем.")
            return True

        # Алерт при 80%
        if usage["percent_used"] >= ALERT_THRESHOLD * 100:
            await _send_alert(
                f"⚠️ БЮДЖЕТ CLAUDE API: {usage['percent_used']}%\n"
                f"Потрачено: ${usage['spent_usd']:.2f} / ${usage['budget_usd']:.2f}\n"
                f"Осталось: ${usage['remaining']:.2f}"
            )

        # Блокировка при 100%
        if usage["remaining"] <= 0:
            logger.error(
                f"[BudgetGuard] {agent_name}: дневной бюджет исчерпан. "
                f"Потрачено ${usage['spent_usd']:.2f}"
            )
            await _send_alert(
                f"🚫 БЮДЖЕТ ИСЧЕРПАН — АГЕНТЫ ОСТАНОВЛЕНЫ\n"
                f"Потрачено: ${usage['spent_usd']:.2f} / ${usage['budget_usd']:.2f}\n"
                f"Сброс в полночь UTC."
            )
            return False

        logger.debug(
            f"[BudgetGuard] {agent_name}: ок "
            f"(использовано {usage['percent_used']}%, "
            f"осталось ${usage['remaining']:.2f})"
        )
        return True


async def _send_alert(text: str):
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


# ── Декоратор для агентных функций ──────────────────────

def budget_guarded(agent_name: str):
    """
    Декоратор: оборачивает вызов агента проверкой бюджета.
    
    @budget_guarded("CONTENT_CREATOR")
    async def content_creator(prompt: str, chain_depth: int = 0) -> str:
        ...
    """
    def decorator(fn):
        async def wrapper(*args, chain_depth: int = 0, **kwargs):
            guard = BudgetGuard(
                litellm_base_url=os.environ["LITELLM_BASE_URL"],
                master_key=os.environ["LITELLM_MASTER_KEY"],
            )
            allowed = await guard.check_before_call(
                agent_name=agent_name,
                chain_depth=chain_depth,
            )
            if not allowed:
                raise BudgetExceededError(
                    f"Агент {agent_name} заблокирован: бюджет или лимит итераций"
                )
            return await fn(*args, chain_depth=chain_depth, **kwargs)
        return wrapper
    return decorator


class BudgetExceededError(Exception):
    """Вызов агента заблокирован из-за бюджета или глубины цепочки."""
