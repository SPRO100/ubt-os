-- Phase 7: Telegram-модуль — tg_accounts
CREATE TABLE IF NOT EXISTS tg_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           TEXT NOT NULL UNIQUE,
    api_id          INT  NOT NULL,
    api_hash        TEXT NOT NULL,

    status          TEXT NOT NULL DEFAULT 'idle',
    -- idle | warming | active | banned | flood_wait

    warming_day     INT  NOT NULL DEFAULT 0,
    warming_phase   TEXT DEFAULT 'idle',
    -- idle | views_only | neutral_content | niche_content | monetization

    vertical        TEXT NOT NULL DEFAULT 'nutra',
    geo             TEXT NOT NULL DEFAULT 'PL',

    proxy           JSONB,
    -- {"host":"...","port":1080,"type":"socks5","user":"...","pass":"..."}

    daily_comments  INT  DEFAULT 0,
    daily_reactions INT  DEFAULT 0,

    ban_reason      TEXT,
    flood_wait_until TIMESTAMPTZ,

    last_action_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tg_status   ON tg_accounts(status);
CREATE INDEX IF NOT EXISTS idx_tg_vertical ON tg_accounts(vertical);

-- Сообщения чата с оркестратором
CREATE TABLE IF NOT EXISTS chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vertical_id UUID,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_vertical ON chat_messages(vertical_id);
