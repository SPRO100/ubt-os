"""
Запись знаний в kb_entries и извлечение [LEARN:] маркеров из ответов агентов.

Используется из main.py после каждого агентского вызова: агент может вставить
маркер [LEARN:] в конец текстового поля — main.py извлечёт, сохранит в KB и
уберёт маркер из ответа до отправки на дашборд.
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger("kb_writer")

_LEARN_RE = re.compile(r"\[LEARN:\s*([^|\]]+)\|([^|\]]+)\|([^\]]+)\]", re.DOTALL)

# Инструкция самообучения — добавляется в конец kb_context для агентов,
# которые генерируют свободный текст и могут обнаружить новый паттерн.
LEARN_INSTRUCTION = (
    "\n\nСАМООБУЧЕНИЕ: Если в ходе работы обнаружил новый устойчивый паттерн "
    "(рабочий хук, лимит платформы, антибан-приём, эффективную схему) — "
    "зафикси в конце своего текстового ответа:\n"
    "[LEARN: entry_key|Заголовок|Суть в 1-3 предложениях]\n"
    "entry_key = <процесс>.<площадка>.<вертикаль>.<схема>  "
    "(пример: content.tiktok.nutra.grey)\n"
    "Максимум 1 маркер. Только реально новое и проверяемое."
)


def parse_learn_markers(text: str) -> list[dict]:
    """Извлекает [LEARN:] маркеры из текста."""
    results = []
    for m in _LEARN_RE.finditer(text):
        entry_key = m.group(1).strip()
        title     = m.group(2).strip()
        content   = m.group(3).strip()
        if entry_key and title and content:
            results.append({"entry_key": entry_key, "title": title, "content": content})
    return results


def strip_learn_markers(text: str) -> str:
    """Убирает [LEARN:] маркеры из строки."""
    return _LEARN_RE.sub("", text).strip()


def scan_and_strip(result: object) -> tuple[object, list[dict]]:
    """
    Рекурсивно обходит dict/list/str, извлекает [LEARN:] маркеры и
    возвращает (очищенный_result, список_learnings).
    """
    learnings: list[dict] = []

    def _process(obj: object) -> object:
        if isinstance(obj, str):
            found = parse_learn_markers(obj)
            if found:
                learnings.extend(found)
                return strip_learn_markers(obj)
            return obj
        if isinstance(obj, list):
            return [_process(item) for item in obj]
        if isinstance(obj, dict):
            return {k: _process(v) for k, v in obj.items()}
        return obj

    return _process(result), learnings


def save_kb_entry(
    db,
    entry_key: str,
    title: str,
    content: str,
    category: str | None = None,
    vertical: str = "any",
) -> bool:
    """
    Записывает или обновляет запись в kb_entries.
    Предыдущая версия с тем же entry_key помечается is_current=False.
    """
    try:
        db.table("kb_entries").update({"is_current": False}).eq(
            "entry_key", entry_key
        ).eq("is_current", True).execute()

        if category is None:
            category = entry_key.split(".")[0] if "." in entry_key else entry_key

        db.table("kb_entries").insert({
            "entry_key":  entry_key,
            "title":      title,
            "content":    content,
            "category":   category,
            "vertical":   vertical,
            "is_current": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        logger.info("kb_writer: сохранена запись %s", entry_key)
        return True
    except Exception as exc:
        logger.warning("kb_writer: ошибка сохранения %s: %s", entry_key, exc)
        return False


def save_learnings(db, learnings: list[dict], default_vertical: str = "any") -> int:
    """Сохраняет список learnings, возвращает число сохранённых записей."""
    saved = 0
    for item in learnings:
        key   = item.get("entry_key", "")
        parts = key.split(".")
        # Вертикаль — третий сегмент entry_key (process.platform.vertical.scheme)
        vertical = parts[2] if len(parts) >= 3 else default_vertical
        if vertical not in ("nutra", "betting", "both", "any"):
            vertical = default_vertical
        ok = save_kb_entry(
            db,
            entry_key=key,
            title=item.get("title", ""),
            content=item.get("content", ""),
            vertical=vertical,
        )
        if ok:
            saved += 1
    return saved
