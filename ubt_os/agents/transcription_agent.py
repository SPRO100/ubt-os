"""
TRANSCRIPTION AGENT
AI-транскрипция видео из медиа-хранилища + извлечение хука.
Вдохновлён функцией "Транскрипция" DOHOO.ai.

Запуск: POST /transcribe
"""
from __future__ import annotations
import asyncio
import logging
import os

import httpx
from anthropic import AsyncAnthropic
from supabase import create_client, Client

logger = logging.getLogger("ubt_os.transcription_agent")

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"
WHISPER_API_URL  = "https://api.openai.com/v1/audio/transcriptions"

HOOK_EXTRACT_PROMPT = """Ты — эксперт по созданию хуков для коротких видео.

Дан транскрипт видео. Твоя задача:
1. Выдели хук — первые 10-15 секунд речи (примерно 30-50 слов).
2. Определи тип хука: question|shock|stats|story|testimonial|before_after|countdown|controversy|curiosity|ugc_organic
3. Оцени силу хука (1-10).
4. Объясни почему хук работает (или нет).

ОТВЕТ: строго JSON.

{
  "hook_text": "дословный текст хука",
  "hook_type": "...",
  "hook_strength": 1-10,
  "why_works": "...",
  "full_text_preview": "первые 100 слов транскрипта"
}"""


def _get_db() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


# ── Движок транскрипции ───────────────────────────────────

class TranscriptionEngine:
    """
    Пробует транскрипцию в порядке: Deepgram → OpenAI Whisper → заглушка.
    """

    async def transcribe(self, video_url: str, language: str = "ru") -> dict:
        deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        openai_key   = os.getenv("OPENAI_API_KEY")

        if deepgram_key:
            result = await self._deepgram(video_url, language, deepgram_key)
            if result:
                return result

        if openai_key:
            result = await self._whisper(video_url, language, openai_key)
            if result:
                return result

        logger.warning("Transcription: нет ключей Deepgram/OpenAI, пропуск")
        return {"full_text": "", "duration_sec": 0.0, "word_count": 0}

    async def _deepgram(self, url: str, lang: str, api_key: str) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    DEEPGRAM_API_URL,
                    headers={
                        "Authorization": f"Token {api_key}",
                        "Content-Type":  "application/json",
                    },
                    json={
                        "url":      url,
                        "language": lang,
                        "punctuate": True,
                        "utterances": False,
                    },
                    params={"model": "nova-2"},
                )
                resp.raise_for_status()
                data = resp.json()
                transcript = (
                    data.get("results", {})
                    .get("channels", [{}])[0]
                    .get("alternatives", [{}])[0]
                    .get("transcript", "")
                )
                duration = data.get("metadata", {}).get("duration", 0.0)
                return {
                    "full_text":   transcript,
                    "duration_sec": float(duration),
                    "word_count":  len(transcript.split()),
                    "engine":      "deepgram",
                }
        except Exception as e:
            logger.warning(f"Deepgram error: {e}")
            return None

    async def _whisper(self, url: str, lang: str, api_key: str) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Загрузим аудио-поток для Whisper
                dl = await client.get(url, follow_redirects=True)
                dl.raise_for_status()
                audio_bytes = dl.content

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    WHISPER_API_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": ("audio.mp4", audio_bytes, "audio/mp4")},
                    data={"model": "whisper-1", "language": lang},
                )
                resp.raise_for_status()
                data = resp.json()
                transcript = data.get("text", "")
                return {
                    "full_text":   transcript,
                    "duration_sec": 0.0,
                    "word_count":  len(transcript.split()),
                    "engine":      "whisper",
                }
        except Exception as e:
            logger.warning(f"Whisper error: {e}")
            return None


# ── Извлечение хука через Claude ──────────────────────────

class HookExtractor:

    def __init__(self):
        self.client = AsyncAnthropic()

    async def extract(self, full_text: str) -> dict:
        if not full_text or len(full_text) < 20:
            return {"hook_text": "", "hook_type": "unknown", "hook_strength": 0}

        try:
            resp = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=HOOK_EXTRACT_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"ТРАНСКРИПТ:\n{full_text[:3000]}"
                }],
            )
            from ubt_os.utils.llm_utils import extract_json
            return extract_json(getattr(resp.content[0], "text", ""))
        except Exception as e:
            logger.warning(f"HookExtractor error: {e}")
            return {"hook_text": full_text[:150], "hook_type": "unknown", "hook_strength": 5}


