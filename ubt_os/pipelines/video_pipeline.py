"""
Пайплайн nutra / ubt (betting) с ДИНАМИЧЕСКИМ выбором профиля вывода.

Обязательная часть (всегда): A21 CONTENT_CREATOR (+ A19 humanizer) → A25 COMPLIANCE_GATE.
Опциональная часть — по профилю `output`:

  Профиль      | Опциональные шаги            | Higgsfield (A30)
  -------------|------------------------------|-----------------
  text/native  | —                            | ПРОПУСКАЕТСЯ
  video        | видео 9:16                   | очередь
  carousel     | карусель                     | очередь (carousel)
  full         | видео                        | очередь

Смысл: белая/текстовая связка не тащится через Higgsfield и не требует его
ключ/воркер. Если профиль просит видео, а провайдеров генерации нет — воркер
сам деградирует (VIDEO_PROVIDER_CHAIN: stock → fal → higgsfield); текстовый
профиль вообще не ставит задачу в очередь.

Пайплайн НИЧЕГО не публикует: результат — черновики в content_plans (+ videos
в очереди, если профиль этого требует). Публикация остаётся за пользователем
(принцип UBT OS: user is always the final decision-maker).
"""
from __future__ import annotations

import logging
import os

from ubt_os.agents.content_creator import ContentCreator, ContentFormat
from ubt_os.agents.compliance_gate import ComplianceGate
from ubt_os.core.agent_api_layer import AccountReader, ContentPlanWriter, VideoWriter
from ubt_os.pipelines.higgsfield_queue import HiggsFieldQueue, VideoJob

logger = logging.getLogger("ubt_os.video_pipeline")

# Ротация форматов при count > 1 — чтобы партия не была однотипной
DEFAULT_FORMATS = [
    ContentFormat.HOOK_PROBLEM,
    ContentFormat.UGC_REACTION,
    ContentFormat.BEFORE_AFTER,
]

MAX_BATCH = 10  # защита от случайного count=1000 из n8n

# Профили, которым нужна генерация видео (очередь Higgsfield/провайдеры).
# Всё остальное (text/native/script) — только скрипт, без очереди видео.
_VIDEO_PROFILES = {"video", "carousel", "full", "shorts"}


def _needs_video(output: str) -> bool:
    return (output or "video").lower() in _VIDEO_PROFILES


def _build_mcsla_prompt(script: str, vertical: str, geo: str) -> str:
    """Промпт для Higgsfield: UGC 9:16 без брендов и медицинских визуалов."""
    return (
        f"UGC vertical video 9:16 for {vertical} offer, GEO {geo}. "
        "Authentic selfie-style creator, natural lighting, handheld camera, "
        "dynamic cuts every 2-3 seconds, no on-screen brand logos, "
        "no medical claims visuals, no text overlays with guarantees. "
        f"Voiceover script: {script[:800]}"
    )


def _pick_account(vertical: str, account_id: str | None) -> dict | None:
    """Активный аккаунт для привязки контент-плана."""
    accounts = AccountReader.get_active()
    if account_id:
        return next((a for a in accounts if str(a.get("id")) == str(account_id)), None)
    matching = [a for a in accounts if a.get("vertical") in (vertical, None, "")]
    pool = matching or accounts
    return pool[0] if pool else None


async def run_video_pipeline(
    vertical: str,
    geo: str = "US",
    offer: str = "",
    count: int = 1,
    account_id: str | None = None,
    provider: str = "",
    output: str = "video",
) -> dict:
    """
    output — профиль вывода:
      text | native | script → только скрипт (без видео, без очереди A30)
      video | carousel | full | shorts → скрипт + задача в очередь генерации
    """
    acc = _pick_account(vertical, account_id)
    if not acc:
        logger.warning("video_pipeline(%s): нет активных аккаунтов — пропуск", vertical)
        return {"status": "skipped", "reason": "нет активных аккаунтов"}

    want_video = _needs_video(output)

    creator = ContentCreator()
    gate    = ComplianceGate()
    # Очередь Higgsfield нужна только для видео-профилей — иначе не трогаем Redis-очередь
    queue   = HiggsFieldQueue(os.environ["REDIS_URL"]) if want_video else None

    count = max(1, min(int(count), MAX_BATCH))
    created, blocked = 0, 0
    items: list[dict] = []

    for i in range(count):
        fmt = DEFAULT_FORMATS[i % len(DEFAULT_FORMATS)]

        piece = await creator.create(fmt, vertical, geo, offer)
        text  = piece.humanized_text

        check = await gate.check(text, vertical, geo)
        if check.is_blocked:
            blocked += 1
            items.append({
                "format": fmt.value, "status": "blocked",
                "reason": check.reason, "violations": check.violations,
            })
            logger.warning(
                "video_pipeline(%s): контент заблокирован compliance (%s)",
                vertical, check.reason,
            )
            continue
        if not check.passed and check.clean_version:
            text = check.clean_version  # warning → публикуем исправленную версию

        mcsla = _build_mcsla_prompt(text, vertical, geo)
        plan  = ContentPlanWriter.create(
            account_id=str(acc["id"]),
            title=f"{vertical}/{geo} {fmt.value} — {offer or 'auto'}"[:120],
            format=fmt.value,
            vertical=vertical,
            script=text,
            mcsla_prompt=mcsla,
        )

        if not want_video:
            # Текстовый профиль: скрипт готов, видео не нужно — не трогаем A30
            created += 1
            items.append({
                "format": fmt.value, "status": "script_ready",
                "content_plan_id": plan["id"],
                "compliance_score": check.score, "humanize_score": piece.humanize_score,
            })
            continue

        video = VideoWriter.create(str(plan["id"]), account_id=str(acc["id"]))
        assert queue is not None  # want_video → очередь инициализирована
        await queue.enqueue(VideoJob(
            job_id=str(video["id"]),
            vertical=vertical,
            mcsla_prompt=mcsla,
            account_id=str(acc["id"]),
            content_plan_id=str(plan["id"]),
            script=text,
            provider=provider,
        ))
        created += 1
        items.append({
            "format": fmt.value, "status": "queued",
            "content_plan_id": plan["id"], "video_id": video["id"],
            "compliance_score": check.score, "humanize_score": piece.humanize_score,
        })

    logger.info(
        "video_pipeline(%s/%s, output=%s): готово %d (%s), заблокировано %d",
        vertical, geo, output, created,
        "видео в очереди" if want_video else "скриптов без видео", blocked,
    )
    return {
        "status": "ok", "vertical": vertical, "geo": geo, "output": output,
        "video_generated": want_video,
        "account_id": acc["id"], "created": created, "blocked": blocked,
        "items": items,
    }
