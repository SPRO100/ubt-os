"""
A35 — TTS_AGENT
Озвучка faceless-видео: тонкий клиент к TTS-провайдерам с fallback.
Порядок: self-hosted сервер (TTS_SERVER_URL — Kokoro/Chatterbox) →
edge-tts (бесплатно, без ключа) → ElevenLabs (ELEVENLABS_API_KEY).
Аудио грузится в Supabase Storage.

Запуск: POST /tts
"""
from __future__ import annotations
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("ubt_os.tts_agent")

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
_WORDS_PER_MIN = 150  # средний темп закадрового голоса

# Бесплатные нейроголоса Microsoft (edge-tts) — без ключа и GPU
EDGE_VOICE_RU_DEFAULT = "ru-RU-DmitryNeural"
EDGE_VOICE_EN_DEFAULT = "en-US-ChristopherNeural"


@dataclass
class TTSResult:
    provider: str
    voice: str
    chars: int
    est_duration_sec: float
    audio_url: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Чистые функции (тестируемые) ──────────────────────────

def chunk_text(text: str, max_chars: int = 2500) -> list[str]:
    """Режет длинный скрипт на куски по границам предложений, не длиннее max_chars."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    chunks: list[str] = []
    cur = ""
    for s in sentences:
        if len(cur) + len(s) + 1 > max_chars and cur:
            chunks.append(cur.strip())
            cur = ""
        cur = f"{cur} {s}".strip() if cur else s
    if cur:
        chunks.append(cur.strip())
    return chunks


def estimate_duration(text: str, wpm: int = _WORDS_PER_MIN) -> float:
    """Оценка длительности озвучки в секундах по числу слов."""
    words = len((text or "").split())
    if words == 0:
        return 0.0
    return round(words / wpm * 60, 1)


def pick_provider(server_url: str | None, elevenlabs_key: str | None) -> str | None:
    """Выбирает провайдера по доступным настройкам (без учёта edge)."""
    if server_url:
        return "local"
    if elevenlabs_key:
        return "elevenlabs"
    return None


def provider_chain(server_url: str | None, elevenlabs_key: str | None) -> list[str]:
    """Порядок fallback: self-hosted → edge (всегда доступен) → ElevenLabs."""
    chain = []
    if server_url:
        chain.append("local")
    chain.append("edge")
    if elevenlabs_key:
        chain.append("elevenlabs")
    return chain


def edge_voice_for(text: str, voice: str | None = None) -> str:
    """Голос edge-tts: явный voice с 'Neural' в имени, иначе по языку текста."""
    if voice and "Neural" in voice:
        return voice
    if re.search(r"[а-яА-ЯёЁ]", text or ""):
        return os.getenv("EDGE_TTS_VOICE_RU", EDGE_VOICE_RU_DEFAULT)
    return os.getenv("EDGE_TTS_VOICE_EN", EDGE_VOICE_EN_DEFAULT)


# ── Провайдеры ────────────────────────────────────────────

async def _local(text: str, voice: str, server_url: str) -> bytes | None:
    """Self-hosted TTS (Kokoro/Chatterbox FastAPI): ожидаем audio/* в ответе."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(server_url.rstrip("/"), json={"text": text, "voice": voice})
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        logger.warning("tts: self-hosted сервер недоступен: %s", e)
        return None


async def _edge(text: str, voice: str) -> bytes | None:
    """Бесплатный edge-tts (Microsoft): mp3 без ключа. Длинный текст — нативно."""
    try:
        import edge_tts
        buf = bytearray()
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                buf.extend(chunk["data"])
        return bytes(buf) or None
    except Exception as e:
        logger.warning("tts: edge-tts ошибка: %s", e)
        return None


async def _elevenlabs(text: str, voice_id: str, api_key: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{ELEVENLABS_URL}/{voice_id}",
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json={"text": text, "model_id": "eleven_multilingual_v2",
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
            )
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        logger.warning("tts: ElevenLabs ошибка: %s", e)
        return None


def _upload_audio(audio: bytes) -> str | None:
    """Грузит mp3 в Supabase Storage (MEDIA_BUCKET), возвращает публичный URL."""
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not (supabase_url and service_key):
        return None
    bucket = os.getenv("MEDIA_BUCKET", "media")
    name = f"voiceover/{uuid.uuid4().hex}.mp3"
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{supabase_url}/storage/v1/object/{bucket}/{name}",
                headers={"Authorization": f"Bearer {service_key}", "Content-Type": "audio/mpeg"},
                content=audio,
            )
            resp.raise_for_status()
        return f"{supabase_url}/storage/v1/object/public/{bucket}/{name}"
    except Exception as e:
        logger.warning("tts: загрузка аудио не удалась: %s", e)
        return None


async def synth_speech(
    text: str,
    voice: str | None = None,
    provider: str | None = None,
) -> tuple[str | None, bytes | None]:
    """Синтез полного текста по цепочке провайдеров → (провайдер, mp3-байты).

    Используется и /tts, и stock_video_pipeline (там нужны байты, не URL).
    """
    server_url = os.getenv("TTS_SERVER_URL")
    el_key = os.getenv("ELEVENLABS_API_KEY")
    chain = [provider] if provider else provider_chain(server_url, el_key)
    chunks = chunk_text(text)

    for prov in chain:
        audio: bytes | None = None
        if prov == "local" and server_url:
            parts = [await _local(c, voice or "default", server_url) for c in chunks]
            audio = b"".join(p for p in parts if p) or None
        elif prov == "edge":
            audio = await _edge(text, edge_voice_for(text, voice))
        elif prov == "elevenlabs" and el_key:
            vid = voice or os.getenv("ELEVENLABS_VOICE_ID") or "default"
            parts = [await _elevenlabs(c, vid, el_key) for c in chunks]
            audio = b"".join(p for p in parts if p) or None
        if audio:
            return prov, audio
    return None, None


async def run_tts(
    text: str,
    voice: str | None = None,
    provider: str | None = None,
    upload: bool = True,
) -> dict:
    """Точка входа для /tts."""
    text = (text or "").strip()
    if not text:
        return {"error": "text обязателен"}

    chunks = chunk_text(text)
    chosen, audio = await synth_speech(text, voice=voice, provider=provider)

    result = TTSResult(
        provider=chosen or "none", voice=voice or edge_voice_for(text, voice),
        chars=len(text), est_duration_sec=estimate_duration(text),
    )
    if audio is None:
        result.error = f"провайдер {chosen} не вернул аудио"
    elif upload:
        result.audio_url = _upload_audio(audio)
        if not result.audio_url:
            result.error = "аудио получено, но загрузка в хранилище не удалась"

    logger.info("tts | provider=%s chars=%d chunks=%d url=%s",
                chosen, len(text), len(chunks), bool(result.audio_url))
    return {
        "provider": result.provider,
        "voice": result.voice,
        "chars": result.chars,
        "chunks": len(chunks),
        "est_duration_sec": result.est_duration_sec,
        "audio_url": result.audio_url,
        "error": result.error,
        "created_at": result.created_at,
    }
