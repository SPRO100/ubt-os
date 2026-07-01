-- ================================================================
-- DOHOO-inspired features schema
-- Применить: make db-migrate или psql $DATABASE_URL < this_file
-- ================================================================

-- Hook Templates: библиотека выигрышных хуков
CREATE TABLE IF NOT EXISTS hook_templates (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vertical         VARCHAR(50)    NOT NULL,   -- nutra | betting
    geo              VARCHAR(5)     NOT NULL DEFAULT 'RU',
    platform         VARCHAR(50)    NOT NULL,
    hook_type        VARCHAR(50)    NOT NULL,   -- question | shock | stats | ...
    hook_text        TEXT           NOT NULL,
    hook_duration_sec NUMERIC(4,1),
    visual_style     VARCHAR(50),
    source_video_url TEXT,
    source_account   TEXT,
    views_at_capture BIGINT         DEFAULT 0,
    er_at_capture    NUMERIC(6,4)   DEFAULT 0,
    is_active        BOOLEAN        DEFAULT TRUE,
    created_at       TIMESTAMPTZ    DEFAULT NOW(),
    CONSTRAINT hook_templates_source_uniq UNIQUE (source_video_url)
);

-- Competitor Patterns: расширенная таблица паттернов
-- (базовая уже может существовать — добавляем недостающие поля)
DO $$ BEGIN
    ALTER TABLE competitor_patterns ADD COLUMN IF NOT EXISTS hook_text TEXT;
    ALTER TABLE competitor_patterns ADD COLUMN IF NOT EXISTS hook_strength INT DEFAULT 5;
    ALTER TABLE competitor_patterns ADD COLUMN IF NOT EXISTS why_works TEXT;
    ALTER TABLE competitor_patterns ADD COLUMN IF NOT EXISTS target_emotion VARCHAR(50);
    ALTER TABLE competitor_patterns ADD COLUMN IF NOT EXISTS recommended_adaptation TEXT;
    ALTER TABLE competitor_patterns ADD COLUMN IF NOT EXISTS risk_level VARCHAR(10) DEFAULT 'medium';
    ALTER TABLE competitor_patterns ADD COLUMN IF NOT EXISTS source_account TEXT;
    ALTER TABLE competitor_patterns ADD COLUMN IF NOT EXISTS source_video_url TEXT;
    ALTER TABLE competitor_patterns ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;
EXCEPTION WHEN OTHERS THEN NULL; END $$;

-- Competitor Reports: агрегированные отчёты A14
CREATE TABLE IF NOT EXISTS competitor_reports (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vertical              VARCHAR(50) NOT NULL,
    period_days           INT         DEFAULT 3,
    total_analyzed        INT         DEFAULT 0,
    dominant_hook_type    VARCHAR(50),
    dominant_visual_style VARCHAR(50),
    top_hooks             JSONB       DEFAULT '[]',
    emerging_trends       TEXT[]      DEFAULT '{}',
    avoid_patterns        TEXT[]      DEFAULT '{}',
    weekly_recommendation TEXT,
    confidence_score      NUMERIC(3,2) DEFAULT 0.5,
    raw_json              JSONB,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

-- Competitor Signals: входные данные для A14
CREATE TABLE IF NOT EXISTS competitor_signals (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vertical     VARCHAR(50)  NOT NULL,
    geo          VARCHAR(5)   NOT NULL DEFAULT 'RU',
    platform     VARCHAR(50)  NOT NULL,
    video_url    TEXT,
    thumbnail_url TEXT,
    title        TEXT,
    account_name TEXT,
    views        BIGINT       DEFAULT 0,
    er           NUMERIC(6,4) DEFAULT 0,
    scraped_at   TIMESTAMPTZ  DEFAULT NOW(),
    created_at   TIMESTAMPTZ  DEFAULT NOW(),
    CONSTRAINT competitor_signals_url_uniq UNIQUE (video_url)
);

-- Transcriptions: результаты AI-транскрипции
CREATE TABLE IF NOT EXISTS transcriptions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_url      TEXT         NOT NULL,
    full_text      TEXT,
    hook_text      TEXT,
    hook_type      VARCHAR(50)  DEFAULT 'unknown',
    hook_strength  INT          DEFAULT 0,
    language       VARCHAR(10)  DEFAULT 'ru',
    duration_sec   NUMERIC(8,2) DEFAULT 0,
    word_count     INT          DEFAULT 0,
    engine         VARCHAR(30),   -- deepgram | whisper | none
    source         VARCHAR(30)  DEFAULT 'competitor',   -- competitor | own_content
    vertical       VARCHAR(50),
    platform       VARCHAR(50),
    created_at     TIMESTAMPTZ  DEFAULT NOW(),
    CONSTRAINT transcriptions_url_uniq UNIQUE (video_url)
);

