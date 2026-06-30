"""
A23 — YOUTUBE_CREATOR
Производит контент для YouTube Shorts и длинных видео.
Retention-инжиниринг, hook-варианты, SEO-пакет, календарь.
Основан на claude-youtube (AgriciDaniel/claude-youtube, 218 ⭐).
Запускается по требованию из оркестратора.
"""
from __future__ import annotations
import asyncio, logging, os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.youtube_creator")


class YTFormat(str, Enum):
    SHORTS       = "shorts"        # 15–60 сек, вирусный
    LONG_FORM    = "long_form"     # 8–15 мин, обзор/обучение
    HOOK         = "hook"          # 5 вариантов первых 30 сек
    SCRIPT       = "script"        # Полный скрипт с retention-паузами
    METADATA     = "metadata"      # Title + description + tags + chapters
    AUDIT        = "audit"         # Аудит канала по 4 измерениям
    IDEATE       = "ideate"        # 10 идей видео с keyword-анализом
    CALENDAR     = "calendar"      # Месячный контент-календарь
    THUMBNAIL    = "thumbnail"     # Бриф для превью (3 A/B варианта)
    REPURPOSE    = "repurpose"     # Адаптация видео под TikTok/IG/Telegram


SYSTEM_PROMPTS = {
    YTFormat.SHORTS: """Ты — продюсер вирусных YouTube Shorts для affiliate-маркетинга.
Вертикали: nutra, betting. GEO: US, BR, MX, DE, PL.

Структура Shorts (15–60 сек):
- 0–3 сек: Pattern interrupt хук (цифра / шок / обещание)
- 3–15 сек: Проблема + агитация
- 15–45 сек: Решение / трансформация / доказательство
- 45–60 сек: CTA + призыв к подписке

ФОРМАТ JSON:
{
  "title": "...", "duration_target": "сек",
  "hook": "...", "script": "...", "cta": "...",
  "retention_notes": ["паузы каждые N сек для удержания"],
  "tags": ["..."], "thumbnail_concept": "...",
  "drop_off_risk": "low|medium|high", "drop_off_reason": "..."
}""",

    YTFormat.LONG_FORM: """Ты — сценарист YouTube видео (8–15 минут) для affiliate-маркетинга.
Retention-инжиниринг: pattern interrupt каждые 60–90 секунд.

Структура:
- 0–30 сек: Mega hook (обещание главного результата)
- 30–90 сек: Intro (почему смотреть ДО КОНЦА)
- 2–12 мин: Основной контент (3–5 блоков по 2–3 мин каждый)
- 12–14 мин: Climax (главное обещание выполнено)
- 14–15 мин: CTA + следующее видео

ФОРМАТ JSON:
{
  "title": "...", "target_duration": "мин",
  "hook": "...", "intro": "...",
  "blocks": [{"title": "...", "script": "...", "pattern_interrupt": "..."}],
  "cta": "...", "chapters": [{"time": "00:00", "title": "..."}],
  "retention_score": 0-10
}""",

    YTFormat.HOOK: """Создай 5 вариантов хука для YouTube видео (первые 30 секунд).

Типы хуков:
1. Цифровой шок ("87% людей не знают что...")
2. Обещание трансформации ("Через 5 минут ты узнаешь...")
3. Контринтуитивное утверждение ("Всё что ты знал о X — неверно")
4. Личная история ("6 месяцев назад я весил...")
5. FOMO ("Это видео я удалю через 48 часов")

ФОРМАТ JSON:
{"hooks": [{"type": "...", "script": "...", "drop_off_risk": "low|medium|high", "strength": 1-10}]}""",

    YTFormat.METADATA: """Создай полный SEO-пакет для YouTube видео.

ФОРМАТ JSON:
{
  "titles": ["3 варианта title (≤60 символов)"],
  "description": "полное описание (500–1000 слов) с ключами",
  "tags": ["20–30 тегов от общих к специфичным"],
  "chapters": [{"time": "00:00", "title": "..."}],
  "hashtags": ["#3-5 хэштегов"],
  "end_screen_cta": "...",
  "cards_timing": [{"time": "сек", "text": "..."}],
  "seo_score": 0-100
}""",

    YTFormat.AUDIT: """Проведи аудит YouTube канала по 4 измерениям.

ФОРМАТ JSON:
{
  "scores": {
    "seo": 0-100,
    "performance": 0-100,
    "content": 0-100,
    "monetization": 0-100,
    "total": 0-100
  },
  "seo_issues": ["..."],
  "performance_issues": ["..."],
  "content_issues": ["..."],
  "monetization_issues": ["..."],
  "quick_wins": ["топ-3 действия для роста"],
  "monthly_potential": "прогноз просмотров"
}""",

    YTFormat.IDEATE: """Сгенерируй 10 идей видео с keyword-анализом.

ФОРМАТ JSON:
{
  "ideas": [
    {
      "rank": 1,
      "title": "...",
      "keyword": "главный ключ",
      "monthly_searches": "оценка",
      "competition": "low|medium|high",
      "format": "shorts|long_form",
      "hook_angle": "...",
      "estimated_views": "диапазон"
    }
  ]
}""",

    YTFormat.CALENDAR: """Создай месячный контент-календарь YouTube.

ФОРМАТ JSON:
{
  "month": "...",
  "strategy": "общая стратегия месяца",
  "weeks": [
    {
      "week": 1,
      "theme": "тема недели",
      "videos": [
        {"day": "пн", "format": "shorts|long", "title": "...", "publish_time": "HH:MM UTC"}
      ]
    }
  ],
  "seasonal_hooks": ["события месяца для привязки контента"],
  "cpm_note": "ожидаемый CPM (если монетизация)"
}""",

    YTFormat.THUMBNAIL: """Создай бриф для thumbnail (превью) YouTube видео — 3 A/B варианта.

ФОРМАТ JSON:
{
  "variants": [
    {
      "variant": "A|B|C",
      "concept": "...",
      "background": "...",
      "text_overlay": "макс 4 слова",
      "face_expression": "...",
      "color_scheme": "...",
      "ctr_prediction": "low|medium|high",
      "rationale": "почему сработает"
    }
  ],
  "recommended": "A|B|C",
  "ab_test_note": "..."
}""",

    YTFormat.REPURPOSE: """Адаптируй YouTube контент под другие платформы.

ФОРМАТ JSON:
{
  "tiktok": {"hook": "...", "script": "...", "caption": "...", "hashtags": ["..."]},
  "instagram_reels": {"hook": "...", "script": "...", "caption": "..."},
  "telegram": {"post": "...", "preview_text": "..."},
  "twitter_thread": ["твит 1", "твит 2", "твит 3"],
  "email_subject": "...",
  "blog_headline": "..."
}""",
}


