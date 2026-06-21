-- ============================================================
-- PATCH: недостающие таблицы для knowledge_synthesizer.py
-- video_analytics — используется _videos()
-- knowledge_entries — используется _hypotheses() и _prev_learnings()
-- ============================================================

CREATE TABLE IF NOT EXISTS video_analytics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id            UUID REFERENCES videos(id),
    platform            TEXT,
    vertical            TEXT,
    geo                 TEXT,
    format_type         TEXT,
    completion_rate     NUMERIC(5,2),
    er                  NUMERIC(5,2),
    ctr                 NUMERIC(5,2),
    views               BIGINT DEFAULT 0,
    revenue             NUMERIC(12,2) DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_video_analytics_created ON video_analytics(created_at);

CREATE TABLE IF NOT EXISTS knowledge_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            TEXT NOT NULL CHECK (type IN ('hypothesis','daily_learning','weekly_learning','insight')),
    content         TEXT NOT NULL,
    status          TEXT DEFAULT 'pending'
                    CHECK (status IN ('pending','confirmed','rejected','archived')),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_entries_type ON knowledge_entries(type);
CREATE INDEX IF NOT EXISTS idx_knowledge_entries_created ON knowledge_entries(created_at);

COMMENT ON TABLE video_analytics IS 'Patch: добавлена для совместимости с knowledge_synthesizer.py (отсутствовала в исходных 7 схемах)';
COMMENT ON TABLE knowledge_entries IS 'Patch: добавлена для совместимости с knowledge_synthesizer.py (отсутствовала в исходных 7 схемах)';
