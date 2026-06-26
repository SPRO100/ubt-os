"""
RISK ENGINE — Централизованная система риск-скоринга аккаунтов.
5 компонентов → Risk Score 0-100 → автоматические действия.

Пороги:
  0-40  = safe    → нормальная работа
  41-70 = caution → снизить активность
  71-85 = high    → замедлить публикации
  86-100= stop    → остановить всю активность
"""
from __future__ import annotations
import asyncio, logging, os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import httpx
from supabase import create_client, Client

from ubt_os.utils.account_compat import get_account_id  # FIX #5: id vs account_id

logger = logging.getLogger("ubt_os.risk_engine")

# ── Пороги риска ──────────────────────────────────────────
THRESHOLDS = {
    "safe":    (0,   40),
    "caution": (41,  70),
    "high":    (71,  85),
    "stop":    (86, 100),
}

ACTIONS = {
    "safe":    None,
    "caution": "reduce_activity",    # -50% активности
    "high":    "slow_publishing",    # 1 пост/день макс
    "stop":    "pause_all",          # полная остановка
}


@dataclass
class RiskFactors:
    """Собранные данные для расчёта риска."""
    account_id:         str
    platform:           str
    geo:                str
    warming_phase:      str = "unknown"

    # Прокси
    proxy_ping_ms:      float = 0.0
    proxy_anonymity:    bool  = True
    proxy_geo_match:    bool  = True
    proxy_fail_count:   int   = 0         # сбоев за 24ч

    # Устройство
    fingerprint_stable: bool  = True      # fingerprint не менялся
    user_agent_consistent: bool = True
    session_age_days:   int   = 0

    # Поведение
    posts_per_day:      float = 0.0
    actions_per_hour:   float = 0.0
    inter_action_gap_min: float = 0.0     # мин пауза между действиями
    irregular_hours:    bool  = False     # активность в нерабочее время (3-6 утра)

    # Публикации
    publish_fail_count: int   = 0         # неудачных публикаций за 24ч
    duplicate_content:  bool  = False     # детектировано дублирование
    posting_interval_std: float = 0.0     # стандартное отклонение интервалов

    # Вовлечённость
    er_current:         float = 0.0
    er_baseline:        float = 0.0       # средний ER за 14 дней
    er_drop_pct:        float = 0.0       # % падения ER
    shadow_ban_detected: bool = False
    follower_drop_pct:  float = 0.0


