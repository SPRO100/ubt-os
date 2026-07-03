-- ============================================================
-- UBT OS v2 — REVENUE_ANALYST Schema
-- WRITER: A16_REVENUE_ANALYST
-- ============================================================

-- Сырые конверсионные события (из Keitaro постбэка)
CREATE TABLE IF NOT EXISTS revenue_events (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    -- Источник
    click_id            TEXT UNIQUE,           -- Keitaro click ID
    source_video_id     TEXT,                  -- из UTM utm_content
    account_id          TEXT,
    platform            TEXT,
    vertical            TEXT,
    geo                 TEXT,
    partner             TEXT,                  -- 1win | mostbet | dr_cash

    -- Атрибуция (FIX #12 совместимость)
    utm_source          TEXT,
    utm_medium          TEXT,
    utm_campaign        TEXT,
    utm_content         TEXT,
    attribution_window  INTEGER DEFAULT 30,    -- дней

    -- Финансы
    event_type          TEXT,                  -- conversion | lead | install
    status              TEXT DEFAULT 'pending',-- pending | approved | rejected
    payout_model        TEXT,                  -- cpa | revshare | hybrid
    gross_amount        NUMERIC(12,2) DEFAULT 0,
    net_amount          NUMERIC(12,2) DEFAULT 0,
    currency            TEXT DEFAULT 'USD',
    paid_at             TIMESTAMPTZ,

    -- Обогащение видео-метриками (сейчас ничем не заполняется — A16
    -- revenue_analyst удалён как мёртвый код при пересборке агентов)
    video_views         BIGINT,
    video_ctr           FLOAT,
    video_completion    FLOAT,
    creative_score      FLOAT,
    production_cost     NUMERIC(8,2) DEFAULT 0.15,  -- $0.15 средняя себестоимость
    roi                 FLOAT                         -- (net - cost) / cost * 100
);
COMMENT ON TABLE revenue_events IS 'WRITER: A16_REVENUE_ANALYST + Keitaro postback';

-- Дневные агрегаты по вертикали/ГЕО/платформе
CREATE TABLE IF NOT EXISTS revenue_daily (
    id                  BIGSERIAL PRIMARY KEY,
    date                DATE NOT NULL,
    vertical            TEXT NOT NULL,
    geo                 TEXT NOT NULL,
    platform            TEXT NOT NULL,
    partner             TEXT NOT NULL,

    -- Воронка
    impressions         BIGINT DEFAULT 0,
    clicks              BIGINT DEFAULT 0,
    conversions         INTEGER DEFAULT 0,
    approved            INTEGER DEFAULT 0,
    rejected            INTEGER DEFAULT 0,

    -- Финансы
    gross_revenue       NUMERIC(12,2) DEFAULT 0,
    net_revenue         NUMERIC(12,2) DEFAULT 0,
    production_cost     NUMERIC(10,2) DEFAULT 0,

    -- Производные метрики
    ctr                 FLOAT,
    cr                  FLOAT,
    approval_rate       FLOAT,
    epc                 FLOAT,                 -- earnings per click
    roas                FLOAT,                 -- return on ad spend

    -- Воронка-утечки (в % от потенциала)
    ctr_gap             FLOAT,                 -- разрыв до бенчмарка
    cr_gap              FLOAT,
    revenue_upside      NUMERIC(12,2),         -- потенциальный доход при закрытии утечек

    UNIQUE (date, vertical, geo, platform, partner)
);
COMMENT ON TABLE revenue_daily IS 'WRITER: A16_REVENUE_ANALYST';

-- Профитабельность по видео
CREATE TABLE IF NOT EXISTS video_profitability (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    video_id            TEXT NOT NULL,
    account_id          TEXT,
    platform            TEXT,
    vertical            TEXT,
    geo                 TEXT,
    partner             TEXT,

    total_views         BIGINT DEFAULT 0,
    total_clicks        INTEGER DEFAULT 0,
    total_conversions   INTEGER DEFAULT 0,
    total_revenue       NUMERIC(12,2) DEFAULT 0,
    production_cost     NUMERIC(8,2) DEFAULT 0.15,

    revenue_per_view    FLOAT,
    revenue_per_click   FLOAT,
    roi                 FLOAT,
    payback_period_days INTEGER,

    is_scaling_candidate BOOLEAN DEFAULT FALSE,
    scaling_reason       TEXT,

    UNIQUE (video_id, partner)
);
COMMENT ON TABLE video_profitability IS 'WRITER: A16_REVENUE_ANALYST';

-- Сравнение партнёрок
CREATE TABLE IF NOT EXISTS partner_comparison (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    vertical            TEXT NOT NULL,
    geo                 TEXT NOT NULL,
    partner             TEXT NOT NULL,

    conversions         INTEGER DEFAULT 0,
    approved            INTEGER DEFAULT 0,
    gross_revenue       NUMERIC(12,2) DEFAULT 0,
    net_revenue         NUMERIC(12,2) DEFAULT 0,
    avg_payout          NUMERIC(8,2),
    approval_rate       FLOAT,
    epc                 FLOAT,
    avg_hold_days       INTEGER,

    rank_by_epc         INTEGER,
    rank_by_revenue     INTEGER,
    recommendation      TEXT
);

-- Ежедневные отчёты (JSON + markdown)
CREATE TABLE IF NOT EXISTS revenue_reports (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    report_date         DATE NOT NULL,
    report_type         TEXT NOT NULL,         -- daily | weekly
    vertical            TEXT,
    raw_json            JSONB,
    markdown_report     TEXT,
    key_insights        TEXT[],
    scale_alerts        JSONB DEFAULT '[]',
    leak_alerts         JSONB DEFAULT '[]',
    sent_to_telegram    BOOLEAN DEFAULT FALSE
);

-- ── Индексы ───────────────────────────────────────────────
CREATE INDEX idx_revenue_events_video    ON revenue_events(source_video_id);
CREATE INDEX idx_revenue_events_date     ON revenue_events(created_at);
CREATE INDEX idx_revenue_events_partner  ON revenue_events(partner, status);
CREATE INDEX idx_revenue_daily_date      ON revenue_daily(date DESC);
CREATE INDEX idx_video_profit_roi        ON video_profitability(roi DESC);
CREATE INDEX idx_video_profit_scaling    ON video_profitability(is_scaling_candidate) WHERE is_scaling_candidate = TRUE;
