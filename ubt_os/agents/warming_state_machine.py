"""
FIX #4: Прогрев аккаунтов — State Machine
==========================================
Проблема: нет формальной state machine — после рестарта сервера
система не знает, на каком дне прогрева аккаунт.

Решение: полная FSM с персистентностью в Supabase.
Правило прогрева:
  Дни 1-3  → views_only      (только просмотры, 0 постов)
  Дни 4-5  → neutral_content (2 нейтральных видео без CTA)
  Дни 6-7  → niche_content   (2 нишевых видео без ссылок)
  День 8+  → monetization    (CTA + партнёрские ссылки)
"""

from __future__ import annotations
import logging
import os
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("warming.state_machine")


# ══════════════════════════════════════════════════════════
# 1. СОСТОЯНИЯ И ПЕРЕХОДЫ
# ══════════════════════════════════════════════════════════

class WarmingPhase(str, Enum):
    IDLE             = "idle"             # новый аккаунт, ещё не начат прогрев
    VIEWS_ONLY       = "views_only"       # дни 1-3: только смотрим, не постим
    NEUTRAL_CONTENT  = "neutral_content"  # дни 4-5: нейтральный контент
    NICHE_CONTENT    = "niche_content"    # дни 6-7: нишевый контент без CTA
    MONETIZATION     = "monetization"     # день 8+: полноценная монетизация

class AccountStatus(str, Enum):
    NEW          = "new"
    WARMING      = "warming"
    ACTIVE       = "active"
    SHADOW_BANNED = "shadow_banned"
    HARD_BANNED  = "hard_banned"
    REPLACED     = "replaced"
    PAUSED       = "paused"


# Допустимые переходы: из какого → в какое состояние
VALID_TRANSITIONS: dict[AccountStatus, list[AccountStatus]] = {
    AccountStatus.NEW:          [AccountStatus.WARMING],
    AccountStatus.WARMING:      [AccountStatus.ACTIVE, AccountStatus.SHADOW_BANNED, AccountStatus.PAUSED],
    AccountStatus.ACTIVE:       [AccountStatus.SHADOW_BANNED, AccountStatus.HARD_BANNED, AccountStatus.PAUSED],
    AccountStatus.SHADOW_BANNED:[AccountStatus.REPLACED, AccountStatus.ACTIVE],
    AccountStatus.HARD_BANNED:  [AccountStatus.REPLACED],
    AccountStatus.PAUSED:       [AccountStatus.WARMING, AccountStatus.ACTIVE],
    AccountStatus.REPLACED:     [],
}

# Фаза по дню прогрева
PHASE_BY_DAY: list[tuple[int, int, WarmingPhase]] = [
    (1, 3, WarmingPhase.VIEWS_ONLY),
    (4, 5, WarmingPhase.NEUTRAL_CONTENT),
    (6, 7, WarmingPhase.NICHE_CONTENT),
    (8, 9999, WarmingPhase.MONETIZATION),
]

# Допустимые действия по фазе
ALLOWED_ACTIONS: dict[WarmingPhase, list[str]] = {
    WarmingPhase.IDLE:            [],
    WarmingPhase.VIEWS_ONLY:      ["view", "like"],
    WarmingPhase.NEUTRAL_CONTENT: ["view", "like", "post_neutral", "follow"],
    WarmingPhase.NICHE_CONTENT:   ["view", "like", "post_niche", "follow", "comment"],
    WarmingPhase.MONETIZATION:    ["view", "like", "post_cta", "follow", "comment", "react", "story"],
}

# Дневной лимит постов по фазе
DAILY_POST_LIMIT: dict[WarmingPhase, int] = {
    WarmingPhase.IDLE:            0,
    WarmingPhase.VIEWS_ONLY:      0,
    WarmingPhase.NEUTRAL_CONTENT: 2,
    WarmingPhase.NICHE_CONTENT:   2,
    WarmingPhase.MONETIZATION:    5,
}


# ══════════════════════════════════════════════════════════
# 2. STATE MACHINE
# ══════════════════════════════════════════════════════════

@dataclass
class AccountWarmingState:
    account_id:       str
    status:           AccountStatus
    warming_day:      int
    warming_phase:    WarmingPhase
    warming_started:  Optional[datetime]
    last_action:      Optional[datetime]


