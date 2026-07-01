"""
Типобезопасное извлечение данных из ответов Supabase/postgrest.

postgrest ≥ 2.31 типизирует APIResponse.data как JSON
(bool | str | int | float | Sequence[JSON] | Mapping[str, JSON] | None),
из-за чего каждое обращение rows[0]["field"] ломает mypy.
Фактически select()/insert()/update() всегда возвращают список словарей,
поэтому здесь единая точка приведения типов.
"""
from __future__ import annotations

from typing import Any, cast


def rows(resp: Any) -> list[dict[str, Any]]:
    """Список строк из ответа запроса (пустой список, если data пуст)."""
    return cast("list[dict[str, Any]]", getattr(resp, "data", None) or [])


def first_row(resp: Any) -> dict[str, Any] | None:
    """Первая строка ответа или None (для .limit(1) / .maybe_single())."""
    data = getattr(resp, "data", None)
    if data is None:
        return None
    if isinstance(data, list):
        return cast("dict[str, Any]", data[0]) if data else None
    return cast("dict[str, Any]", data)


def one_row(resp: Any) -> dict[str, Any]:
    """Единственная строка ответа (для .single() / insert().data[0])."""
    data = getattr(resp, "data", None)
    if isinstance(data, list):
        return cast("dict[str, Any]", data[0])
    return cast("dict[str, Any]", data)
