"""
A25 — COMPLIANCE_GATE
Трёхуровневая проверка контента перед публикацией.
Блокирует: медицинские диагнозы, гарантии выигрыша, запрещённые слова,
trademark конкурентов, обещания конкретных сроков похудения.
Запускается автоматически из content_creator перед передачей в Blotato.
"""
from __future__ import annotations
import asyncio, logging, os, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.compliance_gate")


class RiskLevel(str, Enum):
    SAFE    = "safe"
    WARNING = "warning"
    BLOCKED = "blocked"


# Быстрые regex-проверки (уровень 1 — без LLM)
_HARD_BLOCK_NUTRA = re.compile(
    r"(cure[sd]?|治|гаранти|diagnos|лечит|лечу|вылечит|heals?|"
    r"lose \d+ (kg|lbs|pound|кг) in \d+|похудеть на \d+ кг за \d+|"
    r"100%|guaranteed results?|результат гарантирован|"
    r"FDA approved|клинически доказано)",
    re.IGNORECASE,
)
_HARD_BLOCK_BETTING = re.compile(
    r"(guaranteed (win|profit|return)|беспроигрышн|100% win|"
    r"gарантирован.*выигр|стратегия без проигрыша|"
    r"bet and always win|всегда выигрываешь)",
    re.IGNORECASE,
)
_TRADEMARK = re.compile(
    r"\b(1win|mostbet|melbet|pin.?up|dr\.?cash|betway|bet365|"
    r"bovada|draftkings|fanduel)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """Ты — Compliance Officer для аффилиат-маркетинга (betting + nutra).
Проверь контент по трём уровням. Верни строгий JSON без лишнего текста.

ЗАПРЕЩЕНО для nutra:
- Медицинские диагнозы и заявления о лечении
- Гарантированные результаты за конкретный срок (например "минус 10 кг за 2 недели")
- Слова: cure, heal, diagnose, treat, FDA approved, clinically proven
- Обещания: "100% работает", "гарантированный результат"

ЗАПРЕЩЕНО для betting:
- Гарантии выигрыша ("всегда выигрываешь", "беспроигрышная стратегия")
- Системы ставок с гарантированной прибылью
- "100% win rate", "guaranteed profit"

ЗАПРЕЩЕНО для обоих:
- Имена конкурентов как основные ключевые слова
- Призывы к незаконным действиям
- Контент для несовершеннолетних

ФОРМАТ JSON:
{
  "risk_level": "safe|warning|blocked",
  "score": 0-100,
  "violations": [
    {"rule": "название правила", "text": "цитата из контента", "severity": "hard|soft"}
  ],
  "suggestions": ["как исправить нарушение 1", "как исправить нарушение 2"],
  "clean_version": "исправленная версия текста (только если risk_level=warning)",
  "reason": "краткое объяснение решения"
}

Если нарушений нет — violations: [], clean_version: null."""


@dataclass
class ComplianceResult:
    text: str
    vertical: str
    geo: str
    risk_level: RiskLevel
    score: int
    violations: list[dict]
    suggestions: list[str]
    clean_version: str | None
    reason: str
    passed: bool
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_blocked(self) -> bool:
        return self.risk_level == RiskLevel.BLOCKED


class ComplianceGate:

    def __init__(self):
        self.llm = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def _fast_check(self, text: str, vertical: str) -> list[dict]:
        """Уровень 1: regex без LLM — мгновенно."""
        violations = []
        pattern = _HARD_BLOCK_NUTRA if vertical == "nutra" else _HARD_BLOCK_BETTING
        for m in pattern.finditer(text):
            violations.append({"rule": "hard_block_regex", "text": m.group(), "severity": "hard"})
        for m in _TRADEMARK.finditer(text):
            violations.append({"rule": "trademark_mention", "text": m.group(), "severity": "soft"})
        return violations

    async def check(self, text: str, vertical: str = "nutra", geo: str = "US") -> ComplianceResult:
        """Полная трёхуровневая проверка."""
        # Уровень 1: regex
        fast_violations = self._fast_check(text, vertical)
        hard_blocked = any(v["severity"] == "hard" for v in fast_violations)

        if hard_blocked:
            # Не тратим токены — сразу блокируем
            return ComplianceResult(
                text=text, vertical=vertical, geo=geo,
                risk_level=RiskLevel.BLOCKED, score=0,
                violations=fast_violations,
                suggestions=["Удали медицинские заявления / гарантии результата"],
                clean_version=None,
                reason="Жёсткое нарушение обнаружено regex-фильтром без LLM",
                passed=False,
            )

        # Уровни 2 и 3: LLM-проверка
        user_msg = (
            f"Вертикаль: {vertical} | GEO: {geo}\n"
            f"Быстрые нарушения (regex): {fast_violations}\n\n"
            f"--- КОНТЕНТ ---\n{text[:4000]}\n---\n\n"
            f"Выполни полную проверку и верни JSON."
        )

        resp = await self.llm.messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        data = _extract_json(resp.content[0].text, fallback={
            "risk_level": "warning", "score": 50, "violations": fast_violations,
            "suggestions": [], "clean_version": None, "reason": "parse_error",
        })

        risk = RiskLevel(data.get("risk_level", "warning"))
        score = int(data.get("score", 50))

        result = ComplianceResult(
            text=text, vertical=vertical, geo=geo,
            risk_level=risk,
            score=score,
            violations=data.get("violations", fast_violations),
            suggestions=data.get("suggestions", []),
            clean_version=data.get("clean_version"),
            reason=data.get("reason", ""),
            passed=risk == RiskLevel.SAFE,
        )
        logger.info(
            "compliance_gate | vertical=%s geo=%s risk=%s score=%d violations=%d",
            vertical, geo, risk.value, score, len(result.violations),
        )
        return result

    async def check_batch(
        self,
        texts: list[str],
        vertical: str = "nutra",
        geo: str = "US",
    ) -> list[ComplianceResult]:
        return await asyncio.gather(*[self.check(t, vertical, geo) for t in texts])


async def run(text: str = "", vertical: str = "nutra", geo: str = "US") -> dict:
    gate = ComplianceGate()
    result = await gate.check(text or "Try our product — guaranteed to cure diabetes in 7 days!", vertical, geo)
    return {
        "risk_level": result.risk_level.value,
        "score": result.score,
        "passed": result.passed,
        "violations": result.violations,
        "suggestions": result.suggestions,
        "reason": result.reason,
    }