class RiskScorer:
    """
    Пять компонентов риска, каждый 0-100.
    Итоговый score = взвешенная сумма.
    """

    # Веса компонентов
    WEIGHTS = {
        "proxy":      0.20,
        "device":     0.15,
        "behavior":   0.25,
        "publishing": 0.20,
        "engagement": 0.20,
    }

    def proxy_risk(self, f: RiskFactors) -> tuple[float, list[str]]:
        """Риск связанный с прокси-качеством."""
        score   = 0.0
        factors = []

        # Задержка прокси
        if f.proxy_ping_ms > 500:
            score += 40
            factors.append(f"proxy_slow: {f.proxy_ping_ms:.0f}ms > 500ms")
        elif f.proxy_ping_ms > 300:
            score += 20
            factors.append(f"proxy_laggy: {f.proxy_ping_ms:.0f}ms")

        # Анонимность
        if not f.proxy_anonymity:
            score += 30
            factors.append("proxy_not_anonymous: IP leak detected")

        # Гео-несоответствие
        if not f.proxy_geo_match:
            score += 25
            factors.append("proxy_geo_mismatch: proxy GEO ≠ account GEO")

        # Сбои
        if f.proxy_fail_count > 5:
            score += 20
            factors.append(f"proxy_unstable: {f.proxy_fail_count} fails/24h")
        elif f.proxy_fail_count > 2:
            score += 10

        return min(score, 100), factors

    def device_risk(self, f: RiskFactors) -> tuple[float, list[str]]:
        """Риск fingerprint нестабильности."""
        score   = 0.0
        factors = []

        if not f.fingerprint_stable:
            score += 50
            factors.append("fingerprint_changed: высокий риск детекции")

        if not f.user_agent_consistent:
            score += 25
            factors.append("user_agent_inconsistent")

        if f.session_age_days < 7:
            score += 20
            factors.append(f"new_session: только {f.session_age_days} дней")
        elif f.session_age_days < 14:
            score += 10

        return min(score, 100), factors

    def behavior_risk(self, f: RiskFactors) -> tuple[float, list[str]]:
        """Риск ботоподобного поведения."""
        score   = 0.0
        factors = []

        # Слишком много постов
        if f.platform == "tiktok" and f.posts_per_day > 5:
            score += 30
            factors.append(f"posting_too_fast: {f.posts_per_day:.1f}/day (max 5)")
        elif f.posts_per_day > 10:
            score += 40
            factors.append(f"posting_excessive: {f.posts_per_day:.1f}/day")

        # Слишком много действий в час
        if f.actions_per_hour > 30:
            score += 35
            factors.append(f"action_spam: {f.actions_per_hour:.0f}/h (max 30)")

        # Слишком маленькие паузы
        if f.inter_action_gap_min < 2:
            score += 25
            factors.append(f"no_human_delay: {f.inter_action_gap_min:.1f}min gaps")

        # Нерабочие часы
        if f.irregular_hours:
            score += 15
            factors.append("active_at_3-6am: suspicious pattern")

        # Регулярные интервалы (машинный паттерн)
        if f.posting_interval_std < 5:  # интервалы слишком одинаковы (мин)
            score += 20
            factors.append("robotic_schedule: interval std < 5min")

        return min(score, 100), factors

    def publishing_risk(self, f: RiskFactors) -> tuple[float, list[str]]:
        """Риск связанный с публикациями."""
        score   = 0.0
        factors = []

        if f.publish_fail_count > 3:
            score += 40
            factors.append(f"publish_failures: {f.publish_fail_count}/24h")
        elif f.publish_fail_count > 1:
            score += 15

        if f.duplicate_content:
            score += 35
            factors.append("duplicate_content: platform может пессимизировать")

        # Публикация на непрогретом аккаунте
        if f.warming_phase in ("idle", "views_only") and f.posts_per_day > 0:
            score += 50
            factors.append(f"publishing_before_warmup: phase={f.warming_phase}")

        return min(score, 100), factors

    def engagement_risk(self, f: RiskFactors) -> tuple[float, list[str]]:
        """Риск на основе метрик вовлечённости."""
        score   = 0.0
        factors = []

        if f.shadow_ban_detected:
            score += 60
            factors.append("shadow_ban_detected: ER < 1% при baseline > 4%")

        if f.er_drop_pct > 70:
            score += 40
            factors.append(f"er_collapsed: -{f.er_drop_pct:.0f}% from baseline")
        elif f.er_drop_pct > 40:
            score += 20
            factors.append(f"er_drop: -{f.er_drop_pct:.0f}% from baseline")

        if f.follower_drop_pct > 10:
            score += 25
            factors.append(f"follower_loss: -{f.follower_drop_pct:.0f}%/day")

        return min(score, 100), factors

    def calculate(self, f: RiskFactors) -> dict:
        """Итоговый расчёт."""
        pr, pf  = self.proxy_risk(f)
        dr, df  = self.device_risk(f)
        br, bff = self.behavior_risk(f)
        pbr,pbf = self.publishing_risk(f)
        er, ef  = self.engagement_risk(f)

        composite = (
            pr  * self.WEIGHTS["proxy"]      +
            dr  * self.WEIGHTS["device"]     +
            br  * self.WEIGHTS["behavior"]   +
            pbr * self.WEIGHTS["publishing"] +
            er  * self.WEIGHTS["engagement"]
        )
        composite = round(min(composite, 100), 2)

        level  = "safe"
        for lvl, (lo, hi) in THRESHOLDS.items():
            if lo <= composite <= hi:
                level = lvl
                break

        all_factors = pf + df + bff + pbf + ef

        return {
            "account_id":        f.account_id,
            "platform":          f.platform,
            "geo":               f.geo,
            "warming_phase":     f.warming_phase,
            "proxy_risk":        round(pr, 2),
            "device_risk":       round(dr, 2),
            "behavior_risk":     round(br, 2),
            "publishing_risk":   round(pbr, 2),
            "engagement_risk":   round(er, 2),
            "risk_score":        composite,
            "risk_level":        level,
            "risk_factors":      all_factors,
            "recommended_action":ACTIONS[level],
        }


