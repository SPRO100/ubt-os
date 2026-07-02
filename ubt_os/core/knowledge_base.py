"""
FIX #9: Knowledge Base — Версионирование
=========================================
Проблема: OPTIMIZER перезаписывает стратегии без истории.
Откатиться к "до изменения" невозможно.

Решение: immutable append-only записи + версии + superseded_by.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional
import uuid

logger = logging.getLogger("knowledge_base.versioning")


# ══════════════════════════════════════════════════════════
# 1. SQL СХЕМА
# ══════════════════════════════════════════════════════════

KB_SCHEMA_SQL = """
-- ─────────────────────────────────────────────────────
-- FIX #9: Knowledge Base с версионированием
-- Записи НИКОГДА не удаляются и не обновляются напрямую.
-- Новая версия создаётся как новая строка.
--
-- Реальная схема применяется через deploy/08_patch_kb_entries.sql.
-- Таблица называется kb_entries (НЕ knowledge_entries — та занята
-- под записи A18 knowledge_synthesizer со схемой type/content/date).
-- ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS kb_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Идентификация
    entry_key       TEXT NOT NULL,    -- например: "strategy.betting.tiktok"
    category        TEXT NOT NULL,    -- strategy | ban_pattern | content | metrics
    vertical        TEXT,             -- betting | nutra | both
    
    -- Содержимое
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,    -- markdown или JSON
    tags            TEXT[],
    
    -- Версионирование
    version         INT  NOT NULL DEFAULT 1,
    is_current      BOOLEAN NOT NULL DEFAULT TRUE,
    superseded_by   UUID REFERENCES kb_entries(id),
    
    -- Метаданные изменения
    changed_by      TEXT NOT NULL DEFAULT 'OPTIMIZER',  -- агент или 'user'
    change_reason   TEXT,                               -- почему изменено
    source_metric   TEXT,                               -- какая метрика триггернула
    source_value    NUMERIC,                            -- значение метрики
    
    -- Временные метки
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until     TIMESTAMPTZ                         -- NULL = активна
);

-- Уникальность: только одна current запись на ключ
CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_entries_current
    ON kb_entries(entry_key)
    WHERE is_current = TRUE;

-- Быстрый поиск по категории
CREATE INDEX IF NOT EXISTS idx_kb_entries_category   ON kb_entries(category);
CREATE INDEX IF NOT EXISTS idx_kb_entries_vertical   ON kb_entries(vertical);
CREATE INDEX IF NOT EXISTS idx_kb_entries_created    ON kb_entries(created_at DESC);

