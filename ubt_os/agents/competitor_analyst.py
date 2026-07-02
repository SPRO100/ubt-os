"""
A31 — COMPETITOR_ANALYST
Мониторинг конкурентов: сбор паттернов, анализ хуков, выявление трендов.
Дополняет A27 spy_analyzer (анализ хуков на собственном LLM-пайплайне).

Запуск: POST /competitor/analyze
"""
from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from anthropic import AsyncAnthropic
from supabase import create_client, Client

from ubt_os.utils.llm_utils import extract_json as _extract_json
from ubt_os.utils.supabase_utils import rows, one_row

logger = logging.getLogger("ubt_os.competitor_analyst")

HOOK_TYPES = [
    "question",        # "Ты знаешь почему...?"
    "shock",           # "Это ЗАПРЕЩЕНО в России!"
    "stats",           # "97% людей не знают..."
    "story",           # "Три года назад я потерял всё..."
    "testimonial",     # "Я похудела на 12 кг за 30 дней"
    "before_after",    # До/После
    "countdown",       # "Через 3 дня это исчезнет"
    "controversy",     # Провокация / спорное мнение
    "curiosity",       # "Вот что происходит если..."
    "ugc_organic",     # Имитация пользовательского видео
]

VISUAL_STYLES = [
    "talking_head",    # Говорящая голова в кадре
    "voiceover_text",  # Закадровый голос + текст/графика
    "screen_record",   # Запись экрана
    "ugc_raw",         # "Сырое" UGC, без монтажа
    "animation",       # Анимация / motion graphics
    "slideshow",       # Слайды + нарезка
    "split_screen",    # Разделённый экран (до/после)
]


def _get_db() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


# ── Сбор конкурентных сигналов ────────────────────────────

class CompetitorSignalCollector:

    def __init__(self, db: Client, vertical: str, lookback_days: int = 3):
        self.db = db
        self.vertical = vertical
        self.since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    def collect(self) -> list[dict]:
        res = (
            self.db.table("competitor_signals")
            .select("id,platform,video_url,title,views,er,geo,account_name,created_at")
            .eq("vertical", self.vertical)
            .gte("created_at", self.since)
            .order("views", desc=True)
            .limit(50)
            .execute()
        )
        return rows(res)

    def get_existing_patterns(self) -> set[str]:
        """Уже проанализированные URL чтобы не дублировать."""
        res = (
            self.db.table("competitor_patterns")
            .select("source_video_url")
            .eq("vertical", self.vertical)
            .gte("created_at", self.since)
            .execute()
        )
        return {r["source_video_url"] for r in rows(res) if r.get("source_video_url")}


# ── Claude-анализ хука ─────────────────────────────────────

