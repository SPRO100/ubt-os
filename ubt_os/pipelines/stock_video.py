"""
STOCK_VIDEO_PIPELINE — бесплатная генерация faceless-видео без GPU.

Конвейер (все компоненты уже в системе):
  скрипт → ключевые слова (Haiku) → стоковые клипы Pexels (бесплатный API)
  → озвучка A35 (edge-tts, бесплатно) → ffmpeg: кроп 9:16, склейка, голос
  → Supabase Storage → публичный URL.

Себестоимость ролика ≈ токены Haiku (< $0.01). Работает на VDS без GPU.
Требует: PEXELS_API_KEY (бесплатная регистрация, 200 req/час), ffmpeg.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path

import httpx

from ubt_os.agents.tts_agent import synth_speech, estimate_duration
from ubt_os.utils.llm_utils import extract_json, response_text

logger = logging.getLogger("ubt_os.stock_video")

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"

# Запасные ключевые слова, если Haiku недоступен
FALLBACK_KEYWORDS = {
    "nutra":   ["healthy lifestyle", "fitness woman morning", "fresh vegetables"],
    "betting": ["stadium crowd cheering", "soccer goal celebration", "sports fans"],
}

OUT_W, OUT_H, OUT_FPS = 1080, 1920, 30


# ── Чистые функции (тестируемые) ──────────────────────────

def pick_video_files(pexels_response: dict, max_clips: int) -> list[str]:
    """Выбирает из ответа Pexels ссылки на вертикальные mp4 (лучшее качество ≤1080p)."""
    urls: list[str] = []
    for video in pexels_response.get("videos", []):
        files = [
            f for f in video.get("video_files", [])
            if f.get("file_type") == "video/mp4"
            and (f.get("height") or 0) >= 960
            and (f.get("width") or 0) <= (f.get("height") or 0)  # вертикаль/квадрат
        ]
        if not files:
            continue
        files.sort(key=lambda f: f.get("height") or 0)
        urls.append(files[0]["link"])
        if len(urls) >= max_clips:
            break
    return urls


def fallback_keywords(vertical: str) -> list[str]:
    return FALLBACK_KEYWORDS.get(vertical, FALLBACK_KEYWORDS["nutra"])


# ── Ключевые слова через Haiku ────────────────────────────

async def extract_keywords(script: str, vertical: str, geo: str) -> list[str]:
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic()
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": (
                "По скрипту вертикального видео подбери 3 английских поисковых "
                "запроса для стоковых видеоклипов (Pexels). Визуальные сцены, "
                "без брендов и текста. Ответ строго JSON: "
                '{"keywords": ["...", "...", "..."]}\n\n'
                f"Вертикаль: {vertical}, GEO: {geo}\nСкрипт: {script[:600]}"
            )}],
        )
        data = extract_json(response_text(resp), fallback={})
        kws = [str(k) for k in data.get("keywords", []) if k]
        return kws[:3] or fallback_keywords(vertical)
    except Exception as e:
        logger.warning("stock_video: keywords через Haiku не удались: %s", e)
        return fallback_keywords(vertical)


# ── Pexels ────────────────────────────────────────────────

async def search_stock_clips(keywords: list[str], max_clips: int, api_key: str) -> list[str]:
    urls: list[str] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for kw in keywords:
            if len(urls) >= max_clips:
                break
            try:
                resp = await client.get(
                    PEXELS_SEARCH_URL,
                    headers={"Authorization": api_key},
                    params={"query": kw, "orientation": "portrait", "per_page": 3},
                )
                resp.raise_for_status()
                urls += [u for u in pick_video_files(resp.json(), max_clips - len(urls))
                         if u not in urls]
            except Exception as e:
                logger.warning("stock_video: Pexels '%s' ошибка: %s", kw, e)
    return urls[:max_clips]


async def _download(client: httpx.AsyncClient, url: str, dest: Path) -> bool:
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception as e:
        logger.warning("stock_video: скачивание клипа не удалось: %s", e)
        return False


# ── ffmpeg ────────────────────────────────────────────────

async def _run_ffmpeg(*args: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg: {err.decode()[:300]}")


async def _probe_duration(path: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    try:
        return float(json.loads(out)["format"]["duration"])
    except Exception:
        return 0.0


async def assemble_video(clip_paths: list[Path], audio_path: Path,
                         workdir: Path, target_sec: float) -> Path:
    """Кроп в 9:16, нарезка сегментов под длительность озвучки, склейка + голос."""
    seg = max(2.5, target_sec / len(clip_paths))
    normalized: list[Path] = []
    vf = (f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
          f"crop={OUT_W}:{OUT_H},fps={OUT_FPS},format=yuv420p")
    for i, clip in enumerate(clip_paths):
        out = workdir / f"norm_{i}.mp4"
        await _run_ffmpeg("-i", str(clip), "-t", f"{seg:.2f}", "-vf", vf,
                          "-an", "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "23", str(out))
        normalized.append(out)

    concat_list = workdir / "list.txt"
    concat_list.write_text("".join(f"file '{p}'\n" for p in normalized))
    final = workdir / "final.mp4"
    await _run_ffmpeg("-f", "concat", "-safe", "0", "-i", str(concat_list),
                      "-i", str(audio_path), "-map", "0:v", "-map", "1:a",
                      "-c:v", "copy", "-c:a", "aac", "-shortest", str(final))
    return final


# ── Загрузка результата ───────────────────────────────────

def _upload_video(data: bytes) -> str | None:
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not (supabase_url and service_key):
        return None
    bucket = os.getenv("MEDIA_BUCKET", "media")
    name = f"stock_video/{uuid.uuid4().hex}.mp4"
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{supabase_url}/storage/v1/object/{bucket}/{name}",
                # новые ключи sb_secret_* требуют и apikey, и Authorization
                headers={"Authorization": f"Bearer {service_key}",
                         "apikey": service_key,
                         "Content-Type": "video/mp4"},
                content=data,
            )
            resp.raise_for_status()
        return f"{supabase_url}/storage/v1/object/public/{bucket}/{name}"
    except Exception as e:
        logger.warning("stock_video: загрузка видео не удалась: %s", e)
        return None


# ── Точка входа ───────────────────────────────────────────

async def run_stock_video(
    script: str,
    vertical: str = "nutra",
    geo: str = "US",
    voice: str | None = None,
    max_clips: int = 4,
    keywords: list[str] | None = None,
) -> dict:
    """Собирает faceless-видео 9:16 из стоковых клипов с озвучкой скрипта."""
    script = (script or "").strip()
    if not script:
        return {"error": "script обязателен"}
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return {"error": "PEXELS_API_KEY не задан (бесплатный ключ: pexels.com/api)"}

    kws = keywords or await extract_keywords(script, vertical, geo)
    clip_urls = await search_stock_clips(kws, max_clips, api_key)
    if not clip_urls:
        return {"error": f"Pexels не вернул клипов по запросам {kws}", "keywords": kws}

    tts_provider, audio = await synth_speech(script, voice=voice)
    if not audio:
        return {"error": "озвучка не удалась (все TTS-провайдеры)", "keywords": kws}

    with tempfile.TemporaryDirectory(prefix="stockvid_") as tmp:
        workdir = Path(tmp)
        audio_path = workdir / "voice.mp3"
        audio_path.write_bytes(audio)
        audio_sec = await _probe_duration(audio_path) or estimate_duration(script)

        clips: list[Path] = []
        async with httpx.AsyncClient(timeout=120) as client:
            for i, url in enumerate(clip_urls):
                dest = workdir / f"clip_{i}.mp4"
                if await _download(client, url, dest):
                    clips.append(dest)
        if not clips:
            return {"error": "не удалось скачать ни один клип", "keywords": kws}

        final = await assemble_video(clips, audio_path, workdir, audio_sec)
        duration = await _probe_duration(final)
        video_url = _upload_video(final.read_bytes())

    if not video_url:
        return {"error": "видео собрано, но загрузка в хранилище не удалась"}

    logger.info("stock_video | %s/%s clips=%d dur=%.1fs tts=%s ✅",
                vertical, geo, len(clips), duration, tts_provider)
    return {
        "provider": "stock",
        "video_url": video_url,
        "duration": round(duration, 1),
        "clips_used": len(clips),
        "keywords": kws,
        "tts_provider": tts_provider,
    }