-- Таблица бан-паттернов (отдельная для быстрого поиска)
CREATE TABLE IF NOT EXISTS ban_patterns (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform        TEXT NOT NULL,
    pattern_type    TEXT NOT NULL,  -- shadow_ban | hard_ban | rate_limit
    trigger         TEXT NOT NULL,  -- что вызвало бан
    context         JSONB,          -- доп. данные
    account_id      UUID REFERENCES accounts(id),
    warming_day     INT,
    warming_phase   TEXT,
    logged_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ban_platform ON ban_patterns(platform, pattern_type);
"""


# ══════════════════════════════════════════════════════════
# 2. KNOWLEDGE BASE CLIENT
# ══════════════════════════════════════════════════════════

class KnowledgeBase:
    """
    Immutable append-only Knowledge Base.
    Новые версии создаются через update(), старые сохраняются.
    """

    # kb_entries — версионируемая таксономия. НЕ knowledge_entries (там A18).
    TABLE = "kb_entries"

    def __init__(self, db_client, table: str | None = None):
        self.db = db_client
        self.table = table or self.TABLE

    # ── ЧИТАТЬ ──────────────────────────────────────────

    def get_current(self, entry_key: str) -> Optional[dict]:
        """Возвращает актуальную версию записи."""
        res = (
            self.db.table(self.table)
            .select("*")
            .eq("entry_key", entry_key)
            .eq("is_current", True)
            .maybe_single()
            .execute()
        )
        return res.data

    def get_history(self, entry_key: str) -> list[dict]:
        """Возвращает полную историю изменений по ключу."""
        return (
            self.db.table(self.table)
            .select("id,version,title,changed_by,change_reason,created_at,is_current")
            .eq("entry_key", entry_key)
            .order("version", desc=True)
            .execute()
            .data
        )

    def search(self, category: str | None = None, vertical: str | None = None,
               tags: list[str] | None = None) -> list[dict]:
        """Поиск по категории/вертикали/тегам (только current)."""
        q = (
            self.db.table(self.table)
            .select("id,entry_key,title,category,vertical,version,created_at")
            .eq("is_current", True)
        )
        if category:
            q = q.eq("category", category)
        if vertical:
            q = q.in_("vertical", [vertical, "both"])
        if tags:
            q = q.overlaps("tags", tags)
        return q.order("created_at", desc=True).execute().data

    # ── ЗАПИСАТЬ / ОБНОВИТЬ ─────────────────────────────

    def create(
        self,
        entry_key:    str,
        category:     str,
        title:        str,
        content:      str,
        vertical:     str | None = None,
        tags:         list[str] | None = None,
        changed_by:   str = "OPTIMIZER",
        change_reason: str | None = None,
        source_metric: str | None = None,
        source_value:  float | None = None,
    ) -> dict:
        """Создаёт первую версию записи."""
        existing = self.get_current(entry_key)
        if existing:
            raise ValueError(
                f"Запись '{entry_key}' уже существует (v{existing['version']}). "
                f"Используй update() для изменения."
            )
        row = self.db.table(self.table).insert({
            "entry_key":    entry_key,
            "category":     category,
            "vertical":     vertical,
            "title":        title,
            "content":      content,
            "tags":         tags or [],
            "version":      1,
            "is_current":   True,
            "changed_by":   changed_by,
            "change_reason": change_reason,
            "source_metric": source_metric,
            "source_value":  source_value,
        }).execute().data[0]
        logger.info(f"[KB] Создана: {entry_key} v1 by {changed_by}")
        return row

    def update(
        self,
        entry_key:     str,
        content:       str,
        title:         str | None = None,
        tags:          list[str] | None = None,
        changed_by:    str = "OPTIMIZER",
        change_reason: str | None = None,
        source_metric: str | None = None,
        source_value:  float | None = None,
    ) -> dict:
        """
        Создаёт новую версию.
        Старая версия сохраняется с is_current=False.
        """
        now      = datetime.now(timezone.utc)
        current  = self.get_current(entry_key)

        if not current:
            # Создаём с нуля если не существует
            return self.create(
                entry_key=entry_key, category="strategy",
                title=title or entry_key, content=content,
                changed_by=changed_by, change_reason=change_reason,
            )

        new_version = current["version"] + 1
        new_id      = str(uuid.uuid4())

        # 1. Вставляем новую версию
        new_row = self.db.table(self.table).insert({
            "id":           new_id,
            "entry_key":    entry_key,
            "category":     current["category"],
            "vertical":     current.get("vertical"),
            "title":        title or current["title"],
            "content":      content,
            "tags":         tags if tags is not None else current.get("tags", []),
            "version":      new_version,
            "is_current":   True,
            "changed_by":   changed_by,
            "change_reason": change_reason,
            "source_metric": source_metric,
            "source_value":  source_value,
            "valid_from":   now.isoformat(),
        }).execute().data[0]

        # 2. Помечаем старую как устаревшую
        self.db.table(self.table).update({
            "is_current":   False,
            "superseded_by": new_id,
            "valid_until":  now.isoformat(),
        }).eq("id", current["id"]).execute()

        logger.info(
            f"[KB] Обновлена: {entry_key} "
            f"v{current['version']} → v{new_version} "
            f"by {changed_by} | причина: {change_reason}"
        )
        return new_row

    def rollback(self, entry_key: str, target_version: int) -> dict:
        """
        Откатывает к указанной версии.
        Создаёт НОВУЮ версию с содержимым старой (audit trail сохраняется).
        """
        history = self.get_history(entry_key)
        target  = next((h for h in history if h.get("version") == target_version), None)

        if not target:
            raise ValueError(f"Версия {target_version} не найдена для '{entry_key}'")

        # Получаем полный контент целевой версии
        full_target = (
            self.db.table(self.table)
            .select("*").eq("id", target["id"])
            .single().execute().data
        )

        return self.update(
            entry_key=    entry_key,
            content=      full_target["content"],
            title=        full_target["title"],
            changed_by=   "user",
            change_reason=f"Rollback к v{target_version}",
        )
