"""
Видео-пайплайн nutra / ubt (betting): A21 → A25 → очередь A30.

Цепочка на один запуск:
  1. A21 CONTENT_CREATOR  — скрипт по Brand Voice (+ A19 humanizer внутри)
  2. A25 COMPLIANCE_GATE  — блокирует запрещённые клеймы, warning → clean_version
  3. SoT                  — content_plans (draft) + videos (queued) через Writer'ы
  4. HiggsFieldQueue      — задание на генерацию видео (обрабатывает воркер A30)

Пайплайн НИЧЕГО не публикует: результат — черновики в content_plans и
сгенерированные видео в videos. Публикация остаётся за пользователем
(принцип UBT OS: user is always the final decision-maker).
"""
from __future__ import annotations

import logging
import os

from ubt_os.agents.content_creator import ContentCreator, ContentFormat, Vertical
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
) -> dict:
    acc = _pick_account(vertical, account_id)
    if not acc:
        logger.warning("video_pipeline(%s): нет активных аккаунтов — пропуск", vertical)
        return {"status": "skipped", "reason": "нет активных аккаунтов"}

    creator = ContentCreator()
    gate    = ComplianceGate()
    queue   = HiggsFieldQueue(os.environ["REDIS_URL"])

    count = max(1, min(int(count), MAX_BATCH))
    created, blocked = 0, 0
    items: list[dict] = []

    for i in range(count):
        fmt = DEFAULT_FORMATS[i % len(DEFAULT_FORMATS)]

        piece = await creator.create(fmt, Vertical(vertical), geo, offer)
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
        video = VideoWriter.create(str(plan["id"]))

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
        "video_pipeline(%s/%s): в очереди %d, заблокировано %d",
        vertical, geo, created, blocked,
    )
    return {
        "status": "ok", "vertical": vertical, "geo": geo,
        "account_id": acc["id"], "created": created, "blocked": blocked,
        "items": items,
    }
