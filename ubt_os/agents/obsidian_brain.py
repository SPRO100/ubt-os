"""
A24 — OBSIDIAN_BRAIN
Самоорганизующийся AI-мозг на базе Obsidian Vault.
Из каждого источника создаёт 8–15 wiki-страниц.
Горячий кэш (hot.md) — помнит контекст между сессиями.
Health-чекер — находит мёртвые ссылки и противоречия.
Основан на claude-obsidian (AgriciDaniel/claude-obsidian, 8.2k ⭐).
Запускается ежедневно 00:30 + по требованию при получении нового источника.
"""
from __future__ import annotations
import logging, os, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.obsidian_brain")

VAULT_ROOT = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "/home/user/ubt-os/obsidian-vault"))
WIKI_DIR   = VAULT_ROOT / "50 Resources" / "knowledge" / "wiki"
HOT_CACHE  = VAULT_ROOT / "50 Resources" / "knowledge" / "hot.md"
RAW_DIR    = VAULT_ROOT / "00 Inbox" / "raw"

INGEST_PROMPT = """Ты — AI-библиотекарь для Obsidian Vault проекта UBT OS.
Контекст проекта: multi-agent affiliate система (betting + nutra, GEO: US/BR/MX/DE/PL).

Из предоставленного источника создай структурированные wiki-страницы.

ПРАВИЛА:
- Создай 3–8 страниц (меньше лучше, чем пустые страницы)
- Каждая страница — отдельная концепция, факт или инсайт
- Используй [[wikilinks]] для связей между страницами
- Фокус: что применимо к UBT OS прямо сейчас
- Добавь раздел "## Применение для UBT OS" в каждую страницу

ФОРМАТ ОТВЕТА (JSON):
{
  "pages": [
    {
      "filename": "kebab-case-name.md",
      "title": "Заголовок страницы",
      "tags": ["tag1", "tag2"],
      "content": "полный markdown контент страницы",
      "links_to": ["другая-страница.md"]
    }
  ],
  "hot_cache_update": "1-2 строки для горячего кэша — самое важное из источника",
  "summary": "одна строка: что добавлено и зачем"
}"""

QUERY_PROMPT = """Ты — AI-ассистент с доступом к базе знаний UBT OS (Obsidian Vault).

Отвечай ТОЛЬКО на основе предоставленных wiki-страниц.
Цитируй конкретные страницы: [[название-страницы]].
Если информации нет в базе — скажи прямо.

ФОРМАТ ОТВЕТА (JSON):
{
  "answer": "развёрнутый ответ с цитатами",
  "sources": ["wiki/page1.md", "wiki/page2.md"],
  "confidence": "high|medium|low",
  "missing_knowledge": "что нужно добавить в базу для полного ответа"
}"""

HEALTH_PROMPT = """Проверь здоровье Obsidian Vault базы знаний.

Найди:
1. Мёртвые ссылки ([[страница]] которой нет в файловой системе)
2. Пустые страницы (< 100 символов)
3. Страницы без тегов
4. Противоречия между страницами
5. Устаревший контент (дата > 30 дней без обновлений)

ФОРМАТ ОТВЕТА (JSON):
{
  "dead_links": [{"file": "...", "broken_link": "..."}],
  "empty_pages": ["..."],
  "no_tags": ["..."],
  "contradictions": [{"page1": "...", "page2": "...", "conflict": "..."}],
  "stale_pages": ["..."],
  "health_score": 0-100,
  "action_items": ["..."]
}"""


@dataclass
class IngestResult:
    source: str
    pages_created: int
    filenames: list[str]
    hot_cache_update: str
    summary: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class QueryResult:
    question: str
    answer: str
    sources: list[str]
    confidence: str
    missing_knowledge: str


