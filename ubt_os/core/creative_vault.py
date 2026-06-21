"""
CREATIVE VAULT — Analytics Engine
Вычисляет Creative/Viral/Conversion Score для каждого видео.
Обновляет hook_rankings, cta_rankings, winning_patterns.
Запуск: ежедневно в 01:00 через n8n cron.
"""
from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from supabase import create_client, Client

logger = logging.getLogger("ubt_os.creative_vault")


# ── Формулы скоров ────────────────────────────────────────

class ScoringEngine:
    """
    Три независимых скора + composite.

    Creative Score (0-100):
        Оценивает качество крео — насколько хорошо видео удерживает внимание.
        = completion_rate(50%) + replay_factor(20%) + engagement_rate(30%)

    Viral Score (0-100):
        Оценивает вирусный потенциал — шанс органического распространения.
        = shares_rate(40%) + saves_rate(30%) + comments_rate(30%)

    Conversion Score (0-100):
        Оценивает коммерческую эффективность.
        = ctr(40%) + cr(40%) + revenue_per_view(20%)

    Composite Score:
        = creative(30%) + viral(30%) + conversion(40%)
    """

    # Бенчмарки по платформам (для нормализации)
    BENCHMARKS = {
        "tiktok":    {"completion": 0.55, "ctr": 0.025, "cr": 0.02, "er": 0.06},
        "youtube":   {"completion": 0.65, "ctr": 0.035, "cr": 0.018, "er": 0.05},
        "instagram": {"completion": 0.50, "ctr": 0.015, "cr": 0.015, "er": 0.07},
    }

    def creative_score(self, asset: dict) -> float:
        platform  = asset.get("platform", "tiktok")
        bench     = self.BENCHMARKS.get(platform, self.BENCHMARKS["tiktok"])

        completion = asset.get("completion_rate", 0)
        views      = max(asset.get("views", 1), 1)
        replays    = asset.get("replay_count", 0)
        likes      = asset.get("likes", 0)
        comments   = asset.get("comments", 0)
        shares     = asset.get("shares", 0)
        saves      = asset.get("saves", 0)

        completion_norm = min(completion / bench["completion"], 1.5) / 1.5
        replay_factor   = min(replays / views / 0.15, 1.0)
        er              = (likes + comments + shares + saves) / views
        er_norm         = min(er / bench["er"], 1.5) / 1.5

        score = (completion_norm * 50) + (replay_factor * 20) + (er_norm * 30)
        return round(min(score * 100, 100), 2)

    def viral_score(self, asset: dict) -> float:
        views    = max(asset.get("views", 1), 1)
        shares   = asset.get("shares", 0)
        saves    = asset.get("saves", 0)
        comments = asset.get("comments", 0)

        shares_rate   = min(shares / views / 0.03, 1.0)
        saves_rate    = min(saves  / views / 0.04, 1.0)
        comments_rate = min(comments / views / 0.02, 1.0)

        score = (shares_rate * 40) + (saves_rate * 30) + (comments_rate * 30)
        return round(min(score * 100, 100), 2)

    def conversion_score(self, asset: dict) -> float:
        platform = asset.get("platform", "tiktok")
        bench    = self.BENCHMARKS.get(platform, self.BENCHMARKS["tiktok"])

        ctr      = asset.get("ctr", 0)
        cr       = asset.get("cr", 0)
        views    = max(asset.get("views", 1), 1)
        revenue  = float(asset.get("revenue", 0))

        ctr_norm     = min(ctr / bench["ctr"], 2.0) / 2.0
        cr_norm      = min(cr  / bench["cr"],  2.0) / 2.0
        rev_per_view = min(revenue / views / 0.005, 1.0)

        score = (ctr_norm * 40) + (cr_norm * 40) + (rev_per_view * 20)
        return round(min(score * 100, 100), 2)

    def composite_score(self, cs: float, vs: float, cvs: float) -> float:
        return round(cs * 0.30 + vs * 0.30 + cvs * 0.40, 2)


# ── Обновление скоров ─────────────────────────────────────

