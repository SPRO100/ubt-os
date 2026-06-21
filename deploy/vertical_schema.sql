-- ============================================================
-- UBT OS — Vertical Configs Schema
-- WRITER: ORCHESTRATOR (через vertical_loader.py)
-- ============================================================

CREATE TABLE IF NOT EXISTS vertical_configs (
    id           TEXT PRIMARY KEY,          -- slug: cars_korea
    name         TEXT NOT NULL,
    category     TEXT NOT NULL,             -- ecommerce | affiliate | infoproduct | realestate | crypto | dating | services
    status       TEXT DEFAULT 'active',     -- active | paused | draft
    config_yaml  JSONB NOT NULL,            -- полный конфиг
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Текущая активная вертикаль на сессию
CREATE TABLE IF NOT EXISTS active_verticals (
    id           BIGSERIAL PRIMARY KEY,
    session_id   TEXT NOT NULL,
    vertical_id  TEXT REFERENCES vertical_configs(id),
    started_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_verticals_status   ON vertical_configs(status);
CREATE INDEX idx_verticals_category ON vertical_configs(category);

-- Заполняем стартовые конфиги (Беттинг + Нутра)
INSERT INTO vertical_configs (id, name, category, config_yaml) VALUES
('betting_ru', 'Беттинг (RU/KZ)', 'affiliate', '{
  "vertical": {"id":"betting_ru","name":"Беттинг","category":"affiliate"},
  "audience": {"geo":["RU","KZ"],"language":["ru"],"age_range":"22-40","gender":"male"},
  "content": {
    "tone": "нативный, экспертный — прогнозист",
    "first_15_sec_rule": "показать результат ставки или факт — без прямой рекламы",
    "cta_style": "промокод в профиле",
    "forbidden_words": ["гарантированный выигрыш","100% зайдёт"]
  },
  "platforms": {"allowed":["tiktok","youtube","telegram"],"primary":"tiktok","tiktok_sensitivity":"medium"},
  "monetization": {"model":"affiliate_revshare","funnel_type":"simple","affiliate":{"network":"1win","cookie_days":365}}
}'::jsonb),

('nutra_joints_pl', 'Нутра — суставы (PL)', 'affiliate', '{
  "vertical": {"id":"nutra_joints_pl","name":"Нутра Суставы PL","category":"affiliate"},
  "audience": {"geo":["PL"],"language":["pl"],"age_range":"45-70","gender":"any"},
  "content": {
    "tone": "доверительный, от человека который решил проблему",
    "first_15_sec_rule": "боль суставов — не упоминать продукт первые 15 сек",
    "cta_style": "ссылка в bio — нативно",
    "forbidden_words": ["лечит","гарантирует выздоровление","медицинский факт"]
  },
  "platforms": {"allowed":["tiktok","youtube","instagram"],"primary":"tiktok","tiktok_sensitivity":"low"},
  "monetization": {"model":"affiliate_cpa","funnel_type":"prelanding","affiliate":{"network":"dr_cash","cookie_days":30}}
}'::jsonb)

ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE vertical_configs IS 'WRITER: ORCHESTRATOR via vertical_loader.py';
