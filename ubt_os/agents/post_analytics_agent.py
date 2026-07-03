"""
A36 — POST_ANALYTICS
Синхронизирует нативные метрики (impressions/reach/views/likes/comments/
shares/saves) с площадок для уже опубликованных постов из
direct_publish_jobs. Пишет снапшоты в post_metrics.

Закрывает пробел: до этого агента в системе не было ни одной живой
метрики вовлечённости с самих платформ — только revenue_events (деньги)
и ручной ввод. Идея — как у Postiz: unified per-post analytics dashboard,
только через прямые нативные API вместо агрегатора.

Запуск: POST /analytics/sync  или  agent="post_analytics" в /agents/run
"""
from __future__ import annotations
import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from supabase import create_client, Client

from ubt_os.utils.supabase_utils import rows

logger = logging.getLogger("ubt_os.post_analytics")


@dataclass
class MetricsResult:
    success:      bool
    impressions:  int = 0
    reach:        int = 0
    views:        int = 0
    likes:        int = 0
    comments:     int = 0
    shares:       int = 0
    saves:        int = 0
    error:        Optional[str] = None
    raw_response: Optional[dict] = None

    @property
    def engagement_rate(self) -> float:
        """Вовлечённость = (лайки+комменты+шеры+сохранения) / (impressions или reach или views)."""
        base = self.impressions or self.reach or self.views
        if not base:
            return 0.0
        engaged = self.likes + self.comments + self.shares + self.saves
        return round(engaged / base * 100, 3)


# ── Базовый класс fetcher'а метрик ────────────────────────

class MetricsFetcher:

    def __init__(self, credentials: dict):
        self.credentials = credentials

    async def fetch(self, platform_post_id: str) -> MetricsResult:
        raise NotImplementedError


# ── TikTok ────────────────────────────────────────────────

class TikTokMetricsFetcher(MetricsFetcher):
    """TikTok Content Posting API v2 — Query Video List."""

    BASE = "https://open.tiktokapis.com/v2"

    async def fetch(self, platform_post_id: str) -> MetricsResult:
        token = self.credentials.get("access_token")
        if not token:
            return MetricsResult(success=False, error="TikTok: нет access_token")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE}/video/query/",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
                params={"fields": "id,view_count,like_count,comment_count,share_count"},
                json={"filters": {"video_ids": [platform_post_id]}},
            )

        if resp.status_code >= 400:
            return MetricsResult(success=False, error=f"TikTok {resp.status_code}: {resp.text[:200]}")
        data   = resp.json()
        videos = data.get("data", {}).get("videos", [])
        if not videos:
            return MetricsResult(success=False, error="TikTok: видео не найдено", raw_response=data)
        v = videos[0]
        return MetricsResult(
            success=True,
            views=v.get("view_count", 0), likes=v.get("like_count", 0),
            comments=v.get("comment_count", 0), shares=v.get("share_count", 0),
            raw_response=data,
        )


# ── YouTube ───────────────────────────────────────────────

class YouTubeMetricsFetcher(MetricsFetcher):
    """YouTube Data API v3 — videos.statistics."""

    BASE = "https://www.googleapis.com/youtube/v3"

    async def fetch(self, platform_post_id: str) -> MetricsResult:
        token = self.credentials.get("access_token")
        if not token:
            return MetricsResult(success=False, error="YouTube: нет access_token")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE}/videos",
                headers={"Authorization": f"Bearer {token}"},
                params={"part": "statistics", "id": platform_post_id},
            )

        if resp.status_code >= 400:
            return MetricsResult(success=False, error=f"YouTube {resp.status_code}: {resp.text[:200]}")
        data  = resp.json()
        items = data.get("items", [])
        if not items:
            return MetricsResult(success=False, error="YouTube: видео не найдено", raw_response=data)
        stats = items[0].get("statistics", {})
        return MetricsResult(
            success=True,
            views=int(stats.get("viewCount", 0)), likes=int(stats.get("likeCount", 0)),
            comments=int(stats.get("commentCount", 0)),
            raw_response=data,
        )


# ── Instagram ─────────────────────────────────────────────

class InstagramMetricsFetcher(MetricsFetcher):
    """Instagram Graph API — Media Insights."""

    BASE = "https://graph.facebook.com/v19.0"

    async def fetch(self, platform_post_id: str) -> MetricsResult:
        token = self.credentials.get("access_token")
        if not token:
            return MetricsResult(success=False, error="Instagram: нет access_token")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE}/{platform_post_id}/insights",
                params={
                    "metric": "impressions,reach,likes,comments,saved,shares",
                    "access_token": token,
                },
            )

        if resp.status_code >= 400:
            return MetricsResult(success=False, error=f"Instagram {resp.status_code}: {resp.text[:200]}")
        data   = resp.json()
        values = {m["name"]: (m.get("values", [{}])[-1].get("value", 0)) for m in data.get("data", [])}
        return MetricsResult(
            success=True,
            impressions=values.get("impressions", 0), reach=values.get("reach", 0),
            likes=values.get("likes", 0), comments=values.get("comments", 0),
            shares=values.get("shares", 0), saves=values.get("saved", 0),
            raw_response=data,
        )


