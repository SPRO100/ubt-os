-- ─────────────────────────────────────────────────────────
-- FIX: A28 warmup_manager хранил состояние прогрева в локальном JSON-файле
-- (~/.ubt_os/warmup_state.json) — при пересборке контейнера прогресс терялся,
-- при этом accounts.warming_day/warming_phase уже существовали, но не
-- использовались. Переносим A28 на Supabase: недостающие поля инфраструктуры
-- (device_type/proxy_type/has_local_sim/bio_link_enabled) + свободные заметки.
-- Идемпотентно: можно применять повторно.
-- ─────────────────────────────────────────────────────────

ALTER TABLE accounts ADD COLUMN IF NOT EXISTS device_type      TEXT DEFAULT 'GLOBAL';
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS proxy_type       TEXT DEFAULT 'mobile';
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS has_local_sim    BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS bio_link_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS warmup_notes     TEXT;
