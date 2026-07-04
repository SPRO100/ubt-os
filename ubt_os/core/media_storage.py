"""
Единая точка загрузки видео/медиа в Supabase Storage — с организацией по
папкам (проект/аккаунт), чтобы ролики не сваливались в одну кучу и не
терялись. Используется higgsfield_queue (переносит temp CDN провайдера в
своё хранилище) и video_uniqualizer (кладёт уникализированные копии).
"""
from __future__ import annotations

import logging
import os
import uuid

import httpx

logger = logging.getLogger("ubt_os.media_storage")


async def upload_video(source: bytes | str, folder: str, filename: str | None = None) -> str:
    """
    Грузит видео в Supabase Storage под указанную папку, возвращает публичный URL.

    source   — готовые байты файла ИЛИ URL, откуда скачать (временный CDN-линк
               провайдера генерации — Higgsfield/fal/Pexels).
    folder   — путь папки в бакете, напр. "projects/{project_id}/{account_id}".
    filename — имя файла; по умолчанию случайный uuid.mp4.
    """
    supabase_url = os.environ["SUPABASE_URL"]
    service_key  = os.environ["SUPABASE_SERVICE_KEY"]
    bucket       = os.getenv("MEDIA_BUCKET", "media")
    name         = filename or f"{uuid.uuid4().hex}.mp4"
    path         = f"{folder.strip('/')}/{name}"

    async with httpx.AsyncClient(timeout=300) as client:
        if isinstance(source, str):
            resp = await client.get(source, follow_redirects=True, timeout=120)
            resp.raise_for_status()
            content = resp.content
        else:
            content = source

        put_resp = await client.post(
            f"{supabase_url}/storage/v1/object/{bucket}/{path}",
            # новые ключи sb_secret_* требуют и apikey, и Authorization
            headers={"Authorization": f"Bearer {service_key}",
                     "apikey": service_key,
                     "Content-Type": "video/mp4",
                     "x-upsert": "true"},
            content=content,
        )
        put_resp.raise_for_status()

    public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{path}"
    logger.info("media_storage: %s → %s", folder, public_url)
    return public_url


async def delete_video(storage_url: str) -> bool:
    """
    Удаляет объект из Supabase Storage по его публичному URL (тот, что вернул
    upload_video). Best-effort — не бросает исключение, только логирует и
    возвращает False, чтобы фоновая очистка не падала на одном плохом URL.
    """
    marker = "/storage/v1/object/public/"
    if marker not in storage_url:
        logger.warning("media_storage: не похоже на наш Storage URL, пропуск: %s", storage_url[:80])
        return False

    supabase_url = os.environ["SUPABASE_URL"]
    service_key  = os.environ["SUPABASE_SERVICE_KEY"]
    bucket, _, path = storage_url.split(marker, 1)[1].partition("/")
    if not path:
        logger.warning("media_storage: не удалось разобрать путь из %s", storage_url[:80])
        return False

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.request(
                "DELETE",
                f"{supabase_url}/storage/v1/object/{bucket}",
                headers={"Authorization": f"Bearer {service_key}", "apikey": service_key},
                json={"prefixes": [path]},
            )
            resp.raise_for_status()
        return True
    except Exception as e:
        logger.warning("media_storage: не удалось удалить %s: %s", storage_url[:80], e)
        return False
