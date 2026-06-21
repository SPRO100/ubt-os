"""
A18 — KNOWLEDGE_SYNTHESIZER
Превращает операционную активность в институциональное знание.
Ежедневно 23:45 + воскресенье 22:00.
"""
from __future__ import annotations
import asyncio, json, logging, os
from datetime import datetime, timedelta
from supabase import create_client, Client
from anthropic import AsyncAnthropic

logger = logging.getLogger("ubt_os.knowledge_synthesizer")


# ── Сбор данных ───────────────────────────────────────────

class KnowledgeDataCollector:

    def __init__(self, db: Client, days: int = 1):
        self.db    = db
        self.since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        self.week  = (datetime.utcnow() - timedelta(days=7)).isoformat()

    def collect_daily(self) -> dict:
        return {
            "date":      datetime.utcnow().date().isoformat(),
            "videos":    self._videos(),
            "revenue":   self._revenue(),
            "top_hooks": self._top_hooks(),
            "incidents": self._incidents(),
            "risk":      self._risk_events(),
            "strategy":  self._strategy_status(),
        }

    def collect_weekly(self) -> dict:
        return {
            "week":         datetime.utcnow().isocalendar()[1],
            "videos_7d":    self._videos(self.week),
            "revenue_7d":   self._revenue(self.week),
            "patterns":     self._patterns(),
            "hypotheses":   self._hypotheses(),
            "prev_learnings": self._prev_learnings(n=5),
        }

    def _videos(self, since: str | None = None) -> list:
        q = (self.db.table("video_analytics")
             .select("platform,vertical,geo,format_type,completion_rate,er,ctr,views,revenue")
             .gte("created_at", since or self.since))
        return q.execute().data

    def _revenue(self, since: str | None = None) -> list:
        return (self.db.table("revenue_daily")
                .select("date,vertical,geo,platform,partner,net_revenue,conversions,ctr,cr")
                .gte("date", (since or self.since)[:10])
                .execute()).data

    def _top_hooks(self) -> list:
        return (self.db.table("hook_rankings")
                .select("hook_text,hook_type,vertical,avg_completion_rate,avg_cr,hook_score")
                .order("hook_score", desc=True).limit(10).execute()).data

    def _incidents(self) -> list:
        return (self.db.table("incidents")
                .select("*").gte("started_at", self.since).execute()).data

    def _risk_events(self) -> list:
        return (self.db.table("risk_events")
                .select("account_id,event_type,severity,description")
                .gte("created_at", self.since).execute()).data

    def _strategy_status(self) -> dict | None:
        rows = (self.db.table("strategy_briefs")
                .select("week_label,top_formats,confidence_score")
                .order("created_at", desc=True).limit(1).execute()).data
        return rows[0] if rows else None

    def _patterns(self) -> list:
        return (self.db.table("winning_patterns")
                .select("*").eq("is_active", True).execute()).data

    def _hypotheses(self) -> list:
        return (self.db.table("knowledge_entries")
                .select("*").eq("type", "hypothesis")
                .order("created_at", desc=True).limit(10).execute()).data

    def _prev_learnings(self, n: int = 5) -> list:
        return (self.db.table("knowledge_entries")
                .select("content,created_at").eq("type", "daily_learning")
                .order("created_at", desc=True).limit(n).execute()).data


# ── Claude анализ ─────────────────────────────────────────

