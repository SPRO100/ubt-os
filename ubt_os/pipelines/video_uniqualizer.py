"""
УНИКАЛИЗАТОР ВИДЕО — из одного готового ролика делает по одной визуально
уникальной копии на каждый ДРУГОЙ активный аккаунт того же проекта
(1 аккаунт = 1 проект — accounts.project_id).

Лёгкая уникализация: джиттер скорости, лёгкий зум-кроп, яркость/контраст,
зеркалирование, сброс метаданных + переэнкод — этого достаточно, чтобы
площадки не считали ролики дубликатами. Ничего не публикует — публикация
остаётся отдельным ручным шагом (принцип UBT OS: пользователь — финальное
решение).

Копии живут 24 часа (COPY_TTL_HOURS) — cleanup_expired_copies() чистит
просроченные по расписанию, оставляя строку как аудит-след. Повторный вызов
uniqualize_video на тот же оригинал пропускает аккаунты, у которых уже есть
живая копия — дублей не плодит.

Запуск: POST /video/uniqualize {"video_id": "..."}
       POST /video/cleanup-expired  (почасовой n8n-крон)
"""
from __future__ import annotations

import logging
import os
import random
import shutil
import subprocess  # nosec B404 — вызываем только фиксированный ffmpeg, без shell
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

from ubt_os.core.agent_api_layer import AccountReader, VideoReader, get_db
from ubt_os.core.media_storage import delete_video, upload_video
from ubt_os.utils.supabase_utils import one_row, rows

logger = logging.getLogger("ubt_os.video_uniqualizer")

# Границы лёгкого джиттера — заметно на уровне хэша/перцептивного отпечатка,
# незаметно для зрителя.
SPEED_RANGE    = (0.97, 1.03)
ZOOM_RANGE     = (1.01, 1.04)
BRIGHTNESS_RANGE = (-0.03, 0.03)
CONTRAST_RANGE = (0.96, 1.04)
FLIP_CHANCE    = 0.5

# Уникализированные копии живут ограниченное время — дёшево перегенерировать
# из оригинала, не нужно хранить вечно и захламлять галерею/Storage.
COPY_TTL_HOURS = 24


def _accounts_in_project(project_id: str, exclude_account_id: str | None) -> list[dict]:
    """Другие активные аккаунты того же проекта — цели уникализации."""
    q = (get_db().table("accounts").select("*")
         .eq("project_id", project_id).eq("status", "active"))
    accounts = rows(q.execute())
    if exclude_account_id:
        accounts = [a for a in accounts if str(a.get("id")) != str(exclude_account_id)]
    return accounts


def _accounts_with_live_copy(video_id: str) -> set[str]:
    """Аккаунты, у которых уже есть неистёкшая копия этого оригинала —
    чтобы не плодить дубли одного и того же видео при повторном клике."""
    existing = rows(
        get_db().table("videos").select("account_id")
        .eq("parent_video_id", video_id).eq("status", "ready").execute()
    )
    return {str(r["account_id"]) for r in existing if r.get("account_id")}


def jitter_params() -> dict:
    """Случайный набор лёгких параметров искажения для одной копии."""
    return {
        "speed": round(random.uniform(*SPEED_RANGE), 3),
        "zoom": round(random.uniform(*ZOOM_RANGE), 3),
        "brightness": round(random.uniform(*BRIGHTNESS_RANGE), 3),
        "contrast": round(random.uniform(*CONTRAST_RANGE), 3),
        "flip": random.random() < FLIP_CHANCE,
    }


def build_filters(params: dict) -> tuple[str, str]:
    """Строит ffmpeg -vf/-af строки из параметров джиттера."""
    zoom = params["zoom"]
    vf = [f"scale=iw*{zoom}:ih*{zoom}", f"crop=iw/{zoom}:ih/{zoom}"]
    if params["flip"]:
        vf.append("hflip")
    vf.append(f"eq=brightness={params['brightness']}:contrast={params['contrast']}")
    speed = params["speed"]
    vf.append(f"setpts={1 / speed}*PTS")
    af = f"atempo={max(0.5, min(2.0, speed))}"
    return ",".join(vf), af


def _run_ffmpeg_variant(src_url: str, out_path: str, params: dict) -> None:
    vf, af = build_filters(params)
    subprocess.run(  # nosec B603 — фиксированный бинарь, аргументы без shell
        ["ffmpeg", "-y", "-i", src_url, "-vf", vf, "-af", af,
         "-map_metadata", "-1", "-c:v", "libx264", "-c:a", "aac", out_path],
        check=True, capture_output=True, timeout=600,
    )


