"""
SOCIAL PUBLISHER — Прямая публикация без лимитов аккаунтов.
Вдохновлён API DOHOO.ai: поддержка 8 платформ, presigned S3 upload,
без ограничений на количество аккаунтов.

Поддерживаемые платформы:
  TikTok | YouTube | Instagram | Facebook | Pinterest | Threads | Twitter/X | LinkedIn

Запуск: POST /publish/direct
"""
from __future__ import annotations
import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx
from supabase import create_client, Client

logger = logging.getLogger("ubt_os.social_publisher")

RETRY_DELAYS = [15 * 60, 60 * 60, 60 * 60]
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1


@dataclass
class PublishRequest:
    """Унифицированный запрос публикации — платформонезависимый."""
    platform:     str
    account_id:   str                   # ID в таблице direct_publish_accounts
    media_url:    str                   # CDN URL видео / изображения
    caption:      str = ""
    hashtags:     list[str] = field(default_factory=list)
    content_type: str = "video"         # video | image | carousel | text
    scheduled_at: Optional[str] = None  # ISO8601 или None = сейчас
    extra:        dict = field(default_factory=dict)  # platform-specific params


@dataclass
class PublishResult:
    success:      bool
    platform_post_id: Optional[str] = None
    error:        Optional[str] = None
    raw_response: Optional[dict] = None


def _get_db() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


# ── Presigned S3 Upload (как у DOHOO) ─────────────────────

async def upload_to_s3_presigned(file_url: str) -> str:
    """
    Загружает медиафайл в Supabase Storage через presigned URL.
    Возвращает публичный CDN URL.
    Нужен если оригинальный URL временный (Higgsfield, etc.).
    """
    supabase_url  = os.environ["SUPABASE_URL"]
    service_key   = os.environ["SUPABASE_SERVICE_KEY"]
    bucket        = os.getenv("MEDIA_BUCKET", "media")
    filename      = f"pub_{int(datetime.now().timestamp())}.mp4"

    async with httpx.AsyncClient(timeout=300) as client:
        # 1. Получаем presigned URL от Supabase Storage
        resp = await client.post(
            f"{supabase_url}/storage/v1/object/upload/sign/{bucket}/{filename}",
            headers={"Authorization": f"Bearer {service_key}"},
            json={"expiresIn": 3600},
        )
        resp.raise_for_status()
        signed_url = resp.json()["signedURL"]

        # 2. Качаем оригинал
        source = await client.get(file_url, follow_redirects=True, timeout=120)
        source.raise_for_status()

        # 3. Заливаем в S3
        await client.put(
            signed_url,
            content=source.content,
            headers={"Content-Type": "video/mp4"},
        )

    public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{filename}"
    logger.info(f"S3 upload: {filename} → {public_url}")
    return public_url


# ── Базовый класс платформенного клиента ──────────────────

class PlatformClient:

    def __init__(self, credentials: dict):
        self.credentials = credentials

    async def publish(self, req: PublishRequest) -> PublishResult:
        raise NotImplementedError

    def _build_caption(self, caption: str, hashtags: list[str]) -> str:
        if not hashtags:
            return caption
        tags = " ".join(f"#{t.lstrip('#')}" for t in hashtags)
        return f"{caption}\n\n{tags}".strip()


# ── TikTok ────────────────────────────────────────────────

