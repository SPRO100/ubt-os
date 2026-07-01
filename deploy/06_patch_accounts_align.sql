-- ─────────────────────────────────────────────────────────
-- FIX: привести таблицу accounts к тому, что реально шлёт дашборд/агенты.
-- Было: id UUID, platform ∈ {tiktok,youtube,instagram,telegram}, нет колонок
--       proxy/publer_profile_id/account_type. Из-за этого «Добавить аккаунт»
--       в дашборде падал (Facebook/Pinterest, строковый id, publer_profile_id).
-- Стало: id TEXT (человекочитаемый), + facebook/pinterest, + недостающие колонки.
-- Идемпотентно: можно применять повторно.
-- ─────────────────────────────────────────────────────────

-- 0. Снимаем вью, которая зависит от direct_publish_jobs.account_id (пересоздадим в конце).
DROP VIEW IF EXISTS v_pending_publish_jobs;

-- 1. Снимаем FK на accounts(id) — иначе нельзя менять тип id.
ALTER TABLE content_plans DROP CONSTRAINT IF EXISTS content_plans_account_id_fkey;
ALTER TABLE publications  DROP CONSTRAINT IF EXISTS publications_account_id_fkey;

-- 2. accounts.id: UUID → TEXT (человекочитаемый, напр. 'tiktok_us_001').
ALTER TABLE accounts     ALTER COLUMN id DROP DEFAULT;
ALTER TABLE accounts     ALTER COLUMN id TYPE TEXT USING id::text;

-- 3. account_id в дочерних таблицах: UUID → TEXT.
ALTER TABLE content_plans ALTER COLUMN account_id TYPE TEXT USING account_id::text;
ALTER TABLE publications  ALTER COLUMN account_id TYPE TEXT USING account_id::text;

-- 4. Возвращаем FK.
ALTER TABLE content_plans
    ADD CONSTRAINT content_plans_account_id_fkey FOREIGN KEY (account_id) REFERENCES accounts(id);
ALTER TABLE publications
    ADD CONSTRAINT publications_account_id_fkey  FOREIGN KEY (account_id) REFERENCES accounts(id);

-- 5. Расширяем набор платформ (Facebook/Pinterest публикуются через Publer/A26).
ALTER TABLE accounts DROP CONSTRAINT IF EXISTS accounts_platform_check;
ALTER TABLE accounts ADD  CONSTRAINT accounts_platform_check
    CHECK (platform IN ('tiktok','youtube','instagram','telegram','facebook','pinterest'));

-- 6. Недостающие колонки, которые вставляет дашборд.
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS proxy             TEXT;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS publer_profile_id TEXT;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS account_type      TEXT;

-- 7. direct_publish_* account_id тоже строковые (ссылаются на accounts.id).
ALTER TABLE direct_publish_accounts ALTER COLUMN account_id TYPE TEXT USING account_id::text;
ALTER TABLE direct_publish_jobs     ALTER COLUMN account_id TYPE TEXT USING account_id::text;

-- 8. Пересоздаём вью очереди прямой публикации (была снята в п.0).
CREATE OR REPLACE VIEW v_pending_publish_jobs AS
SELECT
    dpj.id,
    dpj.platform,
    dpj.content_type,
    dpj.caption,
    dpj.scheduled_at,
    dpj.attempt_count,
    dpa.platform_username
FROM direct_publish_jobs dpj
LEFT JOIN direct_publish_accounts dpa ON dpa.account_id = dpj.account_id AND dpa.platform = dpj.platform
WHERE dpj.status IN ('pending', 'failed')
  AND (dpj.scheduled_at IS NULL OR dpj.scheduled_at <= NOW())
ORDER BY dpj.scheduled_at ASC;
