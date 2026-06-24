"""
FIX #12: Аналитика — Attribution Window
=========================================
Проблема: Keitaro настроен на last-click 30 дней.
1win cookie = 365 дней, Dr.Cash CPA = 30 дней.
Теряем конверсии от аудитории, которая конвертировала позже 30 дней.

Решение:
  - Разные окна атрибуции по партнёрке
  - UTM структура с video_id для трекинга
  - n8n воркфлоу для сверки конверсий с партнёркой
  - Supabase таблица attribution_events
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional
import uuid

logger = logging.getLogger("attribution")


# ══════════════════════════════════════════════════════════
# 1. ОКНА АТРИБУЦИИ ПО ПАРТНЁРКЕ
# ══════════════════════════════════════════════════════════

ATTRIBUTION_WINDOWS: dict[str, dict] = {
    "1win": {
        "click_window_days":    30,     # окно клика
        "view_window_days":     7,      # окно просмотра (view-through)
        "cookie_days":          365,    # реальный cookie партнёрки
        "model":                "last_click",
        "postback_url":         "https://track.1win.xxx/postback",
        "revenue_model":        "revshare",  # revshare до 60%
        "cpa_amount":           None,
    },
    "mostbet": {
        "click_window_days":    30,
        "view_window_days":     7,
        "cookie_days":          90,
        "model":                "last_click",
        "postback_url":         "",
        "revenue_model":        "revshare",
        "cpa_amount":           None,
    },
    "melbet": {
        "click_window_days":    30,
        "view_window_days":     3,
        "cookie_days":          90,
        "model":                "last_click",
        "postback_url":         "",
        "revenue_model":        "cpa",
        "cpa_amount":           None,
    },
    "dr_cash": {
        "click_window_days":    30,
        "view_window_days":     1,
        "cookie_days":          30,
        "model":                "last_click",
        "postback_url":         "",
        "revenue_model":        "cpa",
        "cpa_amount":           50,      # $25-100 CPA COD
    },
}


# ══════════════════════════════════════════════════════════
# 2. UTM СТРУКТУРА
# ══════════════════════════════════════════════════════════

def build_utm(
    video_id:       str,
    account_id:     str,
    platform:       str,
    vertical:       str,
    partner:        str,
    geo:            str,
    content_format: str,
) -> dict[str, str]:
    """
    Строит UTM параметры для каждого видео.
    video_id позволяет атрибутировать конкретное видео.
    
    Пример результата:
    utm_source=tiktok
    utm_medium=short_video
    utm_campaign=nutra_dr_cash_PL
    utm_content=vid_abc123_historia_transformacii
    utm_term=PL_warmer_day12
    """
    vid_short = video_id.replace("-", "")[:8]
    acc_short = account_id.replace("-", "")[:6]

    return {
        "utm_source":   platform,
        "utm_medium":   "short_video",
        "utm_campaign": f"{vertical}_{partner}_{geo}",
        "utm_content":  f"vid_{vid_short}_{content_format}",
        "utm_term":     f"{geo}_{acc_short}",
    }


def build_tracking_url(
    partner:        str,
    offer_id:       str,
    keitaro_base:   str,
    **utm_params
) -> str:
    """Строит полный tracking URL через Keitaro."""
    from urllib.parse import urlencode
    params = {
        "offer_id": offer_id,
        **utm_params,
        "click_id": "{click_id}",    # Keitaro подставит автоматически
    }
    return f"{keitaro_base}/click?{urlencode(params)}"


# ══════════════════════════════════════════════════════════
# 3. SQL СХЕМА ДЛЯ ATTRIBUTION
# ══════════════════════════════════════════════════════════

ATTRIBUTION_SQL = """
-- Клики по видео
CREATE TABLE IF NOT EXISTS click_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keitaro_click_id TEXT UNIQUE,
    video_id        UUID REFERENCES videos(id),
    account_id      UUID REFERENCES accounts(id),
    publication_id  UUID REFERENCES publications(id),
    
    -- UTM
    utm_source      TEXT,
    utm_medium      TEXT,
    utm_campaign    TEXT,
    utm_content     TEXT,
    utm_term        TEXT,
    
    -- Контекст
    partner         TEXT,
    geo             TEXT,
    platform        TEXT,
    
    -- Технические
    ip_hash         TEXT,   -- хеш IP, не сам IP (GDPR)
    user_agent_hash TEXT,
    
    clicked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Конверсии (postback от партнёрки)
