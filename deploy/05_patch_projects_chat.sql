ALTER TABLE knowledge_entries ADD COLUMN IF NOT EXISTS vertical TEXT;
CREATE INDEX IF NOT EXISTS idx_knowledge_entries_vertical ON knowledge_entries(vertical);

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    vertical_id TEXT REFERENCES vertical_configs(id),
    role TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_vertical ON chat_messages(vertical_id, created_at);

INSERT INTO vertical_configs (id, name, category, config_yaml) VALUES
('travel_agency', 'Турагент', 'services', '{
  "vertical": {"id":"travel_agency","name":"Турагент","category":"services"},
  "audience": {"geo":["RU"],"language":["ru"]},
  "content": {"tone":"экспертный, тёплый — travel-консультант","cta_style":"заявка на просчёт тура"},
  "platforms": {"allowed":["instagram","telegram","tiktok"],"primary":"instagram"},
  "monetization": {"model":"lead_gen","client_type":"white"}
}'::jsonb),
('cars_korea', 'Авто из Кореи', 'ecommerce', '{
  "vertical": {"id":"cars_korea","name":"Авто из Кореи","category":"ecommerce"},
  "audience": {"geo":["RU","KZ"],"language":["ru"]},
  "content": {"tone":"экспертный — автоподбор","cta_style":"заявка на просчёт авто"},
  "platforms": {"allowed":["instagram","youtube","telegram"],"primary":"youtube"},
  "monetization": {"model":"lead_gen","client_type":"white"}
}'::jsonb)
ON CONFLICT (id) DO NOTHING;
