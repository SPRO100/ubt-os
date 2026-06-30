"""
A28 — WARMUP_MANAGER
Трекер прогрева TikTok/Instagram аккаунтов.
14-дневный план для новых аккаунтов, 7-дневный для aged.
Валидирует GEO-инфраструктуру (device fingerprint, proxy type, SIM).
Блокирует публикацию через A26 если аккаунт не прошёл прогрев.
"""
from __future__ import annotations
import json, logging, os
from dataclasses import dataclass, asdict
from datetime import date
from enum import Enum
from pathlib import Path

logger = logging.getLogger("ubt_os.warmup_manager")

_STATE_FILE = Path(os.environ.get("WARMUP_STATE_FILE", str(Path.home() / ".ubt_os" / "warmup_state.json")))

# Лимиты активности по дням (new account, 14 days)
_DAILY_LIMITS_NEW = {
    1:  {"likes": 0,  "follows": 0,  "comments": 0, "posts": 0},
    2:  {"likes": 20, "follows": 0,  "comments": 0, "posts": 0},
    3:  {"likes": 30, "follows": 10, "comments": 2, "posts": 0},
    4:  {"likes": 30, "follows": 10, "comments": 2, "posts": 0},
    5:  {"likes": 40, "follows": 15, "comments": 5, "posts": 1},
    6:  {"likes": 40, "follows": 15, "comments": 5, "posts": 1},
    7:  {"likes": 40, "follows": 15, "comments": 5, "posts": 1},
    8:  {"likes": 50, "follows": 20, "comments": 10,"posts": 2},
    9:  {"likes": 50, "follows": 20, "comments": 10,"posts": 2},
    10: {"likes": 50, "follows": 20, "comments": 10,"posts": 3},
    11: {"likes": 50, "follows": 20, "comments": 10,"posts": 3},
    12: {"likes": 50, "follows": 20, "comments": 10,"posts": 3},
    13: {"likes": 50, "follows": 20, "comments": 10,"posts": 3},
    14: {"likes": 50, "follows": 20, "comments": 10,"posts": 3},
}

# Для aged аккаунтов (7 дней)
_DAILY_LIMITS_AGED = {
    1: {"likes": 20, "follows": 5,  "comments": 2, "posts": 0},
    2: {"likes": 30, "follows": 10, "comments": 5, "posts": 1},
    3: {"likes": 40, "follows": 15, "comments": 5, "posts": 2},
    4: {"likes": 50, "follows": 20, "comments": 10,"posts": 2},
    5: {"likes": 50, "follows": 20, "comments": 10,"posts": 3},
    6: {"likes": 50, "follows": 20, "comments": 10,"posts": 3},
    7: {"likes": 50, "follows": 20, "comments": 10,"posts": 3},
}

_CONTENT_SPLIT = {
    "new": {
        "days_1_7":  {"neutral": 100, "targeted": 0},
        "days_8_10": {"neutral": 80,  "targeted": 20},
        "days_11_14":{"neutral": 70,  "targeted": 30},
    },
    "aged": {
        "days_1_3":  {"neutral": 80,  "targeted": 20},
        "days_4_7":  {"neutral": 50,  "targeted": 50},
    },
}


class WarmupStatus(str, Enum):
    NOT_STARTED   = "not_started"
    WARMING_UP    = "warming_up"
    READY         = "ready"
    BLOCKED       = "blocked"
    PAUSED        = "paused"


class DeviceType(str, Enum):
    GLOBAL = "GLOBAL"
    US     = "US"
    RU     = "RU"
    CN     = "CN"
    OTHER  = "OTHER"


class ProxyType(str, Enum):
    MOBILE      = "mobile"
    RESIDENTIAL = "residential"
    DATACENTER  = "datacenter"
    VPN         = "vpn"
    NONE        = "none"


@dataclass
class InfraIssue:
    severity: str   # critical | warning
    field: str
    message: str
    fix: str


@dataclass
class AccountState:
    account_id: str
    geo: str
    account_type: str           # new | aged
    platform: str               # tiktok | instagram
    device_type: str            # GLOBAL | US | RU | CN
    proxy_type: str             # mobile | residential | datacenter | vpn
    has_local_sim: bool
    warmup_status: str
    start_date: str             # ISO date
    current_day: int
    total_days: int
    bio_link_enabled: bool
    notes: str


@dataclass
class WarmupCheckResult:
    account_id: str
    status: WarmupStatus
    current_day: int
    total_days: int
    progress_pct: float
    today_limits: dict
    content_split: dict
    bio_link_allowed: bool
    infra_issues: list[dict]   # сериализованные InfraIssue (asdict) — для JSON-ответа
    ready_to_publish: bool
    next_action: str
    message: str


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def _days_since(date_str: str) -> int:
    try:
        start = date.fromisoformat(date_str)
        return (date.today() - start).days + 1
    except Exception:
        return 1