class WarmingStateMachine:
    """
    Управляет переходами состояний прогрева.
    Все изменения персистируются в Supabase.
    """

    def __init__(self, db_client):
        self.db = db_client

    def get_phase_for_day(self, day: int) -> WarmingPhase:
        if day <= 0:
            return WarmingPhase.IDLE
        for start, end, phase in PHASE_BY_DAY:
            if start <= day <= end:
                return phase
        return WarmingPhase.MONETIZATION

    def can_transition(self, current: AccountStatus, target: AccountStatus) -> bool:
        return target in VALID_TRANSITIONS.get(current, [])

    def get_state(self, account_id: str) -> AccountWarmingState:
        """Загружает текущее состояние из БД."""
        row = (
            self.db.table("accounts")
            .select("id,status,warming_day,warming_phase,warming_started_at,last_action_at")
            .eq("id", account_id)
            .single()
            .execute()
            .data
        )
        return AccountWarmingState(
            account_id=      row["id"],
            status=          AccountStatus(row["status"]),
            warming_day=     row["warming_day"] or 0,
            warming_phase=   WarmingPhase(row["warming_phase"] or "idle"),
            warming_started= row.get("warming_started_at"),
            last_action=     row.get("last_action_at"),
        )

    def start_warming(self, account_id: str) -> AccountWarmingState:
        """Переводит NEW аккаунт в WARMING, день 1."""
        state = self.get_state(account_id)
        if not self.can_transition(state.status, AccountStatus.WARMING):
            raise InvalidTransition(
                f"Аккаунт {account_id}: нельзя перейти "
                f"{state.status} → {AccountStatus.WARMING}"
            )
        now = datetime.now(timezone.utc)
        self.db.table("accounts").update({
            "status":             AccountStatus.WARMING.value,
            "warming_day":        1,
            "warming_phase":      WarmingPhase.VIEWS_ONLY.value,
            "warming_started_at": now.isoformat(),
            "last_action_at":     now.isoformat(),
        }).eq("id", account_id).execute()
        logger.info(f"[Warming] {account_id}: STARTED день 1 → {WarmingPhase.VIEWS_ONLY}")
        return self.get_state(account_id)

    def advance_day(self, account_id: str) -> AccountWarmingState:
        """
        Увеличивает день прогрева на 1.
        Вызывается ежедневно cron-ом (n8n account-checker).
        """
        state = self.get_state(account_id)
        if state.status != AccountStatus.WARMING:
            raise InvalidTransition(
                f"Аккаунт {account_id} не в статусе WARMING (текущий: {state.status})"
            )
        new_day   = state.warming_day + 1
        new_phase = self.get_phase_for_day(new_day)
        now       = datetime.now(timezone.utc)

        update_payload = {
            "warming_day":    new_day,
            "warming_phase":  new_phase.value,
            "last_action_at": now.isoformat(),
        }

        # День 8+ → переводим в ACTIVE
        if new_day >= 8:
            update_payload["status"] = AccountStatus.ACTIVE.value
            logger.info(f"[Warming] {account_id}: день {new_day} → ACTIVE ✅")
        else:
            logger.info(f"[Warming] {account_id}: день {new_day} → {new_phase}")

        self.db.table("accounts").update(update_payload).eq("id", account_id).execute()
        return self.get_state(account_id)

    def mark_shadow_banned(self, account_id: str, reason: str) -> AccountWarmingState:
        state = self.get_state(account_id)
        if not self.can_transition(state.status, AccountStatus.SHADOW_BANNED):
            raise InvalidTransition(f"{account_id}: нельзя → SHADOW_BANNED из {state.status}")
        now = datetime.now(timezone.utc)
        self.db.table("accounts").update({
            "status":         AccountStatus.SHADOW_BANNED.value,
            "last_action_at": now.isoformat(),
        }).eq("id", account_id).execute()
        # Записываем причину в knowledge base
        self._log_ban_reason(account_id, "shadow_ban", reason)
        logger.warning(f"[Warming] {account_id}: SHADOW BANNED. Причина: {reason}")
        return self.get_state(account_id)

    def can_post(self, account_id: str) -> bool:
        """Проверяет, можно ли публиковать на аккаунте."""
        state = self.get_state(account_id)
        if state.status not in (AccountStatus.WARMING, AccountStatus.ACTIVE):
            return False
        allowed = ALLOWED_ACTIONS.get(state.warming_phase, [])
        return any(a.startswith("post") for a in allowed)

    def can_use_cta(self, account_id: str) -> bool:
        """Проверяет, можно ли использовать CTA/партнёрские ссылки."""
        state = self.get_state(account_id)
        return (
            state.status == AccountStatus.ACTIVE and
            state.warming_phase == WarmingPhase.MONETIZATION
        )

    def get_daily_post_limit(self, account_id: str) -> int:
        state = self.get_state(account_id)
        return DAILY_POST_LIMIT.get(state.warming_phase, 0)

    def _log_ban_reason(self, account_id: str, ban_type: str, reason: str):
        """Сохраняет причину бана для Knowledge Base."""
        try:
            self.db.table("ban_log").insert({
                "account_id": account_id,
                "ban_type":   ban_type,
                "reason":     reason,
                "logged_at":  datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as e:
            logger.error(f"Не удалось записать в ban_log: {e}")


# ══════════════════════════════════════════════════════════
# 3. N8N DAILY CRON — продвижение дня прогрева
# ══════════════════════════════════════════════════════════

DAILY_WARMING_CRON_CODE = """
// n8n Code Node: daily-warming-advance
// Cron: 0 9 * * * (каждый день в 09:00)

const { data: warmingAccounts } = await supabase
  .from('accounts')
  .select('id, warming_day, warming_phase, warming_started_at')
  .eq('status', 'warming');

const results = [];

for (const account of warmingAccounts) {
  const newDay = account.warming_day + 1;
  
  // Определяем фазу
  let newPhase;
  if (newDay <= 3)      newPhase = 'views_only';
  else if (newDay <= 5) newPhase = 'neutral_content';
  else if (newDay <= 7) newPhase = 'niche_content';
  else                  newPhase = 'monetization';
  
  const update = { warming_day: newDay, warming_phase: newPhase };
  
  // День 8 → переводим в active
  if (newDay >= 8) {
    update.status = 'active';
  }
  
  await supabase.from('accounts').update(update).eq('id', account.id);
  results.push({ id: account.id, day: newDay, phase: newPhase });
}

return results.map(r => ({ json: r }));
"""


# ══════════════════════════════════════════════════════════
# 4. КАСТОМНЫЕ ИСКЛЮЧЕНИЯ
# ══════════════════════════════════════════════════════════

class InvalidTransition(Exception):
    """Недопустимый переход состояния."""
