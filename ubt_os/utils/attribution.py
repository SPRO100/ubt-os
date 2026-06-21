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