@dataclass
class YTContent:
    format: str
    vertical: str
    geo: str
    content: dict
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class YoutubeCreator:

    def __init__(self):
        self.llm = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    async def create(
        self,
        fmt: YTFormat,
        vertical: str,
        geo: str,
        topic: str = "",
        offer: str = "",
        channel_data: dict | None = None,
    ) -> YTContent:
        system = SYSTEM_PROMPTS.get(fmt, SYSTEM_PROMPTS[YTFormat.SHORTS])

        context = f"Вертикаль: {vertical} | GEO: {geo} | Оффер: {offer}"
        if topic:
            context += f" | Тема: {topic}"
        if channel_data:
            context += f"\n\nДанные канала: {channel_data}"

        response = await self.llm.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": f"{context}\n\nСоздай контент и верни JSON."}],
        )

        data = _extract_json(response.content[0].text, fallback={"error": "parse_failed", "raw": response.content[0].text})

        result = YTContent(format=fmt.value, vertical=vertical, geo=geo, content=data)
        logger.info("youtube_creator | fmt=%s vertical=%s geo=%s", fmt.value, vertical, geo)
        return result

    async def full_package(self, vertical: str, geo: str, topic: str, offer: str = "") -> dict[str, YTContent]:
        """Полный пакет: скрипт + хуки + метаданные + thumbnail + repurpose."""
        tasks = {
            "script":    self.create(YTFormat.SCRIPT,     vertical, geo, topic, offer),
            "hooks":     self.create(YTFormat.HOOK,       vertical, geo, topic, offer),
            "metadata":  self.create(YTFormat.METADATA,   vertical, geo, topic, offer),
            "thumbnail": self.create(YTFormat.THUMBNAIL,  vertical, geo, topic, offer),
            "repurpose": self.create(YTFormat.REPURPOSE,  vertical, geo, topic, offer),
        }
        results = await asyncio.gather(*tasks.values())
        return dict(zip(tasks.keys(), results))


async def run(vertical: str = "nutra", geo: str = "US", topic: str = "", offer: str = "") -> dict:
    creator = YoutubeCreator()
    pkg = await creator.full_package(vertical, geo, topic, offer)
    return {k: v.content for k, v in pkg.items()}