async def uniqualize_video(video_id: str) -> dict:
    """
    video_id — готовый (status=ready) исходный ролик с привязанным аккаунтом.
    Возвращает по одной новой записи videos на каждый другой активный аккаунт
    проекта аккаунта-источника.
    """
    if not shutil.which("ffmpeg"):
        return {"error": "ffmpeg недоступен на сервере — уникализация невозможна"}

    src = VideoReader.get_by_id(video_id)
    if not src:
        return {"error": f"видео {video_id} не найдено"}
    if src.get("status") != "ready" or not src.get("storage_url"):
        return {"error": "исходное видео ещё не готово (status != ready)"}

    src_account_id = src.get("account_id")
    if not src_account_id:
        return {"error": "у исходного видео не привязан аккаунт — некуда искать проект"}

    account = AccountReader.get_by_id(str(src_account_id))
    project_id = (account or {}).get("project_id")
    if not project_id:
        return {"error": "аккаунт-источник не привязан к проекту (accounts.project_id)"}

    targets = _accounts_in_project(project_id, exclude_account_id=src_account_id)
    if not targets:
        return {"error": "в проекте нет других активных аккаунтов для уникализации",
                 "project_id": project_id}

    have_copy = _accounts_with_live_copy(video_id)
    skipped = [str(a["id"]) for a in targets if str(a["id"]) in have_copy]
    targets = [a for a in targets if str(a["id"]) not in have_copy]

    created: list[dict] = []
    errors: list[dict] = []
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=COPY_TTL_HOURS)).isoformat()
    with tempfile.TemporaryDirectory() as td:
        for acc in targets:
            acc_id = acc["id"]
            out_path = os.path.join(td, f"{uuid.uuid4().hex}.mp4")
            try:
                _run_ffmpeg_variant(src["storage_url"], out_path, jitter_params())
                with open(out_path, "rb") as f:
                    content = f.read()
                folder = f"projects/{project_id}/{acc_id}/copies"
                storage_url = await upload_video(content, folder=folder)
                row = one_row(get_db().table("videos").insert({
                    "account_id": str(acc_id),
                    "parent_video_id": video_id,
                    "storage_url": storage_url,
                    "duration_sec": src.get("duration_sec"),
                    "status": "ready",
                    "expires_at": expires_at,
                }).execute())
                created.append({"account_id": acc_id, "video_id": row["id"], "storage_url": storage_url})
            except Exception as e:
                logger.warning("uniqualize(%s): аккаунт %s — ошибка: %s", video_id, acc_id, e)
                errors.append({"account_id": acc_id, "error": str(e)})

    logger.info("uniqualize(%s): создано %d, пропущено (уже есть копия) %d, ошибок %d",
                video_id, len(created), len(skipped), len(errors))
    return {
        "status": "ok" if created else ("skipped" if skipped and not errors else "failed"),
        "source_video_id": video_id, "project_id": project_id,
        "created": created, "skipped": skipped, "errors": errors,
    }


async def cleanup_expired_copies(limit: int = 200) -> dict:
    """
    Находит уникализированные копии с истёкшим expires_at, удаляет файл из
    Storage и помечает строку status='expired' (storage_url=NULL) — это и
    есть аудит-след: "у аккаунта была копия оригинала X, создана тогда-то".
    Оригиналы (parent_video_id IS NULL, expires_at IS NULL) не трогает.

    Запуск: POST /video/cleanup-expired (почасовой n8n-крон).
    """
    now = datetime.now(timezone.utc).isoformat()
    expired = rows(
        get_db().table("videos").select("id,storage_url")
        .eq("status", "ready")
        .lt("expires_at", now)
        .limit(limit)
        .execute()
    )

    cleaned, failed = 0, 0
    for v in expired:
        video_id = v["id"]
        storage_url = v.get("storage_url")
        ok = await delete_video(storage_url) if storage_url else True
        if not ok:
            failed += 1
            logger.warning("cleanup_expired_copies: не удалось удалить файл %s", video_id)
            continue
        get_db().table("videos").update({
            "status": "expired", "storage_url": None,
        }).eq("id", video_id).execute()
        cleaned += 1

    if expired:
        logger.info("cleanup_expired_copies: очищено %d, ошибок %d", cleaned, failed)
    return {"status": "ok", "checked": len(expired), "cleaned": cleaned, "failed": failed}


async def delete_video_cascade(video_id: str, dry_run: bool = True) -> dict:
    """
    Удаляет видео вместе со всей веткой его уникализированных копий
    (videos где parent_video_id = video_id) — если оригинал не устраивает,
    вся ветка дублей уходит вместе с ним. dry_run=true только считает.
    """
    video = VideoReader.get_by_id(video_id)
    if not video:
        return {"error": f"видео {video_id} не найдено"}

    copies = rows(get_db().table("videos").select("id,storage_url")
                  .eq("parent_video_id", video_id).execute())
    copy_ids = [c["id"] for c in copies]
    all_ids = [video_id] + copy_ids

    pub_ids = [p["id"] for p in rows(
        get_db().table("publications").select("id").in_("video_id", all_ids).execute()
    )]

    counts = {"copies": len(copy_ids), "publications": len(pub_ids)}
    if dry_run:
        return {"status": "dry_run", "video_id": video_id, "counts": counts}

    if pub_ids:
        get_db().table("publications").delete().in_("id", pub_ids).execute()

    for url in [video.get("storage_url"), *[c.get("storage_url") for c in copies]]:
        if url:
            await delete_video(url)

    get_db().table("videos").delete().in_("id", all_ids).execute()

    logger.info("delete_video_cascade(%s): удалено копий %d, публикаций %d",
                video_id, len(copy_ids), len(pub_ids))
    return {"status": "deleted", "video_id": video_id, "counts": counts}
