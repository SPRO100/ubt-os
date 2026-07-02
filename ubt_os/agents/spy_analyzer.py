"""
A27 — SPY_ANALYZER
Анализирует топ-крипы конкурентов из PiPiAds/AdHeart.
Извлекает паттерны хуков, структуру видео, эффективные фразы.
Генерирует ready-to-use creative brief для A21 content_creator.
"""
from __future__ import annotations
import logging, os
from dataclasses import dataclass
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.spy_analyzer")


@dataclass
class HookPattern:
    pattern: str
    example: str
    platform: str
    effectiveness: str


@dataclass
class SpyAnalysisResult:
    vertical: str
    geo: str
    platform: str
    creatives_analyzed: int
    hook_patterns: list[dict]
    content_structures: list[dict]
    key_phrases: list[str]
    forbidden_phrases: list[str]
    winning_formats: list[str]
    creative_brief: str
    a21_prompt_extension: str


_SYSTEM_PROMPT = """Ты — эксперт по анализу affiliate-рекламы и spy-инструментам (PiPiAds, AdHeart, BigSpy).
Анализируешь описания/транскрипты рекламных крипов конкурентов и извлекаешь паттерны.

ЗАДАЧА: На основе предоставленных данных о конкурентных крипах выяви:
1. Паттерны хуков (первые 3 секунды): что цепляет аудиторию
2. Структуры видео: как построено успешное видео
3. Эффективные фразы: soft claims, CTAs, pain points
4. Запрещённые фразы: что явно нарушает модерацию
5. Выигрышные форматы: storytelling/ugc/educational/comparison

ВЕРНИ СТРОГО JSON без лишнего текста:
{
  "hook_patterns": [
    {"pattern": "цифра + шок", "example": "I lost 23 lbs in 30 days doing THIS", "effectiveness": "high"}
  ],
  "content_structures": [
    {"name": "personal story", "structure": "problem → discovery → result → cta", "seconds": "0-60", "notes": "works for nutra US"}
  ],
  "key_phrases": ["supports blood sugar", "my 30-day journey", "link in bio"],
  "forbidden_phrases": ["cures diabetes", "guaranteed weight loss"],
  "winning_formats": ["ugc testimonial", "before/after lifestyle", "educational how-to"],
  "creative_brief": "Многострочный brief для A21: что делать, какой хук, структура, фразы...",
  "a21_prompt_extension": "Дополнение к промпту A21 — 2-3 абзаца с конкретными инструкциями"
}"""


class SpyAnalyzer:
    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    async def analyze(
        self,
        creatives: list[str],
        vertical: str = "nutra",
        geo: str = "US",
        platform: str = "tiktok",
        focus: str = "hooks",
        kb_context: str = "",
    ) -> SpyAnalysisResult:
        """
        Анализирует список описаний крипов и возвращает паттерны.

        Args:
            creatives: Список текстовых описаний/транскриптов рекламных крипов
            vertical: nutra|betting
            geo: US|BR|MX|DE|PL
            platform: tiktok|facebook|instagram
            focus: hooks|structure|phrases|all
        """
        if not creatives:
            return SpyAnalysisResult(
                vertical=vertical, geo=geo, platform=platform,
                creatives_analyzed=0,
                hook_patterns=[], content_structures=[],
                key_phrases=[], forbidden_phrases=[],
                winning_formats=[],
                creative_brief="Нет данных для анализа. Предоставьте описания крипов.",
                a21_prompt_extension="",
            )

        creatives_text = "\n\n---\n\n".join(
            f"КРИП #{i+1}:\n{c}" for i, c in enumerate(creatives)
        )

        user_msg = f"""Анализируй {len(creatives)} крипов конкурентов.

Вертикаль: {vertical}
GEO: {geo}
Платформа: {platform}
Фокус анализа: {focus}

КРИПЫ ДЛЯ АНАЛИЗА:
{creatives_text}

Верни JSON с паттернами, фразами и creative brief для нашего A21 content_creator."""

        from ubt_os.core.kb_writer import LEARN_INSTRUCTION
        eff_sys = _SYSTEM_PROMPT + (f"\n\n{kb_context}" if kb_context else "") + LEARN_INSTRUCTION
        resp = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=eff_sys,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = getattr(resp.content[0], "text", "")

        fallback: dict = {
            "hook_patterns": [],
            "content_structures": [],
            "key_phrases": [],
            "forbidden_phrases": [],
            "winning_formats": [],
            "creative_brief": raw[:500],
            "a21_prompt_extension": "",
        }
        data = _extract_json(raw, fallback)

        return SpyAnalysisResult(
            vertical=vertical,
            geo=geo,
            platform=platform,
            creatives_analyzed=len(creatives),
            hook_patterns=data.get("hook_patterns", []),
            content_structures=data.get("content_structures", []),
            key_phrases=data.get("key_phrases", []),
            forbidden_phrases=data.get("forbidden_phrases", []),
            winning_formats=data.get("winning_formats", []),
            creative_brief=data.get("creative_brief", ""),
            a21_prompt_extension=data.get("a21_prompt_extension", ""),
        )

    async def analyze_single(
        self,
        creative: str,
        vertical: str = "nutra",
        geo: str = "US",
        platform: str = "tiktok",
    ) -> SpyAnalysisResult:
        return await self.analyze([creative], vertical, geo, platform)

    async def compare_hooks(
        self,
        hooks: list[str],
        vertical: str = "nutra",
        geo: str = "US",
    ) -> dict:
        """Сравнивает несколько хуков и ранжирует их по потенциалу."""
        hooks_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(hooks))
        resp = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system="Ты эксперт по хукам в TikTok-рекламе. Верни JSON без лишнего текста.",
            messages=[{"role": "user", "content": f"""Вертикаль: {vertical}, GEO: {geo}

Оцени каждый хук по шкале 1-10 и объясни.
Хуки:
{hooks_text}

JSON формат:
{{
  "rankings": [
    {{"hook": "...", "score": 8, "reason": "...", "improvement": "..."}}
  ],
  "winner": "...",
  "winner_reason": "..."
}}"""}],
        )
        return _extract_json(getattr(resp.content[0], "text", ""), {"rankings": [], "winner": hooks[0] if hooks else "", "winner_reason": "Нет данных"})
