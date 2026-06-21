ALTER TABLE knowledge_entries DROP CONSTRAINT IF EXISTS knowledge_entries_type_check;

ALTER TABLE knowledge_entries
    ADD CONSTRAINT knowledge_entries_type_check
    CHECK (type IN (
        'hypothesis','daily_learning','weekly_learning',
        'insight','experiment','compound_learning'
    ));

ALTER TABLE knowledge_entries ADD COLUMN IF NOT EXISTS date DATE;
ALTER TABLE knowledge_entries ADD COLUMN IF NOT EXISTS subtype TEXT;

CREATE INDEX IF NOT EXISTS idx_knowledge_entries_date ON knowledge_entries(date);
