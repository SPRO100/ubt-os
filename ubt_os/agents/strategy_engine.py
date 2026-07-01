"""
A15 — STRATEGY_ENGINE
Определяет что производить следующие 7 дней.
Запускается через n8n webhook: POST /strategy/collect
"""
from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import create_client, Client
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import extract_json as _extract_json
from ubt_os.utils.supabase_utils import one_row

logger = logging.getLogger("ubt_os.strategy_engine")

# ── Supabase клиент ───────────────────────────────────────
def get_db() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )

# ── Сбор входных данных ───────────────────────────────────
class StrategyDataCollector:

    def __init__(self, db: Client, lookback_days: int = 7):
        self.db = db
        self.since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    async def collect(self) -> dict[str, Any]:
        trends      = self._fetch_trends()
        analytics   = self._fetch_analytics()
        revenue     = self._fetch_revenue()
        competitors = self._fetch_competitors()
        knowledge   = self._fetch_knowledge()

        return {
            "trends":      trends,
            "analytics":   analytics,
            "revenue":     revenue,
            "competitors": competitors,
            "knowledge":   knowledge,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    def _fetch_trends(self) -> list:
        res = (
            self.db.table("trend_signals")
            .select("*")
            .gte("created_at", self.since)
            .order("score", desc=True)
            .limit(20)
            .execute()
        )
        return res.data

    def _fetch_analytics(self) -> list:
        res = (
            self.db.table("video_analytics")
            .select("platform,vertical,geo,format_type,completion_rate,er,ctr,views")
            .gte("created_at", self.since)
            .execute()
        )
        return res.data

    def _fetch_revenue(self) -> list:
        res = (
            self.db.table("revenue_events")
            .select("vertical,geo,platform,source_video_id,net_amount,partner")
            .gte("created_at", self.since)
            .execute()
        )
        return res.data

    def _fetch_competitors(self) -> list:
        res = (
            self.db.table("competitor_patterns")
            .select("vertical,geo,platform,hook_type,visual_style,views,er")
            .gte("created_at", self.since)
            .order("views", desc=True)
            .limit(30)
            .execute()
        )
        return res.data

    def _fetch_knowledge(self) -> list:
        res = (
            self.db.table("knowledge_entries")
            .select("*")
            .eq("type", "winning_pattern")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return res.data


# ── Claude анализ ─────────────────────────────────────────
class StrategyAnalyst:

    SYSTEM_PROMPT = """Ты — STRATEGY_ENGINE системы UBT OS.
Твоя задача: проанализировать данные за последние 7 дней и определить
стратегию производства контента на следующие 7 дней.

ПРАВИЛА:
- Только конкретные действия с числовым обоснованием.
- Каждый top_format должен иметь причину (поле reason) с цифрами.
- stop_formats — только форматы с completion_rate < 40% ИЛИ CR = 0.
- trend_windows — только тренды с expires_in_days < 7.
- confidence_score: 0.8+ если данных достаточно, ниже если мало данных.

ОТВЕТ: строго JSON, без пояснений вне JSON.

СХЕМА:
{
  "week": "2026-WXX",
  "vertical": "nutra|betting",
  "geo_priority": ["XX", ...],
  "platform_priority": ["tiktok|youtube|instagram", ...],
  "top_formats": [
    {"format": "...", "reason": "...", "priority": 1, "daily_quota": N}
  ],
  "stop_formats": ["..."],
  "scale_formats": ["..."],
  "trend_windows": [
    {"trend": "...", "opportunity": "...", "expires_in_days": N}
  ],
  "daily_queue": [
    {"day": "Mon", "formats": [...], "geo": "XX", "platform": "..."}
  ],
  "risk_flags": ["..."],
  "confidence_score": 0.0
}"""

    def __init__(self):
        self.client = AsyncAnthropic()

    async def analyze(self, data: dict) -> dict:
        week_num = datetime.now(timezone.utc).isocalendar()[1]
        year     = datetime.now(timezone.utc).year

        resp = await self.client.messages.create(
            model   = "claude-sonnet-5",
            max_tokens = 4096,
            system  = self.SYSTEM_PROMPT,
            messages = [{
                "role":    "user",
                "content": (
                    f"Данные за последние 7 дней:\n\n"
                    f"ТРЕНДЫ ({len(data['trends'])} шт):\n{data['trends']}\n\n"
                    f"АНАЛИТИКА ({len(data['analytics'])} видео):\n{data['analytics']}\n\n"
                    f"ДОХОД ({len(data['revenue'])} событий):\n{data['revenue']}\n\n"
                    f"КОНКУРЕНТЫ ({len(data['competitors'])} паттернов):\n{data['competitors']}\n\n"
                    f"ИСТОРИЯ ({len(data['knowledge'])} паттернов):\n{data['knowledge']}\n\n"
                    f"Сгенерируй Strategic Brief для {year}-W{week_num:02d}."
                )
            }],
        )

        brief = _extract_json(resp.content[0].text)
        brief["raw_json"]  = brief.copy()
        brief["week_label"] = f"{year}-W{week_num:02d}"
        return brief


# ── Сохранение ────────────────────────────────────────────
class StrategyWriter:

    def __init__(self, db: Client):
        self.db = db

    def save_brief(self, brief: dict) -> int:
        res = (
            self.db.table("strategy_briefs")
            .insert({
                "week_label":        brief["week_label"],
                "vertical":          brief.get("vertical", "nutra"),
                "geo_priority":      brief.get("geo_priority", []),
                "platform_priority": brief.get("platform_priority", []),
                "top_formats":       brief.get("top_formats", []),
                "stop_formats":      brief.get("stop_formats", []),
                "scale_formats":     brief.get("scale_formats", []),
                "trend_windows":     brief.get("trend_windows", []),
                "risk_flags":        brief.get("risk_flags", []),
                "confidence_score":  brief.get("confidence_score"),
                "raw_json":          brief.get("raw_json"),
                "approved_by_user":  False,
            })
            .execute()
        )
        brief_id = one_row(res)["id"]
        self._save_daily_queues(brief_id, brief)
        return brief_id

    def _save_daily_queues(self, brief_id: int, brief: dict):
        rows = []
        today = datetime.now(timezone.utc).date()

        for i, entry in enumerate(brief.get("daily_queue", [])):
            date = today + timedelta(days=i)
            rows.append({
                "date":               date.isoformat(),
                "strategy_brief_id":  brief_id,
                "vertical":           brief.get("vertical", "nutra"),
                "platform":           (brief.get("platform_priority") or ["tiktok"])[0],
                "geo":                entry.get("geo", "PL"),
                "formats":            entry.get("formats", []),
                "status":             "pending",
            })

        if rows:
            self.db.table("daily_queues").upsert(rows, on_conflict="date,vertical,platform,geo").execute()

    def to_markdown(self, brief: dict) -> str:
        lines = [
            "---",
            "type: daily",
            "tags: [type/strategy, project/ubt-os]",
            f"created: {datetime.now(timezone.utc).date()}",
            "---",
            "",
            f"# 🧭 Strategy Brief — {brief.get('week_label')}",
            "",
            f"**Вертикаль:** {brief.get('vertical')} | "
            f"**ГЕО:** {', '.join(brief.get('geo_priority', []))} | "
            f"**Уверенность:** {int(brief.get('confidence_score',0)*100)}%",
            "",
            "## Топ форматы",
        ]
        for fmt in brief.get("top_formats", []):
            lines.append(f"- **{fmt['format']}** (приоритет {fmt['priority']}, {fmt['daily_quota']}/день) — {fmt['reason']}")
        lines += [
            "",
            "## Масштабировать",
        ]
        for s in brief.get("scale_formats", []):
            lines.append(f"- {s}")
        lines += [
            "",
            "## Остановить",
        ]
        for s in brief.get("stop_formats", []):
            lines.append(f"- {s}")
        lines += [
            "",
            "## Тренд-окна",
        ]
        for tw in brief.get("trend_windows", []):
            lines.append(f"- **{tw['trend']}** — {tw['opportunity']} (истекает через {tw['expires_in_days']} дн.)")
        lines += [
            "",
            "## Флаги рисков",
        ]
        for r in brief.get("risk_flags", []):
            lines.append(f"- ⚠️ {r}")
        return "\n".join(lines)


# ── Точка входа (вызывается из n8n через webhook) ─────────
async def run_strategy_engine(lookback_days: int = 7) -> dict:
    db        = get_db()
    collector = StrategyDataCollector(db, lookback_days)
    analyst   = StrategyAnalyst()
    writer    = StrategyWriter(db)

    logger.info("STRATEGY_ENGINE: сбор данных...")
    data = await collector.collect()

    logger.info("STRATEGY_ENGINE: анализ (Claude Sonnet)...")
    brief = await analyst.analyze(data)

    logger.info("STRATEGY_ENGINE: сохранение...")
    brief_id = writer.save_brief(brief)

    brief["markdown_report"] = writer.to_markdown(brief)
    brief["brief_id"]        = brief_id

    logger.info(f"STRATEGY_ENGINE: готово ✅ id={brief_id} confidence={brief.get('confidence_score')}")
    return brief


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_strategy_engine())