def _validate_infra(device_type: str, proxy_type: str, has_local_sim: bool, geo: str) -> list[InfraIssue]:
    issues: list[InfraIssue] = []

    if device_type in (DeviceType.RU, DeviceType.CN):
        issues.append(InfraIssue(
            severity="critical",
            field="device_type",
            message=f"Device fingerprint '{device_type}' режет органику до публикации",
            fix="Замени на GLOBAL или US device. Рекомендован Dolphin Anty с GLOBAL fingerprint.",
        ))

    if proxy_type in (ProxyType.VPN, ProxyType.DATACENTER):
        issues.append(InfraIssue(
            severity="critical",
            field="proxy_type",
            message=f"'{proxy_type}' детектируется TikTok → моментальный бан или shadow ban",
            fix="Используй mobile (4G/5G) прокси — Nodemaven или MobileHQ. Один прокси на аккаунт.",
        ))

    if proxy_type == ProxyType.NONE:
        issues.append(InfraIssue(
            severity="critical",
            field="proxy_type",
            message="Нет прокси — аккаунт работает с твоим реальным IP",
            fix="Подключи мобильный US прокси (Nodemaven, MobileHQ).",
        ))

    if geo == "US" and not has_local_sim:
        issues.append(InfraIssue(
            severity="warning",
            field="has_local_sim",
            message="Нет US SIM-карты — алгоритм TikTok считает GEO аккаунта не-US",
            fix="Купи Airalo US eSIM ($5–15). SIM = GEO-сигнал #2 в алгоритме.",
        ))

    return issues


def _get_today_limits(account_type: str, day: int) -> dict:
    if account_type == "aged":
        limits_map = _DAILY_LIMITS_AGED
        day = min(day, 7)
    else:
        limits_map = _DAILY_LIMITS_NEW
        day = min(day, 14)
    return limits_map.get(day, limits_map[max(limits_map.keys())])


def _get_content_split(account_type: str, day: int) -> dict:
    if account_type == "aged":
        if day <= 3:
            return _CONTENT_SPLIT["aged"]["days_1_3"]
        return _CONTENT_SPLIT["aged"]["days_4_7"]
    else:
        if day <= 7:
            return _CONTENT_SPLIT["new"]["days_1_7"]
        elif day <= 10:
            return _CONTENT_SPLIT["new"]["days_8_10"]
        return _CONTENT_SPLIT["new"]["days_11_14"]


def _get_next_action(account_type: str, day: int, issues: list[InfraIssue]) -> str:
    if issues and any(i.severity == "critical" for i in issues):
        return f"Устрани критические проблемы инфраструктуры: {issues[0].fix}"
    total = 7 if account_type == "aged" else 14
    if day == 1:
        return "Скролли FYP 20–30 минут. Никаких лайков, подписок, комментариев сегодня."
    elif day <= 4:
        return "Лайкай похожий контент, подписывайся на аккаунты в нише. Не публикуй."
    elif day <= 6:
        return "Опубликуй первое НЕЙТРАЛЬНОЕ видео (не по офферу). Лайки, подписки, комменты в лимите."
    elif day == 7:
        return "Тест видео близкое к теме оффера, но без прямого CTA. Ссылку в bio НЕ ставить."
    elif day <= 10:
        return "Пости 2–3 раза в день. 80% нейтральный / 20% целевой контент."
    elif day < total:
        return "Финальная фаза: 70% нейтральный / 30% целевой. Ссылку в bio можно добавить."
    return "Прогрев завершён! Аккаунт готов к полноценной публикации через A26."