class KnowledgeAnalyst:

    DAILY_PROMPT = """Ты — KNOWLEDGE_SYNTHESIZER системы UBT OS.
Проанализируй операционные данные за сегодня и создай синтез знаний.

ДАННЫЕ: {data}

ПРЕДЫДУЩИЕ ЗНАНИЯ (не повторяй): {prev}

Ответь строго по схеме JSON:
{{
  "what_worked": ["конкретный факт с цифрами", ...],
  "what_failed": ["факт + причина", ...],
  "why_analysis": "3-4 предложения объясняющих паттерн дня",
  "experiment_tomorrow": "одна переменная, один измеримый результат",
  "changed_assumptions": ["что изменилось в нашем понимании", ...],
  "new_hypothesis": {{"statement": "если X то Y", "confidence": 0.0, "test_by": "дата"}},
  "key_metric_today": {{"name": "...", "value": "...", "vs_yesterday": "..."}},
  "markdown_content": "полная markdown запись для Obsidian"
}}"""

    WEEKLY_PROMPT = """Ты — KNOWLEDGE_SYNTHESIZER системы UBT OS.
Создай стратегический обзор недели.

ДАННЫЕ 7 ДНЕЙ: {data}

Ответь строго по схеме JSON:
{{
  "winning_patterns": [{{"pattern": "...", "evidence": "...", "scale": true}}],
  "dead_patterns": [{{"pattern": "...", "reason": "..."}}],
  "strategic_shifts": ["что изменилось в стратегии", ...],
  "top_hypotheses": [{{"hypothesis": "...", "status": "confirmed|rejected|pending"}}],
  "next_week_priority": "одна главная задача следующей недели",
  "compound_learning": "самый важный вывод который влияет на всё",
  "markdown_content": "полная markdown запись для Obsidian"
}}"""

    def __init__(self):
        self.client = AsyncAnthropic()

    async def synthesize_daily(self, data: dict, prev: list) -> dict:
        resp = await self.client.messages.create(
            model="claude-sonnet-4-6", max_tokens=4096,
            messages=[{"role": "user", "content":
                self.DAILY_PROMPT.format(
                    data=json.dumps(data, ensure_ascii=False, default=str),
                    prev=json.dumps(prev, ensure_ascii=False, default=str)
                )
            }],
        )
        return json.loads(resp.content[0].text)

    async def synthesize_weekly(self, data: dict) -> dict:
        resp = await self.client.messages.create(
            model="claude-sonnet-4-6", max_tokens=4096,
            messages=[{"role": "user", "content":
                self.WEEKLY_PROMPT.format(
                    data=json.dumps(data, ensure_ascii=False, default=str)
                )
            }],
        )
        return json.loads(resp.content[0].text)


# ── Writer ────────────────────────────────────────────────

class KnowledgeWriter:

    def __init__(self, db: Client):
        self.db = db

    def save_daily(self, synthesis: dict) -> list[int]:
        """Append-only записи — никогда не обновляем существующие."""
        ids = []
        date = datetime.utcnow().date().isoformat()

        # Сохраняем каждый вывод как отдельную запись
        entries = []

        for item in synthesis.get("what_worked", []):
            entries.append({"type": "daily_learning", "subtype": "worked",
                            "content": item, "date": date})
        for item in synthesis.get("what_failed", []):
            entries.append({"type": "daily_learning", "subtype": "failed",
                            "content": item, "date": date})

        hyp = synthesis.get("new_hypothesis")
        if hyp and hyp.get("statement"):
            entries.append({"type": "hypothesis",
                            "content": hyp["statement"],
                            "metadata": hyp, "date": date})

        exp = synthesis.get("experiment_tomorrow")
        if exp:
            entries.append({"type": "experiment",
                            "content": exp, "date": date})

        for entry in entries:
            res = self.db.table("knowledge_entries").insert(entry).execute()
            ids.append(res.data[0]["id"])

        return ids

    def save_weekly(self, synthesis: dict) -> list[int]:
        ids  = []
        week = f"W{datetime.utcnow().isocalendar()[1]:02d}"

        for p in synthesis.get("winning_patterns", []):
            self.db.table("winning_patterns").upsert(
                {"pattern_name": p["pattern"][:100],
                 "is_active": True, "vertical": "all"},
                on_conflict="pattern_name,vertical,geo,platform"
            ).execute()

        compound = synthesis.get("compound_learning")
        if compound:
            res = self.db.table("knowledge_entries").insert({
                "type": "compound_learning", "content": compound,
                "date": datetime.utcnow().date().isoformat(),
                "metadata": {"week": week}
            }).execute()
            ids.append(res.data[0]["id"])

        return ids

    def to_obsidian_daily(self, synthesis: dict, date: str) -> tuple[str, str]:
        """Возвращает (path, content) для Obsidian."""
        path    = f"60 Daily/synthesis/{date}.md"
        content = synthesis.get("markdown_content", "")
        if not content:
            lines = [
                f"---\ntype: daily-synthesis\ntags: [knowledge, synthesis]\ndate: {date}\n---\n",
                f"# 🧠 Синтез знаний — {date}\n",
                f"## Что сработало",
            ]
            for w in synthesis.get("what_worked", []):
                lines.append(f"- ✅ {w}")
            lines += ["\n## Что провалилось"]
            for f in synthesis.get("what_failed", []):
                lines.append(f"- ❌ {f}")
            why = synthesis.get("why_analysis", "")
            if why:
                lines += [f"\n## Почему\n{why}"]
            exp = synthesis.get("experiment_tomorrow", "")
            if exp:
                lines += [f"\n## Эксперимент завтра\n> {exp}"]
            hyp = synthesis.get("new_hypothesis", {})
            if hyp:
                lines += [f"\n## Новая гипотеза\n> {hyp.get('statement','')}"]
            content = "\n".join(lines)
        return path, content

    def to_obsidian_weekly(self, synthesis: dict, week: str) -> tuple[str, str]:
        path    = f"60 Daily/synthesis/{week}-weekly.md"
        content = synthesis.get("markdown_content", "")
        if not content:
            lines = [
                f"---\ntype: weekly-synthesis\ntags: [knowledge, weekly]\nweek: {week}\n---\n",
                f"# 🧠 Недельный обзор — {week}\n",
                f"## Выигрышные паттерны",
            ]
            for p in synthesis.get("winning_patterns", []):
                scale = "🚀 масштабировать" if p.get("scale") else ""
                lines.append(f"- **{p['pattern']}** — {p['evidence']} {scale}")
            lines += ["\n## Мёртвые паттерны"]
            for p in synthesis.get("dead_patterns", []):
                lines.append(f"- ~~{p['pattern']}~~ — {p['reason']}")
            compound = synthesis.get("compound_learning", "")
            if compound:
                lines += [f"\n## Главный вывод недели\n> {compound}"]
            priority = synthesis.get("next_week_priority", "")
            if priority:
                lines += [f"\n## Приоритет следующей недели\n> {priority}"]
            content = "\n".join(lines)
        return path, content

    def format_telegram(self, synthesis: dict, is_weekly: bool = False) -> str:
        if is_weekly:
            compound  = synthesis.get("compound_learning", "—")
            priority  = synthesis.get("next_week_priority", "—")
            n_winning = len(synthesis.get("winning_patterns", []))
            n_dead    = len(synthesis.get("dead_patterns", []))
            return (
                f"🧠 *KNOWLEDGE SYNTHESIZER — Неделя*\n\n"
                f"Выигрышных паттернов: *{n_winning}*\n"
                f"Мёртвых паттернов: *{n_dead}*\n\n"
                f"Главный вывод:\n_{compound}_\n\n"
                f"Приоритет след. недели:\n→ {priority}"
            )
        worked = synthesis.get("what_worked", [])
        failed = synthesis.get("what_failed", [])
        exp    = synthesis.get("experiment_tomorrow", "")
        return (
            f"🧠 *KNOWLEDGE SYNTHESIZER*\n\n"
            f"✅ Сработало: {worked[0] if worked else '—'}\n"
            f"❌ Провал: {failed[0] if failed else '—'}\n"
            f"🔬 Завтра тестируем: _{exp or '—'}_"
        )