CREATE TABLE IF NOT EXISTS conversion_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    click_id        UUID REFERENCES click_events(id),
    keitaro_click_id TEXT,
    
    partner         TEXT NOT NULL,
    offer_id        TEXT,
    conversion_type TEXT,   -- registration | deposit | purchase
    revenue_usd     NUMERIC(10,2),
    payout_usd      NUMERIC(10,2),
    
    -- Атрибуция
    days_since_click    INT,
    attribution_model   TEXT,
    is_within_window    BOOLEAN,
    
    converted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_clicks_video     ON click_events(video_id);
CREATE INDEX IF NOT EXISTS idx_clicks_partner   ON click_events(partner);
CREATE INDEX IF NOT EXISTS idx_clicks_geo       ON click_events(geo);
CREATE INDEX IF NOT EXISTS idx_conv_click       ON conversion_events(click_id);
CREATE INDEX IF NOT EXISTS idx_conv_partner     ON conversion_events(partner);
CREATE INDEX IF NOT EXISTS idx_conv_date        ON conversion_events(converted_at);

-- Представление: ROI по видео
CREATE OR REPLACE VIEW v_video_roi AS
SELECT
    v.id           AS video_id,
    cp.title       AS content_title,
    cp.vertical,
    a.platform,
    a.geo,
    COUNT(DISTINCT ce.id)      AS clicks,
    COUNT(DISTINCT conv.id)    AS conversions,
    COALESCE(SUM(conv.payout_usd), 0) AS revenue_usd,
    CASE WHEN COUNT(DISTINCT ce.id) > 0
         THEN ROUND(COUNT(DISTINCT conv.id)::numeric / COUNT(DISTINCT ce.id) * 100, 2)
         ELSE 0
    END AS cvr_percent
FROM videos v
JOIN content_plans cp  ON cp.id = v.content_plan_id
JOIN publications pub  ON pub.video_id = v.id
JOIN accounts     a    ON a.id = pub.account_id
LEFT JOIN click_events      ce   ON ce.video_id = v.id
LEFT JOIN conversion_events conv ON conv.click_id = ce.id
GROUP BY v.id, cp.title, cp.vertical, a.platform, a.geo;
"""


# ══════════════════════════════════════════════════════════
# 4. KEITARO КОНФИГУРАЦИЯ (инструкция)
# ══════════════════════════════════════════════════════════

KEITARO_SETUP_GUIDE = """
# Настройка Keitaro для UBT OS

## Кампании по партнёркам

### 1win (BeΦтинг)
- Click window: 30 дней
- View window: 7 дней  
- Model: last_click
- Postback: добавить S2S постбек с {click_id}&status={status}&payout={payout}
- Cookie: 365 дней (настроить в 1win кабинете)

### Dr.Cash (Нутра)
- Click window: 30 дней
- View window: 1 день
- Model: last_click
- Postback: https://KEITARO_DOMAIN/postback?click_id={click_id}&status=approved&payout={payout}

## UTM маппинг в Keitaro
utm_source     → source
utm_medium     → medium  
utm_campaign   → campaign
utm_content    → creative (video_id будет виден)
utm_term       → keyword (geo + account)

## Токены для передачи в партнёрку
{click_id}  → subid1 у 1win
{utm_content} → subid2 (для видентификации видео)