# ── Facebook ──────────────────────────────────────────────

class FacebookMetricsFetcher(MetricsFetcher):
    """Facebook Graph API — Post Insights + счётчики реакций."""

    BASE = "https://graph.facebook.com/v19.0"

    async def fetch(self, platform_post_id: str) -> MetricsResult:
        token = self.credentials.get("access_token")
        if not token:
            return MetricsResult(success=False, error="Facebook: нет access_token")

        async with httpx.AsyncClient(timeout=30) as client:
            insights = await client.get(
                f"{self.BASE}/{platform_post_id}/insights",
                params={"metric": "post_impressions,post_engaged_users", "access_token": token},
            )
            counts = await client.get(
                f"{self.BASE}/{platform_post_id}",
                params={"fields": "likes.summary(true),comments.summary(true),shares", "access_token": token},
            )

        if insights.status_code >= 400 and counts.status_code >= 400:
            return MetricsResult(success=False, error=f"Facebook {insights.status_code}: {insights.text[:200]}")

        ins_data = insights.json() if insights.status_code < 400 else {}
        cnt_data = counts.json() if counts.status_code < 400 else {}
        values   = {m["name"]: (m.get("values", [{}])[-1].get("value", 0)) for m in ins_data.get("data", [])}

        return MetricsResult(
            success=True,
            impressions=values.get("post_impressions", 0),
            reach=values.get("post_engaged_users", 0),
            likes=cnt_data.get("likes", {}).get("summary", {}).get("total_count", 0),
            comments=cnt_data.get("comments", {}).get("summary", {}).get("total_count", 0),
            shares=cnt_data.get("shares", {}).get("count", 0),
            raw_response={"insights": ins_data, "counts": cnt_data},
        )


# ── Pinterest ─────────────────────────────────────────────

class PinterestMetricsFetcher(MetricsFetcher):
    """Pinterest API v5 — Pin Analytics."""

    BASE = "https://api.pinterest.com/v5"

    async def fetch(self, platform_post_id: str) -> MetricsResult:
        token = self.credentials.get("access_token")
        if not token:
            return MetricsResult(success=False, error="Pinterest: нет access_token")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE}/pins/{platform_post_id}/analytics",
                headers={"Authorization": f"Bearer {token}"},
                params={"metric_types": "IMPRESSION,SAVE,PIN_CLICK,OUTBOUND_CLICK"},
            )

        if resp.status_code >= 400:
            return MetricsResult(success=False, error=f"Pinterest {resp.status_code}: {resp.text[:200]}")
        data    = resp.json()
        totals  = data.get("all", {}).get("summary_metrics", {})
        return MetricsResult(
            success=True,
            impressions=totals.get("IMPRESSION", 0), saves=totals.get("SAVE", 0),
            shares=totals.get("PIN_CLICK", 0),
            raw_response=data,
        )


# ── Threads ───────────────────────────────────────────────

class ThreadsMetricsFetcher(MetricsFetcher):
    """Threads API — Media Insights."""

    BASE = "https://graph.threads.net/v1.0"

    async def fetch(self, platform_post_id: str) -> MetricsResult:
        token = self.credentials.get("access_token")
        if not token:
            return MetricsResult(success=False, error="Threads: нет access_token")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE}/{platform_post_id}/insights",
                params={"metric": "views,likes,replies,reposts,quotes", "access_token": token},
            )

        if resp.status_code >= 400:
            return MetricsResult(success=False, error=f"Threads {resp.status_code}: {resp.text[:200]}")
        data   = resp.json()
        values = {m["name"]: (m.get("values", [{}])[-1].get("value", 0)) for m in data.get("data", [])}
        return MetricsResult(
            success=True,
            views=values.get("views", 0), likes=values.get("likes", 0),
            comments=values.get("replies", 0), shares=values.get("reposts", 0) + values.get("quotes", 0),
            raw_response=data,
        )


# ── Twitter / X ───────────────────────────────────────────