class TikTokClient(PlatformClient):
    """TikTok Content Posting API v2."""

    BASE = "https://open.tiktokapis.com/v2"

    async def publish(self, req: PublishRequest) -> PublishResult:
        token = self.credentials.get("access_token")
        if not token:
            return PublishResult(success=False, error="TikTok: нет access_token")

        caption = self._build_caption(req.caption, req.hashtags)[:2200]

        async with httpx.AsyncClient(timeout=120) as client:
            if req.content_type == "video":
                resp = await client.post(
                    f"{self.BASE}/post/publish/video/init/",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
                    json={
                        "post_info": {
                            "title": caption,
                            "privacy_level": req.extra.get("privacy_level", "PUBLIC_TO_EVERYONE"),
                            "disable_duet": req.extra.get("disable_duet", False),
                            "disable_stitch": req.extra.get("disable_stitch", False),
                        },
                        "source_info": {
                            "source": "PULL_FROM_URL",
                            "video_url": req.media_url,
                        },
                    }
                )
            else:
                # Photo carousel (TikTok Photo Mode)
                resp = await client.post(
                    f"{self.BASE}/post/publish/content/init/",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
                    json={
                        "post_info": {
                            "title": caption,
                            "privacy_level": "PUBLIC_TO_EVERYONE",
                            "photo_covered_count": 1,
                        },
                        "source_info": {
                            "source": "PULL_FROM_URL",
                            "photo_images": [req.media_url],
                            "photo_cover_index": 0,
                        },
                        "post_mode": "DIRECT_POST",
                        "media_type": "PHOTO",
                    }
                )

        if resp.status_code >= 400:
            return PublishResult(success=False, error=f"TikTok {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        publish_id = data.get("data", {}).get("publish_id")
        return PublishResult(success=True, platform_post_id=publish_id, raw_response=data)


# ── YouTube ───────────────────────────────────────────────

class YouTubeClient(PlatformClient):
    """YouTube Data API v3 — загрузка видео."""

    BASE = "https://www.googleapis.com/upload/youtube/v3"

    async def publish(self, req: PublishRequest) -> PublishResult:
        token = self.credentials.get("access_token")
        if not token:
            return PublishResult(success=False, error="YouTube: нет access_token")

        caption   = req.caption[:5000]
        tags      = req.hashtags[:500]
        privacy   = req.extra.get("privacy_status", "public")
        category  = req.extra.get("category_id", "22")

        async with httpx.AsyncClient(timeout=300) as client:
            source = await client.get(req.media_url, follow_redirects=True, timeout=180)
            source.raise_for_status()

            resp = await client.post(
                f"{self.BASE}/videos?uploadType=multipart&part=snippet,status",
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "metadata": (None, f"""{{
                        "snippet": {{
                            "title": "{caption[:100]}",
                            "description": "{caption}",
                            "tags": {tags},
                            "categoryId": "{category}"
                        }},
                        "status": {{"privacyStatus": "{privacy}"}}
                    }}""", "application/json; charset=UTF-8"),
                    "media": ("video.mp4", source.content, "video/mp4"),
                }
            )

        if resp.status_code >= 400:
            return PublishResult(success=False, error=f"YouTube {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return PublishResult(success=True, platform_post_id=data.get("id"), raw_response=data)


# ── Instagram ─────────────────────────────────────────────

class InstagramClient(PlatformClient):
    """Instagram Graph API — Reels, Photo, Carousel."""

    BASE = "https://graph.facebook.com/v19.0"

    async def publish(self, req: PublishRequest) -> PublishResult:
        token    = self.credentials.get("access_token")
        ig_user  = self.credentials.get("ig_user_id")
        if not token or not ig_user:
            return PublishResult(success=False, error="Instagram: нет access_token/ig_user_id")

        caption = self._build_caption(req.caption, req.hashtags)[:2200]

        async with httpx.AsyncClient(timeout=120) as client:
            if req.content_type in ("video", "reels"):
                container = await client.post(
                    f"{self.BASE}/{ig_user}/media",
                    params={
                        "media_type":  "REELS",
                        "video_url":   req.media_url,
                        "caption":     caption,
                        "share_to_feed": req.extra.get("share_to_feed", True),
                        "access_token": token,
                    }
                )
            elif req.content_type == "carousel":
                # Создаём контейнеры для каждого айтема
                items = req.extra.get("media_urls", [req.media_url])
                item_ids = []
                for item_url in items:
                    item_resp = await client.post(
                        f"{self.BASE}/{ig_user}/media",
                        params={
                            "image_url":    item_url,
                            "is_carousel_item": True,
                            "access_token": token,
                        }
                    )
                    item_ids.append(item_resp.json().get("id"))
                container = await client.post(
                    f"{self.BASE}/{ig_user}/media",
                    params={
                        "media_type":   "CAROUSEL",
                        "caption":      caption,
                        "children":     ",".join(item_ids),
                        "access_token": token,
                    }
                )
            else:
                container = await client.post(
                    f"{self.BASE}/{ig_user}/media",
                    params={
                        "image_url":    req.media_url,
                        "caption":      caption,
                        "access_token": token,
                    }
                )

            if container.status_code >= 400:
                return PublishResult(success=False, error=f"IG container {container.status_code}: {container.text[:200]}")
            container_id = container.json().get("id")

            # Публикуем контейнер
            publish = await client.post(
                f"{self.BASE}/{ig_user}/media_publish",
                params={"creation_id": container_id, "access_token": token}
            )

        if publish.status_code >= 400:
            return PublishResult(success=False, error=f"IG publish {publish.status_code}: {publish.text[:200]}")
        data = publish.json()
        return PublishResult(success=True, platform_post_id=data.get("id"), raw_response=data)


# ── Facebook ──────────────────────────────────────────────

class FacebookClient(PlatformClient):
    """Facebook Graph API — публикация на страницу."""

    BASE = "https://graph.facebook.com/v19.0"

    async def publish(self, req: PublishRequest) -> PublishResult:
        token   = self.credentials.get("access_token")
        page_id = self.credentials.get("page_id")
        if not token or not page_id:
            return PublishResult(success=False, error="Facebook: нет access_token/page_id")

        caption = self._build_caption(req.caption, req.hashtags)

        async with httpx.AsyncClient(timeout=120) as client:
            if req.content_type == "video":
                resp = await client.post(
                    f"{self.BASE}/{page_id}/videos",
                    params={
                        "file_url":    req.media_url,
                        "description": caption,
                        "access_token": token,
                    }
                )
            elif req.content_type in ("image", "photo"):
                resp = await client.post(
                    f"{self.BASE}/{page_id}/photos",
                    params={
                        "url":         req.media_url,
                        "caption":     caption,
                        "access_token": token,
                    }
                )
            else:
                resp = await client.post(
                    f"{self.BASE}/{page_id}/feed",
                    params={
                        "message":      caption,
                        "access_token": token,
                    }
                )

        if resp.status_code >= 400:
            return PublishResult(success=False, error=f"Facebook {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        post_id = data.get("id") or data.get("post_id")
        return PublishResult(success=True, platform_post_id=post_id, raw_response=data)


# ── Pinterest ─────────────────────────────────────────────

class PinterestClient(PlatformClient):
    """Pinterest API v5 — создание пинов."""

    BASE = "https://api.pinterest.com/v5"

    async def publish(self, req: PublishRequest) -> PublishResult:
        token    = self.credentials.get("access_token")
        board_id = self.credentials.get("board_id") or req.extra.get("board_id")
        if not token or not board_id:
            return PublishResult(success=False, error="Pinterest: нет access_token/board_id")

        caption = req.caption[:500]

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE}/pins",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "board_id":   board_id,
                    "title":      caption[:100],
                    "description": caption,
                    "media_source": {
                        "source_type": "video_url" if req.content_type == "video" else "image_url",
                        "url": req.media_url,
                    },
                    "link": req.extra.get("link"),
                }
            )

        if resp.status_code >= 400:
            return PublishResult(success=False, error=f"Pinterest {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return PublishResult(success=True, platform_post_id=data.get("id"), raw_response=data)


# ── Threads ───────────────────────────────────────────────

class ThreadsClient(PlatformClient):
    """Threads API — публикация постов."""

    BASE = "https://graph.threads.net/v1.0"

    async def publish(self, req: PublishRequest) -> PublishResult:
        token    = self.credentials.get("access_token")
        user_id  = self.credentials.get("threads_user_id")
        if not token or not user_id:
            return PublishResult(success=False, error="Threads: нет access_token/threads_user_id")

        caption = self._build_caption(req.caption, req.hashtags)[:500]

        async with httpx.AsyncClient(timeout=60) as client:
            params: dict[str, Any] = {"text": caption, "access_token": token}
            if req.media_url and req.content_type == "video":
                params.update({"media_type": "VIDEO", "video_url": req.media_url})
            elif req.media_url and req.content_type == "image":
                params.update({"media_type": "IMAGE", "image_url": req.media_url})
            else:
                params["media_type"] = "TEXT"

            container = await client.post(f"{self.BASE}/{user_id}/threads", params=params)
            if container.status_code >= 400:
                return PublishResult(success=False, error=f"Threads container {container.status_code}: {container.text[:200]}")
            container_id = container.json().get("id")

            publish = await client.post(
                f"{self.BASE}/{user_id}/threads_publish",
                params={"creation_id": container_id, "access_token": token}
            )

        if publish.status_code >= 400:
            return PublishResult(success=False, error=f"Threads publish {publish.status_code}: {publish.text[:200]}")
        data = publish.json()
        return PublishResult(success=True, platform_post_id=data.get("id"), raw_response=data)


# ── Twitter / X ───────────────────────────────────────────

class TwitterClient(PlatformClient):
    """Twitter API v2 — твиты с медиа."""

    BASE = "https://api.twitter.com/2"

    async def publish(self, req: PublishRequest) -> PublishResult:
        token = self.credentials.get("access_token")
        if not token:
            return PublishResult(success=False, error="Twitter: нет access_token")

        caption = self._build_caption(req.caption, req.hashtags)[:280]

        body: dict[str, Any] = {"text": caption}

        if req.media_url:
            media_id = await self._upload_media(req.media_url, token)
            if media_id:
                body["media"] = {"media_ids": [media_id]}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE}/tweets",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
            )

        if resp.status_code >= 400:
            return PublishResult(success=False, error=f"Twitter {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return PublishResult(success=True, platform_post_id=data.get("data", {}).get("id"), raw_response=data)

    async def _upload_media(self, media_url: str, token: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                src = await client.get(media_url, follow_redirects=True)
                init = await client.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"command": "INIT", "total_bytes": len(src.content), "media_type": "video/mp4"},
                )
                media_id = init.json().get("media_id_string")

                await client.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"command": "APPEND", "media_id": media_id, "segment_index": 0},
                    files={"media": src.content},
                )
                await client.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"command": "FINALIZE", "media_id": media_id},
                )
            return media_id
        except Exception as e:
            logger.warning(f"Twitter media upload error: {e}")
            return None


