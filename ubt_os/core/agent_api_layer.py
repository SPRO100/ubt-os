"""
FIX #1: Single Source of Truth — API-слой между агентами
=========================================================
Правило: агент НЕ пишет напрямую в чужую таблицу.
Каждый агент имеет свой ридер (read) и райтер (write).
Чужое — только через этот модуль (read-only).
"""

from __future__ import annotations
import os
from typing import Optional
from supabase import create_client, Client
from datetime import datetime, timezone

# ── инициализация ──────────────────────────────────────────
_supabase: Optional[Client] = None

def get_db() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_KEY"]   # service key — только внутри агентов
        )
    return _supabase


# ══════════════════════════════════════════════════════════
# READER: для всех агентов — читать можно всё
# ══════════════════════════════════════════════════════════

class AccountReader:
    """Только чтение. Writer — ACCOUNT_MANAGER."""

    @staticmethod
    def get_active(platform: str | None = None) -> list[dict]:
        q = get_db().table("accounts").select("*").eq("status", "active")
        if platform:
            q = q.eq("platform", platform)
        return q.execute().data

    @staticmethod
    def get_by_id(account_id: str) -> dict | None:
        res = get_db().table("accounts").select("*").eq("id", account_id).maybe_single().execute()
        return res.data

    @staticmethod
    def get_warming() -> list[dict]:
        return get_db().table("accounts").select("*").eq("status", "warming").execute().data


class ContentPlanReader:
    """Только чтение. Writer — CONTENT_CREATOR."""

    @staticmethod
    def get_approved() -> list[dict]:
        return (
            get_db().table("content_plans")
            .select("*")
            .eq("status", "approved")
            .execute().data
        )

    @staticmethod
    def get_by_id(plan_id: str) -> dict | None:
        res = get_db().table("content_plans").select("*").eq("id", plan_id).maybe_single().execute()
        return res.data


class VideoReader:
    """Только чтение. Writer — VIDEO_DIRECTOR."""

    @staticmethod
    def get_ready() -> list[dict]:
        return get_db().table("videos").select("*").eq("status", "ready").execute().data

    @staticmethod
    def get_by_id(video_id: str) -> dict | None:
        res = get_db().table("videos").select("*").eq("id", video_id).maybe_single().execute()
        return res.data


# ══════════════════════════════════════════════════════════
# WRITER: каждый агент — только своя таблица
# ══════════════════════════════════════════════════════════

class AccountWriter:
    """Только ACCOUNT_MANAGER должен использовать этот класс."""

    AGENT_NAME = "ACCOUNT_MANAGER"

    @classmethod
    def _check_ownership(cls, row: dict):
        if row.get("owned_by_agent") and row["owned_by_agent"] != cls.AGENT_NAME:
            raise PermissionError(
                f"Запись принадлежит {row['owned_by_agent']}, "
                f"не {cls.AGENT_NAME}. Используй Reader для чтения."
            )

    @classmethod
    def update_status(cls, account_id: str, status: str, extra: dict | None = None) -> dict:
        payload = {"status": status}
        if extra:
            payload.update(extra)
        return get_db().table("accounts").update(payload).eq("id", account_id).execute().data

    @classmethod
    def advance_warming_day(cls, account_id: str) -> dict:
        acc = AccountReader.get_by_id(account_id)
        if not acc:
            raise ValueError(f"Account {account_id} not found")
        new_day = acc["warming_day"] + 1
        phase = _warming_phase_for_day(new_day)
        return cls.update_status(account_id, "warming", {
            "warming_day": new_day,
            "warming_phase": phase,
            "last_action_at": datetime.now(timezone.utc).isoformat(),
        })


class ContentPlanWriter:
    """Только CONTENT_CREATOR."""

    @staticmethod
    def create(account_id: str, title: str, format: str,
               vertical: str, script: str, mcsla_prompt: str) -> dict:
        return get_db().table("content_plans").insert({
            "account_id":   account_id,
            "title":        title,
            "format":       format,
            "vertical":     vertical,
            "script":       script,
            "mcsla_prompt": mcsla_prompt,
            "status":       "draft",
        }).execute().data[0]

    @staticmethod
    def approve(plan_id: str, approved_by: str = "user") -> dict:
        return get_db().table("content_plans").update({
            "status": "approved",
            "approved_by": approved_by,
        }).eq("id", plan_id).execute().data


class VideoWriter:
    """Только VIDEO_DIRECTOR."""

    @staticmethod
    def create(content_plan_id: str) -> dict:
        return get_db().table("videos").insert({
            "content_plan_id": content_plan_id,
            "status": "queued",
        }).execute().data[0]

    @staticmethod
    def set_generating(video_id: str, job_id: str) -> dict:
        return get_db().table("videos").update({
            "higgsfield_job_id": job_id,
            "status": "generating",
        }).eq("id", video_id).execute().data

    @staticmethod
    def set_ready(video_id: str, storage_url: str, duration_sec: int) -> dict:
        return get_db().table("videos").update({
            "status": "ready",
            "storage_url": storage_url,
            "duration_sec": duration_sec,
        }).eq("id", video_id).execute().data

    @staticmethod
    def set_failed(video_id: str, error: str) -> dict:
        return get_db().table("videos").update({
            "status": "failed",
            "error_message": error,
        }).eq("id", video_id).execute().data


class PublicationWriter:
    """Только PUBLISHING."""

    @staticmethod
    def schedule(video_id: str, account_id: str, scheduled_at: datetime) -> dict:
        return get_db().table("publications").insert({
            "video_id":     video_id,
            "account_id":   account_id,
            "scheduled_at": scheduled_at.isoformat(),
            "status":       "scheduled",
        }).execute().data[0]

    @staticmethod
    def mark_published(pub_id: str, platform_post_id: str) -> dict:
        return get_db().table("publications").update({
            "status":           "published",
            "published_at":     datetime.now(timezone.utc).isoformat(),
            "platform_post_id": platform_post_id,
        }).eq("id", pub_id).execute().data

    @staticmethod
    def increment_attempt(pub_id: str, error: str) -> dict:
        pub = get_db().table("publications").select("attempt_count").eq("id", pub_id).single().execute().data
        new_count = (pub["attempt_count"] or 0) + 1
        new_status = "dead_letter" if new_count >= 3 else "failed"
        return get_db().table("publications").update({
            "attempt_count": new_count,
            "last_error":    error,
            "status":        new_status,
        }).eq("id", pub_id).execute().data


# ══════════════════════════════════════════════════════════
# ХЕЛПЕРЫ
# ══════════════════════════════════════════════════════════

def _warming_phase_for_day(day: int) -> str:
    """Возвращает фазу прогрева по номеру дня (см. Fix #4)."""
    if day <= 0:
        return "idle"
    elif day <= 3:
        return "views_only"
    elif day <= 5:
        return "neutral_content"
    elif day <= 7:
        return "niche_content"
    else:
        return "monetization"