# ── Запись в БД ───────────────────────────────────────────

class TranscriptionWriter:

    def __init__(self, db: Client):
        self.db = db

    def save(
        self,
        video_url: str,
        transcription: dict,
        hook: dict,
        source: str = "competitor",
        vertical: str = "nutra",
        platform: str = "tiktok",
        language: str = "ru",
    ) -> str:
        res = self.db.table("transcriptions").upsert(
            {
                "video_url":    video_url,
                "full_text":    transcription.get("full_text", ""),
                "hook_text":    hook.get("hook_text", ""),
                "hook_type":    hook.get("hook_type", "unknown"),
                "hook_strength": hook.get("hook_strength", 0),
                "language":     language,
                "duration_sec": transcription.get("duration_sec", 0),
                "word_count":   transcription.get("word_count", 0),
                "engine":       transcription.get("engine", "unknown"),
                "source":       source,
                "vertical":     vertical,
                "platform":     platform,
            },
            on_conflict="video_url",
        ).execute()
        return res.data[0]["id"]

    def promote_to_hook_template(
        self,
        hook: dict,
        video_url: str,
        vertical: str,
        platform: str,
        geo: str = "RU",
    ):
        if hook.get("hook_strength", 0) < 7:
            return
        self.db.table("hook_templates").upsert(
            {
                "vertical":      vertical,
                "geo":           geo,
                "platform":      platform,
                "hook_type":     hook.get("hook_type", "unknown"),
                "hook_text":     hook.get("hook_text", ""),
                "source_video_url": video_url,
            },
            on_conflict="source_video_url",
        ).execute()


# ── Точка входа ───────────────────────────────────────────

async def run_transcription(
    video_url: str,
    source: str = "competitor",
    vertical: str = "nutra",
    platform: str = "tiktok",
    geo: str = "RU",
    language: str = "ru",
) -> dict:
    db = _get_db()

    existing = (
        db.table("transcriptions")
        .select("id,hook_text,hook_type,hook_strength")
        .eq("video_url", video_url)
        .limit(1)
        .execute()
    ).data

    if existing:
        logger.info(f"Transcription: уже есть для {video_url[:60]}")
        return {"status": "cached", **existing[0]}

    engine    = TranscriptionEngine()
    extractor = HookExtractor()
    writer    = TranscriptionWriter(db)

    logger.info(f"Transcription: запуск для {video_url[:60]}")

    transcription = await engine.transcribe(video_url, language)
    hook          = await extractor.extract(transcription.get("full_text", ""))

    record_id = writer.save(video_url, transcription, hook, source, vertical, platform, language)
    writer.promote_to_hook_template(hook, video_url, vertical, platform, geo)

    logger.info(
        f"Transcription готово: words={transcription.get('word_count', 0)}, "
        f"hook={hook.get('hook_type')} сила={hook.get('hook_strength')}/10"
    )
    return {
        "status":        "ok",
        "id":            record_id,
        "hook_text":     hook.get("hook_text", ""),
        "hook_type":     hook.get("hook_type", "unknown"),
        "hook_strength": hook.get("hook_strength", 0),
        "word_count":    transcription.get("word_count", 0),
        "duration_sec":  transcription.get("duration_sec", 0),
        "engine":        transcription.get("engine", "none"),
    }


async def run_batch_transcription(video_urls: list[str], **kwargs) -> list[dict]:
    """Транскрибирует список URL параллельно пачками по 3."""
    results = []
    for i in range(0, len(video_urls), 3):
        batch = video_urls[i:i+3]
        batch_results = await asyncio.gather(
            *[run_transcription(url, **kwargs) for url in batch],
            return_exceptions=True,
        )
        for url, result in zip(batch, batch_results):
            if isinstance(result, BaseException):
                logger.error(f"Transcription batch error for {url}: {result}")
                results.append({"status": "error", "url": url, "error": str(result)})
            else:
                results.append(result)
        await asyncio.sleep(1)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_transcription("https://example.com/test.mp4"))
