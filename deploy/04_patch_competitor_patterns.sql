CREATE TABLE IF NOT EXISTS competitor_patterns (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vertical        TEXT,
    geo             TEXT,
    platform        TEXT,
    hook_type       TEXT,
    visual_style    TEXT,
    views           BIGINT DEFAULT 0,
    er              NUMERIC(5,2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_competitor_patterns_created ON competitor_patterns(created_at);

COMMENT ON TABLE competitor_patterns IS 'Patch 4: добавлена для совместимости с strategy_engine.py (отсутствовала в исходных схемах)';