# ── LinkedIn ──────────────────────────────────────────────

class LinkedInClient(PlatformClient):
    """LinkedIn Share API — профессиональный контент."""

    BASE = "https://api.linkedin.com/v2"

    async def publish(self, req: PublishRequest) -> PublishResult:
        token   = self.credentials.get("access_token")
        person  = self.credentials.get("person_id")
        if not token or not person:
            return PublishResult(success=False, error="LinkedIn: нет access_token/person_id")

        caption = self._build_caption(req.caption, req.hashtags)[:3000]

        body: dict[str, Any] = {
            "author": f"urn:li:person:{person}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        if req.media_url and req.content_type in ("image", "photo"):
            media_urn = await self._register_image(req.media_url, token, person)
            if media_urn:
                body["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                body["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                    {"status": "READY", "media": media_urn, "description": {"text": caption[:200]}}
                ]

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE}/ugcPosts",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type":  "application/json",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                json=body,
            )

        if resp.status_code >= 400:
            return PublishResult(success=False, error=f"LinkedIn {resp.status_code}: {resp.text[:200]}")
        post_id = resp.headers.get("x-restli-id")
        return PublishResult(success=True, platform_post_id=post_id, raw_response=resp.json())

    async def _register_image(self, image_url: str, token: str, person: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                reg = await client.post(
                    f"{self.BASE}/assets?action=registerUpload",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={
                        "registerUploadRequest": {
                            "owner": f"urn:li:person:{person}",
                            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                            "serviceRelationships": [
                                {"identifier": "urn:li:userGeneratedContent", "relationshipType": "OWNER"}
                            ],
                        }
                    },
                )
                reg_data   = reg.json()
                upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                asset_urn  = reg_data["value"]["asset"]

                src = await client.get(image_url, follow_redirects=True)
                await client.put(
                    upload_url,
                    content=src.content,
                    headers={"Authorization": f"Bearer {token}"},
                )
            return asset_urn
        except Exception as e:
            logger.warning(f"LinkedIn image register error: {e}")
            return None


# ── Фабрика клиентов ──────────────────────────────────────

PLATFORM_CLIENTS: dict[str, type[PlatformClient]] = {
    "tiktok":    TikTokClient,
    "youtube":   YouTubeClient,
    "instagram": InstagramClient,
    "facebook":  FacebookClient,
    "pinterest": PinterestClient,
    "threads":   ThreadsClient,
    "twitter":   TwitterClient,
    "x":         TwitterClient,
    "linkedin":  LinkedInClient,
}


def get_client(platform: str, credentials: dict) -> PlatformClient:
    cls = PLATFORM_CLIENTS.get(platform.lower())
    if not cls:
        raise ValueError(f"Неизвестная платформа: {platform}")
    return cls(credentials)


# ── Главный Publisher с DLQ ───────────────────────────────

class DirectSocialPublisher:
    """
    Публикует напрямую в платформу без ограничений на кол-во аккаунтов.
    Поддерживает DLQ retry (аналог BlotatoPublisher, но без Blotato).
    """

    def __init__(self, db: Client):
        self.db = db

    async def publish(self, job_id: str) -> dict:
        job = (
            self.db.table("direct_publish_jobs")
            .select("*")
            .eq("id", job_id)
            .single()
            .execute()
            .data
        )
        if not job:
            raise ValueError(f"Job {job_id} не найдена")

        if job["status"] in ("published", "dead_letter"):
            return {"status": job["status"]}

        credentials = self._get_credentials(job["account_id"], job["platform"])
        client      = get_client(job["platform"], credentials)
        attempt     = job.get("attempt_count", 0) + 1

        self.db.table("direct_publish_jobs").update({
            "status": "processing",
            "attempt_count": attempt,
        }).eq("id", job_id).execute()

        req = PublishRequest(
            platform=job["platform"],
            account_id=job["account_id"],
            media_url=job.get("media_url", ""),
            caption=job.get("caption", ""),
            hashtags=job.get("hashtags", []),
            content_type=job.get("content_type", "video"),
            scheduled_at=job.get("scheduled_at"),
            extra=job.get("extra_params", {}),
        )

        result = await client.publish(req)

        if result.success:
            self.db.table("direct_publish_jobs").update({
                "status":           "published",
                "platform_post_id": result.platform_post_id,
                "published_at":     datetime.now(timezone.utc).isoformat(),
            }).eq("id", job_id).execute()
            logger.info(f"[DirectPublisher] ✅ {job_id[:8]} {job['platform']}: published")
            return {"status": "published", "platform_post_id": result.platform_post_id}

        return await self._handle_failure(job, attempt, result.error or "unknown error")

    def _get_credentials(self, account_id: str, platform: str) -> dict:
        res = (
            self.db.table("direct_publish_accounts")
            .select("access_token,refresh_token,platform_user_id,extra_data")
            .eq("account_id", account_id)
            .eq("platform", platform)
            .limit(1)
            .execute()
        ).data
        if not res:
            return {}
        row = res[0]
        creds = {
            "access_token":  row.get("access_token"),
            "refresh_token": row.get("refresh_token"),
        }
        creds.update(row.get("extra_data") or {})
        return creds

    async def _handle_failure(self, job: dict, attempt: int, error: str) -> dict:
        job_id = job["id"]
        if attempt >= MAX_ATTEMPTS:
            self.db.table("direct_publish_jobs").update({
                "status":        "dead_letter",
                "attempt_count": attempt,
                "last_error":    error,
            }).eq("id", job_id).execute()
            logger.error(f"[DirectPublisher] ❌ {job_id[:8]}: dead_letter после {attempt} попыток")
            await self._alert(job, attempt, error)
            return {"status": "dead_letter", "error": error}

        delay    = RETRY_DELAYS[attempt - 1]
        next_try = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
        self.db.table("direct_publish_jobs").update({
            "status":        "failed",
            "attempt_count": attempt,
            "last_error":    error,
            "scheduled_at":  next_try,
        }).eq("id", job_id).execute()
        logger.warning(f"[DirectPublisher] ⚠️ {job_id[:8]}: retry через {delay//60}мин")
        return {"status": "retry_scheduled", "next_try": next_try, "error": error}

    async def _alert(self, job: dict, attempt: int, error: str):
        bot_token = os.getenv("TELEGRAM_ALERT_BOT_TOKEN")
        chat_id   = os.getenv("TELEGRAM_ALERT_CHAT_ID")
        if not bot_token or not chat_id:
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": (
                            f"🚨 DIRECT PUBLISH DEAD LETTER\n"
                            f"ID: {job['id'][:8]}\n"
                            f"Платформа: {job['platform']}\n"
                            f"Попыток: {attempt}/{MAX_ATTEMPTS}\n"
                            f"Ошибка: {error[:200]}"
                        )
                    }
                )
        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")


