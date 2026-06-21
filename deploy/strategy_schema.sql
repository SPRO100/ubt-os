-- ============================================================
-- UBT OS v2 — STRATEGY_ENGINE Schema
-- FIX совместимость: использует agent_api_layer (FIX #1)
-- ============================================================

-- Недельные стратегические брифы
CREATE TABLE IF NOT EXISTS strategy_briefs (
    id                 BIGSERIAL PRIMARY KEY,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    week_label         TEXT NOT NULL,              -- '2026-W23'
    vertical           TEXT NOT NULL,              -- 'nutra' | 'betting'
    geo_priority       TEXT[] NOT NULL,            -- ['PL','RO','MX']
    platform_priority  TEXT[] NOT NULL,            -- ['tiktok','youtube']
    top_formats        JSONB NOT NULL DEFAULT '[]',
    stop_formats       TEXT[] DEFAULT '{}',
    scale_formats      TEXT[] DEFAULT '{}',
    trend_windows      JSONB DEFAULT '[]',
    risk_flags         TEXT[] DEFAULT '{}',
    confidence_score   FLOAT CHECK (confidence_score BETWEEN 0 AND 1),
    raw_json           JSONB,                      -- полный JSON от Claude
    approved_by_user   BOOLEAN DEFAULT FALSE,
    approved_at        TIMESTAMPTZ,
    superseded_by      BIGINT REFERENCES strategy_briefs(id)
);

-- Ежедневные очереди контента
CREATE TABLE IF NOT EXISTS daily_queues (
    id                 BIGSERIAL PRIMARY KEY,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    date               DATE NOT NULL,
    strategy_brief_id  BIGINT REFERENCES strategy_briefs(id),
    vertical           TEXT NOT NULL,
    platform           TEXT NOT NULL,
    geo                TEXT NOT NULL,
    formats            TEXT[] NOT NULL,
    quota_per_format   JSONB DEFAULT '{}',         -- {"transformation_story": 3}
    status             TEXT DEFAULT 'pending',     -- pending | active | done
    processed_at       TIMESTAMPTZ,
    UNIQUE (date, vertical, platform, geo)
);

-- Входящие тренд-сигналы (от TREND_HUNTER)
CREATE TABLE IF NOT EXISTS trend_signals (
    id                 BIGSERIAL PRIMARY KEY,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    platform           TEXT NOT NULL,
    vertical           TEXT NOT NULL,
    geo                TEXT NOT NULL,
    topic              TEXT NOT NULL,
    score              FLOAT,                      -- 0-1 viral probability
    source             TEXT,                       -- 'tiktok_search' | 'competitor'
    expires_at         TIMESTAMPTZ,
    used_in_brief      BIGINT REFERENCES strategy_briefs(id)
);

-- Индексы
CREATE INDEX idx_strategy_briefs_week    ON strategy_briefs(week_label, vertical);
CREATE INDEX idx_daily_queues_date       ON daily_queues(date, vertical);
CREATE INDEX idx_trend_signals_score     ON trend_signals(score DESC);
CREATE INDEX idx_trend_signals_expires   ON trend_signals(expires_at);

-- OwnerShip метки (FIX #1 совместимость)
COMMENT ON TABLE strategy_briefs IS 'WRITER: A15_STRATEGY_ENGINE';
COMMENT ON TABLE daily_queues    IS 'WRITER: A15_STRATEGY_ENGINE';
COMMENT ON TABLE trend_signals   IS 'WRITER: A2_TREND_HUNTER';
