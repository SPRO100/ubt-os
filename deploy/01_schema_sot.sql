-- ============================================================
-- FIX #1: Single Source of Truth
-- Каждая сущность имеет ONE writer agent.
-- Остальные читают через view или API-слой.
-- ============================================================

-- ─────────────────────────────────────────
-- 1. ACCOUNTS — владелец: ACCOUNT_MANAGER
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform        TEXT NOT NULL CHECK (platform IN ('tiktok','youtube','instagram','telegram')),
    username        TEXT,
    proxy_id        UUID REFERENCES proxies(id),
    gologin_profile_id TEXT,
    status          TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new','warming','active','shadow_banned','hard_banned','replaced','paused')),
    warming_started_at  TIMESTAMPTZ,
    warming_day         INT NOT NULL DEFAULT 0,
    warming_phase       TEXT NOT NULL DEFAULT 'idle'
                        CHECK (warming_phase IN (
                            'idle','views_only','neutral_content',
                            'niche_content','monetization'
                        )),
    last_action_at      TIMESTAMPTZ,
    last_post_at        TIMESTAMPTZ,
    er_7d               NUMERIC(5,2),   -- engagement rate последние 7 дней
    niche               TEXT,
    geo                 TEXT,           -- PL, RO, MX, BR, IN ...
    partner_program     TEXT,           -- 1win, mostbet, dr.cash ...
    vertical_id         TEXT,           -- привязка к проекту (vertical_configs.id)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- WRITER: только ACCOUNT_MANAGER может менять эту строку
    owned_by_agent  TEXT NOT NULL DEFAULT 'ACCOUNT_MANAGER'
);

-- Добавить колонку если уже существует (миграция)
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS vertical_id TEXT;

-- ─────────────────────────────────────────
-- 2. CONTENT_PLANS — владелец: CONTENT_CREATOR
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS content_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id),
    title           TEXT NOT NULL,
    format          TEXT,            -- история_трансформации, угадай_счёт и т.д.
    vertical        TEXT CHECK (vertical IN ('nutra','betting')),
    script          TEXT,
    mcsla_prompt    TEXT,            -- готовый промпт для Higgsfield
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','approved','in_production','published','archived')),
    approved_by     TEXT,            -- 'user' или 'OPTIMIZER'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    owned_by_agent  TEXT NOT NULL DEFAULT 'CONTENT_CREATOR'
);

-- ─────────────────────────────────────────
-- 3. VIDEOS — владелец: VIDEO_DIRECTOR
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS videos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_plan_id UUID NOT NULL REFERENCES content_plans(id),
    higgsfield_job_id TEXT,
    storage_url     TEXT,
    duration_sec    INT,
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN (
                        'queued','generating','ready',
                        'rendering','rendered','failed','published'
                    )),
    error_message   TEXT,
    retry_count     INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    owned_by_agent  TEXT NOT NULL DEFAULT 'VIDEO_DIRECTOR'
);

-- ─────────────────────────────────────────
-- 4. PUBLICATIONS — владелец: PUBLISHING
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS publications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id        UUID NOT NULL REFERENCES videos(id),
    account_id      UUID NOT NULL REFERENCES accounts(id),
    scheduled_at    TIMESTAMPTZ NOT NULL,
    published_at    TIMESTAMPTZ,
    platform_post_id TEXT,
    status          TEXT NOT NULL DEFAULT 'scheduled'
                    CHECK (status IN (
                        'scheduled','publishing','published',
                        'failed','dead_letter'
                    )),
    attempt_count   INT NOT NULL DEFAULT 0,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    owned_by_agent  TEXT NOT NULL DEFAULT 'PUBLISHING'
);

-- ─────────────────────────────────────────
-- 5. PROXIES — владелец: ACCOUNT_MANAGER
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS proxies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host        TEXT NOT NULL,
    port        INT NOT NULL,
    username    TEXT,
    password    TEXT,
    type        TEXT DEFAULT 'residential',
    geo         TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    last_ping_ms INT,
    last_checked_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 6. AGENT_LOCKS — для идемпотентности (Fix #3)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_locks (
    lock_key    TEXT PRIMARY KEY,
    locked_by   TEXT NOT NULL,       -- имя агента
    locked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);

-- ─────────────────────────────────────────
-- 7. AUTO updated_at trigger
-- ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['accounts','content_plans','videos','publications']
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_updated_at ON %I;
             CREATE TRIGGER trg_updated_at
             BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION set_updated_at();', t, t
        );
    END LOOP;
END;
$$;

-- ─────────────────────────────────────────
-- 8. Индексы производительности
-- ─────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_accounts_status         ON accounts(status);
CREATE INDEX IF NOT EXISTS idx_accounts_platform       ON accounts(platform);
CREATE INDEX IF NOT EXISTS idx_content_plans_status    ON content_plans(status);
CREATE INDEX IF NOT EXISTS idx_videos_status           ON videos(status);
CREATE INDEX IF NOT EXISTS idx_publications_scheduled  ON publications(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_publications_status     ON publications(status);
CREATE INDEX IF NOT EXISTS idx_agent_locks_expires     ON agent_locks(expires_at);

-- ─────────────────────────────────────────
-- 9. Очистка истёкших локов (вызывать cron-ом)
-- ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION cleanup_expired_locks()
RETURNS INT AS $$
DECLARE deleted INT;
BEGIN
    DELETE FROM agent_locks WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted = ROW_COUNT;
    RETURN deleted;
END;
$$ LANGUAGE plpgsql;
