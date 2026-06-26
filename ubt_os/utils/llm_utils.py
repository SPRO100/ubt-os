"""
Утилиты для работы с LLM-ответами.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any

logger = logging.getLogger("ubt_os.llm_utils")


def extract_json(text: str, fallback: Any = None) -> Any:
    """Парсит JSON из ответа Claude, убирая markdown-обёртку ```json ... ```.

    Возвращает fallback если JSON невалидный и fallback задан,
    иначе пробрасывает JSONDecodeError.
    """
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*\n(.*)\n```\s*$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        if fallback is not None:
            logger.warning(f"Не удалось распарсить JSON из LLM-ответа: {e}. Используется fallback.")
            return fallback
        raise
