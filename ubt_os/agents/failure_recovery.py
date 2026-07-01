"""
A17 — FAILURE_RECOVERY_AGENT
Health checks для 9 зависимостей + автоматические fallback стратегии.
Запуск: каждые 60 секунд через n8n или как отдельный процесс.
"""
from __future__ import annotations
import asyncio, logging, os, time
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Optional
import httpx
from supabase import create_client, Client
import redis.asyncio as aioredis

from ubt_os.utils.supabase_utils import rows

logger = logging.getLogger("ubt_os.failure_recovery")


class HealthStatus(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    name:           str
    status:         HealthStatus = HealthStatus.HEALTHY
    latency_ms:     float        = 0.0
    error:          Optional[str]= None
    fallback_active:bool         = False
    checked_at:     str          = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Health Checkers ───────────────────────────────────────

class HealthChecker:
    """Проверяет доступность каждого компонента."""

    def __init__(self):
        self.timeout = 10.0
        self._client = None

    async def _http(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def check_litellm(self) -> ComponentHealth:
        url = os.environ.get("LITELLM_BASE_URL", "http://litellm:4000")
        t   = time.monotonic()
        try:
            r = await (await self._http()).get(f"{url}/health")
            ms = (time.monotonic() - t) * 1000
            if r.status_code == 200:
                return ComponentHealth("litellm", HealthStatus.HEALTHY, ms)
            return ComponentHealth("litellm", HealthStatus.DEGRADED, ms, f"HTTP {r.status_code}")
        except Exception as e:
            return ComponentHealth("litellm", HealthStatus.UNHEALTHY, 0, str(e))

    async def check_anthropic(self) -> ComponentHealth:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        t = time.monotonic()
        try:
            r = await (await self._http()).get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            )
            ms = (time.monotonic() - t) * 1000
            ok = r.status_code == 200
            return ComponentHealth("anthropic",
                HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED, ms,
                None if ok else f"HTTP {r.status_code}")
        except Exception as e:
            return ComponentHealth("anthropic", HealthStatus.UNHEALTHY, 0, str(e))

    async def check_higgsfield(self) -> ComponentHealth:
        url = "https://api.higgsfield.ai/health"
        t   = time.monotonic()
        try:
            r  = await (await self._http()).get(url)
            ms = (time.monotonic() - t) * 1000
            ok = r.status_code < 400
            return ComponentHealth("higgsfield",
                HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED, ms,
                None if ok else f"HTTP {r.status_code}")
        except Exception as e:
            return ComponentHealth("higgsfield", HealthStatus.UNHEALTHY, 0, str(e))

    async def check_elevenlabs(self) -> ComponentHealth:
        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        t = time.monotonic()
        try:
            r = await (await self._http()).get(
                "https://api.elevenlabs.io/v1/user",
                headers={"xi-api-key": api_key},
            )
            ms = (time.monotonic() - t) * 1000
            if r.status_code == 200:
                data = r.json()
                used = data.get("subscription", {}).get("character_count", 0)
                limit= data.get("subscription", {}).get("character_limit", 1)
                pct  = used / limit if limit else 0
                if pct > 0.9:
                    return ComponentHealth("elevenlabs", HealthStatus.DEGRADED, ms,
                                           f"quota {pct*100:.0f}% used")
                return ComponentHealth("elevenlabs", HealthStatus.HEALTHY, ms)
            return ComponentHealth("elevenlabs", HealthStatus.DEGRADED, ms, f"HTTP {r.status_code}")
        except Exception as e:
            return ComponentHealth("elevenlabs", HealthStatus.UNHEALTHY, 0, str(e))

    async def check_publer(self) -> ComponentHealth:
        url     = "https://app.publer.io/api/v1/user"
        api_key = os.environ.get("PUBLER_API_KEY", "")
        t = time.monotonic()
        try:
            r  = await (await self._http()).get(url, headers={"Authorization": f"Bearer {api_key}"})
            ms = (time.monotonic() - t) * 1000
            ok = r.status_code == 200
            return ComponentHealth("publer",
                HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED, ms,
                None if ok else f"HTTP {r.status_code}")
        except Exception as e:
            return ComponentHealth("publer", HealthStatus.UNHEALTHY, 0, str(e))

    async def check_supabase(self) -> ComponentHealth:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        t   = time.monotonic()
        try:
            r  = await (await self._http()).get(
                f"{url}/rest/v1/",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
            )
            ms = (time.monotonic() - t) * 1000
            ok = r.status_code in (200, 404)   # 404 = DB ok, table not found
            return ComponentHealth("supabase",
                HealthStatus.HEALTHY if ok else HealthStatus.UNHEALTHY, ms,
                None if ok else f"HTTP {r.status_code}")
        except Exception as e:
            return ComponentHealth("supabase", HealthStatus.UNHEALTHY, 0, str(e))

    async def check_redis(self) -> ComponentHealth:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        t   = time.monotonic()
        try:
            r  = aioredis.from_url(url)
            await r.ping()
            ms = (time.monotonic() - t) * 1000
            await r.aclose()
            return ComponentHealth("redis", HealthStatus.HEALTHY, ms)
        except Exception as e:
            return ComponentHealth("redis", HealthStatus.UNHEALTHY, 0, str(e))

    async def check_keitaro(self) -> ComponentHealth:
        domain  = os.environ.get("KEITARO_DOMAIN", "")
        api_key = os.environ.get("KEITARO_API_KEY", "")
        if not domain:
            return ComponentHealth("keitaro", HealthStatus.DEGRADED, 0, "KEITARO_DOMAIN not set")
        t = time.monotonic()
        try:
            r = await (await self._http()).get(
                f"https://{domain}/admin_api/v1/status",
                headers={"Api-Key": api_key},
            )
            ms = (time.monotonic() - t) * 1000
            ok = r.status_code == 200
            return ComponentHealth("keitaro",
                HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED, ms,
                None if ok else f"HTTP {r.status_code}")
        except Exception as e:
            return ComponentHealth("keitaro", HealthStatus.UNHEALTHY, 0, str(e))

    async def check_tiktok_uploader(self) -> ComponentHealth:
        url = os.environ.get("TIKTOK_UPLOADER_URL", "http://tiktok-uploader:8080")
        t   = time.monotonic()
        try:
            r  = await (await self._http()).get(f"{url}/health")
            ms = (time.monotonic() - t) * 1000
            ok = r.status_code == 200
            return ComponentHealth("tiktok_uploader",
                HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED, ms,
                None if ok else f"HTTP {r.status_code}")
        except Exception as e:
            return ComponentHealth("tiktok_uploader", HealthStatus.UNHEALTHY, 0, str(e))

    async def check_all(self) -> dict[str, ComponentHealth]:
        results = await asyncio.gather(
            self.check_litellm(),
            self.check_anthropic(),
            self.check_higgsfield(),
            self.check_elevenlabs(),
            self.check_publer(),
            self.check_supabase(),
            self.check_redis(),
            self.check_keitaro(),
            self.check_tiktok_uploader(),
            return_exceptions=True,
        )
        names = ["litellm","anthropic","higgsfield","elevenlabs",
                 "publer","supabase","redis","keitaro","tiktok_uploader"]
        out = {}
        for name, res in zip(names, results):
            if isinstance(res, BaseException):
                out[name] = ComponentHealth(name, HealthStatus.UNHEALTHY, 0, str(res))
            else:
                out[name] = res
        return out


# ── Fallback Manager ──────────────────────────────────────

class FallbackManager:
    """Активирует fallback стратегии при отказах."""

    FALLBACKS: dict[str, list[str]] = {
        "higgsfield":      ["short_video_maker", "cached_template"],
        "elevenlabs":      ["edge_tts", "no_voice"],
        "publer":          ["tiktok_uploader", "upload_post", "dlq"],
        "tiktok_uploader": ["publer"],
        "keitaro":         ["supabase_utm_direct"],
        "litellm":         ["anthropic_direct"],
        "anthropic":       ["cached_script"],
    }

    def __init__(self, db: Client):
        self.db = db

    def activate(self, component: str) -> list[str]:
        fallbacks = self.FALLBACKS.get(component, [])
        if fallbacks:
            self.db.table("component_fallbacks").upsert({
                "component":      component,
                "fallback_chain": fallbacks,
                "active":         True,
                "activated_at":   datetime.now(timezone.utc).isoformat(),
            }, on_conflict="component").execute()
            logger.warning(f"[Fallback] {component} → {fallbacks[0]}")
        return fallbacks

    def deactivate(self, component: str):
        self.db.table("component_fallbacks").update({
            "active": False, "resolved_at": datetime.now(timezone.utc).isoformat()
        }).eq("component", component).execute()
        logger.info(f"[Fallback] {component} restored")

    def get_active(self) -> list[dict]:
        return rows(
            self.db.table("component_fallbacks")
            .select("*").eq("active", True).execute()
        )


# ── Degradation Level ─────────────────────────────────────

def degradation_level(health: dict[str, ComponentHealth]) -> int:
    unhealthy = sum(1 for h in health.values() if h.status == HealthStatus.UNHEALTHY)
    if unhealthy == 0:    return 0
    if unhealthy <= 2:    return 1
    if unhealthy <= 4:    return 2
    if unhealthy <= 5:    return 3
    return 4


# ── Alert ─────────────────────────────────────────────────

async def send_alert(msg: str, level: str = "warning"):
    token   = os.environ.get("TELEGRAM_ALERT_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_ALERT_CHAT_ID")
    if not token or not chat_id:
        return
    emoji = {"info":"ℹ️","warning":"⚠️","critical":"🚨"}.get(level,"⚠️")
    async with httpx.AsyncClient() as c:
        await c.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id,
                  "text": f"{emoji} *FAILURE RECOVERY*\n{msg}",
                  "parse_mode": "Markdown"},
            timeout=10,
        )


