-- ============================================================
-- UBT OS v2 — CREATIVE VAULT Schema
-- Централизованная база творческих ассетов
-- WRITER: A11_ANALYTICS_AGENT (единственный писатель)
-- ============================================================

-- Главная таблица: каждое видео с метриками
CREATE TABLE IF NOT EXISTS creative_assets (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    -- Идентификация
    video_id            TEXT UNIQUE NOT NULL,
    account_id          TEXT NOT NULL,
    platform            TEXT NOT NULL,   -- tiktok | youtube | instagram
    vertical            TEXT NOT NULL,   -- nutra | betting
    geo                 TEXT NOT NULL,

    -- Контент
    hook_text           TEXT NOT NULL,
    hook_type           TEXT NOT NULL,   -- transformation | doctor | antagonist | fact | story
    cta_text            TEXT,
    cta_position        TEXT,            -- start | middle | end
    topic               TEXT NOT NULL,
    format_type         TEXT NOT NULL,
    duration_sec        INTEGER,
    visual_style        TEXT,            -- ugc | cinematic | animation
    has_subtitles       BOOLEAN DEFAULT TRUE,
    mcsla_prompt        TEXT,

    -- Метрики охвата
    views               BIGINT DEFAULT 0,
    reach               BIGINT DEFAULT 0,
    impressions         BIGINT DEFAULT 0,

    -- Метрики вовлечённости
    watch_time_avg_sec  FLOAT DEFAULT 0,
    completion_rate     FLOAT DEFAULT 0, -- 0-1
    replay_count        INTEGER DEFAULT 0,
    likes               INTEGER DEFAULT 0,
    comments            INTEGER DEFAULT 0,
    shares              INTEGER DEFAULT 0,
    saves               INTEGER DEFAULT 0,

    -- Конверсионные метрики
    ctr                 FLOAT DEFAULT 0, -- click-through rate
    clicks              INTEGER DEFAULT 0,
    cr                  FLOAT DEFAULT 0, -- conversion rate
    conversions         INTEGER DEFAULT 0,
    revenue             NUMERIC(12,2) DEFAULT 0,
    partner             TEXT,

    -- Скоры (вычисляются Analytics Agent)
    creative_score      FLOAT,           -- 0-100: качество крео
    viral_score         FLOAT,           -- 0-100: вирусный потенциал
    conversion_score    FLOAT,           -- 0-100: конверсионность
    composite_score     FLOAT,           -- взвешенный итог

    -- Статус
    is_top_performer    BOOLEAN DEFAULT FALSE,
    is_archived         BOOLEAN DEFAULT FALSE,
    scores_updated_at   TIMESTAMPTZ
);
COMMENT ON TABLE creative_assets IS 'WRITER: A11_ANALYTICS_AGENT';

-- Таблица хуков с ранжированием
CREATE TABLE IF NOT EXISTS hook_rankings (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    hook_text           TEXT NOT NULL,
    hook_type           TEXT NOT NULL,
    vertical            TEXT NOT NULL,
    geo                 TEXT NOT NULL,
    platform            TEXT NOT NULL,
    avg_completion_rate FLOAT,
    avg_ctr             FLOAT,
    avg_cr              FLOAT,
    usage_count         INTEGER DEFAULT 1,
    total_revenue       NUMERIC(12,2) DEFAULT 0,
    hook_score          FLOAT,           -- итоговый балл хука
    last_used_at        TIMESTAMPTZ,
    UNIQUE (hook_text, vertical, geo, platform)
);
COMMENT ON TABLE hook_rankings IS 'WRITER: A11_ANALYTICS_AGENT';

-- Таблица CTA с ранжированием
CREATE TABLE IF NOT EXISTS cta_rankings (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    cta_text            TEXT NOT NULL,
    cta_position        TEXT NOT NULL,
    vertical            TEXT NOT NULL,
    platform            TEXT NOT NULL,
    avg_ctr             FLOAT,
    avg_cr              FLOAT,
    usage_count         INTEGER DEFAULT 1,
    cta_score           FLOAT,
    UNIQUE (cta_text, vertical, platform, cta_position)
);
COMMENT ON TABLE cta_rankings IS 'WRITER: A11_ANALYTICS_AGENT';

-- Паттерны выигрышных комбинаций
CREATE TABLE IF NOT EXISTS winning_patterns (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    pattern_name        TEXT NOT NULL,
    vertical            TEXT NOT NULL,
    geo                 TEXT NOT NULL,
    platform            TEXT NOT NULL,
    hook_type           TEXT,
    format_type         TEXT,
    visual_style        TEXT,
    duration_range      TEXT,           -- '30-45s' | '45-60s'
    cta_position        TEXT,
    avg_completion_rate FLOAT,
    avg_ctr             FLOAT,
    avg_cr              FLOAT,
    avg_revenue         NUMERIC(12,2),
    sample_count        INTEGER,
    confidence          FLOAT,          -- статистическая значимость
    discovered_at       TIMESTAMPTZ DEFAULT NOW(),
    is_active           BOOLEAN DEFAULT TRUE
);
COMMENT ON TABLE winning_patterns IS 'WRITER: A11_ANALYTICS_AGENT';

-- Кластеры трендов (для hook similarity search)
CREATE TABLE IF NOT EXISTS content_clusters (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    cluster_name        TEXT NOT NULL,
    vertical            TEXT NOT NULL,
    topics              TEXT[],
    representative_hook TEXT,
    asset_ids           BIGINT[],       -- creative_assets.id
    avg_composite_score FLOAT,
    trend_direction     TEXT,           -- rising | stable | declining
    last_updated        TIMESTAMPTZ
);

-- ── Индексы ───────────────────────────────────────────────
CREATE INDEX idx_creative_composite  ON creative_assets(composite_score DESC);
CREATE INDEX idx_creative_vertical   ON creative_assets(vertical, geo, platform);
CREATE INDEX idx_creative_hook_type  ON creative_assets(hook_type, vertical);
CREATE INDEX idx_creative_top        ON creative_assets(is_top_performer) WHERE is_top_performer = TRUE;
CREATE INDEX idx_hook_score          ON hook_rankings(hook_score DESC);
CREATE INDEX idx_cta_score           ON cta_rankings(cta_score DESC);
CREATE INDEX idx_patterns_active     ON winning_patterns(vertical, geo) WHERE is_active = TRUE;

-- ── Trigger: обновление updated_at ───────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER creative_assets_updated_at
    BEFORE UPDATE ON creative_assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── View: топ перформеры (используется дашбордом) ────────
CREATE OR REPLACE VIEW top_performers AS
SELECT
    video_id, platform, vertical, geo,
    hook_text, hook_type, format_type,
    views, completion_rate, ctr, cr, revenue,
    creative_score, viral_score, conversion_score, composite_score
FROM creative_assets
WHERE composite_score > 70
  AND is_archived = FALSE
ORDER BY composite_score DESC
LIMIT 100;