class CreativeVaultUpdater:

    def __init__(self, db: Client):
        self.db      = db
        self.scoring = ScoringEngine()

    async def update_all_scores(self, lookback_days: int = 7):
        """Пересчитывает скоры для всех видео за lookback_days."""
        since = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat()
        assets = (
            self.db.table("creative_assets")
            .select("*")
            .gte("updated_at", since)
            .is_("is_archived", "false")
            .execute()
        ).data

        logger.info(f"Creative Vault: обновляем скоры для {len(assets)} видео")

        for asset in assets:
            cs  = self.scoring.creative_score(asset)
            vs  = self.scoring.viral_score(asset)
            cvs = self.scoring.conversion_score(asset)
            cmp = self.scoring.composite_score(cs, vs, cvs)

            self.db.table("creative_assets").update({
                "creative_score":    cs,
                "viral_score":       vs,
                "conversion_score":  cvs,
                "composite_score":   cmp,
                "is_top_performer":  cmp >= 70,
                "scores_updated_at": datetime.utcnow().isoformat(),
            }).eq("id", asset["id"]).execute()

        await self._update_hook_rankings()
        await self._update_cta_rankings()
        await self._detect_winning_patterns()
        logger.info("Creative Vault: обновление завершено ✅")

    async def _update_hook_rankings(self):
        """Агрегирует метрики по тексту хука."""
        assets = self.db.table("creative_assets").select(
            "hook_text,hook_type,vertical,geo,platform,"
            "completion_rate,ctr,cr,revenue"
        ).is_("is_archived", "false").execute().data

        # Группируем по ключу
        groups: dict[tuple, list] = {}
        for a in assets:
            key = (a["hook_text"], a["hook_type"],
                   a["vertical"], a["geo"], a["platform"])
            groups.setdefault(key, []).append(a)

        for (hook_text, hook_type, vertical, geo, platform), items in groups.items():
            n   = len(items)
            avg_completion = sum(i.get("completion_rate",0) for i in items) / n
            avg_ctr        = sum(i.get("ctr",0)             for i in items) / n
            avg_cr         = sum(i.get("cr",0)              for i in items) / n
            total_revenue  = sum(float(i.get("revenue",0))  for i in items)

            hook_score = (
                avg_completion * 0.35 +
                avg_ctr        * 10   +
                avg_cr         * 20
            ) * 100 / 3

            self.db.table("hook_rankings").upsert({
                "hook_text":           hook_text,
                "hook_type":           hook_type,
                "vertical":            vertical,
                "geo":                 geo,
                "platform":            platform,
                "avg_completion_rate": avg_completion,
                "avg_ctr":             avg_ctr,
                "avg_cr":              avg_cr,
                "usage_count":         n,
                "total_revenue":       total_revenue,
                "hook_score":          round(min(hook_score, 100), 2),
                "last_used_at":        datetime.utcnow().isoformat(),
            }, on_conflict="hook_text,vertical,geo,platform").execute()

    async def _update_cta_rankings(self):
        """Агрегирует метрики по CTA тексту."""
        assets = self.db.table("creative_assets").select(
            "cta_text,cta_position,vertical,platform,ctr,cr"
        ).is_("is_archived", "false").not_.is_("cta_text", "null").execute().data

        groups: dict[tuple, list] = {}
        for a in assets:
            key = (a["cta_text"], a.get("cta_position","end"),
                   a["vertical"], a["platform"])
            groups.setdefault(key, []).append(a)

        for (cta_text, cta_pos, vertical, platform), items in groups.items():
            n       = len(items)
            avg_ctr = sum(i.get("ctr",0) for i in items) / n
            avg_cr  = sum(i.get("cr",0)  for i in items) / n
            score   = (avg_ctr * 10 + avg_cr * 20) * 100 / 2

            self.db.table("cta_rankings").upsert({
                "cta_text":     cta_text,
                "cta_position": cta_pos,
                "vertical":     vertical,
                "platform":     platform,
                "avg_ctr":      avg_ctr,
                "avg_cr":       avg_cr,
                "usage_count":  n,
                "cta_score":    round(min(score, 100), 2),
            }, on_conflict="cta_text,vertical,platform,cta_position").execute()

    async def _detect_winning_patterns(self, min_samples: int = 5):
        """
        Находит комбинации (hook_type + format + visual_style + duration)
        с composite_score > 65 при n >= min_samples.
        """
        assets = self.db.table("creative_assets").select(
            "hook_type,format_type,visual_style,duration_sec,"
            "cta_position,vertical,geo,platform,"
            "completion_rate,ctr,cr,revenue,composite_score"
        ).gte("composite_score", 65).is_("is_archived", "false").execute().data

        groups: dict[tuple, list] = {}
        for a in assets:
            dur = a.get("duration_sec", 0)
            dur_bucket = "short(<30)" if dur < 30 else ("mid(30-45)" if dur < 46 else "long(45+)")
            key = (
                a.get("hook_type","unknown"),
                a.get("format_type","unknown"),
                a.get("visual_style","unknown"),
                dur_bucket,
                a.get("cta_position","end"),
                a["vertical"], a["geo"], a["platform"],
            )
            groups.setdefault(key, []).append(a)

        for key, items in groups.items():
            if len(items) < min_samples:
                continue
            (hook_type, format_type, visual_style, dur_range,
             cta_pos, vertical, geo, platform) = key
            n           = len(items)
            avg_cr      = sum(i.get("cr",0) for i in items) / n
            avg_ctr     = sum(i.get("ctr",0) for i in items) / n
            avg_comp    = sum(i.get("completion_rate",0) for i in items) / n
            avg_rev     = sum(float(i.get("revenue",0)) for i in items) / n
            confidence  = min(n / 20, 1.0)

            name = f"{hook_type}+{format_type}+{visual_style}_{dur_range}"
            self.db.table("winning_patterns").upsert({
                "pattern_name":        name,
                "vertical":            vertical,
                "geo":                 geo,
                "platform":            platform,
                "hook_type":           hook_type,
                "format_type":         format_type,
                "visual_style":        visual_style,
                "duration_range":      dur_range,
                "cta_position":        cta_pos,
                "avg_completion_rate": avg_comp,
                "avg_ctr":             avg_ctr,
                "avg_cr":              avg_cr,
                "avg_revenue":         avg_rev,
                "sample_count":        n,
                "confidence":          confidence,
                "is_active":           True,
            }, on_conflict="pattern_name,vertical,geo,platform").execute()
            logger.info(f"Паттерн: {name} ({n} samples, conf={confidence:.2f})")


# ── Точка входа ───────────────────────────────────────────

async def run_creative_vault_update(lookback_days: int = 7):
    db      = create_client(os.environ["SUPABASE_URL"],
                            os.environ["SUPABASE_SERVICE_KEY"])
    updater = CreativeVaultUpdater(db)
    await updater.update_all_scores(lookback_days)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_creative_vault_update())
