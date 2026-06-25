-- GramGPT-inspired: comment log + channel targets
-- Применить в Supabase SQL Editor

-- Лог комментариев T3-COMMENTER
CREATE TABLE IF NOT EXISTS comment_log (
  id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id  text NOT NULL,
  phone       text,
  channel     text NOT NULL,
  text        text,
  msg_id      bigint,
  vertical    text,
  posted_at   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS comment_log_account_idx ON comment_log(account_id);
CREATE INDEX IF NOT EXISTS comment_log_posted_idx  ON comment_log(posted_at DESC);

-- Таргет-каналы для T3-COMMENTER (результаты парсера)
CREATE TABLE IF NOT EXISTS channel_targets (
  id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  username     text UNIQUE NOT NULL,
  title        text,
  subscribers  integer DEFAULT 0,
  has_comments boolean DEFAULT true,
  keyword      text,
  vertical     text,
  parsed_at    timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS channel_targets_vertical_idx ON channel_targets(vertical);

-- Очередь контента для всех платформ
CREATE TABLE IF NOT EXISTS content_queue (
  id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id   text,
  platform     text NOT NULL,
  title        text,
  content_url  text,
  caption      text,
  scheduled_at timestamptz,
  status       text DEFAULT 'pending',  -- pending / scheduled / posted / failed
  vertical     text,
  geo          text,
  created_at   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS content_queue_status_idx   ON content_queue(status);
CREATE INDEX IF NOT EXISTS content_queue_platform_idx ON content_queue(platform);
CREATE INDEX IF NOT EXISTS content_queue_scheduled_idx ON content_queue(scheduled_at);
