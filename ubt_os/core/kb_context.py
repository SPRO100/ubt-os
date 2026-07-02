"""
Загрузка релевантных записей KB для system prompt агентов.

Использование в агенте:
    from ubt_os.core.kb_context import load_kb_context
    kb_section = load_kb_context(db, process="zaliv", platform="tiktok", vertical="nutra")
    system_prompt = f"...\n\n{kb_section}"
"""
from __future__ import annotations
import logging

logger = logging.getLogger("kb_context")


def load_kb_context(
    db,
    *,
    process: str | None = None,
    platform: str | None = None,
    vertical: str | None = None,
    scheme: str | None = None,
    limit: int = 6,
    max_content_chars: int = 600,
) -> str:
    """
    Загружает релевантные записи из kb_entries и возвращает
    отформатированный блок для вставки в system prompt.

    Порядок приоритета:
      1. Записи с точным совпадением process + platform + vertical
      2. Записи с совпадением process + vertical (любая площадка)
      3. Записи с совпадением vertical (любой процесс/площадка)
    Объединяем без дублей, ограничиваем limit.
    """
    try:
        entries = _fetch_relevant(db, process=process, platform=platform,
                                  vertical=vertical, scheme=scheme, limit=limit)
        if not entries:
            return ""
        lines = ["## БАЗА ЗНАНИЙ (применимые практики)\n"]
        for e in entries:
            content_preview = (e.get("content") or "")[:max_content_chars]
            if len(e.get("content") or "") > max_content_chars:
                content_preview += "…"
            lines.append(f"**[{e['entry_key']}] {e['title']}**\n{content_preview}\n")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("kb_context: не удалось загрузить записи: %s", exc)
        return ""


def _fetch_relevant(db, *, process, platform, vertical, scheme, limit) -> list[dict]:
    """Собирает записи в порядке убывания специфичности."""
    seen: set[str] = set()
    result: list[dict] = []

    # Проход 1: точное совпадение process + platform + vertical
    if process and platform and vertical:
        _add_from(db, seen, result, limit,
                  process=process, platform=platform, vertical=vertical, scheme=scheme)

    # Проход 2: process + vertical (любая площадка, включая 'any')
    if process and vertical and len(result) < limit:
        _add_from(db, seen, result, limit,
                  process=process, platform=None, vertical=vertical, scheme=scheme)

    # Проход 3: только vertical (любой процесс)
    if vertical and len(result) < limit:
        _add_from(db, seen, result, limit,
                  process=None, platform=None, vertical=vertical, scheme=scheme)

    # Проход 4: process без vertical-фильтра (если vertical не задан)
    if process and not vertical and len(result) < limit:
        _add_from(db, seen, result, limit,
                  process=process, platform=None, vertical=None, scheme=None)

    return result[:limit]


def _add_from(db, seen: set, result: list, limit: int, *,
              process, platform, vertical, scheme):
    if len(result) >= limit:
        return
    try:
        q = (
            db.table("kb_entries")
            .select("entry_key,title,content,category,vertical")
            .eq("is_current", True)
        )
        if process:
            q = q.eq("category", process)
        if vertical:
            q = q.in_("vertical", [vertical, "both", "any"])
        if platform:
            q = q.like("entry_key", f"%.{platform}.%")
        if scheme:
            q = q.like("entry_key", f"%.{scheme}")
        rows = q.order("created_at", desc=True).limit(limit).execute().data or []
        for row in rows:
            key = row.get("entry_key", "")
            if key and key not in seen:
                seen.add(key)
                result.append(row)
                if len(result) >= limit:
                    break
    except Exception as exc:
        logger.warning("kb_context._add_from: %s", exc)
