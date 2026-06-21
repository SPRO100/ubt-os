-- ============================================================
-- UBT OS v2 — FAILURE_RECOVERY Schema
-- WRITER: A17_FAILURE_RECOVERY_AGENT
-- ============================================================

-- Текущее состояние здоровья компонентов
CREATE TABLE IF NOT EXISTS component_health (
    id              BIGSERIAL PRIMARY KEY,
    component       TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'healthy',  -- healthy|degraded|unhealthy
    latency_ms      FLOAT DEFAULT 0,
    error           TEXT,
    fallback_active BOOLEAN DEFAULT FALSE,
    checked_at      TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE component_health IS 'WRITER: A17_FAILURE_RECOVERY_AGENT';

-- История health checks
CREATE TABLE IF NOT EXISTS health_check_history (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    component   TEXT NOT NULL,
    status      TEXT NOT NULL,
    latency_ms  FLOAT,
    error       TEXT
);

-- Активные fallback цепочки
CREATE TABLE IF NOT EXISTS component_fallbacks (
    id             BIGSERIAL PRIMARY KEY,
    component      TEXT NOT NULL UNIQUE,
    fallback_chain TEXT[] NOT NULL,
    active         BOOLEAN DEFAULT FALSE,
    activated_at   TIMESTAMPTZ,
    resolved_at    TIMESTAMPTZ
);
COMMENT ON TABLE component_fallbacks IS 'WRITER: A17_FAILURE_RECOVERY_AGENT';

-- Инциденты (начало и конец каждого отказа)
CREATE TABLE IF NOT EXISTS incidents (
    id             BIGSERIAL PRIMARY KEY,
    started_at     TIMESTAMPTZ DEFAULT NOW(),
    resolved_at    TIMESTAMPTZ,
    component      TEXT NOT NULL,
    severity       TEXT NOT NULL,  -- low|medium|high|critical
    description    TEXT,
    fallback_used  TEXT,
    duration_min   FLOAT,
    impact         TEXT            -- none|partial|full
);

-- ── Индексы ───────────────────────────────────────────────
CREATE INDEX idx_health_component ON component_health(component);
CREATE INDEX idx_health_history   ON health_check_history(component, created_at DESC);
CREATE INDEX idx_incidents_open   ON incidents(resolved_at) WHERE resolved_at IS NULL;

-- ── View: текущий статус системы ──────────────────────────
CREATE OR REPLACE VIEW system_health_summary AS
SELECT
    COUNT(*) FILTER (WHERE status = 'healthy')   AS healthy_count,
    COUNT(*) FILTER (WHERE status = 'degraded')  AS degraded_count,
    COUNT(*) FILTER (WHERE status = 'unhealthy') AS unhealthy_count,
    COUNT(*) FILTER (WHERE fallback_active)       AS fallbacks_active,
    MAX(checked_at) AS last_check,
    CASE
        WHEN COUNT(*) FILTER (WHERE status='unhealthy') >= 5 THEN 4
        WHEN COUNT(*) FILTER (WHERE status='unhealthy') >= 3 THEN 3
        WHEN COUNT(*) FILTER (WHERE status='unhealthy') >= 2 THEN 2
        WHEN COUNT(*) FILTER (WHERE status='unhealthy') >= 1 THEN 1
        ELSE 0
    END AS degradation_level
FROM component_health;