# ── Автоматические действия ───────────────────────────────
class RiskActionExecutor:

    def __init__(self, db: Client, n8n_url: str):
        self.db      = db
        self.n8n_url = n8n_url

    async def execute(self, result: dict, prev_score: float = 0):
        action = result["recommended_action"]
        level  = result["risk_level"]

        if action == "pause_all":
            await self._pause_account(result["account_id"])
            await self._alert(result, "🛑 СТОП")

        elif action == "slow_publishing":
            await self._slow_publishing(result["account_id"])
            await self._alert(result, "⚠️ ЗАМЕДЛЕНИЕ")

        elif action == "reduce_activity":
            await self._reduce_activity(result["account_id"])
            if result["risk_score"] - prev_score > 15:
                await self._alert(result, "🟡 ПОВЫШЕННЫЙ РИСК")

    async def _pause_account(self, account_id: str):
        resp = self.db.table("accounts").update({
            "publishing_enabled": False,
            "pause_reason": "risk_score_critical",
            "paused_at": datetime.utcnow().isoformat(),
        }).eq("account_id", account_id).execute()
        if not resp.data:
            logger.error(f"[Risk] _pause_account: UPDATE не затронул строк для {account_id}")
        else:
            logger.warning(f"[Risk] СТОП: {account_id} — публикации заблокированы")

    async def _slow_publishing(self, account_id: str):
        resp = self.db.table("accounts").update({
            "max_posts_per_day": 1,
            "throttle_reason": "risk_score_high",
        }).eq("account_id", account_id).execute()
        if not resp.data:
            logger.error(f"[Risk] _slow_publishing: UPDATE не затронул строк для {account_id}")
        else:
            logger.warning(f"[Risk] Замедление: {account_id} → max 1 пост/день")

    async def _reduce_activity(self, account_id: str):
        resp = self.db.table("accounts").update({
            "activity_multiplier": 0.5,
        }).eq("account_id", account_id).execute()
        if not resp.data:
            logger.error(f"[Risk] _reduce_activity: UPDATE не затронул строк для {account_id}")

    async def _alert(self, result: dict, prefix: str):
        token   = os.environ.get("TELEGRAM_ALERT_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_ALERT_CHAT_ID")
        if not token or not chat_id:
            return
        factors_text = "\n".join(f"  • {f}" for f in result["risk_factors"][:3])
        msg = (
            f"{prefix} *RISK ENGINE*\n"
            f"Аккаунт: `{result['account_id']}`\n"
            f"Платформа: {result['platform']} / {result['geo']}\n"
            f"Risk Score: *{result['risk_score']:.0f}/100* ({result['risk_level'].upper()})\n"
            f"Факторы:\n{factors_text}\n"
            f"Действие: `{result['recommended_action']}`"
        )
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=10,
            )


