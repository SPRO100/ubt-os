"""
A34 — CAPTION_AGENT
Авто-субтитры для коротких видео: из word-level таймингов (Deepgram или
переданных) строит стилизованный ASS (TikTok-style, фразами по 2–4 слова) и SRT,
плюс готовую ffmpeg-команду для «вжигания». Субтитры резко поднимают удержание
на органике.

Burn (ffmpeg) — опционально и best-effort; по умолчанию агент отдаёт .ass/.srt
и команду, а рендер делает отдельный воркер/сервер.

Запуск: POST /caption
"""
from __future__ import annotations
import logging
import os
import shutil
import subprocess  # nosec B404 — вызываем только фиксированный ffmpeg, без shell
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("ubt_os.caption_agent")

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"

# Пресеты стиля (шрифт, размер, цвет заливки/обводки в ASS &HBBGGRR)
STYLE_PRESETS: dict[str, dict] = {
    "tiktok":   {"font": "Arial Black", "size": 18, "primary": "&H00FFFFFF", "outline": "&H00000000", "bord": 3},
    "bold_yellow": {"font": "Arial Black", "size": 18, "primary": "&H0000FFFF", "outline": "&H00000000", "bord": 3},
    "minimal":  {"font": "Arial", "size": 14, "primary": "&H00FFFFFF", "outline": "&H80000000", "bord": 2},
}


@dataclass
class CaptionResult:
    video_url: str
    language: str
    style: str
    segment_count: int
    srt: str
    ass: str
    ffmpeg_cmd: str
    burned_url: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Тайминги и группировка (чистые функции) ───────────────

def _fmt_srt_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_ass_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def group_words(words: list[dict], max_words: int = 4, max_gap: float = 0.6) -> list[dict]:
    """Группирует слова в короткие фразы-сегменты для читаемых субтитров.

    Новый сегмент начинается при достижении max_words или паузе > max_gap.
    Каждое слово: {"word","start","end"}. Возвращает [{"text","start","end"}].
    """
    segments: list[dict] = []
    cur: list[dict] = []
    for w in words:
        text = str(w.get("word", "")).strip()
        if not text:
            continue
        if cur:
            gap = float(w.get("start", 0)) - float(cur[-1].get("end", 0))
            if len(cur) >= max_words or gap > max_gap:
                segments.append(_flush(cur))
                cur = []
        cur.append(w)
    if cur:
        segments.append(_flush(cur))
    return segments


def _flush(chunk: list[dict]) -> dict:
    return {
        "text":  " ".join(str(w.get("word", "")).strip() for w in chunk).strip(),
        "start": float(chunk[0].get("start", 0)),
        "end":   float(chunk[-1].get("end", 0)),
    }


def build_srt(segments: list[dict]) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_ts(seg['start'])} --> {_fmt_srt_ts(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def build_ass(segments: list[dict], style: str = "tiktok") -> str:
    st = STYLE_PRESETS.get(style, STYLE_PRESETS["tiktok"])
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 108\n"
        "PlayResY: 192\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
        "BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV\n"
        f"Style: Cap,{st['font']},{st['size']},{st['primary']},{st['outline']},"
        f"&H00000000,1,{st['bord']},0,2,6,6,20\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Text\n"
    )
    body = "".join(
        f"Dialogue: 0,{_fmt_ass_ts(seg['start'])},{_fmt_ass_ts(seg['end'])},Cap,"
        f"{seg['text'].upper()}\n"
        for seg in segments
    )
    return header + body


def ffmpeg_burn_cmd(video: str, ass_path: str, out: str) -> str:
    return f'ffmpeg -y -i "{video}" -vf "ass={ass_path}" -c:a copy "{out}"'


# ── Источник таймингов (Deepgram) ─────────────────────────

async def _deepgram_words(url: str, lang: str, api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            DEEPGRAM_API_URL,
            headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
            params={"model": "nova-2", "punctuate": "true"},
            json={"url": url, "language": lang},
        )
        resp.raise_for_status()
        data = resp.json()
        return (
            data.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("words", [])
        ) or []


def _try_burn(video_url: str, ass: str) -> str | None:
    """Best-effort вжигание субтитров, если доступен ffmpeg. Иначе None."""
    if not shutil.which("ffmpeg"):
        logger.info("caption: ffmpeg недоступен — burn пропущен")
        return None
    try:
        with tempfile.TemporaryDirectory() as td:
            ass_path = os.path.join(td, "subs.ass")
            out_path = os.path.join(td, "out.mp4")
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass)
            subprocess.run(  # nosec B603 — фиксированный бинарь, аргументы без shell
                ["ffmpeg", "-y", "-i", video_url, "-vf", f"ass={ass_path}",
                 "-c:a", "copy", out_path],
                check=True, capture_output=True, timeout=600,
            )
            logger.info("caption: burn выполнен (локальный файл %s)", out_path)
            # Загрузку в хранилище оставляем воркеру; возвращаем локальный путь-маркер
            return out_path
    except Exception as e:
        logger.warning("caption: burn не удался: %s", e)
        return None


async def run_caption(
    video_url: str,
    words: list[dict] | None = None,
    language: str = "ru",
    style: str = "tiktok",
    max_words: int = 4,
    burn: bool = False,
) -> dict:
    """Точка входа для /caption."""
    if not video_url:
        return {"error": "video_url обязателен"}

    if not words:
        key = os.getenv("DEEPGRAM_API_KEY")
        if not key:
            return {"error": "нет word-таймингов: передай words или задай DEEPGRAM_API_KEY"}
        try:
            words = await _deepgram_words(video_url, language, key)
        except Exception as e:
            return {"error": f"Deepgram недоступен: {e}"}

    segments = group_words(words or [], max_words=max_words)
    if not segments:
        return {"error": "пустой транскрипт — субтитры не построены"}

    ass = build_ass(segments, style)
    srt = build_srt(segments)
    result = CaptionResult(
        video_url=video_url, language=language, style=style,
        segment_count=len(segments), srt=srt, ass=ass,
        ffmpeg_cmd=ffmpeg_burn_cmd(video_url, "subs.ass", "out.mp4"),
    )

    if burn:
        result.burned_url = _try_burn(video_url, ass)

    logger.info("caption | video=%s style=%s segments=%d burned=%s",
                video_url[:60], style, len(segments), bool(result.burned_url))
    return {
        "video_url": result.video_url,
        "language": result.language,
        "style": result.style,
        "segment_count": result.segment_count,
        "srt": result.srt,
        "ass": result.ass,
        "ffmpeg_cmd": result.ffmpeg_cmd,
        "burned_url": result.burned_url,
        "created_at": result.created_at,
    }