@dataclass
class HealthReport:
    dead_links: list[dict]
    empty_pages: list[str]
    no_tags: list[str]
    contradictions: list[dict]
    stale_pages: list[str]
    health_score: int
    action_items: list[str]
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ObsidianBrain:

    def __init__(self):
        self.llm = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        WIKI_DIR.mkdir(parents=True, exist_ok=True)
        RAW_DIR.mkdir(parents=True, exist_ok=True)

    def _read_hot_cache(self) -> str:
        if HOT_CACHE.exists():
            return HOT_CACHE.read_text(encoding="utf-8")[-3000:]
        return ""

    def _update_hot_cache(self, update: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        line = f"\n**{timestamp}** | {update}"
        current = HOT_CACHE.read_text(encoding="utf-8") if HOT_CACHE.exists() else "# Hot Cache — последние инсайты\n"
        lines = current.split("\n")
        if len(lines) > 200:
            lines = lines[:1] + lines[-150:]
        HOT_CACHE.write_text("\n".join(lines) + line, encoding="utf-8")

    def _read_wiki_index(self) -> str:
        if not WIKI_DIR.exists():
            return "Wiki пуста"
        pages = list(WIKI_DIR.glob("*.md"))
        summaries = []
        for p in pages[:50]:
            text = p.read_text(encoding="utf-8")[:300]
            summaries.append(f"### [[{p.stem}]]\n{text}\n")
        return "\n".join(summaries)

    def _find_dead_links(self) -> list[dict]:
        if not WIKI_DIR.exists():
            return []
        existing = {p.stem for p in WIKI_DIR.glob("*.md")}
        dead = []
        for page in WIKI_DIR.glob("*.md"):
            text = page.read_text(encoding="utf-8")
            links = re.findall(r"\[\[([^\]]+)\]\]", text)
            for link in links:
                stem = link.split("|")[0].strip()
                if stem not in existing:
                    dead.append({"file": page.name, "broken_link": link})
        return dead

    async def ingest(self, source_text: str, source_name: str = "unknown") -> IngestResult:
        hot = self._read_hot_cache()
        user_msg = f"""Источник: {source_name}
Горячий кэш (контекст):
{hot}

--- ИСТОЧНИК ---
{source_text[:6000]}
---

Создай wiki-страницы и верни JSON."""

        response = await self.llm.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=INGEST_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        data = _extract_json(response.content[0].text, fallback={"pages": [], "hot_cache_update": "", "summary": "parse_error"})
        pages = data.get("pages", [])
        filenames = []

        for page in pages:
            fname = page.get("filename", "unknown.md")
            tags = page.get("tags", [])
            content = page.get("content", "")
            frontmatter = f"---\ntags: [{', '.join(tags)}]\ncreated: {datetime.now(timezone.utc).date()}\nsource: {source_name}\n---\n\n"
            (WIKI_DIR / fname).write_text(frontmatter + content, encoding="utf-8")
            filenames.append(fname)

        hot_update = data.get("hot_cache_update", "")
        if hot_update:
            self._update_hot_cache(hot_update)

        result = IngestResult(
            source=source_name,
            pages_created=len(filenames),
            filenames=filenames,
            hot_cache_update=hot_update,
            summary=data.get("summary", ""),
        )
        logger.info("obsidian_brain | ingest source=%s pages=%d", source_name, result.pages_created)
        return result

    async def query(self, question: str) -> QueryResult:
        wiki_index = self._read_wiki_index()
        hot = self._read_hot_cache()

        user_msg = f"""Вопрос: {question}

Горячий кэш:
{hot}

База знаний (wiki):
{wiki_index}

Ответь на основе базы знаний и верни JSON."""

        response = await self.llm.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=QUERY_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        data = _extract_json(response.content[0].text, fallback={
            "answer": response.content[0].text,
            "sources": [], "confidence": "low", "missing_knowledge": "",
        })

        return QueryResult(
            question=question,
            answer=data.get("answer", ""),
            sources=data.get("sources", []),
            confidence=data.get("confidence", "low"),
            missing_knowledge=data.get("missing_knowledge", ""),
        )

    async def health_check(self) -> HealthReport:
        dead_links = self._find_dead_links()
        wiki_index = self._read_wiki_index()

        response = await self.llm.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=HEALTH_PROMPT,
            messages=[{"role": "user", "content": f"Мёртвые ссылки (уже найдены): {dead_links}\n\nИндекс wiki:\n{wiki_index}"}],
        )

        data = _extract_json(response.content[0].text, fallback={
            "dead_links": dead_links, "empty_pages": [], "no_tags": [],
            "contradictions": [], "stale_pages": [], "health_score": 50, "action_items": [],
        })

        report = HealthReport(
            dead_links=data.get("dead_links", dead_links),
            empty_pages=data.get("empty_pages", []),
            no_tags=data.get("no_tags", []),
            contradictions=data.get("contradictions", []),
            stale_pages=data.get("stale_pages", []),
            health_score=data.get("health_score", 50),
            action_items=data.get("action_items", []),
        )
        logger.info("obsidian_brain | health_check score=%d dead_links=%d", report.health_score, len(report.dead_links))
        return report

    async def auto_ingest_raw(self) -> list[IngestResult]:
        """Обрабатывает все файлы из 00 Inbox/raw/."""
        results: list[IngestResult] = []
        if not RAW_DIR.exists():
            return results
        for raw_file in RAW_DIR.glob("*.md"):
            text = raw_file.read_text(encoding="utf-8")
            result = await self.ingest(text, source_name=raw_file.stem)
            results.append(result)
            raw_file.rename(raw_file.with_suffix(".processed.md"))
        return results


async def run() -> dict:
    brain = ObsidianBrain()
    results = await brain.auto_ingest_raw()
    health = await brain.health_check()
    return {
        "ingested": len(results),
        "pages_created": sum(r.pages_created for r in results),
        "vault_health": health.health_score,
    }
