-- ============================================================
-- PATCH #7: post_metrics — нативная аналитика по постам
-- ============================================================
-- Проблема: воронка конверсии и ads_auditor работали только с
-- revenue_events (деньги) или ручным вводом account_data — не было
-- ни одной живой метрики (impressions/reach/likes/comments/shares)
-- с самих площадок. A36 post_analytics_agent синхронизирует их
-- нативно через API TikTok/YouTube/Instagram/Facebook/Pinterest/
-- Threads/Twitter/LinkedIn и пишет сюда снапшотами (time-series —
-- один пост может иметь несколько строк с разным fetched_at, чтобы
-- видеть рост метрик со временем).
--
-- Зависит от 06_patch_accounts_align.sql: account_id ссылается на
-- accounts.id / direct_publish_jobs.account_id, которые там стали TEXT
-- (человекочитаемый id вида 'tiktok_us_001'), не UUID.
-- ============================================================

CREATE TABLE IF NOT EXISTS post_metrics (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    publication_id    UUID REFERENCES publications(id),
    direct_job_id     UUID REFERENCES direct_publish_jobs(id),
    account_id        TEXT,
    platform          VARCHAR(50) NOT NULL,
    platform_post_id  TEXT NOT NULL,
    impressions       INT NOT NULL DEFAULT 0,
    reach             INT NOT NULL DEFAULT 0,
    views             INT NOT NULL DEFAULT 0,
    likes             INT NOT NULL DEFAULT 0,
    comments          INT NOT NULL DEFAULT 0,
    shares            INT NOT NULL DEFAULT 0,
    saves             INT NOT NULL DEFAULT 0,
    engagement_rate   NUMERIC(6,3) NOT NULL DEFAULT 0,
    raw_response      JSONB NOT NULL DEFAULT '{}',
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- WRITER: только POST_ANALYTICS может писать в эту таблицу
    owned_by_agent    TEXT NOT NULL DEFAULT 'POST_ANALYTICS'
);

CREATE INDEX IF NOT EXISTS idx_post_metrics_platform_post
    ON post_metrics(platform, platform_post_id);
CREATE INDEX IF NOT EXISTS idx_post_metrics_fetched_at
    ON post_metrics(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_post_metrics_account
    ON post_metrics(account_id);

-- Последний снапшот метрик по каждому посту (для дашборда)
CREATE OR REPLACE VIEW v_post_metrics_latest AS
SELECT DISTINCT ON (platform, platform_post_id)
    id, publication_id, direct_job_id, account_id, platform, platform_post_id,
    impressions, reach, views, likes, comments, shares, saves,
    engagement_rate, fetched_at
FROM post_metrics
ORDER BY platform, platform_post_id, fetched_at DESC;

-- Агрегаты по платформе за всё время (для карточек Dashboard/Analytics)
CREATE OR REPLACE VIEW v_platform_engagement AS
SELECT
    platform,
    COUNT(DISTINCT platform_post_id)   AS posts_tracked,
    SUM(impressions)                   AS total_impressions,
    SUM(reach)                         AS total_reach,
    SUM(views)                         AS total_views,
    SUM(likes)                         AS total_likes,
    SUM(comments)                      AS total_comments,
    SUM(shares)                        AS total_shares,
    ROUND(AVG(engagement_rate), 3)     AS avg_engagement_rate
FROM v_post_metrics_latest
GROUP BY platform;