# ── Main Recovery Loop ────────────────────────────────────

class FailureRecoveryAgent:

    def __init__(self):
        self.checker  = HealthChecker()
        self.db       = create_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
        )
        self.fallbacks = FallbackManager(self.db)
        self._prev_health: dict[str, HealthStatus] = {}

    async def run_once(self) -> dict:
        health = await self.checker.check_all()
        level  = degradation_level(health)
        now    = datetime.now(timezone.utc).isoformat()

        for name, h in health.items():
            prev = self._prev_health.get(name, HealthStatus.HEALTHY)

            # Новый отказ
            if h.status == HealthStatus.UNHEALTHY and prev != HealthStatus.UNHEALTHY:
                self.fallbacks.activate(name)
                await send_alert(
                    f"*{name}* недоступен\nОшибка: `{h.error}`\n"
                    f"Fallback: `{self.fallbacks.FALLBACKS.get(name,['none'])[0]}`",
                    "critical" if name in ("supabase","redis") else "warning",
                )

            # Восстановление
            elif h.status == HealthStatus.HEALTHY and prev == HealthStatus.UNHEALTHY:
                self.fallbacks.deactivate(name)
                await send_alert(f"*{name}* восстановлен ✅", "info")

            # Сохранение в БД
            self.db.table("component_health").upsert({
                "component":      name,
                "status":         h.status.value,
                "latency_ms":     h.latency_ms,
                "error":          h.error,
                "fallback_active":h.fallback_active,
                "checked_at":     now,
            }, on_conflict="component").execute()

            self._prev_health[name] = h.status

        # Уровень деградации
        if level >= 3:
            await send_alert(
                f"*УРОВЕНЬ ДЕГРАДАЦИИ {level}*\n"
                f"Недоступных компонентов: {sum(1 for h in health.values() if h.status==HealthStatus.UNHEALTHY)}/9\n"
                f"Система в ограниченном режиме.",
                "critical",
            )

        return {
            "level":    level,
            "health":   {k: v.status.value for k,v in health.items()},
            "fallbacks":self.fallbacks.get_active(),
        }

    async def run_loop(self, interval_sec: int = 60):
        """Непрерывный мониторинг каждые N секунд."""
        logger.info(f"FAILURE_RECOVERY: мониторинг каждые {interval_sec}s")
        while True:
            try:
                result = await self.run_once()
                logger.info(f"Health check: level={result['level']} "
                            f"healthy={sum(1 for v in result['health'].values() if v=='healthy')}/9")
            except Exception as e:
                logger.error(f"Health check error: {e}")
            await asyncio.sleep(interval_sec)


async def run_failure_recovery():
    agent = FailureRecoveryAgent()
    await agent.run_loop(60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_failure_recovery())