## Важно
- Включить дедупликацию по IP + UA (window 24ч)
- Фильтр botов: настроить в Filters → Bot Protection
- UTM per video обязателен для атрибуции на уровне контента
"""


# ══════════════════════════════════════════════════════════
# 5. АНАЛИТИК: сверка конверсий
# ══════════════════════════════════════════════════════════

class AttributionAnalyzer:
    """
    Анализирует атрибуцию конверсий.
    Находит конверсии вне стандартного окна (потенциально теряемые).
    """

    def __init__(self, db_client):
        self.db = db_client

    def get_late_conversions(self, partner: str, days_threshold: int = 30) -> list[dict]:
        """
        Конверсии, которые случились позже стандартного окна.
        Эти данные нужны для переговоров с партнёркой о расширении окна.
        """
        return (
            self.db.table("conversion_events")
            .select("*")
            .eq("partner", partner)
            .gt("days_since_click", days_threshold)
            .eq("is_within_window", False)
            .order("converted_at", desc=True)
            .execute()
            .data
        )

    def get_roi_by_video(self, limit: int = 20) -> list[dict]:
        """Топ видео по ROI."""
        return (
            self.db.rpc("v_video_roi_ordered", {"lmt": limit})
            .execute()
            .data
        )

    def get_best_geo_vertical(self) -> list[dict]:
        """Лучшие комбинации ГЕО × вертикаль."""
        return (
            self.db.table("conversion_events")
            .select("partner, geo_from_click:click_events!inner(geo), payout_usd")
            .not_.is_("payout_usd", "null")
            .execute()
            .data
        )


# ══════════════════════════════════════════════════════════
# 6. POSTBACK HANDLER — приём конверсий от Keitaro
# ══════════════════════════════════════════════════════════

class KeitaroPostbackHandler:
    """
    Принимает S2S postback от Keitaro и записывает revenue_event в Supabase.
    URL: POST /keitaro/postback
    Параметры от Keitaro: click_id, status, payout, offer_id, partner
    """

    def __init__(self, db_client):
        self.db = db_client

    def handle(self, params: dict) -> dict:
        """
        Обрабатывает входящий postback.
        params — query string или JSON тело от Keitaro.
        """
        click_id   = params.get("click_id") or params.get("keitaro_click_id")
        status     = params.get("status", "unknown")
        payout     = float(params.get("payout") or 0)
        offer_id   = params.get("offer_id", "")
        partner    = params.get("partner") or self._detect_partner(offer_id)

        if not click_id:
            return {"ok": False, "error": "missing click_id"}

        # Находим исходный клик
        click_rows = (
            self.db.table("click_events")
            .select("id, video_id, clicked_at, partner, geo")
            .eq("keitaro_click_id", click_id)
            .limit(1)
            .execute()
            .data
        )

        click_row = click_rows[0] if click_rows else None
        days_since = None
        within_window = False

        if click_row:
            clicked_at = datetime.fromisoformat(click_row["clicked_at"].replace("Z", "+00:00"))
            days_since = (datetime.now(timezone.utc) - clicked_at).days
            window_cfg = ATTRIBUTION_WINDOWS.get(click_row.get("partner", partner), {})
            within_window = days_since <= window_cfg.get("click_window_days", 30)

        # Записываем revenue_event
        event = {
            "keitaro_click_id":   click_id,
            "click_id":           click_row["id"] if click_row else None,
            "partner":            partner,
            "offer_id":           offer_id,
            "conversion_type":    status,
            "payout_usd":         payout,
            "days_since_click":   days_since,
            "attribution_model":  "last_click",
            "is_within_window":   within_window,
            "converted_at":       datetime.now(timezone.utc).isoformat(),
        }

        try:
            self.db.table("conversion_events").insert(event).execute()
            logger.info(
                f"Postback recorded: partner={partner} status={status} "
                f"payout=${payout} within_window={within_window}"
            )
            return {"ok": True, "within_window": within_window, "payout": payout}
        except Exception as e:
            logger.error(f"Failed to record postback: {e}")
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _detect_partner(offer_id: str) -> str:
        """Определяет партнёрку по offer_id если не передана явно."""
        oid = offer_id.lower()
        if "1win" in oid or "1w" in oid:
            return "1win"
        if "mostbet" in oid or "mb" in oid:
            return "mostbet"
        if "drca" in oid or "cash" in oid:
            return "dr_cash"
        return "unknown"
