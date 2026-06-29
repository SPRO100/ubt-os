"""
A21 — CONTENT_CREATOR
Генерирует готовый контент для betting/nutra по шаблонам Marketing Skills.
Brand Voice + SEO + Stop-Slop пост-обработка.
Запускается по расписанию из strategy_engine или вручную.
"""
from __future__ import annotations
import asyncio, logging, os
from dataclasses import dataclass
from enum import Enum
from anthropic import AsyncAnthropic

from ubt_os.agents.text_humanizer import TextHumanizer, HumanizeResult
from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.content_creator")


class ContentFormat(str, Enum):
    BEFORE_AFTER = "before_after_testimonial"
    HOOK_PROBLEM = "short_hook_problem_solution"
    UGC_REACTION = "ugc_reaction"
    SERIES_DAY   = "series_day"
    SEO_ARTICLE  = "seo_article"
    CAPTION      = "caption"


class Vertical(str, Enum):
    NUTRA   = "nutra"
    BETTING = "betting"


BRAND_VOICE = {
    "nutra": {
        "US": "Ты — доверительный друг, уже прошедший через похудение/здоровье. Говоришь от первого лица. Признаёшь скептицизм. Конкретные детали вместо общих слов. Без суперлативов.",
        "BR": "Ты — тёплый друг, говоришь эмоционально, упоминаешь семью и сообщество. Язык: Portuguese (BR).",
        "MX": "Ты — часть сообщества, доверие через «мои подруги тоже». Язык: Spanish (MX).",
        "DE": "Ты — рациональный, опираешься на факты и исследования. Язык: German.",
        "PL": "Ты — надёжный, акцент на безопасности и проверенности. Язык: Polish.",
    },
    "betting": {
        "US": "Ты — опытный игрок, делишься стратегией (не удачей). Конкретные суммы и выводы. FOMO через ограниченность бонуса.",
        "BR": "Ты — страстный болельщик, любишь футбол, говоришь про community. Язык: Portuguese (BR).",
        "MX": "Ты — знаток спорта, делишься лайфхаком с другом. Язык: Spanish (MX).",
        "DE": "Ты — аналитик, про надёжность платформы и условия. Язык: German.",
        "PL": "Ты — осторожный игрок, акцент на бонусах и безопасности. Язык: Polish.",
    },
}

CONTENT_PROMPTS = {
    ContentFormat.BEFORE_AFTER: """Напиши скрипт видео "До/После" (30 секунд).

Структура:
- 0-3 сек: Хук — боль/проблема героя (одна конкретная деталь)
- 3-10 сек: Момент X — что изменило всё
- 10-20 сек: Результат — конкретные цифры и детали
- 20-27 сек: Proof — почему веришь (деталь, не реклама)
- 27-30 сек: Мягкий CTA

Формат вывода JSON:
{{"script": "...", "hook": "...", "cta": "...", "hashtags": ["..."], "caption": "..."}}""",

    ContentFormat.HOOK_PROBLEM: """Напиши 5 вариантов хука для 15-30 секундного видео.

Форматы хуков:
1. Вопрос-шок ("Ты знаешь почему 90% не могут...")
2. Цифровой факт ("3 недели назад я весил...")
3. "Я не верил пока не" — личный опыт
4. Контрастная трансформация ("Раньше... Теперь...")
5. Срочность/FOMO ("Только сегодня / Последние 24 часа")

Формат вывода JSON:
{{"hooks": [{{"type": "...", "text": "...", "strength": 1-10}}]}}""",

    ContentFormat.UGC_REACTION: """Напиши UGC-скрипт от первого лица (реакция/отзыв).

Звучит как органичный отзыв, НЕ реклама.
Включи: конкретную деталь (день/ситуация) + сомнение + результат + рекомендация.
30-45 секунд.

Формат вывода JSON:
{{"script": "...", "hook": "...", "caption": "...", "hashtags": ["..."]}}""",

    ContentFormat.SERIES_DAY: """Напиши один пост из серии прогрева аккаунта.

День {day}/5:
1 = Личная история (боль)
2 = Проблема углубляется
3 = Попытки без результата
4 = Находка/решение
5 = Результат + CTA

Формат вывода JSON:
{{"day": {day}, "script": "...", "hook": "...", "caption": "...", "hashtags": ["..."]}}""",

    ContentFormat.CAPTION: """Напиши подпись к видео (150-250 символов).

Включи: основной месседж + CTA + 3-5 хэштегов.
НЕ пересказывай видео — дополни его.

Формат вывода JSON:
{{"caption": "...", "hashtags": ["..."], "cta": "..."}}""",
}


