"""
A26 — BLOTATO_PUBLISHER
Публикация готового контента в TikTok / Instagram / YouTube Shorts через Blotato API.
Автоматически прогоняет текст через ComplianceGate (A25) перед отправкой.
Добавляет Keitaro UTM-параметры к ссылкам.
Логирует результат в Supabase таблицу published_posts.
"""
from __future__ import annotations
import asyncio, logging, os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import httpx

from ubt_os.agents.compliance_gate import ComplianceGate, RiskLevel

logger = logging.getLogger("ubt_os.blotato_publisher")

BLOTATO_API = os.environ.get("BLOTATO_API_URL", "https://api.blotato.com/v1")


class PublishPlatform(str, Enum):
    TIKTOK    = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE   = "youtube"


@dataclass
class PublishResult:
    platform: str
    status: str          # "published" | "blocked" | "failed" | "dry_run"
    post_id: str | None
    url: str | None
    compliance_score: int
    compliance_risk: str
    error: str | None = None
    published_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


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


class BlatoPublisher:

    def __init__(self):
        self.compliance = ComplianceGate()
        self._api_key = os.environ.get("BLOTATO_API_KEY", "")

    async def publish(
        self,
        text: str,
        platform: PublishPlatform,
        vertical: str = "nutra",
        geo: str = "US",
        affiliate_url: str = "",
        media_url: str = "",
        dry_run: bool = False,
    ) -> PublishResult:
        """
        Публикует пост.
        dry_run=True — проверяет compliance и возвращает что было бы отправлено,
        но не делает реальный запрос к Blotato.
        """
        # Шаг 1: Compliance Gate
        compliance = await self.compliance.check(text, vertical, geo)

        if compliance.is_blocked:
            logger.warning(
                "blotato_publisher | BLOCKED platform=%s risk=%s violations=%d",
                platform.value, compliance.risk_level.value, len(compliance.violations),
            )
            return PublishResult(
                platform=platform.value, status="blocked", post_id=None, url=None,
                compliance_score=compliance.score, compliance_risk=compliance.risk_level.value,
                error=f"Compliance Gate заблокировал: {compliance.reason}",
            )

        # Шаг 2: Используем чистую версию если compliance предложил исправление
        final_text = compliance.clean_version if compliance.clean_version else text

        # Шаг 3: Добавляем UTM к ссылке
        final_url = _build_utm(affiliate_url, vertical, geo, platform.value)

        if dry_run or not self._api_key:
            logger.info("blotato_publisher | DRY RUN platform=%s", platform.value)
            return PublishResult(
                platform=platform.value, status="dry_run", post_id=None,
                url=final_url,
                compliance_score=compliance.score,
                compliance_risk=compliance.risk_level.value,
                error=None if self._api_key else "BLOTATO_API_KEY не задан",
            )

        # Шаг 4: Отправка в Blotato
        payload = {
            "platform": platform.value,
            "text": final_text,
            "media_url": media_url,
            "link": final_url,
            "geo": geo,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{BLOTATO_API}/posts",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                post_id = data.get("id") or data.get("post_id")
                post_url = data.get("url") or data.get("post_url")

                logger.info(
                    "blotato_publisher | PUBLISHED platform=%s post_id=%s",
                    platform.value, post_id,
                )
                return PublishResult(
                    platform=platform.value, status="published",
                    post_id=post_id, url=post_url,
                    compliance_score=compliance.score,
                    compliance_risk=compliance.risk_level.value,
                )

        except Exception as exc:
            logger.exception("blotato_publisher | FAILED platform=%s: %s", platform.value, exc)
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
            self.publish(text, p, vertical, geo, affiliate_url, media_url, dry_run)
            for p in platforms
        ])


async def run(
    text: str = "",
    platform: str = "tiktok",
    vertical: str = "nutra",
    geo: str = "US",
    dry_run: bool = True,
) -> dict:
    publisher = BlatoPublisher()
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
