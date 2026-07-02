"""
A16 — REVENUE_ANALYST
Объясняет доход, находит утечки в воронке,
сравнивает партнёрок и выявляет кандидатов на масштабирование.
"""
from __future__ import annotations
import asyncio, logging, os, json
from datetime import datetime, timedelta, timezone
from typing import Any
from supabase import create_client, Client

from ubt_os.utils.llm_utils import response_text
from ubt_os.utils.supabase_utils import one_row
from anthropic import AsyncAnthropic

logger = logging.getLogger("ubt_os.revenue_analyst")

FUNNEL_BENCHMARKS = {
    "tiktok":    {"ctr": 0.025, "cr": 0.032, "approval": 0.85},
    "youtube":   {"ctr": 0.032, "cr": 0.025, "approval": 0.90},
    "instagram": {"ctr": 0.018, "cr": 0.022, "approval": 0.85},
}

# ── Сбор данных ───────────────────────────────────────────
class RevenueDataCollector:

    def __init__(self, db: Client, period_days: int = 1):
        self.db   = db
        self.since = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

    def collect(self) -> dict[str, Any]:
        events      = self._events()
        daily_agg   = self._daily_aggregates()
        video_prof  = self._video_profitability()
        partner_cmp = self._partner_comparison()
        return {
            "events":       events,
            "daily":        daily_agg,
            "videos":       video_prof,
            "partners":     partner_cmp,
            "period_days":  1,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    def _events(self) -> list:
        return (self.db.table("revenue_events")
                .select("*").gte("created_at", self.since).execute()).data

    def _daily_aggregates(self) -> list:
        return (self.db.table("revenue_daily")
                .select("*")
                .gte("date", self.since[:10]).execute()).data

    def _video_profitability(self) -> list:
        return (self.db.table("video_profitability")
                .select("*")
                .order("roi", desc=True)
                .limit(20).execute()).data

    def _partner_comparison(self) -> list:
        return (self.db.table("partner_comparison")
                .select("*")
                .order("epc", desc=True).execute()).data


# ── Аналитика воронки ─────────────────────────────────────
class FunnelAnalyzer:

    def detect_leaks(self, daily_rows: list) -> list[dict]:
        leaks = []
        for row in daily_rows:
            platform   = row.get("platform", "tiktok")
            bench      = FUNNEL_BENCHMARKS.get(platform, FUNNEL_BENCHMARKS["tiktok"])
            actual_ctr = row.get("ctr", 0)
            actual_cr  = row.get("cr", 0)
            impressions= row.get("impressions", 1)
            clicks     = row.get("clicks", 0)

            cr_gap, upside = 0.0, 0.0

            if actual_ctr and actual_ctr < bench["ctr"] * 0.8:
                ideal_clicks= int(impressions * bench["ctr"])
                extra_clicks = ideal_clicks - clicks
                upside      += extra_clicks * actual_cr * float(row.get("avg_payout", 40))
                leaks.append({
                    "type":     "weak_cta",
                    "platform": platform,
                    "geo":      row.get("geo"),
                    "partner":  row.get("partner"),
                    "actual":   round(actual_ctr * 100, 2),
                    "benchmark":round(bench["ctr"] * 100, 2),
                    "upside":   round(upside, 2),
                    "action":   "Заменить CTA в видео с CTR < 2%",
                })

            if actual_cr and actual_cr < bench["cr"] * 0.8:
                cr_gap  = bench["cr"] - actual_cr
                upside2 = clicks * cr_gap * float(row.get("avg_payout", 40))
                leaks.append({
                    "type":     "weak_prelander",
                    "platform": platform,
                    "geo":      row.get("geo"),
                    "partner":  row.get("partner"),
                    "actual":   round(actual_cr * 100, 2),
                    "benchmark":round(bench["cr"] * 100, 2),
                    "upside":   round(upside2, 2),
                    "action":   "A/B тест прелендинга или смена оффера",
                })

        return sorted(leaks, key=lambda x: x["upside"], reverse=True)

    def detect_scaling_candidates(self, videos: list) -> list[dict]:
        candidates = []
        for v in videos:
            roi = v.get("roi", 0)
            rev = float(v.get("total_revenue", 0))
            if roi and roi > 300 and rev > 50:
                candidates.append({
                    "video_id":   v["video_id"],
                    "platform":   v.get("platform"),
                    "geo":        v.get("geo"),
                    "roi":        round(roi, 1),
                    "revenue":    round(rev, 2),
                    "rev_per_view": round(v.get("revenue_per_view", 0), 4),
                    "reason":     f"ROI {round(roi)}% при ${round(rev,2)} дохода",
                })
        return sorted(candidates, key=lambda x: x["roi"], reverse=True)[:5]


# ── Claude-анализ и генерация отчёта ─────────────────────
class RevenueReportGenerator:

    SYSTEM_PROMPT = """Ты — REVENUE_ANALYST системы UBT OS.
Анализируй данные и давай КОНКРЕТНЫЕ объяснения дохода.

ПРАВИЛА:
- Каждое утверждение подкреплено цифрой.
- Без фраз "возможно", "может быть", "рекомендуется" — только конкретика.
- Секция "Масштабировать" — только если ROI > 300% И revenue > $50.
- Секция "Остановить" — только если CR = 0 за 3+ дня подряд.

ОБЯЗАТЕЛЬНЫЕ СЕКЦИИ:
1. summary (3-4 предложения: что произошло)
2. what_worked (список с цифрами)
3. what_failed (список с причинами)
4. funnel_leaks (утечки с upside $$$)
5. scale_now (топ-3 кандидата)
6. stop_now (что отключить)
7. forecast_7d (прогноз на 7 дней)

ФОРМАТ: JSON с полем markdown_report."""

    def __init__(self):
        self.client = AsyncAnthropic()

    async def generate(self, data: dict, leaks: list, candidates: list) -> dict:
        payload = {**data, "funnel_leaks": leaks, "scaling_candidates": candidates}
        resp = await self.client.messages.create(
            model      = "claude-sonnet-5",
            max_tokens = 4096,
            system     = self.SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
        )
        result = json.loads(response_text(resp))
        result["markdown_report"] = self._to_markdown(result)
        return result

    @staticmethod
    def _to_markdown(r: dict) -> str:
        d = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines = [
            f"---\ntype: daily\ntags: [revenue, ubt-os]\ndate: {d}\n---\n",
            f"# 💰 Revenue Report — {d}\n",
            f"## Сводка\n{r.get('summary','')}\n",
            "## Что сработало",
        ]
        for w in r.get("what_worked", []):
            lines.append(f"- ✅ {w}")
        lines += ["\n## Что не сработало"]
        for f in r.get("what_failed", []):
            lines.append(f"- ❌ {f}")
        lines += ["\n## Утечки воронки"]
        for leak in r.get("funnel_leaks", []):
            lines.append(
                f"- ⚠️ **{leak.get('type')}** [{leak.get('platform')}/{leak.get('geo')}] "
                f"— потенциал +${leak.get('upside',0):.0f} | {leak.get('action')}"
            )
        lines += ["\n## Масштабировать сейчас"]
        for sc in r.get("scale_now", []):
            lines.append(f"- 🚀 {sc}")
        lines += ["\n## Остановить"]
        for st in r.get("stop_now", []):
            lines.append(f"- 🛑 {st}")
        lines += [f"\n## Прогноз 7 дней\n{r.get('forecast_7d','')}"]
        return "\n".join(lines)


# ── Writer ────────────────────────────────────────────────
class RevenueWriter:

    def __init__(self, db: Client):
        self.db = db

    def save_report(self, report: dict, report_type: str = "daily") -> int:
        res = (self.db.table("revenue_reports").insert({
            "report_date":    datetime.now(timezone.utc).date().isoformat(),
            "report_type":    report_type,
            "raw_json":       report,
            "markdown_report":report.get("markdown_report",""),
            "key_insights":   report.get("what_worked",[])[:3],
            "scale_alerts":   report.get("scale_now",[]),
            "leak_alerts":    report.get("funnel_leaks",[]),
        }).execute())
        return one_row(res)["id"]

    def update_video_profitability(self, candidates: list):
        for c in candidates:
            self.db.table("video_profitability").upsert({
                "video_id":             c["video_id"],
                "is_scaling_candidate": True,
                "scaling_reason":       c["reason"],
            }, on_conflict="video_id,partner").execute()

    def format_telegram(self, report: dict, leaks: list, candidates: list) -> str:
        total  = sum(float(e.get("net_amount",0)) for e in report.get("events",[]))
        n_conv = len([e for e in report.get("events",[]) if e.get("status")=="approved"])
        top_up = sum(leak.get("upside",0) for leak in leaks[:2])
        lines  = [
            "💰 *REVENUE REPORT*",
            f"Доход: *${total:.2f}* | Конверсий: *{n_conv}*",
        ]
        if candidates:
            lines.append(f"🚀 Масштабировать: *{candidates[0]['video_id'][:20]}* (ROI {candidates[0]['roi']:.0f}%)")
        if leaks:
            lines.append(f"⚠️ Утечка воронки: потенциал +${top_up:.0f}")
        lines.append("📋 Полный отчёт в Obsidian")
        return "\n".join(lines)


# ── Точка входа ───────────────────────────────────────────
async def run_revenue_analyst(period_days: int = 1) -> dict:
    db        = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    collector = RevenueDataCollector(db, period_days)
    analyzer  = FunnelAnalyzer()
    generator = RevenueReportGenerator()
    writer    = RevenueWriter(db)

    logger.info("REVENUE_ANALYST: сбор данных...")
    data       = collector.collect()

    logger.info("REVENUE_ANALYST: анализ воронки...")
    leaks      = analyzer.detect_leaks(data["daily"])
    candidates = analyzer.detect_scaling_candidates(data["videos"])

    logger.info("REVENUE_ANALYST: генерация отчёта (Claude Sonnet)...")
    report     = await generator.generate(data, leaks, candidates)

    logger.info("REVENUE_ANALYST: сохранение...")
    report_id  = writer.save_report(report)
    writer.update_video_profitability(candidates)

    report["report_id"]   = report_id
    report["telegram_msg"]= writer.format_telegram(report, leaks, candidates)
    logger.info(f"REVENUE_ANALYST: готово ✅ id={report_id}")
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_revenue_analyst())
