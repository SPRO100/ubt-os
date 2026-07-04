-- ============================================================
-- Жизненный цикл видео: срок жизни уникализированных копий (24ч)
-- и аудит-след после их истечения.
-- ============================================================

-- Момент истечения — ставится при создании копии (created_at + 24h).
-- У оригиналов остаётся NULL (живут бессрочно).
ALTER TABLE videos ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_videos_expires_at ON videos(expires_at) WHERE expires_at IS NOT NULL;

-- Разрешаем 'expired' в CHECK на status (истёкшая копия: файл в Storage
-- удалён, storage_url=NULL, но строка остаётся как аудит-след —
-- "у аккаунта была копия оригинала X, создана тогда-то").
ALTER TABLE videos DROP CONSTRAINT IF EXISTS videos_status_check;
ALTER TABLE videos ADD CONSTRAINT videos_status_check
    CHECK (status IN (
        'queued','generating','ready',
        'rendering','rendered','failed','published','expired'
    ));

COMMENT ON COLUMN videos.expires_at IS 'Для уникализированных копий — момент авто-удаления файла (24ч); NULL у оригиналов';