@dataclass
class ContentPiece:
    format: str
    vertical: str
    geo: str
    raw_content: dict
    humanized_text: str
    humanize_score: int
    passed_quality: bool


class ContentCreator:

    def __init__(self):
        self.llm = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.humanizer = TextHumanizer()

    def _build_system(self, vertical: str, geo: str) -> str:
        voice = BRAND_VOICE.get(vertical, {}).get(geo, BRAND_VOICE["nutra"]["US"])
        return f"""Ты — контент-криейтор для {vertical} вертикали, GEO: {geo}.

ГОЛОС БРЕНДА: {voice}

ЗАПРЕЩЕНО:
- "гарантированно", "чудо", "мгновенно", "без усилий"
- Медицинские диагнозы и обещания лечения
- "100% выигрыш", "точно заработаешь"
- Любые суперлативы и гиперболы

ОБЯЗАТЕЛЬНО:
- Конкретные детали вместо общих слов
- Живой разговорный язык
- Одна главная идея на контент-единицу
- Соответствие платформе: TikTok/Instagram Reels"""

    async def create(
        self,
        fmt: ContentFormat,
        vertical: Vertical,
        geo: str,
        offer: str = "",
        day: int = 1,
    ) -> ContentPiece:
        system = self._build_system(vertical.value, geo)
        prompt_template = CONTENT_PROMPTS.get(fmt, CONTENT_PROMPTS[ContentFormat.HOOK_PROBLEM])
        prompt = prompt_template.replace("{day}", str(day))

        user_msg = f"Оффер: {offer}\nGEO: {geo}\n\nСоздай контент:"

        response = await self.llm.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": f"{prompt}\n\n{user_msg}"}],
        )

        raw = _extract_json(response.content[0].text, fallback={"script": response.content[0].text})

        main_text = raw.get("script") or raw.get("caption") or str(raw)
        humanized: HumanizeResult = await self.humanizer.humanize(main_text, geo=geo, vertical=vertical.value)

        piece = ContentPiece(
            format=fmt.value,
            vertical=vertical.value,
            geo=geo,
            raw_content=raw,
            humanized_text=humanized.humanized_text,
            humanize_score=humanized.final_score.get("total", 0),
            passed_quality=humanized.passed,
        )

        logger.info(
            "content_creator | fmt=%s vertical=%s geo=%s score=%d passed=%s",
            fmt.value, vertical.value, geo, piece.humanize_score, piece.passed_quality,
        )
        return piece

    async def create_batch(self, requests: list[dict]) -> list[ContentPiece]:
        tasks = [
            self.create(
                fmt=ContentFormat(r["format"]),
                vertical=Vertical(r["vertical"]),
                geo=r.get("geo", "US"),
                offer=r.get("offer", ""),
                day=r.get("day", 1),
            )
            for r in requests
        ]
        return await asyncio.gather(*tasks)


async def run(vertical: str = "nutra", geo: str = "US", offer: str = "") -> list[ContentPiece]:
    creator = ContentCreator()
    requests = [
        {"format": ContentFormat.HOOK_PROBLEM.value, "vertical": vertical, "geo": geo, "offer": offer},
        {"format": ContentFormat.BEFORE_AFTER.value, "vertical": vertical, "geo": geo, "offer": offer},
        {"format": ContentFormat.UGC_REACTION.value,  "vertical": vertical, "geo": geo, "offer": offer},
    ]
    return await creator.create_batch(requests)
