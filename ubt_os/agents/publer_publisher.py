"""
A26 — PUBLER_PUBLISHER
Публикация готового контента в TikTok / Facebook / Instagram / Pinterest через Publer API.
Автоматически прогоняет текст через ComplianceGate (A25) перед отправкой.
Добавляет Keitaro UTM-параметры к ссылкам.

Настройка:
  PUBLER_API_KEY                     — API ключ Publer ($12/мес, уже прошёл TikTok audit)
  PUBLER_TIKTOK_PROFILE_IDS          — ID профилей TikTok через запятую
  PUBLER_FACEBOOK_PROFILE_IDS        — ID профилей Facebook Pages через запятую
  PUBLER_INSTAGRAM_PROFILE_IDS       — ID профилей Instagram через запятую
  PUBLER_PINTEREST_PROFILE_IDS       — ID профилей Pinterest через запятую
  PUBLER_PINTEREST_BOARD_IDS         — ID досок Pinterest (опционально, одна на профиль)
"""
from __future__ import annotations
import asyncio, logging, os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import httpx

from ubt_os.agents.compliance_gate import ComplianceGate

logger = logging.getLogger("ubt_os.publer_publisher")

PUBLER_API = "https://app.publer.io/api/v1"


class PublishPlatform(str, Enum):
    TIKTOK    = "tiktok"
    FACEBOOK  = "facebook"
    INSTAGRAM = "instagram"
    PINTEREST = "pinterest"


@dataclass
class PublishResult:
    platform: str
    status: str          # "published" | "blocked" | "failed" | "dry_run"
    post_id: str | None
    url: str | None
    compliance_score: int
    compliance_risk: str
    error: str | None = None
    published_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _build_utm(base_url: str, vertical: str, geo: str, platform: str) -> str:
    """Добавляет Keitaro UTM к affiliate-ссылке."""
    if not base_url:
        return base_url
    sep = "&" if "?" in base_url else "?"
    return (
        f"{base_url}{sep}"
        f"utm_source={platform}&utm_medium=organic&utm_campaign={vertical}_{geo}"
        f"&utm_content=ubt_os"
    )


def _get_profile_ids(platform: str) -> list[str]:
    """Получает profile_ids из env для заданной платформы."""
    env_map = {
        "tiktok":    "PUBLER_TIKTOK_PROFILE_IDS",
        "facebook":  "PUBLER_FACEBOOK_PROFILE_IDS",
        "instagram": "PUBLER_INSTAGRAM_PROFILE_IDS",
        "pinterest": "PUBLER_PINTEREST_PROFILE_IDS",
    }
    raw = os.environ.get(env_map.get(platform, ""), "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def _get_pinterest_board_ids() -> list[str]:
    """Получает board_ids для Pinterest (опционально)."""
    raw = os.environ.get("PUBLER_PINTEREST_BOARD_IDS", "")
    return [x.strip() for x in raw.split(",") if x.strip()]


class PubelerPublisher:

    def __init__(self) -> None:
        self.compliance = ComplianceGate()
        self._api_key = os.environ.get("PUBLER_API_KEY", "")

    async def publish(
        self,
        text: str,
        platform: PublishPlatform,
        vertical: str = "nutra",
        geo: str = "US",
        affiliate_url: str = "",
        media_url: str = "",
        profile_ids: list[str] | None = None,
        dry_run: bool = False,
    ) -> PublishResult:
        """
        Публикует пост через Publer API.
        dry_run=True — только проверяет compliance, без реального запроса к Publer.
        """
        compliance = await self.compliance.check(text, vertical, geo)

        if compliance.is_blocked:
            logger.warning(
                "publer_publisher | BLOCKED platform=%s risk=%s violations=%d",
                platform.value, compliance.risk_level.value, len(compliance.violations),
            )
            return PublishResult(
                platform=platform.value, status="blocked", post_id=None, url=None,
                compliance_score=compliance.score, compliance_risk=compliance.risk_level.value,
                error=f"Compliance Gate заблокировал: {compliance.reason}",
            )

        final_text = compliance.clean_version if compliance.clean_version else text
        final_url  = _build_utm(affiliate_url, vertical, geo, platform.value)
        pids       = profile_ids or _get_profile_ids(platform.value)

        if dry_run or not self._api_key:
            logger.info("publer_publisher | DRY RUN platform=%s profile_ids=%s", platform.value, pids)
            return PublishResult(
                platform=platform.value, status="dry_run", post_id=None,
                url=final_url,
                compliance_score=compliance.score,
                compliance_risk=compliance.risk_level.value,
                error=None if self._api_key else "PUBLER_API_KEY не задан",
            )

        if not pids:
            env_hint = f"PUBLER_{platform.value.upper()}_PROFILE_IDS"
            return PublishResult(
                platform=platform.value, status="failed", post_id=None, url=None,
                compliance_score=compliance.score, compliance_risk=compliance.risk_level.value,
                error=f"Не заданы profile_ids. Добавь {env_hint} в переменные окружения.",
            )

        payload: dict = {"profile_ids": pids, "text": final_text}
        if media_url:
            payload["media_urls"] = [media_url]
        if final_url:
            payload["link"] = final_url
        if platform == PublishPlatform.PINTEREST:
            board_ids = _get_pinterest_board_ids()
            if board_ids:
                payload["board_ids"] = board_ids

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{PUBLER_API}/posts",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                post_id  = data.get("id") or data.get("post_id")
                post_url = data.get("url") or data.get("post_url") or data.get("link")

                logger.info(
                    "publer_publisher | PUBLISHED platform=%s post_id=%s",
                    platform.value, post_id,
                )
                return PublishResult(
                    platform=platform.value, status="published",
                    post_id=str(post_id) if post_id else None,
                    url=post_url,
                    compliance_score=compliance.score,
                    compliance_risk=compliance.risk_level.value,
                )

        except Exception as exc:
            logger.exception("publer_publisher | FAILED platform=%s: %s", platform.value, exc)
            return PublishResult(
                platform=platform.value, status="failed", post_id=None, url=None,
                compliance_score=compliance.score, compliance_risk=compliance.risk_level.value,
                error=str(exc),
            )

    async def publish_all(
        self,
        text: str,
        platforms: list[PublishPlatform],
        vertical: str = "nutra",
        geo: str = "US",
        affiliate_url: str = "",
        media_url: str = "",
        dry_run: bool = False,
    ) -> list[PublishResult]:
        """Публикует на несколько платформ параллельно."""
        return await asyncio.gather(*[
            self.publish(text, p, vertical, geo, affiliate_url, media_url, dry_run=dry_run)
            for p in platforms
        ])


# Обратная совместимость — старые импорты BlatoPublisher продолжают работать
BlatoPublisher = PubelerPublisher


async def run(
    text: str = "",
    platform: str = "tiktok",
    vertical: str = "nutra",
    geo: str = "US",
    dry_run: bool = True,
) -> dict:
    publisher = PubelerPublisher()
    result = await publisher.publish(
        text or "Check out this amazing product that changed my life!",
        PublishPlatform(platform),
        vertical, geo, dry_run=dry_run,
    )
    return {
        "status": result.status,
        "platform": result.platform,
        "compliance_score": result.compliance_score,
        "compliance_risk": result.compliance_risk,
        "url": result.url,
        "error": result.error,
    }
