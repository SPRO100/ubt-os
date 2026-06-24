-- AgentOps: таблица для трекинга LiteLLM расходов
CREATE TABLE IF NOT EXISTS llm_usage_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model         TEXT NOT NULL,
    agent_name    TEXT,
    vertical      TEXT,
    input_tokens  INT  DEFAULT 0,
    output_tokens INT  DEFAULT 0,
    cost_usd      NUMERIC(12, 8) DEFAULT 0,
    duration_ms   INT  DEFAULT 0,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_model      ON llm_usage_events(model);
CREATE INDEX IF NOT EXISTS idx_llm_agent      ON llm_usage_events(agent_name);
CREATE INDEX IF NOT EXISTS idx_llm_vertical   ON llm_usage_events(vertical);
CREATE INDEX IF NOT EXISTS idx_llm_created_at ON llm_usage_events(created_at);