class TwitterMetricsFetcher(MetricsFetcher):
    """Twitter API v2 — public_metrics."""

    BASE = "https://api.twitter.com/2"

    async def fetch(self, platform_post_id: str) -> MetricsResult:
        token = self.credentials.get("access_token")
        if not token:
            return MetricsResult(success=False, error="Twitter: нет access_token")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE}/tweets/{platform_post_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"tweet.fields": "public_metrics"},
            )

        if resp.status_code >= 400:
            return MetricsResult(success=False, error=f"Twitter {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        pm   = data.get("data", {}).get("public_metrics", {})
        return MetricsResult(
            success=True,
            impressions=pm.get("impression_count", 0),
            likes=pm.get("like_count", 0), comments=pm.get("reply_count", 0),
            shares=pm.get("retweet_count", 0) + pm.get("quote_count", 0),
            raw_response=data,
        )


# ── LinkedIn ──────────────────────────────────────────────

class LinkedInMetricsFetcher(MetricsFetcher):
    """LinkedIn Social Actions API — лайки/комменты (impressions требуют org-level API)."""

    BASE = "https://api.linkedin.com/v2"

    async def fetch(self, platform_post_id: str) -> MetricsResult:
        token = self.credentials.get("access_token")
        if not token:
            return MetricsResult(success=False, error="LinkedIn: нет access_token")

        urn = platform_post_id if platform_post_id.startswith("urn:") else f"urn:li:ugcPost:{platform_post_id}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE}/socialActions/{urn}",
                headers={"Authorization": f"Bearer {token}", "X-Restli-Protocol-Version": "2.0.0"},
            )

        if resp.status_code >= 400:
            return MetricsResult(success=False, error=f"LinkedIn {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return MetricsResult(
            success=True,
            likes=data.get("likesSummary", {}).get("totalLikes", 0),
            comments=data.get("commentsSummary", {}).get("totalFirstLevelComments", 0),
            raw_response=data,
        )


METRICS_FETCHERS: dict[str, type[MetricsFetcher]] = {
    "tiktok":    TikTokMetricsFetcher,
    "youtube":   YouTubeMetricsFetcher,
    "instagram": InstagramMetricsFetcher,
    "facebook":  FacebookMetricsFetcher,
    "pinterest": PinterestMetricsFetcher,
    "threads":   ThreadsMetricsFetcher,
    "twitter":   TwitterMetricsFetcher,
    "x":         TwitterMetricsFetcher,
    "linkedin":  LinkedInMetricsFetcher,
}


# ── Оркестрация синхронизации ──────────────────────────────

class PostAnalyticsAgent:
    """A36 — синхронизирует нативные метрики опубликованных постов в post_metrics."""

    def __init__(self, db: Client):
        self.db = db

    def _credentials(self, account_id: Optional[str], platform: str) -> dict:
        q = (
            self.db.table("direct_publish_accounts")
            .select("access_token,refresh_token,platform_user_id,extra_data")
            .eq("platform", platform)
            .eq("is_active", True)
        )
        if account_id:
            q = q.eq("account_id", account_id)
        res = rows(q.limit(1).execute())
        if not res:
            return {}
        row   = res[0]
        creds = {"access_token": row.get("access_token"), "refresh_token": row.get("refresh_token")}
        creds.update(row.get("extra_data") or {})
        return creds

    def _published_jobs(self, platform: Optional[str], limit: int) -> list[dict]:
        q = (
            self.db.table("direct_publish_jobs")
            .select("id,account_id,platform,platform_post_id,published_at")
            .eq("status", "published")
            .order("published_at", desc=True)
            .limit(limit)
        )
        if platform:
            q = q.eq("platform", platform)
        return rows(q.execute())

    async def sync(self, platform: Optional[str] = None, limit: int = 100) -> dict:
        jobs = self._published_jobs(platform, limit)
        synced, failed, skipped = 0, 0, 0
        details: list[dict] = []

        for job in jobs:
            post_id = job.get("platform_post_id")
            plat    = (job.get("platform") or "").lower()
            if not post_id or not plat:
                skipped += 1
                continue

            fetcher_cls = METRICS_FETCHERS.get(plat)
            if not fetcher_cls:
                skipped += 1
                continue

            creds   = self._credentials(job.get("account_id"), plat)
            fetcher = fetcher_cls(creds)
            result  = await fetcher.fetch(post_id)

            if not result.success:
                failed += 1
                details.append({"job_id": job["id"], "platform": plat, "error": result.error})
                continue

            self.db.table("post_metrics").insert({
                "direct_job_id":   job["id"],
                "account_id":      job.get("account_id"),
                "platform":        plat,
                "platform_post_id": post_id,
                "impressions":     result.impressions,
                "reach":           result.reach,
                "views":           result.views,
                "likes":           result.likes,
                "comments":        result.comments,
                "shares":          result.shares,
                "saves":           result.saves,
                "engagement_rate": result.engagement_rate,
                "raw_response":    result.raw_response or {},
            }).execute()

            synced += 1
            details.append({
                "job_id": job["id"], "platform": plat,
                "engagement_rate": result.engagement_rate,
            })

        logger.info(
            "POST_ANALYTICS: sync завершён — synced=%d failed=%d skipped=%d",
            synced, failed, skipped,
        )
        return {"synced": synced, "failed": failed, "skipped": skipped, "total": len(jobs), "details": details}


# ── Точка входа ───────────────────────────────────────────

async def run_post_analytics(platform: Optional[str] = None, limit: int = 100) -> dict:
    db    = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    agent = PostAnalyticsAgent(db)
    return await agent.sync(platform=platform, limit=limit)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_post_analytics())
