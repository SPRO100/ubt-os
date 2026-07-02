-- ============================================================
-- PATCH: kb_entries — версионируемая база знаний по таксономии
-- ------------------------------------------------------------
-- ВАЖНО: это НЕ knowledge_entries.
--   knowledge_entries (patch 02/03/05) — записи A18 knowledge_synthesizer
--     (схема type/content/date/subtype/status/metadata).
--   kb_entries (эта таблица) — структурированная база знаний по
--     таксономии <процесс>.<площадка>.<вертикаль>.<схема>, куда пишут
--     оркестратор (маркер [LEARN]) и OPTIMIZER. Append-only + версии.
--
-- Схема совпадает с ubt_os/core/knowledge_base.py::KnowledgeBase.
-- ============================================================

CREATE TABLE IF NOT EXISTS kb_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Идентификация по таксономии: <процесс>.<площадка>.<вертикаль>.<схема>
    entry_key       TEXT NOT NULL,    -- например: "warmup.tiktok.nutra.grey"
    category        TEXT NOT NULL,    -- = процесс (zaliv|warmup|master_prompt|…)
    vertical        TEXT,             -- nutra | betting | both | any

    -- Содержимое
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,    -- markdown или текст
    tags            TEXT[],           -- [процесс, площадка, схема]

    -- Версионирование (append-only: строки не удаляются/не переписываются)
    version         INT  NOT NULL DEFAULT 1,
    is_current      BOOLEAN NOT NULL DEFAULT TRUE,
    superseded_by   UUID REFERENCES kb_entries(id),

    -- Метаданные изменения
    changed_by      TEXT NOT NULL DEFAULT 'orchestrator',  -- агент/'user'/'orchestrator'
    change_reason   TEXT,
    source_metric   TEXT,
    source_value    NUMERIC,

    -- Временные метки
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until     TIMESTAMPTZ                             -- NULL = активна
);

-- Только одна current запись на ключ
CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_entries_current
    ON kb_entries(entry_key)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_kb_entries_category ON kb_entries(category);
CREATE INDEX IF NOT EXISTS idx_kb_entries_vertical ON kb_entries(vertical);
CREATE INDEX IF NOT EXISTS idx_kb_entries_created  ON kb_entries(created_at DESC);

COMMENT ON TABLE kb_entries IS
  'Версионируемая база знаний по таксономии (процесс.площадка.вертикаль.схема). Пишут оркестратор [LEARN] и OPTIMIZER. Не путать с knowledge_entries (A18).';