class WarmupManager:
    """Менеджер прогрева TikTok/Instagram аккаунтов."""

    def register(
        self,
        account_id: str,
        geo: str = "US",
        account_type: str = "new",
        platform: str = "tiktok",
        device_type: str = "GLOBAL",
        proxy_type: str = "mobile",
        has_local_sim: bool = False,
        notes: str = "",
    ) -> WarmupCheckResult:
        """Регистрирует новый аккаунт для прогрева."""
        state = _load_state()
        total_days = 7 if account_type == "aged" else 14
        state[account_id] = {
            "account_id": account_id,
            "geo": geo,
            "account_type": account_type,
            "platform": platform,
            "device_type": device_type,
            "proxy_type": proxy_type,
            "has_local_sim": has_local_sim,
            "warmup_status": WarmupStatus.WARMING_UP,
            "start_date": date.today().isoformat(),
            "current_day": 1,
            "total_days": total_days,
            "bio_link_enabled": False,
            "notes": notes,
        }
        _save_state(state)
        logger.info(f"Аккаунт {account_id} зарегистрирован для {total_days}-дневного прогрева")
        return self.check(account_id)

    def check(self, account_id: str) -> WarmupCheckResult:
        """Возвращает текущее состояние и рекомендации для аккаунта."""
        state = _load_state()
        if account_id not in state:
            return WarmupCheckResult(
                account_id=account_id,
                status=WarmupStatus.NOT_STARTED,
                current_day=0, total_days=14, progress_pct=0.0,
                today_limits={}, content_split={},
                bio_link_allowed=False,
                infra_issues=[],
                ready_to_publish=False,
                next_action="Зарегистрируй аккаунт через warmup_manager.register()",
                message=f"Аккаунт {account_id} не найден в системе прогрева.",
            )

        acc = state[account_id]
        current_day = _days_since(acc["start_date"])
        total_days = acc["total_days"]

        # Обновляем текущий день
        acc["current_day"] = current_day
        state[account_id] = acc
        _save_state(state)

        infra_issues = _validate_infra(
            acc["device_type"], acc["proxy_type"],
            acc["has_local_sim"], acc["geo"]
        )

        is_ready = (
            current_day > total_days
            and not any(i.severity == "critical" for i in infra_issues)
        )
        bio_allowed = current_day >= 10 or (acc.get("bio_link_enabled", False))

        if is_ready:
            status = WarmupStatus.READY
        elif any(i.severity == "critical" for i in infra_issues):
            status = WarmupStatus.BLOCKED
        else:
            status = WarmupStatus.WARMING_UP

        acc["warmup_status"] = status
        state[account_id] = acc
        _save_state(state)

        today_limits = _get_today_limits(acc["account_type"], current_day)
        content_split = _get_content_split(acc["account_type"], current_day)
        next_action = _get_next_action(acc["account_type"], current_day, infra_issues)

        effective_day = min(current_day, total_days)
        progress_pct = round((effective_day / total_days) * 100, 1)

        message = (
            f"День {current_day}/{total_days} прогрева. "
            f"Статус: {status}. "
            + (f"Найдено {len(infra_issues)} проблем инфраструктуры." if infra_issues else "Инфраструктура OK.")
        )

        return WarmupCheckResult(
            account_id=account_id,
            status=status,
            current_day=current_day,
            total_days=total_days,
            progress_pct=progress_pct,
            today_limits=today_limits,
            content_split=content_split,
            bio_link_allowed=bio_allowed,
            infra_issues=[asdict(i) for i in infra_issues],
            ready_to_publish=is_ready,
            next_action=next_action,
            message=message,
        )

    def list_accounts(self) -> list[dict]:
        """Возвращает список всех аккаунтов с их статусами."""
        state = _load_state()
        results = []
        for account_id in state:
            r = self.check(account_id)
            results.append({
                "account_id": account_id,
                "status": r.status,
                "day": r.current_day,
                "total": r.total_days,
                "progress": r.progress_pct,
                "geo": state[account_id]["geo"],
                "ready": r.ready_to_publish,
                "issues": len(r.infra_issues),
            })
        return results

    def enable_bio_link(self, account_id: str) -> dict:
        """Разрешает ссылку в bio для аккаунта."""
        state = _load_state()
        if account_id not in state:
            return {"success": False, "message": "Аккаунт не найден"}
        r = self.check(account_id)
        if not r.bio_link_allowed:
            return {
                "success": False,
                "message": f"Слишком рано. День {r.current_day} из {r.total_days}. Ждать до дня 10+.",
            }
        state[account_id]["bio_link_enabled"] = True
        _save_state(state)
        return {"success": True, "message": f"Ссылка в bio разрешена для {account_id}"}

    def reset(self, account_id: str) -> dict:
        """Сбрасывает прогрев аккаунта (например, после длительного перерыва)."""
        state = _load_state()
        if account_id not in state:
            return {"success": False, "message": "Аккаунт не найден"}
        state[account_id]["start_date"] = date.today().isoformat()
        state[account_id]["warmup_status"] = WarmupStatus.WARMING_UP
        state[account_id]["bio_link_enabled"] = False
        _save_state(state)
        return {"success": True, "message": f"Прогрев {account_id} сброшен. Начат заново."}

    def validate_infra(
        self,
        account_id: str,
        device_type: str,
        proxy_type: str,
        has_local_sim: bool,
        geo: str = "US",
    ) -> dict:
        """Быстрая проверка GEO-инфраструктуры без регистрации."""
        issues = _validate_infra(device_type, proxy_type, has_local_sim, geo)
        return {
            "account_id": account_id,
            "geo": geo,
            "device_type": device_type,
            "proxy_type": proxy_type,
            "has_local_sim": has_local_sim,
            "issues": [asdict(i) for i in issues],
            "infra_ok": len(issues) == 0,
            "critical_count": sum(1 for i in issues if i.severity == "critical"),
            "warning_count": sum(1 for i in issues if i.severity == "warning"),
        }
