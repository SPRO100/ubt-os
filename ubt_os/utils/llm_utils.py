"""
Утилиты для работы с LLM-ответами.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any

logger = logging.getLogger("ubt_os.llm_utils")


def response_text(resp: Any) -> str:
    """Склеивает все текстовые блоки ответа Claude.

    resp.content[0] не всегда TextBlock — модель может первым вернуть
    ThinkingBlock или ToolUseBlock без атрибута .text. Берём только блоки
    с текстом, чтобы не падать с AttributeError.
    """
    parts = []
    for block in getattr(resp, "content", None) or []:
        t = getattr(block, "text", None)
        if isinstance(t, str):
            parts.append(t)
    return "".join(parts)


def _find_balanced_json(text: str) -> str | None:
    """Находит первый сбалансированный JSON-объект или массив в тексте.

    Корректно обрабатывает вложенность и скобки внутри строковых литералов,
    поэтому работает даже если Claude добавил пояснения до/после JSON.
    """
    start = None
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            open_ch, close_ch = ch, ("}" if ch == "{" else "]")
            break
    if start is None:
        return None

    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def extract_json(text: str, fallback: Any = None) -> Any:
    """Парсит JSON из ответа Claude.

    Стратегия (по порядку):
      1. Снимает markdown-обёртку ```json ... ``` если она есть.
      2. Пробует распарсить весь текст целиком.
      3. Вытаскивает первый сбалансированный {...} или [...] из текста
         (на случай, если модель добавила пояснения до/после JSON).

    Возвращает fallback если JSON невалидный и fallback задан,
    иначе пробрасывает JSONDecodeError.
    """
    t = text.strip()

    # 1. markdown fenced block — берём содержимое первого ```...``` блока
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", t, re.DOTALL)
    if m:
        t = m.group(1).strip()

    # 2. весь текст целиком
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # 3. первый сбалансированный JSON-объект/массив
    candidate = _find_balanced_json(t)
    if candidate is not None:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    if fallback is not None:
        logger.warning("Не удалось распарсить JSON из LLM-ответа. Используется fallback.")
        return fallback
    raise json.JSONDecodeError("No valid JSON found in text", t, 0)
