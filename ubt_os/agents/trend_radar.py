"""
A32 — TREND_RADAR
Тренды звуков и хэштегов TikTok: собирает (или принимает) трендовые сигналы,
ранжирует их через Claude под конкретную вертикаль/GEO и выдаёт actionable-бриф
«на чём ехать прямо сейчас». Дополняет A20 trend_scraper и A15 strategy_engine.

Источник трендов (по приоритету):
  1. HTTP-эндпоинт TREND_SOURCE_URL (self-hosted, напр. TikTok Creative Center прокси)
  2. Данные, переданные в запросе (hashtags / sounds)

Запуск: POST /trends/radar
"""
from __future__ import annotations
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from anthropic import AsyncAnthropic
from supabase import create_client, Client

from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.trend_radar")

SYSTEM_PROMPT = """Ты — TREND_RADAR аналитик коротких видео (TikTok/Reels) для affiliate-маркетинга.
Тебе дают список трендовых хэштегов и звуков с темпом роста. Оцени каждый под конкретную
вертикаль и GEO: подходит ли он, на какой стадии жизненного цикла, как его обыграть.

Ранний тренд (растёт, но ещё не на пике) ценнее «горячего» — окно 3–5 дней до пика.

ОТВЕТ: строго JSON без пояснений вне JSON.

СХЕМА:
{
  "ranked": [
    {
      "kind": "hashtag|sound",
      "name": "#... или название звука",
      "growth_pct": число,
      "rank": 1,
      "fit": "high|medium|low",
      "stage": "early|rising|peak|declining",
      "recommendation": "как обыграть под нашу вертикаль (1 фраза)"
    }
  ],
  "top_pick": "что взять в работу в первую очередь и почему",
  "avoid": ["на чём НЕ ехать и почему"]
}"""


@dataclass
class TrendRadarResult:
    vertical: str
    geo: str
    platform: str
    ranked: list[dict]
    top_pick: str
    avoid: list[str]
    source: str
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _get_db() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


async def _fetch_trends(source_url: str, geo: str, platform: str) -> dict:
    """Тянет трендовые хэштеги/звуки из настраиваемого источника.

    Ожидаемый ответ: {"hashtags": [{"name","growth_pct"}...], "sounds": [...]}.
    Возвращает {"hashtags": [], "sounds": []} при любой ошибке (graceful).
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(source_url, params={"geo": geo, "platform": platform})
            resp.raise_for_status()
            data = resp.json()
            return {
                "hashtags": data.get("hashtags", []) or [],
                "sounds":   data.get("sounds", []) or [],
            }
    except Exception as e:
        logger.warning("trend_radar: источник %s недоступен: %s", source_url, e)
        return {"hashtags": [], "sounds": []}


def _as_items(hashtags: list, sounds: list) -> list[dict]:
    """Нормализует вход в единый список сигналов [{kind,name,growth_pct}]."""
    items: list[dict] = []
    for h in hashtags or []:
        if isinstance(h, str) and h.strip():
            items.append({"kind": "hashtag", "name": h.strip(), "growth_pct": 0.0})
        elif isinstance(h, dict) and h.get("name"):
            items.append({"kind": "hashtag", "name": h["name"], "growth_pct": float(h.get("growth_pct", 0) or 0)})
    for s in sounds or []:
        if isinstance(s, str) and s.strip():
            items.append({"kind": "sound", "name": s.strip(), "growth_pct": 0.0})
        elif isinstance(s, dict) and s.get("name"):
            items.append({"kind": "sound", "name": s["name"], "growth_pct": float(s.get("growth_pct", 0) or 0)})
    return items


class TrendRadar:

    def __init__(self):
        self.llm = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    async def analyze(self, items: list[dict], vertical: str, geo: str) -> dict:
        if not items:
            return {"ranked": [], "top_pick": "", "avoid": []}
        listing = "\n".join(
            f"- [{it['kind']}] {it['name']} (рост {it.get('growth_pct', 0)}%)" for it in items[:40]
        )
        resp = await self.llm.messages.create(
            model="claude-sonnet-5",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Вертикаль: {vertical} | GEO: {geo}\n\n"
                    f"ТРЕНДОВЫЕ СИГНАЛЫ:\n{listing}\n\n"
                    f"Проранжируй и дай бриф."
                ),
            }],
        )
        return _extract_json(getattr(resp.content[0], "text", ""), fallback={
            "ranked": [{"kind": it["kind"], "name": it["name"],
                        "growth_pct": it.get("growth_pct", 0), "rank": i + 1,
                        "fit": "medium", "stage": "rising", "recommendation": ""}
                       for i, it in enumerate(items[:10])],
            "top_pick": "",
            "avoid": [],
        })


def _persist(db: Client, result: TrendRadarResult) -> None:
    rows = [{
        "vertical":       result.vertical,
        "geo":            result.geo,
        "platform":       result.platform,
        "kind":           r.get("kind", "hashtag"),
        "name":           r.get("name", ""),
        "growth_pct":     float(r.get("growth_pct", 0) or 0),
        "rank":           int(r.get("rank", 0) or 0),
        "recommendation": r.get("recommendation", ""),
    } for r in result.ranked if r.get("name")]
    if rows:
        db.table("trend_signals").insert(rows).execute()


async def run_trend_radar(
    vertical: str = "nutra",
    geo: str = "US",
    platform: str = "tiktok",
    hashtags: list | None = None,
    sounds: list | None = None,
    persist: bool = True,
) -> dict:
    """Точка входа для /trends/radar."""
    source = "input"
    source_url = os.getenv("TREND_SOURCE_URL")
    if source_url and not (hashtags or sounds):
        fetched = await _fetch_trends(source_url, geo, platform)
        hashtags, sounds = fetched["hashtags"], fetched["sounds"]
        source = source_url

    items = _as_items(hashtags or [], sounds or [])
    if not items:
        return {"error": "нет трендовых данных: задай TREND_SOURCE_URL или передай hashtags/sounds",
                "vertical": vertical, "geo": geo}

    analysis = await TrendRadar().analyze(items, vertical, geo)
    result = TrendRadarResult(
        vertical=vertical, geo=geo, platform=platform,
        ranked=analysis.get("ranked", []),
        top_pick=analysis.get("top_pick", ""),
        avoid=analysis.get("avoid", []),
        source=source,
    )

    if persist:
        try:
            _persist(_get_db(), result)
        except Exception as e:
            logger.warning("trend_radar: не удалось записать trend_signals: %s", e)

    logger.info("trend_radar | vertical=%s geo=%s items=%d ranked=%d",
                vertical, geo, len(items), len(result.ranked))
    return {
        "vertical": result.vertical,
        "geo": result.geo,
        "platform": result.platform,
        "ranked": result.ranked,
        "top_pick": result.top_pick,
        "avoid": result.avoid,
        "source": result.source,
        "analyzed_at": result.analyzed_at,
    }