# ── Точка входа ───────────────────────────────────────────

async def run_daily_synthesis() -> dict:
    db        = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    collector = KnowledgeDataCollector(db, days=1)
    analyst   = KnowledgeAnalyst()
    writer    = KnowledgeWriter(db)

    logger.info("KNOWLEDGE_SYNTHESIZER: сбор данных (daily)...")
    data      = collector.collect_daily()
    prev      = collector._prev_learnings(n=3)

    logger.info("KNOWLEDGE_SYNTHESIZER: синтез (Claude Sonnet)...")
    synthesis = await analyst.synthesize_daily(data, prev)

    logger.info("KNOWLEDGE_SYNTHESIZER: сохранение...")
    writer.save_daily(synthesis)

    date       = datetime.utcnow().date().isoformat()
    path, md   = writer.to_obsidian_daily(synthesis, date)
    synthesis["obsidian_path"] = path
    synthesis["obsidian_md"]   = md
    synthesis["telegram_msg"]  = writer.format_telegram(synthesis)

    logger.info("KNOWLEDGE_SYNTHESIZER: daily ✅")
    return synthesis


async def run_weekly_synthesis() -> dict:
    db        = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    collector = KnowledgeDataCollector(db, days=7)
    analyst   = KnowledgeAnalyst()
    writer    = KnowledgeWriter(db)

    logger.info("KNOWLEDGE_SYNTHESIZER: сбор данных (weekly)...")
    data      = collector.collect_weekly()

    logger.info("KNOWLEDGE_SYNTHESIZER: синтез (Claude Sonnet)...")
    synthesis = await analyst.synthesize_weekly(data)

    logger.info("KNOWLEDGE_SYNTHESIZER: сохранение...")
    writer.save_weekly(synthesis)

    week       = f"W{datetime.utcnow().isocalendar()[1]:02d}"
    path, md   = writer.to_obsidian_weekly(synthesis, week)
    synthesis["obsidian_path"] = path
    synthesis["obsidian_md"]   = md
    synthesis["telegram_msg"]  = writer.format_telegram(synthesis, is_weekly=True)

    logger.info("KNOWLEDGE_SYNTHESIZER: weekly ✅")
    return synthesis


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if mode == "weekly":
        asyncio.run(run_weekly_synthesis())
    else:
        asyncio.run(run_daily_synthesis())