class HookAnalyzer:
    """
    Анализирует хук конкурентного видео по заголовку, описанию и метрикам.
    Если доступен thumbnail URL — передаёт его Claude Vision.
    """

    SYSTEM_PROMPT = """Ты — эксперт по анализу контента в сфере affiliate маркетинга (нутра, беттинг).
Твоя задача: проанализировать хук (первые 3-5 секунд) конкурентного видео.

Хук — это то, что заставляет пользователя НЕ листать дальше.

Классифицируй хук строго по одному из типов:
question | shock | stats | story | testimonial | before_after | countdown | controversy | curiosity | ugc_organic

Визуальный стиль:
talking_head | voiceover_text | screen_record | ugc_raw | animation | slideshow | split_screen

ОТВЕТ: строго JSON без пояснений вне JSON.

СХЕМА:
{
  "hook_type": "...",
  "hook_text": "текст хука (первая фраза/надпись)",
  "hook_strength": 1-10,
  "visual_style": "...",
  "why_works": "одна фраза — почему этот хук работает",
  "target_emotion": "страх|любопытство|жадность|доверие|срочность|развлечение",
  "recommended_adaptation": "как адаптировать под нашу вертикаль",
  "risk_level": "low|medium|high"
}"""

    def __init__(self):
        self.client = AsyncAnthropic()

    async def analyze(self, signal: dict) -> dict | None:
        title = signal.get("title", "")
        account = signal.get("account_name", "")
        platform = signal.get("platform", "")
        views = signal.get("views", 0)
        er = signal.get("er", 0)

        user_content: list[Any] = [
            {
                "type": "text",
                "text": (
                    f"Платформа: {platform}\n"
                    f"Аккаунт: {account}\n"
                    f"Заголовок/текст видео: {title}\n"
                    f"Просмотры: {views:,}\n"
                    f"Engagement Rate: {er:.2%}\n\n"
                    f"Проанализируй хук этого видео."
                )
            }
        ]

        thumbnail_url = signal.get("thumbnail_url")
        if thumbnail_url:
            user_content.insert(0, {
                "type": "image",
                "source": {"type": "url", "url": thumbnail_url},
            })

        try:
            resp = await self.client.messages.create(
                model="claude-sonnet-5",
                max_tokens=512,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            return _extract_json(getattr(resp.content[0], "text", ""))
        except Exception as e:
            logger.warning(f"HookAnalyzer: ошибка для {signal.get('id')}: {e}")
            return None


# ── Агрегированный отчёт ──────────────────────────────────

class CompetitorReportBuilder:

    SYSTEM_PROMPT = """Ты — A14 COMPETITOR_ANALYST системы UBT OS.
На основе данных о хуках конкурентов за период сформируй аналитический отчёт.

ОТВЕТ: строго JSON без пояснений вне JSON.

СХЕМА:
{
  "period": "...",
  "vertical": "...",
  "total_analyzed": N,
  "dominant_hook_type": "...",
  "dominant_visual_style": "...",
  "top_hooks": [
    {
      "hook_type": "...",
      "hook_text": "...",
      "hook_strength": N,
      "why_works": "...",
      "platform": "...",
      "views": N,
      "recommended_adaptation": "..."
    }
  ],
  "emerging_trends": ["тренд 1", "тренд 2"],
  "avoid_patterns": ["паттерн 1 — почему избегать"],
  "weekly_recommendation": "главная рекомендация по хукам на следующую неделю",
  "confidence_score": 0.0
}"""

    def __init__(self):
        self.client = AsyncAnthropic()

    async def build(self, patterns: list[dict], vertical: str, kb_context: str = "") -> dict:
        patterns_text = "\n".join(
            f"- [{p['platform']}] тип={p['hook_type']} сила={p['hook_strength']}/10 "
            f"views={p['views']:,} ER={p.get('er', 0):.2%}: \"{p['hook_text'][:100]}\""
            for p in patterns[:40]
        )

        eff_sys = self.SYSTEM_PROMPT + (f"\n\n{kb_context}" if kb_context else "")
        resp = await self.client.messages.create(
            model="claude-sonnet-5",
            max_tokens=2048,
            system=eff_sys,
            messages=[{
                "role": "user",
                "content": (
                    f"Вертикаль: {vertical}\n"
                    f"Период: последние 3 дня\n"
                    f"Проанализированных видео: {len(patterns)}\n\n"
                    f"ПАТТЕРНЫ ХУКОВ:\n{patterns_text}\n\n"
                    f"Сформируй отчёт."
                )
            }],
        )
        return _extract_json(getattr(resp.content[0], "text", ""))


# ── Запись в БД ───────────────────────────────────────────

class PatternWriter:

    def __init__(self, db: Client):
        self.db = db

    def save_pattern(self, signal: dict, analysis: dict) -> str:
        row = {
            "vertical":        signal.get("vertical", "nutra"),
            "geo":             signal.get("geo", "RU"),
            "platform":        signal.get("platform", "tiktok"),
            "hook_type":       analysis.get("hook_type", "unknown"),
            "hook_text":       analysis.get("hook_text", ""),
            "hook_strength":   analysis.get("hook_strength", 5),
            "visual_style":    analysis.get("visual_style", "unknown"),
            "why_works":       analysis.get("why_works", ""),
            "target_emotion":  analysis.get("target_emotion", ""),
            "recommended_adaptation": analysis.get("recommended_adaptation", ""),
            "risk_level":      analysis.get("risk_level", "medium"),
            "views":           signal.get("views", 0),
            "er":              signal.get("er", 0),
            "source_account":  signal.get("account_name", ""),
            "source_video_url": signal.get("video_url", ""),
        }
        res = self.db.table("competitor_patterns").insert(row).execute()
        return one_row(res)["id"]

    def save_hook_template(self, analysis: dict, signal: dict, vertical: str):
        if analysis.get("hook_strength", 0) < 7:
            return
        self.db.table("hook_templates").upsert({
            "vertical":        vertical,
            "geo":             signal.get("geo", "RU"),
            "platform":        signal.get("platform", "tiktok"),
            "hook_type":       analysis.get("hook_type", "unknown"),
            "hook_text":       analysis.get("hook_text", ""),
            "visual_style":    analysis.get("visual_style", "unknown"),
            "source_video_url": signal.get("video_url", ""),
            "source_account":  signal.get("account_name", ""),
            "views_at_capture": signal.get("views", 0),
            "er_at_capture":   signal.get("er", 0),
        }, on_conflict="source_video_url").execute()

    def save_report(self, report: dict, vertical: str) -> str:
        res = self.db.table("competitor_reports").insert({
            "vertical":              vertical,
            "period_days":           3,
            "total_analyzed":        report.get("total_analyzed", 0),
            "dominant_hook_type":    report.get("dominant_hook_type"),
            "dominant_visual_style": report.get("dominant_visual_style"),
            "top_hooks":             report.get("top_hooks", []),
            "emerging_trends":       report.get("emerging_trends", []),
            "avoid_patterns":        report.get("avoid_patterns", []),
            "weekly_recommendation": report.get("weekly_recommendation"),
            "confidence_score":      report.get("confidence_score", 0.5),
            "raw_json":              report,
        }).execute()
        return one_row(res)["id"]


# ── Точка входа ───────────────────────────────────────────

async def run_competitor_analyst(
    vertical: str = "nutra",
    lookback_days: int = 3,
    kb_context: str = "",
) -> dict:
    db = _get_db()
    collector = CompetitorSignalCollector(db, vertical, lookback_days)
    hook_analyzer = HookAnalyzer()
    report_builder = CompetitorReportBuilder()
    writer = PatternWriter(db)

    logger.info(f"A14 COMPETITOR_ANALYST: вертикаль={vertical}, период={lookback_days}д")

    signals = collector.collect()
    analyzed_urls = collector.get_existing_patterns()

    new_signals = [s for s in signals if s.get("video_url") not in analyzed_urls]
    logger.info(f"Новых сигналов для анализа: {len(new_signals)}/{len(signals)}")

    if not new_signals:
        return {"status": "no_new_signals", "vertical": vertical}

    # Анализируем параллельно пачками по 5
    patterns_saved = []
    for i in range(0, len(new_signals), 5):
        batch = new_signals[i:i+5]
        analyses = await asyncio.gather(*[hook_analyzer.analyze(s) for s in batch])

        for signal, analysis in zip(batch, analyses):
            if not analysis:
                continue
            analysis["views"] = signal.get("views", 0)
            analysis["er"] = signal.get("er", 0)
            analysis["platform"] = signal.get("platform", "")
            writer.save_pattern(signal, analysis)
            writer.save_hook_template(analysis, signal, vertical)
            patterns_saved.append(analysis)

        await asyncio.sleep(0.5)

    # Агрегированный отчёт
    report = {}
    if patterns_saved:
        report = await report_builder.build(patterns_saved, vertical, kb_context=kb_context)
        report_id = writer.save_report(report, vertical)
        report["report_id"] = report_id

    logger.info(
        f"A14 завершён: проанализировано={len(patterns_saved)}, "
        f"доминирующий хук={report.get('dominant_hook_type', 'n/a')}"
    )
    return {
        "status": "ok",
        "vertical": vertical,
        "analyzed": len(patterns_saved),
        "report": report,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_competitor_analyst())
