"""
A19 — TEXT_HUMANIZER
Убирает AI-маркеры из контента перед публикацией через Blotato.
Основан на Stop-Slop методологии.
Запускается как пост-процессор в контент-пайплайне.
"""
from __future__ import annotations
import asyncio, logging, os
from dataclasses import dataclass
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.text_humanizer")

SYSTEM_PROMPT = """Ты — редактор, который делает AI-текст неотличимым от человеческого.

Твоя задача: получить текст и вернуть JSON с очищенной версией и оценками.

ПРАВИЛА ОЧИСТКИ:

Удалить полностью:
- Фразы-заглушки: "В заключение", "Таким образом", "Следует отметить", "Важно подчеркнуть"
- Усилители: "действительно", "безусловно", "несомненно", "очевидно", "буквально"
- Вводные: "Давайте рассмотрим", "Стоит отметить что"
- Мета-комментарии: "В данной статье", "Эта публикация расскажет"

Переписать:
- Пассивный залог → активный ("было сделано" → "сделал")
- Бинарные контрасты → убрать отрицание ("не сложно, а просто" → "просто")
- Все предложения одной длины → чередовать короткие и длинные
- Антропоморфизация ("статья объясняет" → "я объясню")
- Вопрос+ответ в одном абзаце → убрать риторический вопрос

Сохранить:
- Эмодзи если были
- Хэштеги если были
- Числа и факты
- Имена и бренды
- CTA-призывы

ОЦЕНКА (каждый параметр 1-10):
1. directness — говорит прямо без оговорок
2. rhythm — предложения разной длины и структуры
3. trust — не объясняет очевидное
4. authenticity — звучит как живой человек
5. density — каждое слово несёт смысл

Суммарный балл < 35 = нужна доработка.

ФОРМАТ ОТВЕТА (строго JSON):
{
  "original_score": {"directness": 0, "rhythm": 0, "trust": 0, "authenticity": 0, "density": 0, "total": 0},
  "humanized_text": "...",
  "final_score": {"directness": 0, "rhythm": 0, "trust": 0, "authenticity": 0, "density": 0, "total": 0},
  "changes_made": ["список изменений"],
  "passed": true
}"""


@dataclass
class HumanizeResult:
    original_text: str
    humanized_text: str
    original_score: dict
    final_score: dict
    changes_made: list[str]
    passed: bool


class TextHumanizer:

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self.client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    async def humanize(self, text: str, geo: str = "US", vertical: str = "nutra") -> HumanizeResult:
        user_msg = f"""GEO: {geo} | Вертикаль: {vertical}

Текст для очистки:
---
{text}
---

Верни JSON согласно инструкции."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw = getattr(response.content[0], "text", "")
        data = _extract_json(raw, fallback={
            "humanized_text": text,
            "original_score": {"total": 0},
            "final_score": {"total": 0},
            "changes_made": ["parse_error"],
            "passed": False,
        })

        result = HumanizeResult(
            original_text=text,
            humanized_text=data.get("humanized_text", text),
            original_score=data.get("original_score", {}),
            final_score=data.get("final_score", {}),
            changes_made=data.get("changes_made", []),
            passed=data.get("passed", False),
        )

        logger.info(
            "humanize | geo=%s vertical=%s score=%d→%d passed=%s",
            geo, vertical,
            result.original_score.get("total", 0),
            result.final_score.get("total", 0),
            result.passed,
        )

        if not result.passed:
            logger.warning("Текст не прошёл порог качества (total < 35), требует доработки")

        return result

    async def humanize_batch(self, texts: list[dict]) -> list[HumanizeResult]:
        """texts = [{"text": "...", "geo": "US", "vertical": "nutra"}, ...]"""
        tasks = [self.humanize(t["text"], t.get("geo", "US"), t.get("vertical", "nutra")) for t in texts]
        return await asyncio.gather(*tasks)


async def run(texts: list[dict]) -> list[HumanizeResult]:
    humanizer = TextHumanizer()
    return await humanizer.humanize_batch(texts)
