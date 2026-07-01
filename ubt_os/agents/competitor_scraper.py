"""
A33 — COMPETITOR_SCRAPER
Автоматический сбор крипов конкурентов: тонкий клиент к self-hosted scraper-API
(совместимому с Douyin_TikTok_Download_API). Тянет топ-видео по хэштегу/ключу,
нормализует и пишет в таблицу competitor_signals — которую читает A31
competitor_analyst. Замыкает разрыв: раньше крипы заносили вручную.

Требует env TIKTOK_SCRAPER_URL — адрес развёрнутого scraper-сервиса.
Запуск: POST /competitor/scrape
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from supabase import create_client, Client

logger = logging.getLogger("ubt_os.competitor_scraper")


def _get_db() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def _dig(obj: Any, *path, default=None):
    """Безопасно достаёт вложенное значение по пути ключей/индексов."""
    cur = obj
    for key in path:
        try:
            cur = cur[key]
        except (KeyError, IndexError, TypeError):
            return default
    return cur if cur is not None else default


def _extract_items(payload: Any) -> list[dict]:
    """Достаёт список видео из ответа scraper-API (разные обёртки)."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("data", "aweme_list", "videos", "items", "result"):
            val = payload.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
            if isinstance(val, dict):
                for k2 in ("aweme_list", "videos", "items"):
                    if isinstance(val.get(k2), list):
                        return [x for x in val[k2] if isinstance(x, dict)]
    return []


def _normalize(raw: dict, vertical: str, geo: str, platform: str) -> dict | None:
    """Приводит элемент scraper-API к строке competitor_signals.

    Устойчив к разным схемам (Douyin/TikTok). Требуется хотя бы video_url.
    """
    video_url = (
        _dig(raw, "share_url")
        or _dig(raw, "video_url")
        or _dig(raw, "aweme_detail", "share_url")
        or _dig(raw, "video", "play_addr", "url_list", 0)
    )
    if not video_url:
        return None

    title = _dig(raw, "desc") or _dig(raw, "title") or _dig(raw, "aweme_detail", "desc") or ""
    account = (
        _dig(raw, "author", "nickname")
        or _dig(raw, "author", "unique_id")
        or _dig(raw, "aweme_detail", "author", "nickname")
        or ""
    )
    thumb = (
        _dig(raw, "video", "cover", "url_list", 0)
        or _dig(raw, "cover")
        or _dig(raw, "thumbnail_url")
    )
    stats = raw.get("statistics") or raw.get("stats") or {}
    plays = int(_dig(stats, "play_count", default=0) or _dig(raw, "views", default=0) or 0)
    likes = int(_dig(stats, "digg_count", default=0) or 0)
    comments = int(_dig(stats, "comment_count", default=0) or 0)
    shares = int(_dig(stats, "share_count", default=0) or 0)
    er = round((likes + comments + shares) / plays, 4) if plays > 0 else 0.0

    return {
        "vertical":      vertical,
        "geo":           geo,
        "platform":      platform,
        "video_url":     video_url,
        "thumbnail_url": thumb,
        "title":         title[:500] if title else "",
        "account_name":  account[:200] if account else "",
        "views":         plays,
        "er":            er,
        "scraped_at":    datetime.now(timezone.utc).isoformat(),
    }


class CompetitorScraper:

    def __init__(self, scraper_url: str | None = None):
        self.scraper_url = (scraper_url or os.getenv("TIKTOK_SCRAPER_URL") or "").rstrip("/")

    async def fetch(self, query: str, limit: int = 20) -> list[dict]:
        """Запрашивает у scraper-сервиса топ-видео по хэштегу/ключу."""
        if not self.scraper_url:
            raise RuntimeError("TIKTOK_SCRAPER_URL не задан")
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(self.scraper_url, params={"query": query, "count": limit})
            resp.raise_for_status()
            return _extract_items(resp.json())


async def run_competitor_scrape(
    query: str,
    vertical: str = "nutra",
    geo: str = "US",
    platform: str = "tiktok",
    limit: int = 20,
    persist: bool = True,
) -> dict:
    """Точка входа для /competitor/scrape. Пишет в competitor_signals (для A31)."""
    if not query:
        return {"error": "query (хэштег/ключ) обязателен"}
    if not os.getenv("TIKTOK_SCRAPER_URL"):
        return {"error": "TIKTOK_SCRAPER_URL не задан — разверни scraper-сервис (Douyin_TikTok_Download_API)"}

    try:
        raw_items = await CompetitorScraper().fetch(query, limit)
    except Exception as e:
        logger.warning("competitor_scrape: ошибка scraper-API: %s", e)
        return {"error": f"scraper недоступен: {e}"}

    signals = [s for s in (_normalize(r, vertical, geo, platform) for r in raw_items) if s]

    inserted = 0
    if persist and signals:
        try:
            db = _get_db()
            # upsert: не дублируем по video_url (уникальный constraint)
            res = db.table("competitor_signals").upsert(
                signals, on_conflict="video_url", ignore_duplicates=True
            ).execute()
            inserted = len(res.data) if res.data else 0
        except Exception as e:
            logger.warning("competitor_scrape: запись competitor_signals не удалась: %s", e)

    logger.info("competitor_scrape | query=%s vertical=%s собрано=%d записано=%d",
                query, vertical, len(signals), inserted)
    return {
        "query": query,
        "vertical": vertical,
        "geo": geo,
        "platform": platform,
        "scraped": len(signals),
        "inserted": inserted,
        "signals": signals[:limit],
        "next": "запусти A31 competitor_analyst для анализа собранных крипов",
    }
