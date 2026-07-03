"""
УНИКАЛИЗАТОР ВИДЕО — из одного готового ролика делает по одной визуально
уникальной копии на каждый ДРУГОЙ активный аккаунт того же проекта
(1 аккаунт = 1 проект — accounts.project_id).

Лёгкая уникализация: джиттер скорости, лёгкий зум-кроп, яркость/контраст,
зеркалирование, сброс метаданных + переэнкод — этого достаточно, чтобы
площадки не считали ролики дубликатами. Ничего не публикует — публикация
остаётся отдельным ручным шагом (принцип UBT OS: пользователь — финальное
решение).

Запуск: POST /video/uniqualize {"video_id": "..."}
"""
from __future__ import annotations

import logging
import os
import random
import shutil
import subprocess  # nosec B404 — вызываем только фиксированный ffmpeg, без shell
import tempfile
import uuid

from ubt_os.core.agent_api_layer import AccountReader, VideoReader, get_db
from ubt_os.core.media_storage import upload_video
from ubt_os.utils.supabase_utils import one_row, rows

logger = logging.getLogger("ubt_os.video_uniqualizer")

# Границы лёгкого джиттера — заметно на уровне хэша/перцептивного отпечатка,
# незаметно для зрителя.
SPEED_RANGE    = (0.97, 1.03)
ZOOM_RANGE     = (1.01, 1.04)
BRIGHTNESS_RANGE = (-0.03, 0.03)
CONTRAST_RANGE = (0.96, 1.04)
FLIP_CHANCE    = 0.5


def _accounts_in_project(project_id: str, exclude_account_id: str | None) -> list[dict]:
    """Другие активные аккаунты того же проекта — цели уникализации."""
    q = (get_db().table("accounts").select("*")
         .eq("project_id", project_id).eq("status", "active"))
    accounts = rows(q.execute())
    if exclude_account_id:
        accounts = [a for a in accounts if str(a.get("id")) != str(exclude_account_id)]
    return accounts


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

    created: list[dict] = []
    errors: list[dict] = []
    with tempfile.TemporaryDirectory() as td:
        for acc in targets:
            acc_id = acc["id"]
            out_path = os.path.join(td, f"{uuid.uuid4().hex}.mp4")
            try:
                _run_ffmpeg_variant(src["storage_url"], out_path, jitter_params())
                with open(out_path, "rb") as f:
                    content = f.read()
                folder = f"projects/{project_id}/{acc_id}"
                storage_url = await upload_video(content, folder=folder)
                row = one_row(get_db().table("videos").insert({
                    "account_id": str(acc_id),
                    "parent_video_id": video_id,
                    "storage_url": storage_url,
                    "duration_sec": src.get("duration_sec"),
                    "status": "ready",
                }).execute())
                created.append({"account_id": acc_id, "video_id": row["id"], "storage_url": storage_url})
            except Exception as e:
                logger.warning("uniqualize(%s): аккаунт %s — ошибка: %s", video_id, acc_id, e)
                errors.append({"account_id": acc_id, "error": str(e)})

    logger.info("uniqualize(%s): создано %d, ошибок %d", video_id, len(created), len(errors))
    return {
        "status": "ok" if created else "failed",
        "source_video_id": video_id, "project_id": project_id,
        "created": created, "errors": errors,
    }
