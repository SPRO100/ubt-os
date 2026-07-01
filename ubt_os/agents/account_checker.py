"""
FIX #5: Чекер аккаунтов — пороги по фазе прогрева
===================================================
Проблема: чекер применяет ER < 2% для ВСЕХ аккаунтов,
включая новые в прогреве, где низкий ER — норма.
Результат: ложные тревоги, лишние замены аккаунтов.

Решение: разные пороги по фазе + возрасту аккаунта.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("account.checker")


# ══════════════════════════════════════════════════════════
# 1. ПОРОГИ ПО ФАЗЕ
# ══════════════════════════════════════════════════════════

# Структура: фаза → {метрика: (warning_threshold, stop_threshold)}
# None = не проверять эту метрику в данной фазе
THRESHOLDS: dict[str, dict[str, tuple | None]] = {

    "idle": {
        "er":             None,     # не постим, ER не имеет смысла
        "new_followers":  None,
        "proxy_ping_ms":  (500, 2000),
    },

    "views_only": {
        "er":             None,     # не постим → ER не применим
        "new_followers":  None,
        "proxy_ping_ms":  (500, 2000),
    },

    "neutral_content": {
        "er":             (0.3, 0.1),   # очень мягкий порог
        "new_followers":  (0, 0),       # не требуем роста
        "proxy_ping_ms":  (500, 2000),
    },

    "niche_content": {
        "er":             (0.5, 0.2),   # чуть строже
        "new_followers":  (0, 0),
        "proxy_ping_ms":  (500, 2000),
    },

    "monetization": {
        "er":             (2.0, 1.0),   # стандартный порог
        "new_followers":  (1, 0),       # хотим хоть 1 новый/нед
        "proxy_ping_ms":  (500, 2000),
    },
}

# Отдельно: порог ER для established аккаунтов (день 15+)
ESTABLISHED_THRESHOLDS = {
    "er":            (3.0, 1.5),   # ожидаем выше нормы
    "proxy_ping_ms": (300, 1000),
}


# ══════════════════════════════════════════════════════════
# 2. CHECKER КЛАСС
# ══════════════════════════════════════════════════════════

class AccountChecker:
    """
    Проверяет здоровье аккаунта.
    Учитывает фазу прогрева при выборе порогов.
    """

    def __init__(self, db_client, telegram_alert_fn=None):
        self.db       = db_client
        self.alert_fn = telegram_alert_fn

    async def check_all(self) -> list[dict]:
        """Проверяет все active + warming аккаунты."""
        accounts = (
            self.db.table("accounts")
            .select("*")
            .in_("status", ["warming", "active"])
            .execute()
            .data
        )
        results = []
        for acc in accounts:
            result = await self.check_one(acc)
            results.append(result)
        return results

    async def check_one(self, account: dict) -> dict:
        """
        Проверяет один аккаунт.
        Возвращает: {account_id, phase, checks: [...], verdict: ok|warn|stop}
        """
        account_id = account["id"]
        phase      = account.get("warming_phase", "idle")
        warming_day = account.get("warming_day", 0)
        established = warming_day >= 15

        # Выбираем пороги
        thresholds = (
            ESTABLISHED_THRESHOLDS
            if established and account["status"] == "active"
            else THRESHOLDS.get(phase, THRESHOLDS["monetization"])
        )

        checks = []
        verdict = "ok"

        # ─── Проверка ER ───────────────────────────────
        er_threshold = thresholds.get("er")
        if er_threshold is not None:
            er = account.get("er_7d")
            if er is not None:
                warn_t, stop_t = er_threshold
                if er < stop_t:
                    checks.append({
                        "metric": "er",
                        "value":  er,
                        "status": "STOP",
                        "message": f"ER {er:.1f}% < стоп-порог {stop_t:.1f}% для фазы {phase}",
                    })
                    verdict = "stop"
                    await self._handle_stop(account, f"ER {er:.1f}% слишком низкий")
                elif er < warn_t:
                    checks.append({
                        "metric": "er",
                        "value":  er,
                        "status": "WARN",
                        "message": f"ER {er:.1f}% < предупреждение {warn_t:.1f}% для фазы {phase}",
                    })
                    if verdict == "ok":
                        verdict = "warn"
                    await self._handle_warn(account, f"ER {er:.1f}% приближается к минимуму")
                else:
                    checks.append({
                        "metric": "er",
                        "value":  er,
                        "status": "OK",
                        "message": f"ER {er:.1f}% ✅",
                    })
            else:
                checks.append({
                    "metric": "er",
                    "value":  None,
                    "status": "SKIP",
                    "message": "ER не рассчитан (нет данных)",
                })

        # ─── Проверка прокси ──────────────────────────
        proxy_threshold = thresholds.get("proxy_ping_ms")
        if proxy_threshold and account.get("proxy_id"):
            ping = await self._check_proxy(account["proxy_id"])
            warn_t, stop_t = proxy_threshold
            if ping is None or ping > stop_t:
                checks.append({
                    "metric": "proxy",
                    "value":  ping,
                    "status": "STOP",
                    "message": f"Прокси недоступен или ping {ping}ms > {stop_t}ms",
                })
                verdict = "stop"
            elif ping > warn_t:
                checks.append({
                    "metric": "proxy",
                    "value":  ping,
                    "status": "WARN",
                    "message": f"Прокси медленный: {ping}ms > {warn_t}ms",
                })
                if verdict == "ok":
                    verdict = "warn"
            else:
                checks.append({
                    "metric": "proxy",
                    "value":  ping,
                    "status": "OK",
                    "message": f"Прокси OK: {ping}ms ✅",
                })

        # ─── Проверка теневого бана ───────────────────
        if phase == "monetization":
            shadow_check = await self._check_shadow_ban(account)
            checks.append(shadow_check)
            if shadow_check["status"] == "STOP":
                verdict = "stop"

        logger.info(
            f"[Checker] {account_id} ({phase}, день {warming_day}): "
            f"verdict={verdict}, checks={len(checks)}"
        )

        return {
            "account_id":  account_id,
            "platform":    account.get("platform"),
            "phase":       phase,
            "warming_day": warming_day,
            "checks":      checks,
            "verdict":     verdict,
            "checked_at":  datetime.now(timezone.utc).isoformat(),
        }

    async def _handle_stop(self, account: dict, reason: str):
        """Останавливает аккаунт и уведомляет."""
        self.db.table("accounts").update({
            "status": "shadow_banned",
        }).eq("id", account["id"]).execute()

        msg = (
            f"🛑 АККАУНТ ОСТАНОВЛЕН\n"
            f"ID: {account['id'][:8]}...\n"
            f"Платформа: {account.get('platform')}\n"
            f"Фаза: {account.get('warming_phase')}, день {account.get('warming_day')}\n"
            f"Причина: {reason}\n"
            f"Действие: аккаунт переведён в shadow_banned, смени прокси"
        )
        if self.alert_fn:
            await self.alert_fn(msg)

    async def _handle_warn(self, account: dict, reason: str):
        """Отправляет предупреждение (аккаунт продолжает работу)."""
        msg = (
            f"⚠️ ПРЕДУПРЕЖДЕНИЕ АККАУНТА\n"
            f"ID: {account['id'][:8]}...\n"
            f"Платформа: {account.get('platform')}\n"
            f"Причина: {reason}"
        )
        if self.alert_fn:
            await self.alert_fn(msg)

    async def _check_proxy(self, proxy_id: str) -> Optional[int]:
        """Пингует прокси, возвращает задержку в ms."""
        import httpx, time
        proxy_row = (
            self.db.table("proxies")
            .select("host,port,username,password,type")
            .eq("id", proxy_id)
            .single()
            .execute()
            .data
        )
        if not proxy_row:
            return None
        proxy_url = (
            f"http://{proxy_row['username']}:{proxy_row['password']}"
            f"@{proxy_row['host']}:{proxy_row['port']}"
            if proxy_row.get("username")
            else f"http://{proxy_row['host']}:{proxy_row['port']}"
        )
        try:
            start = time.monotonic()
            # httpx ≥ 0.28: аргумент proxies удалён, используется proxy
            async with httpx.AsyncClient(
                proxy=proxy_url,
                timeout=10
            ) as client:
                await client.get("https://api.ipify.org")
            ms = int((time.monotonic() - start) * 1000)
            # Обновляем last_ping в БД
            self.db.table("proxies").update({
                "last_ping_ms":    ms,
                "last_checked_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", proxy_id).execute()
            return ms
        except Exception:
            return None

    async def _check_shadow_ban(self, account: dict) -> dict:
        """
        Упрощённая проверка признаков теневого бана.
        Реальная логика зависит от платформы.
        """
        # Признаки теневого бана:
        # - ER резко упал >50% за последние 3 дня
        # - Новые подписчики = 0 при активных постах
        er_now  = account.get("er_7d") or 0
        # В реальной имплементации сравнивать с er_14d
        # Пока упрощённо:
        if er_now < 0.5 and account.get("last_post_at"):
            return {
                "metric":  "shadow_ban",
                "value":   er_now,
                "status":  "WARN",
                "message": f"Возможный теневой бан: ER={er_now:.1f}% при активных постах",
            }
        return {
            "metric":  "shadow_ban",
            "value":   er_now,
            "status":  "OK",
            "message": "Признаков теневого бана нет ✅",
        }