# ── Главный цикл ─────────────────────────────────────────
class RiskEngine:

    def __init__(self, db: Client):
        self.db       = db
        self.scorer   = RiskScorer()
        self.executor = RiskActionExecutor(
            db, os.environ.get("N8N_WEBHOOK_URL", "")
        )

    async def run_all(self):
        """Проверяет все активные аккаунты."""
        accounts = (
            self.db.table("accounts")
            .select("*")
            .neq("status", "banned")
            .execute()
        ).data

        logger.info(f"Risk Engine: проверяем {len(accounts)} аккаунтов")
        for acc in accounts:
            await self._check_account(acc)

    async def _check_account(self, acc: dict):
        factors = await self._collect_factors(acc)
        result  = self.scorer.calculate(factors)

        # Достаём предыдущий скор
        prev = (
            self.db.table("account_risk_profiles")
            .select("risk_score, consecutive_high")
            .eq("account_id", get_account_id(acc))
            .limit(1).execute()
        ).data
        prev_score  = prev[0]["risk_score"] if prev else 0
        consec_high = prev[0]["consecutive_high"] if prev else 0

        result["prev_risk_score"] = prev_score
        result["score_delta"]     = round(result["risk_score"] - prev_score, 2)
        result["consecutive_high"]= (
            consec_high + 1
            if result["risk_level"] in ("high","stop")
            else 0
        )

        # Сохраняем
        self.db.table("account_risk_profiles").upsert(
            result, on_conflict="account_id"
        ).execute()
        self.db.table("risk_score_history").insert({
            "account_id":   result["account_id"],
            "risk_score":   result["risk_score"],
            "risk_level":   result["risk_level"],
            "risk_factors": result["risk_factors"],
        }).execute()

        # Выполняем действие
        await self.executor.execute(result, prev_score)

    async def _collect_factors(self, acc: dict) -> RiskFactors:
        """Собирает все данные для расчёта риска из БД и внешних проверок."""
        analytics = (
            self.db.table("video_analytics")
            .select("completion_rate,er,views")
            .eq("account_id", get_account_id(acc))
            .gte("created_at", (datetime.utcnow() - timedelta(days=14)).isoformat())
            .execute()
        ).data

        er_values  = [a["er"] for a in analytics if a.get("er")]
        er_baseline= sum(er_values) / len(er_values) if er_values else 0
        er_current = er_values[-1] if er_values else 0
        er_drop    = ((er_baseline - er_current) / er_baseline * 100) if er_baseline else 0

        return RiskFactors(
            account_id        = get_account_id(acc),
            platform          = acc.get("platform", "tiktok"),
            geo               = acc.get("geo", "RU"),
            warming_phase     = acc.get("warming_phase", "unknown"),
            proxy_ping_ms     = float(acc.get("proxy_ping_ms", 100)),
            proxy_anonymity   = bool(acc.get("proxy_anonymous", True)),
            proxy_geo_match   = bool(acc.get("proxy_geo_match", True)),
            proxy_fail_count  = int(acc.get("proxy_fail_24h", 0)),
            fingerprint_stable= bool(acc.get("fingerprint_stable", True)),
            session_age_days  = int(acc.get("session_age_days", 30)),
            posts_per_day     = float(acc.get("posts_last_24h", 0)),
            actions_per_hour  = float(acc.get("actions_last_hour", 0)),
            inter_action_gap_min = float(acc.get("min_action_gap_min", 10)),
            irregular_hours   = bool(acc.get("active_irregular_hours", False)),
            posting_interval_std = float(acc.get("posting_interval_std_min", 30)),
            publish_fail_count= int(acc.get("publish_fail_24h", 0)),
            duplicate_content = bool(acc.get("duplicate_detected", False)),
            er_current        = er_current,
            er_baseline       = er_baseline,
            er_drop_pct       = max(er_drop, 0),
            shadow_ban_detected = er_current < 0.01 and er_baseline > 0.04,
            follower_drop_pct = float(acc.get("follower_drop_pct_day", 0)),
        )


async def run_risk_engine():
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    engine = RiskEngine(db)
    await engine.run_all()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_risk_engine())
