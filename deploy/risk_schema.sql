-- ============================================================
-- UBT OS v2 — RISK ENGINE Schema
-- WRITER: RISK_ENGINE (новый сервис)
-- ============================================================

-- Риск-профили аккаунтов (обновляются каждые 6 часов)
CREATE TABLE IF NOT EXISTS account_risk_profiles (
    id                  BIGSERIAL PRIMARY KEY,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    account_id          TEXT NOT NULL UNIQUE,
    platform            TEXT NOT NULL,
    geo                 TEXT,
    warming_phase       TEXT,              -- из warming_state_machine

    -- Пять компонентов риска (0-100, чем выше — хуже)
    proxy_risk          FLOAT DEFAULT 0,
    device_risk         FLOAT DEFAULT 0,
    behavior_risk       FLOAT DEFAULT 0,
    publishing_risk     FLOAT DEFAULT 0,
    engagement_risk     FLOAT DEFAULT 0,

    -- Итоговый риск-скор (0-100)
    risk_score          FLOAT NOT NULL DEFAULT 0,
    risk_level          TEXT NOT NULL DEFAULT 'safe',  -- safe|caution|high|stop

    -- Факторы, вызвавшие повышение
    risk_factors        JSONB DEFAULT '[]',
    recommended_action  TEXT,

    -- История изменений
    prev_risk_score     FLOAT,
    score_delta         FLOAT,           -- изменение за последние 6 часов
    consecutive_high    INTEGER DEFAULT 0  -- сколько проверок подряд в high/stop
);
COMMENT ON TABLE account_risk_profiles IS 'WRITER: RISK_ENGINE';

-- История скоров (для трендового анализа)
CREATE TABLE IF NOT EXISTS risk_score_history (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    account_id  TEXT NOT NULL,
    risk_score  FLOAT NOT NULL,
    risk_level  TEXT NOT NULL,
    risk_factors JSONB
);

-- Риск-события (конкретные инциденты)
CREATE TABLE IF NOT EXISTS risk_events (
    id           BIGSERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    account_id   TEXT NOT NULL,
    event_type   TEXT NOT NULL,   -- proxy_fail | er_drop | ban_detected | speed_violation
    severity     TEXT NOT NULL,   -- low | medium | high | critical
    description  TEXT,
    resolved     BOOLEAN DEFAULT FALSE,
    resolved_at  TIMESTAMPTZ,
    auto_action  TEXT            -- что система сделала автоматически
);
COMMENT ON TABLE risk_events IS 'WRITER: RISK_ENGINE';

-- ── Индексы ───────────────────────────────────────────────
CREATE INDEX idx_risk_score      ON account_risk_profiles(risk_score DESC);
CREATE INDEX idx_risk_level      ON account_risk_profiles(risk_level);
CREATE INDEX idx_risk_history    ON risk_score_history(account_id, created_at DESC);
CREATE INDEX idx_risk_events_acc ON risk_events(account_id, created_at DESC);

-- ── View: аккаунты требующие внимания ─────────────────────
CREATE OR REPLACE VIEW accounts_at_risk AS
SELECT
    a.account_id, a.platform, a.geo,
    a.risk_score, a.risk_level,
    a.risk_factors, a.recommended_action,
    a.score_delta, a.consecutive_high
FROM account_risk_profiles a
WHERE a.risk_level IN ('caution','high','stop')
ORDER BY a.risk_score DESC;
