"""
A30 — HIGGSFIELD_AGENT
Генерация видео и каруселей через Higgsfield AI API.
Форматы:
  ugc      — UGC-видео 9:16 (TikTok / Instagram), hook + story + CTA
  shorts   — быстрый Short 15–60с
  carousel — мульти-слайд 1:1 или 4:5 (Facebook / Instagram, белые офферы)

Пайплайн: A21 (скрипт) → A30 (медиа) → A26 Publer (публикация)

ENV:
  HIGGSFIELD_API_KEY   — ключ Higgsfield AI
  HIGGSFIELD_API_URL   — кастомный эндпоинт (опционально)
"""
from __future__ import annotations
import asyncio, logging, os
from dataclasses import dataclass, field
from enum import Enum

import httpx
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.higgsfield_agent")

_API_BASE     = os.environ.get("HIGGSFIELD_API_URL", "https://mcp.higgsfield.ai/mcp")
_IMAGE_API    = "https://api.higgsfield.ai/v1/images"
_JOBS_API     = "https://api.higgsfield.ai/v1/jobs"
_POLL_INTERVAL = 5     # секунды между проверками статуса
_MAX_POLL      = 60    # максимум попыток = 5 минут


class VideoFormat(str, Enum):
    UGC      = "ugc"
    SHORTS   = "shorts"
    CAROUSEL = "carousel"


_UGC_MODEL = "seedance_2_0"

_VOICE_MAP = {
    "US": "confident American accent, casual & relatable",
    "BR": "Brazilian Portuguese, warm and energetic",
    "MX": "Mexican Spanish, friendly community tone",
    "DE": "German, clear and factual",
    "PL": "Polish, trustworthy and straightforward",
}

_CAROUSEL_STYLE_DESC = {
    "minimal":     "Clean white background, bold sans-serif typography, professional product photography",
    "lifestyle":   "Warm lifestyle photography, natural light, aspirational everyday setting",
    "testimonial": "Split-panel before/after style, authentic documentary feel",
    "edu":         "Infographic style, numbered steps, icons, educational layout, pastel palette",
}


@dataclass
class HiggsFieldResult:
    format: str
    status: str          # dry_run | pending | processing | completed | failed | timeout
    video_url: str | None = None
    thumbnail_url: str | None = None
    duration_sec: int | None = None
    slides: list[dict] = field(default_factory=list)
    job_id: str | None = None
    prompt_used: str = ""
    error: str | None = None


