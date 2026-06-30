"""
A20 — TREND_SCRAPER
Мониторинг конкурентов и трендов по GEO через Firecrawl API.
Ежедневно 06:00 + по требованию.
Результаты → Supabase (trend_signals) + Obsidian vault.
"""
from __future__ import annotations
import asyncio, logging, os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import httpx
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.trend_scraper")

FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"

ANALYSIS_PROMPT = """Ты — аналитик контента для affiliate-маркетинга (betting / nutra).

Проанализируй скрапированный контент и извлеки структурированные данные.

ФОРМАТ ОТВЕТА (строго JSON):
{
  "hooks": [
    {"text": "...", "format": "question|shock|transformation|number|ugc", "strength": 1-10}
  ],
  "content_formats": ["before_after", "ugc_reaction", "educational", "meme"],
  "audience_pains": ["боль 1", "боль 2"],
  "cta_patterns": ["CTA паттерн 1"],
  "posting_signals": {"frequency": "N/day", "best_time": "HH:MM UTC"},
  "trend_score": 1-10,
  "vertical_fit": {"nutra": 1-10, "betting": 1-10},
  "geo_relevance": {"US": 1-10, "BR": 1-10, "MX": 1-10, "DE": 1-10, "PL": 1-10},
  "action_items": ["Что добавить в стратегию UBT OS"]
}"""


@dataclass
class TrendSignal:
    source_url: str
    geo: str
    vertical: str
    hooks: list[dict]
    content_formats: list[str]
    audience_pains: list[str]
    cta_patterns: list[str]
    trend_score: int
    action_items: list[str]
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FirecrawlClient:

    def __init__(self):
        self.api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def scrape(self, url: str) -> dict[str, Any]:
        if not self.api_key:
            logger.warning("FIRECRAWL_API_KEY не задан, используется заглушка")
            return {"markdown": "", "metadata": {"title": url}}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FIRECRAWL_BASE}/scrape",
                headers=self.headers,
                json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
            )
            resp.raise_for_status()
            return resp.json().get("data", {})

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        if not self.api_key:
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FIRECRAWL_BASE}/search",
                headers=self.headers,
                json={"query": query, "limit": limit},
            )
            resp.raise_for_status()
            return resp.json().get("data", [])


class TrendScraper:

    def __init__(self):
        self.firecrawl = FirecrawlClient()
        self.llm = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    async def analyze_url(self, url: str, geo: str = "US", vertical: str = "nutra") -> TrendSignal:
        scraped = await self.firecrawl.scrape(url)
        content = scraped.get("markdown", "")[:4000]

        if not content:
            logger.warning("Пустой контент для %s", url)
            content = f"URL: {url} — контент недоступен"

        response = await self.llm.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=ANALYSIS_PROMPT,
            messages=[{"role": "user", "content": f"GEO: {geo} | Вертикаль: {vertical}\n\nКонтент:\n{content}"}],
        )

        data = _extract_json(response.content[0].text, fallback={
            "hooks": [], "content_formats": [], "audience_pains": [],
            "cta_patterns": [], "trend_score": 0, "action_items": [],
        })

        signal = TrendSignal(
            source_url=url,
            geo=geo,
            vertical=vertical,
            hooks=data.get("hooks", []),
            content_formats=data.get("content_formats", []),
            audience_pains=data.get("audience_pains", []),
            cta_patterns=data.get("cta_patterns", []),
            trend_score=data.get("trend_score", 0),
            action_items=data.get("action_items", []),
        )

        logger.info("trend_scraper | url=%s geo=%s score=%d", url, geo, signal.trend_score)
        return signal

    async def find_trends(self, vertical: str, geo: str, limit: int = 5) -> list[TrendSignal]:
        queries = {
            "nutra": f"weight loss supplement review {geo} site:tiktok.com OR site:instagram.com",
            "betting": f"sports betting tips {geo} site:tiktok.com OR site:instagram.com",
        }
        query = queries.get(vertical, f"{vertical} {geo}")
        results = await self.firecrawl.search(query, limit=limit)

        tasks = [
            self.analyze_url(r["url"], geo=geo, vertical=vertical)
            for r in results if r.get("url")
        ]
        return await asyncio.gather(*tasks)

    async def competitor_audit(self, urls: list[str], geo: str, vertical: str) -> list[TrendSignal]:
        tasks = [self.analyze_url(url, geo=geo, vertical=vertical) for url in urls]
        return await asyncio.gather(*tasks)


async def run(vertical: str = "nutra", geo: str = "US") -> list[TrendSignal]:
    scraper = TrendScraper()
    return await scraper.find_trends(vertical=vertical, geo=geo)