-- Direct Publish Accounts: токены для прямой публикации (без лимитов)
CREATE TABLE IF NOT EXISTS direct_publish_accounts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id       TEXT,   -- ссылка на accounts.id (человекочитаемый id)
    platform         VARCHAR(50) NOT NULL,
    access_token     TEXT,
    refresh_token    TEXT,
    token_expires_at TIMESTAMPTZ,
    platform_user_id TEXT,
    platform_username TEXT,
    extra_data       JSONB    DEFAULT '{}',   -- page_id, ig_user_id, board_id и т.д.
    is_active        BOOLEAN  DEFAULT TRUE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Direct Publish Jobs: очередь прямой публикации (без Blotato)
CREATE TABLE IF NOT EXISTS direct_publish_jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id       TEXT,   -- ссылка на accounts.id (человекочитаемый id)
    platform         VARCHAR(50)  NOT NULL,
    content_type     VARCHAR(20)  DEFAULT 'video',   -- video | image | carousel | text
    media_url        TEXT,
    caption          TEXT,
    hashtags         TEXT[]       DEFAULT '{}',
    extra_params     JSONB        DEFAULT '{}',
    scheduled_at     TIMESTAMPTZ,
    status           VARCHAR(20)  DEFAULT 'pending', -- pending | processing | published | failed | dead_letter
    platform_post_id TEXT,
    attempt_count    INT          DEFAULT 0,
    last_error       TEXT,
    published_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_hook_templates_vertical_platform ON hook_templates (vertical, platform);
CREATE INDEX IF NOT EXISTS idx_hook_templates_hook_type ON hook_templates (hook_type);
CREATE INDEX IF NOT EXISTS idx_competitor_signals_vertical ON competitor_signals (vertical, platform, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transcriptions_vertical ON transcriptions (vertical, platform);
CREATE INDEX IF NOT EXISTS idx_direct_publish_jobs_status ON direct_publish_jobs (status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_direct_publish_accounts_platform ON direct_publish_accounts (platform, is_active);

-- View: топ хуки по силе
CREATE OR REPLACE VIEW v_top_hooks AS
SELECT
    ht.vertical,
    ht.platform,
    ht.geo,
    ht.hook_type,
    ht.hook_text,
    ht.views_at_capture,
    ht.er_at_capture,
    ht.created_at
FROM hook_templates ht
WHERE ht.is_active = TRUE
ORDER BY ht.er_at_capture DESC, ht.views_at_capture DESC;

-- View: очередь прямой публикации к запуску
CREATE OR REPLACE VIEW v_pending_publish_jobs AS
SELECT
    dpj.id,
    dpj.platform,
    dpj.content_type,
    dpj.caption,
    dpj.scheduled_at,
    dpj.attempt_count,
    dpa.platform_username
FROM direct_publish_jobs dpj
LEFT JOIN direct_publish_accounts dpa ON dpa.account_id = dpj.account_id AND dpa.platform = dpj.platform
WHERE dpj.status IN ('pending', 'failed')
  AND (dpj.scheduled_at IS NULL OR dpj.scheduled_at <= NOW())
ORDER BY dpj.scheduled_at ASC;

-- ─────────────────────────────────────────────────────────
-- trend_signals — A32 TREND_RADAR: ранжированные тренды звуков/хэштегов
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trend_signals (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vertical       VARCHAR(50)  NOT NULL,
    geo            VARCHAR(5)   NOT NULL DEFAULT 'US',
    platform       VARCHAR(50)  NOT NULL DEFAULT 'tiktok',
    kind           VARCHAR(20)  NOT NULL,          -- 'hashtag' | 'sound'
    name           TEXT         NOT NULL,
    growth_pct     NUMERIC(8,2) DEFAULT 0,
    rank           INT          DEFAULT 0,
    recommendation TEXT,
    created_at     TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trend_signals_vertical ON trend_signals (vertical, geo, created_at DESC);
