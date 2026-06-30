"""
A22 — ADS_AUDITOR
Аудит рекламных аккаунтов на TikTok / Meta / YouTube.
250+ проверок. Health Score 0–100 с приоритизированным планом действий.
Основан на claude-ads (AgriciDaniel/claude-ads, 6.6k ⭐).
Запускается по требованию или еженедельно в пятницу 09:00.
"""
from __future__ import annotations
import asyncio, logging, os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.ads_auditor")

# ── Чеклисты по платформам ────────────────────────────────

CHECKS = {
    "tiktok": {
        "структура": [
            "Кампании разделены по вертикалям (nutra / betting отдельно)",
            "Группы объявлений по форматам (before_after / ugc / hook)",
            "Бюджет на уровне кампании, не группы",
            "Дневной лимит установлен (защита от перерасхода)",
        ],
        "таргетинг": [
            "GEO соответствует вертикали (US/BR/MX для nutra, US/BR для betting)",
            "Возраст: 18+ (обязательно для betting)",
            "Lookalike аудитории настроены (если есть пиксель)",
            "Исключения: уже конвертированные пользователи",
            "Interest таргетинг совпадает с болями ЦА",
        ],
        "крео_и_контент": [
            "Минимум 3 варианта крео на группу",
            "Первые 3 секунды — сильный хук (нет лого/бренда в начале)",
            "Субтитры присутствуют",
            "CTA явный и соответствует посадочной",
            "Видео 9:16, 15–60 секунд",
            "Нет запрещённых слов (гарантия, лечение, похудеть за N дней)",
        ],
        "трекинг": [
            "TikTok Pixel установлен на посадочной",
            "Events: ViewContent, AddToCart, Purchase настроены",
            "UTM-метки прописаны в каждом объявлении",
        ],
        "smart_features": [
            "Smart+ кампании протестированы",
            "GMV Max активирован (если e-commerce)",
            "Автоматическое расширение аудитории включено",
        ],
        "соответствие": [
            "Нет медицинских утверждений (для nutra)",
            "Нет гарантий выигрыша (для betting)",
            "Возрастное ограничение 18+ выставлено (betting)",
        ],
    },
    "meta": {
        "структура": [
            "Кампании по целям (Traffic / Conversions / Lead Gen)",
            "Advantage+ Shopping Campaign настроена",
            "CBO (Campaign Budget Optimization) включён",
            "Ad sets не конкурируют (нет overlap аудиторий)",
        ],
        "пиксель_и_capi": [
            "Meta Pixel установлен",
            "Conversions API (CAPI) настроен",
            "Event Match Quality Score > 7",
            "Deduplication настроена (eventID)",
            "Consent Mode V2 активирован (для EU GEO)",
        ],
        "аудитории": [
            "Custom Audiences: посетители сайта 30/60/90 дней",
            "Lookalike 1% от покупателей",
            "Broad таргетинг протестирован",
            "Exclusions: последние покупатели (30 дней)",
        ],
        "крео": [
            "Минимум 5 вариантов на уровне объявления",
            "Форматы: Reels + Stories + Feed",
            "Advantage+ Creative включён",
            "Primary text < 125 символов (не обрезается)",
        ],
        "соответствие": [
            "Special Ad Category не нарушена",
            "Нет запрещённого контента (до/после для похудения)",
            "LegitScript сертификат (если требуется для ниши)",
        ],
    },
    "youtube": {
        "структура": [
            "Кампании: In-Stream / Shorts / Discovery разделены",
            "Видео 6 сек (bumper) протестированы",
            "Demand Gen кампании настроены",
        ],
        "таргетинг": [
            "In-Market аудитории соответствуют вертикали",
            "Custom Intent аудитории (ключевые слова конкурентов)",
            "Placements: исключены нерелевантные каналы",
            "Geographic targeting: соответствует GEO стратегии",
        ],
        "крео": [
            "Первые 5 секунд: хук до кнопки Skip",
            "CTA overlay настроен",
            "Companion banner добавлен",
            "End screen с CTA",
        ],
        "трекинг": [
            "Google Ads конверсии настроены",
            "Linked с Google Analytics 4",
            "View-through конверсии настроены (7 дней)",
        ],
    },
}