class HiggsFieldAgent:

    def __init__(self) -> None:
        self._api_key = os.environ.get("HIGGSFIELD_API_KEY", "")
        self._llm     = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    # ── PUBLIC API ────────────────────────────────────────

    async def generate_ugc(
        self,
        hook: str,
        story: str,
        cta: str,
        vertical: str = "nutra",
        geo: str = "US",
        avatar_style: str = "authentic",
        aspect_ratio: str = "9:16",
    ) -> HiggsFieldResult:
        """UGC-видео для TikTok/Instagram (9:16) или YouTube/горизонтальный формат (16:9)."""
        prompt = self._ugc_prompt(hook, story, cta, vertical, geo, avatar_style, aspect_ratio)
        return await self._submit_and_poll(prompt, _UGC_MODEL, VideoFormat.UGC, aspect_ratio)

    async def generate_shorts(
        self,
        script: str,
        style: str = "dynamic",
        vertical: str = "nutra",
        geo: str = "US",
        aspect_ratio: str = "9:16",
    ) -> HiggsFieldResult:
        """Short 15–60с с быстрым монтажом. 9:16 для TikTok/IG, 16:9 для YouTube Shorts."""
        voice = _VOICE_MAP.get(geo, _VOICE_MAP["US"])
        orient = "vertical" if aspect_ratio == "9:16" else "horizontal widescreen"
        prompt = (
            f"[SHORTS {style.upper()} {vertical.upper()} {geo}] "
            f"Voice: {voice}. "
            f"Script: {script} "
            f"Editing: fast cuts, trending sound, pattern interrupt every 3 seconds. "
            f"Aspect ratio {aspect_ratio} ({orient}). Duration 15–45 seconds."
        )
        return await self._submit_and_poll(prompt, _UGC_MODEL, VideoFormat.SHORTS, aspect_ratio)

    async def generate_carousel(
        self,
        offer_name: str,
        benefits: list[str],
        style: str = "minimal",
        vertical: str = "nutra",
        slide_count: int = 5,
        aspect_ratio: str = "1:1",
    ) -> HiggsFieldResult:
        """
        Мультислайдовая карусель для Facebook / Instagram.
        Оптимально для белых офферов: ecom, инфо-продукты, nutra с мягкими клеймами.
        Slide 1 = hook/проблема, Slides 2–N-1 = бенефиты, Last = CTA.
        """
        if not self._api_key:
            return HiggsFieldResult(
                format="carousel", status="dry_run",
                error="HIGGSFIELD_API_KEY не задан",
            )

        slides_content = await self._plan_slides(offer_name, benefits, style, vertical, slide_count)
        style_desc = _CAROUSEL_STYLE_DESC.get(style, _CAROUSEL_STYLE_DESC["minimal"])

        slide_results: list[dict] = []
        for i, slide in enumerate(slides_content):
            img_prompt = (
                f"{style_desc}. "
                f"Slide {i + 1} of {slide_count} for '{offer_name}'. "
                f"Visual: {slide.get('visual_prompt', slide.get('headline', ''))}. "
                f"Overlay text: '{slide.get('headline', '')}'. "
                f"Aspect ratio {aspect_ratio}. High-quality marketing image."
            )
            try:
                url = await self._gen_image(img_prompt)
                slide_results.append({
                    "slide_num": i + 1,
                    "headline":  slide.get("headline", ""),
                    "caption":   slide.get("caption", ""),
                    "url":       url,
                })
            except Exception as exc:
                logger.warning("carousel slide %d failed: %s", i + 1, exc)
                slide_results.append({
                    "slide_num": i + 1,
                    "headline":  slide.get("headline", ""),
                    "caption":   slide.get("caption", ""),
                    "url":       None,
                    "error":     str(exc),
                })

        ok_count = sum(1 for s in slide_results if s.get("url"))
        return HiggsFieldResult(
            format="carousel",
            status="completed" if ok_count > 0 else "failed",
            slides=slide_results,
            error=None if ok_count > 0 else "Ни один слайд не был создан",
        )

    async def check_status(self, job_id: str) -> HiggsFieldResult:
        """Проверяет статус асинхронного задания по job_id."""
        if not self._api_key:
            return HiggsFieldResult(format="ugc", status="error", error="HIGGSFIELD_API_KEY не задан")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{_JOBS_API}/{job_id}",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
            return HiggsFieldResult(
                format=data.get("format", "ugc"),
                status=data.get("status", "unknown"),
                video_url=data.get("output_url") or data.get("video_url"),
                thumbnail_url=data.get("thumbnail_url"),
                duration_sec=data.get("duration"),
                job_id=job_id,
            )
        except Exception as exc:
            return HiggsFieldResult(format="ugc", status="error", error=str(exc))

    # ── INTERNAL ─────────────────────────────────────────

    def _ugc_prompt(
        self, hook: str, story: str, cta: str,
        vertical: str, geo: str, avatar_style: str,
        aspect_ratio: str = "9:16",
    ) -> str:
        voice = _VOICE_MAP.get(geo, _VOICE_MAP["US"])
        orient = "vertical mobile" if aspect_ratio == "9:16" else "horizontal widescreen"
        return (
            f"[UGC {vertical.upper()} {geo}] "
            f"Avatar: {avatar_style}, {voice}. "
            f"HOOK (0–3s): {hook} "
            f"STORY (3–22s): {story} "
            f"CTA (last 5s): {cta} "
            f"Style: authentic handheld feel, no green screen, natural lighting. "
            f"Aspect ratio {aspect_ratio} ({orient}). Duration 25–40 seconds."
        )

    async def _submit_and_poll(
        self,
        prompt: str,
        model: str,
        fmt: VideoFormat,
        aspect_ratio: str,
    ) -> HiggsFieldResult:
        if not self._api_key:
            return HiggsFieldResult(
                format=fmt.value, status="dry_run",
                prompt_used=prompt[:300],
                error="HIGGSFIELD_API_KEY не задан",
            )
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    _API_BASE,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"model": model, "prompt": prompt, "aspect_ratio": aspect_ratio},
                )
                resp.raise_for_status()
                data = resp.json()

            # Синхронный ответ
            video_url = data.get("output_url") or data.get("video_url")
            if video_url:
                return HiggsFieldResult(
                    format=fmt.value, status="completed",
                    video_url=video_url,
                    thumbnail_url=data.get("thumbnail_url"),
                    duration_sec=data.get("duration"),
                    job_id=data.get("job_id") or data.get("id"),
                    prompt_used=prompt[:300],
                )

            # Асинхронный ответ — поллинг
            job_id = data.get("job_id") or data.get("id")
            if job_id:
                return await self._poll(job_id, fmt, prompt)

            return HiggsFieldResult(
                format=fmt.value, status="failed",
                error=f"Неожиданный ответ API: {str(data)[:300]}",
                prompt_used=prompt[:300],
            )

        except Exception as exc:
            logger.exception("higgsfield_agent | FAILED format=%s: %s", fmt.value, exc)
            return HiggsFieldResult(
                format=fmt.value, status="failed",
                error=str(exc), prompt_used=prompt[:300],
            )

    async def _poll(self, job_id: str, fmt: VideoFormat, prompt: str) -> HiggsFieldResult:
        for attempt in range(_MAX_POLL):
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"{_JOBS_API}/{job_id}",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                status = data.get("status", "processing")
                if status in ("completed", "done", "ready"):
                    return HiggsFieldResult(
                        format=fmt.value, status="completed",
                        video_url=data.get("output_url") or data.get("video_url"),
                        thumbnail_url=data.get("thumbnail_url"),
                        duration_sec=data.get("duration"),
                        job_id=job_id,
                        prompt_used=prompt[:300],
                    )
                if status in ("failed", "error"):
                    return HiggsFieldResult(
                        format=fmt.value, status="failed", job_id=job_id,
                        error=data.get("error", "Higgsfield API вернул ошибку"),
                        prompt_used=prompt[:300],
                    )
                logger.debug("poll attempt=%d status=%s job=%s", attempt + 1, status, job_id[:8])
            except Exception as exc:
                logger.warning("poll error attempt=%d: %s", attempt + 1, exc)

        return HiggsFieldResult(
            format=fmt.value, status="timeout", job_id=job_id,
            error=f"Timeout после {_MAX_POLL * _POLL_INTERVAL}с ожидания",
            prompt_used=prompt[:300],
        )

    async def _gen_image(self, prompt: str) -> str:
        """Генерирует одно изображение, возвращает URL."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                _IMAGE_API,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"prompt": prompt, "size": "1024x1024"},
            )
            resp.raise_for_status()
            data = resp.json()
        url = (
            data.get("url")
            or data.get("image_url")
            or (data.get("data") or [{}])[0].get("url")
        )
        if not url:
            raise ValueError(f"Нет URL в ответе: {str(data)[:200]}")
        return url

    async def _plan_slides(
        self,
        offer_name: str,
        benefits: list[str],
        style: str,
        vertical: str,
        slide_count: int,
    ) -> list[dict]:
        """Планирует контент каждого слайда через Claude Haiku."""
        benefits_str = "\n".join(f"- {b}" for b in benefits[:8])
        msg = (
            f"Create exactly {slide_count} carousel slides for '{offer_name}' ({vertical} offer).\n"
            f"Style: {style}\n"
            f"Benefits:\n{benefits_str}\n\n"
            f"Rules:\n"
            f"- Slide 1: hook or pain point (not product name)\n"
            f"- Slides 2–{slide_count - 1}: one benefit per slide\n"
            f"- Slide {slide_count}: CTA (action + urgency)\n\n"
            f"Return a JSON array of {slide_count} objects, each with:\n"
            f"  headline: string (max 8 words, bold text)\n"
            f"  caption: string (max 20 words, supporting text)\n"
            f"  visual_prompt: string (max 25 words, describe the image visual only)\n"
            f"Return ONLY the JSON array."
        )
        resp = await self._llm.messages.create(
            model="claude-sonnet-5",
            max_tokens=800,
            messages=[{"role": "user", "content": msg}],
        )
        raw = getattr(resp.content[0], "text", "")
        parsed = _extract_json(raw)
        if isinstance(parsed, list) and parsed:
            return parsed[:slide_count]
        # fallback
        return [
            {
                "headline":      b[:60],
                "caption":       f"Discover what {offer_name} can do for you",
                "visual_prompt": f"Product benefit visual: {b}",
            }
            for b in (benefits or [f"Try {offer_name}"])[:slide_count]
        ]


async def run(
    format: str = "ugc",
    hook: str = "",
    story: str = "",
    cta: str = "",
    vertical: str = "nutra",
    geo: str = "US",
    offer_name: str = "Product",
    benefits: list | None = None,
    carousel_style: str = "minimal",
    slide_count: int = 5,
    job_id: str = "",
) -> dict:
    agent = HiggsFieldAgent()

    if format == "check_status" and job_id:
        r = await agent.check_status(job_id)
        return {
            "format": r.format, "status": r.status,
            "video_url": r.video_url, "job_id": r.job_id, "error": r.error,
        }

    if format == "carousel":
        r = await agent.generate_carousel(
            offer_name, benefits or [], carousel_style, vertical, slide_count
        )
        return {
            "format": r.format, "status": r.status,
            "slides": r.slides, "slide_count": len(r.slides), "error": r.error,
        }

    if format == "shorts":
        script = " ".join(filter(None, [hook, story, cta]))
        r = await agent.generate_shorts(script, "dynamic", vertical, geo)
    else:  # ugc (default)
        r = await agent.generate_ugc(hook, story, cta, vertical, geo)

    return {
        "format":        r.format,
        "status":        r.status,
        "video_url":     r.video_url,
        "thumbnail_url": r.thumbnail_url,
        "duration_sec":  r.duration_sec,
        "job_id":        r.job_id,
        "prompt_used":   r.prompt_used,
        "error":         r.error,
    }
