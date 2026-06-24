"""
Compliance Gate — проверка контента перед публикацией.
Использует Haiku для быстрой классификации.
Возвращает: pass | warn | block + причину.
"""

from __future__ import annotations
import logging
import os
import re
from dataclasses import dataclass
from typing import Literal
import httpx

logger = logging.getLogger("compliance_gate")

Verdict = Literal["pass", "warn", "block"]


# ══════════════════════════════════════════════════════════
# 1. БАН-СЛОВА ПО GEO И ВЕРТИКАЛИ
# ══════════════════════════════════════════════════════════

BAN_WORDS: dict[str, list[str]] = {
    # Нутра — медицинские claims (все GEO)
    "nutra_medical": [
        "gwarantuje", "garantuje", "garanteaza", "garantiza", "guarantees",
        "гарантирует выздоровление", "гарантирует лечение",
        "leczy", "vindecă", "cura", "heals", "лечит",
        "kliniczne badania", "studii clinice", "estudios clínicos", "clinical studies",
        "FDA", "EMA", "bez recepty leczy", "fără rețetă vindecă",
    ],
    # Беттинг — запрещённые фразы (RU/KZ)
    "betting_ru": [
        "гарантированный выигрыш", "беспроигрышная стратегия",
        "100% победа", "точный прогноз 100",
        "взлом букмекера", "читерство",
        "несовершеннолетним", "детям", "школьникам",
    ],
    # Нутра PL
    "nutra_PL": [
        "lek", "lekarstwo", "recepta", "farmaceutyczny",
        "gwarantowane leczenie",
    ],
    # Нутра RO
    "nutra_RO": [
        "medicament", "prescripție", "farmaceutic",
        "vindecare garantată",
    ],
    # Нутра MX/BR
    "nutra_LATAM": [
        "medicamento", "prescripción", "farmacéutico",
        "cura garantizada", "remédio", "prescrição",
    ],
    # Нутра IN
    "nutra_IN": [
        "guaranteed cure", "medical prescription", "pharmaceutical drug",
    ],
}

# Мягкие предупреждения (warn, не block)
WARN_WORDS: dict[str, list[str]] = {
    "nutra_all": [
        "врач рекомендует", "doctor recommends", "lekarz poleca",
        "медицинский", "medical", "клиника", "clinic",
        "результаты могут отличаться",
    ],
    "betting_all": [
        "легко заработать", "быстрые деньги", "easy money",
        "без риска", "no risk",
    ],
}


# ══════════════════════════════════════════════════════════
# 2. DATACLASS РЕЗУЛЬТАТА
# ══════════════════════════════════════════════════════════

@dataclass
class ComplianceResult:
    verdict:    Verdict
    reason:     str
    matched:    list[str]   # найденные бан-слова
    geo:        str
    vertical:   str


# ══════════════════════════════════════════════════════════
# 3. GATE
# ══════════════════════════════════════════════════════════

class ComplianceGate:
    """
    Проверяет текст контента перед публикацией.
    Шаг 1: быстрая regex-проверка по словарю бан-слов.
    Шаг 2: если прошёл regex — LLM-проверка на Haiku для edge cases.
    """

    LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
    HAIKU_MODEL = "haiku"

    def check(self, text: str, vertical: str, geo: str) -> ComplianceResult:
        """Синхронная проверка текста."""
        text_lower = text.lower()

        # --- Шаг 1: regex по словарям ---
        blocked, warned = self._regex_check(text_lower, vertical, geo)

        if blocked:
            return ComplianceResult(
                verdict="block",
                reason=f"Запрещённые слова/claims: {', '.join(blocked[:3])}",
                matched=blocked,
                geo=geo,
                vertical=vertical,
            )

        # --- Шаг 2: LLM-проверка если есть предупреждения или текст длинный ---
        if warned or len(text) > 200:
            llm_result = self._llm_check(text, vertical, geo)
            if llm_result.verdict in ("block", "warn"):
                llm_result.matched = warned + llm_result.matched
                return llm_result

        if warned:
            return ComplianceResult(
                verdict="warn",
                reason=f"Потенциально чувствительные слова: {', '.join(warned[:3])}",
                matched=warned,
                geo=geo,
                vertical=vertical,
            )

        return ComplianceResult(
            verdict="pass",
            reason="OK",
            matched=[],
            geo=geo,
            vertical=vertical,
        )

    def _regex_check(
        self, text_lower: str, vertical: str, geo: str
    ) -> tuple[list[str], list[str]]:
        """Возвращает (blocked_words, warned_words)."""
        blocked: list[str] = []
        warned:  list[str] = []

        # Определяем релевантные словари
        check_keys: list[str] = []
        if vertical == "nutra":
            check_keys += ["nutra_medical"]
            if geo == "PL":
                check_keys.append("nutra_PL")
            elif geo == "RO":
                check_keys.append("nutra_RO")
            elif geo in ("MX", "BR"):
                check_keys.append("nutra_LATAM")
            elif geo == "IN":
                check_keys.append("nutra_IN")
        elif vertical == "betting":
            check_keys.append("betting_ru")

        warn_keys: list[str] = []
        if vertical == "nutra":
            warn_keys.append("nutra_all")
        elif vertical == "betting":
            warn_keys.append("betting_all")

        for key in check_keys:
            for word in BAN_WORDS.get(key, []):
                if re.search(re.escape(word.lower()), text_lower):
                    blocked.append(word)

        for key in warn_keys:
            for word in WARN_WORDS.get(key, []):
                if re.search(re.escape(word.lower()), text_lower):
                    warned.append(word)

        return blocked, warned

    def _llm_check(self, text: str, vertical: str, geo: str) -> ComplianceResult:
        """LLM-проверка через Haiku — для edge cases."""
        prompt = f"""You are a compliance checker for affiliate marketing content.
Vertical: {vertical}
GEO: {geo}

Check this content for compliance violations:
1. Medical claims (for nutra): guaranteed cures, treatment claims, clinical study misuse
2. Illegal gambling claims (for betting): guaranteed wins, underage targeting
3. Deceptive advertising

Content:
\"\"\"
{text[:1000]}
\"\"\"

Respond with JSON only:
{{"verdict": "pass|warn|block", "reason": "short explanation", "matched": ["phrase1", "phrase2"]}}"""

        try:
            resp = httpx.post(
                f"{self.LITELLM_URL}/chat/completions",
                json={
                    "model": self.HAIKU_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0,
                },
                timeout=15,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            # Извлекаем JSON из возможных markdown-обёрток
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                raise ValueError("No JSON in LLM response")
            data = __import__("json").loads(match.group())
            return ComplianceResult(
                verdict=data.get("verdict", "pass"),
                reason=data.get("reason", ""),
                matched=data.get("matched", []),
                geo=geo,
                vertical=vertical,
            )
        except Exception as e:
            logger.warning(f"LLM compliance check failed: {e} — defaulting to pass")
            return ComplianceResult(
                verdict="pass",
                reason="LLM check skipped",
                matched=[],
                geo=geo,
                vertical=vertical,
            )


# ══════════════════════════════════════════════════════════
# 4. SINGLETON
# ══════════════════════════════════════════════════════════

_gate: ComplianceGate | None = None

def get_gate() -> ComplianceGate:
    global _gate
    if _gate is None:
        _gate = ComplianceGate()
    return _gate
