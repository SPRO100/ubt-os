-- Sprint 2 Migration: click_events + conversion_events
-- Безопасная версия: FK только если таблицы существуют

-- 1. click_events
CREATE TABLE IF NOT EXISTS click_events (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keitaro_click_id TEXT UNIQUE,
    video_id         UUID,
    account_id       UUID,
    publication_id   UUID,

    utm_source       TEXT,
    utm_medium       TEXT,
    utm_campaign     TEXT,
    utm_content      TEXT,
    utm_term         TEXT,

    partner          TEXT,
    geo              TEXT,
    platform         TEXT,

    ip_hash          TEXT,
    user_agent_hash  TEXT,

    clicked_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. conversion_events
CREATE TABLE IF NOT EXISTS conversion_events (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    click_id         UUID REFERENCES click_events(id) ON DELETE SET NULL,
    keitaro_click_id TEXT,

    partner          TEXT NOT NULL,
    offer_id         TEXT,
    conversion_type  TEXT,
    revenue_usd      NUMERIC(10,2),
    payout_usd       NUMERIC(10,2),

    days_since_click   INT,
    attribution_model  TEXT DEFAULT 'last_click',
    is_within_window   BOOLEAN,

    converted_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    received_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Индексы
CREATE INDEX IF NOT EXISTS idx_clicks_video    ON click_events(video_id);
CREATE INDEX IF NOT EXISTS idx_clicks_partner  ON click_events(partner);
CREATE INDEX IF NOT EXISTS idx_clicks_geo      ON click_events(geo);
CREATE INDEX IF NOT EXISTS idx_conv_click      ON conversion_events(click_id);
CREATE INDEX IF NOT EXISTS idx_conv_partner    ON conversion_events(partner);
CREATE INDEX IF NOT EXISTS idx_conv_date       ON conversion_events(converted_at);
CREATE INDEX IF NOT EXISTS idx_conv_keitaro    ON conversion_events(keitaro_click_id);
