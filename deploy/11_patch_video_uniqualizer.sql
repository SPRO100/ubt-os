-- ============================================================
-- Уникализатор видео: 1 аккаунт = 1 проект, видео в своей папке.
-- ============================================================

-- Проект аккаунта (vertical_configs.id, он же "проект" в дашборде).
-- Один аккаунт принадлежит максимум одному проекту.
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS project_id TEXT REFERENCES vertical_configs(id);
CREATE INDEX IF NOT EXISTS idx_accounts_project ON accounts(project_id);

-- Уникализированные копии видео не имеют собственного content_plan —
-- они просто пересобранная версия исходного ролика под другой аккаунт.
ALTER TABLE videos ALTER COLUMN content_plan_id DROP NOT NULL;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS account_id TEXT REFERENCES accounts(id);
ALTER TABLE videos ADD COLUMN IF NOT EXISTS parent_video_id UUID REFERENCES videos(id);
CREATE INDEX IF NOT EXISTS idx_videos_account ON videos(account_id);
CREATE INDEX IF NOT EXISTS idx_videos_parent  ON videos(parent_video_id);

COMMENT ON COLUMN accounts.project_id IS 'vertical_configs.id — проект аккаунта (1 аккаунт = 1 проект)';
COMMENT ON COLUMN videos.account_id IS 'Аккаунт, для которого предназначено это видео (оригинал или уникализированная копия)';
COMMENT ON COLUMN videos.parent_video_id IS 'Для уникализированных копий — id исходного ролика (videos.id)';