# ── Быстрое создание + запуск джоба ──────────────────────

async def create_and_publish(
    platform:     str,
    account_id:   str,
    media_url:    str,
    caption:      str = "",
    hashtags:     list[str] | None = None,
    content_type: str = "video",
    extra:        dict | None = None,
) -> dict:
    """
    Создаёт джоб в direct_publish_jobs и сразу публикует.
    Лимитов на количество аккаунтов нет.
    """
    db = _get_db()

    res = db.table("direct_publish_jobs").insert({
        "platform":      platform,
        "account_id":    account_id,
        "media_url":     media_url,
        "caption":       caption,
        "hashtags":      hashtags or [],
        "content_type":  content_type,
        "extra_params":  extra or {},
        "status":        "pending",
        "scheduled_at":  datetime.now(timezone.utc).isoformat(),
    }).execute()

    job_id    = res.data[0]["id"]
    publisher = DirectSocialPublisher(db)
    result    = await publisher.publish(job_id)
    result["job_id"] = job_id
    return result


async def bulk_publish(jobs: list[dict]) -> list[dict]:
    """
    Массовая публикация — без ограничений на аккаунты.
    Запускает параллельно пачками по 5.
    """
    results = []
    for i in range(0, len(jobs), 5):
        batch = jobs[i:i+5]
        batch_results = await asyncio.gather(
            *[create_and_publish(**j) for j in batch],
            return_exceptions=True,
        )
        for j, r in zip(batch, batch_results):
            if isinstance(r, BaseException):
                logger.error(f"Bulk publish error для {j.get('platform')}: {r}")
                results.append({"status": "error", "error": str(r), **j})
            else:
                results.append(r)
        await asyncio.sleep(2)
    return results