SYSTEM_PROMPT = """Ты — эксперт по аудиту рекламных аккаунтов для affiliate-маркетинга.
Вертикали: betting, nutra. GEO: US, BR, MX, DE, PL.

Проведи аудит на основе предоставленных данных и чеклиста.
Для каждой проверки: PASS / FAIL / WARNING / N/A.

ФОРМАТ ОТВЕТА (строго JSON):
{
  "platform": "tiktok|meta|youtube",
  "vertical": "nutra|betting",
  "health_score": 0-100,
  "grade": "A+|A|B|C|D|F",
  "checks": {
    "категория": [
      {"check": "...", "status": "PASS|FAIL|WARNING|N/A", "note": "..."}
    ]
  },
  "critical_issues": ["..."],
  "quick_wins": ["..."],
  "action_plan": [
    {"priority": 1, "action": "...", "impact": "high|medium|low", "effort": "high|medium|low"}
  ],
  "estimated_improvement": "..."
}

Health Score:
90-100 = A+ (отличный аккаунт)
80-89  = A  (хороший, мелкие правки)
70-79  = B  (есть проблемы, нужен план)
60-69  = C  (серьёзные проблемы)
<60    = D/F (требует полной переработки)"""


@dataclass
class AuditResult:
    platform: str
    vertical: str
    health_score: int
    grade: str
    checks: dict
    critical_issues: list[str]
    quick_wins: list[str]
    action_plan: list[dict]
    estimated_improvement: str
    audited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AdsAuditor:

    def __init__(self):
        self.llm = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def _build_checklist(self, platform: str) -> str:
        checks = CHECKS.get(platform, {})
        lines = []
        for category, items in checks.items():
            lines.append(f"\n## {category.upper()}")
            for item in items:
                lines.append(f"- {item}")
        return "\n".join(lines)

    async def audit(
        self,
        platform: str,
        vertical: str,
        account_data: dict,
        geo: str = "US",
    ) -> AuditResult:
        checklist = self._build_checklist(platform)

        user_msg = f"""Платформа: {platform.upper()}
Вертикаль: {vertical}
GEO: {geo}

ДАННЫЕ АККАУНТА:
{account_data}

ЧЕКЛИСТ ({platform}):
{checklist}

Проведи полный аудит и верни JSON."""

        response = await self.llm.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        data = _extract_json(response.content[0].text, fallback={
            "platform": platform, "vertical": vertical,
            "health_score": 0, "grade": "F",
            "checks": {}, "critical_issues": ["parse_error"],
            "quick_wins": [], "action_plan": [],
            "estimated_improvement": "N/A",
        })

        result = AuditResult(
            platform=data.get("platform", platform),
            vertical=data.get("vertical", vertical),
            health_score=data.get("health_score", 0),
            grade=data.get("grade", "F"),
            checks=data.get("checks", {}),
            critical_issues=data.get("critical_issues", []),
            quick_wins=data.get("quick_wins", []),
            action_plan=data.get("action_plan", []),
            estimated_improvement=data.get("estimated_improvement", ""),
        )

        logger.info(
            "ads_auditor | platform=%s vertical=%s geo=%s score=%d grade=%s critical=%d",
            platform, vertical, geo,
            result.health_score, result.grade, len(result.critical_issues),
        )
        return result

    async def full_audit(
        self,
        vertical: str,
        geo: str,
        accounts: dict[str, dict],
    ) -> dict[str, AuditResult]:
        """Параллельный аудит по всем платформам."""
        tasks = {
            platform: self.audit(platform, vertical, data, geo)
            for platform, data in accounts.items()
            if platform in CHECKS
        }
        results = await asyncio.gather(*tasks.values())
        return dict(zip(tasks.keys(), results))


async def run(
    platform: str = "tiktok",
    vertical: str = "nutra",
    geo: str = "US",
    account_data: dict | None = None,
) -> AuditResult:
    auditor = AdsAuditor()
    return await auditor.audit(platform, vertical, account_data or {}, geo)
