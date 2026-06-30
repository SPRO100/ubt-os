"""Тесты L1 (regex) проверки A25 ComplianceGate — без обращения к LLM.

Уровень 1 (быстрые regex) критичен для безопасности: он ловит жёсткие
нарушения и блокирует контент ещё до траты токенов на LLM.
"""
import os

import pytest

from ubt_os.agents.compliance_gate import ComplianceGate, RiskLevel


def _gate() -> ComplianceGate:
    """Инстанс без вызова __init__ — L1 не требует Anthropic-клиента."""
    return ComplianceGate.__new__(ComplianceGate)


# ── nutra: hard-блоки ────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "This supplement cures diabetes in 7 days",
    "Clinically proven and FDA approved formula",
    "Lose 10 kg in 14 days guaranteed",
    "Это средство лечит ожирение",
    "Результат гарантирован — 100% работает",
])
def test_nutra_hard_violations_detected(text):
    violations = _gate()._fast_check(text, "nutra")
    assert any(v["severity"] == "hard" for v in violations), text


def test_clean_nutra_text_has_no_hard_violations():
    text = "Многие отмечают прилив энергии и лёгкость после курса витаминов."
    violations = _gate()._fast_check(text, "nutra")
    assert not any(v["severity"] == "hard" for v in violations)


# ── betting: hard-блоки ──────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Guaranteed win every time with this system",
    "Беспроигрышная стратегия ставок",
    "100% win rate strategy",
    "Bet and always win",
])
def test_betting_hard_violations_detected(text):
    violations = _gate()._fast_check(text, "betting")
    assert any(v["severity"] == "hard" for v in violations), text


# ── trademark — soft ─────────────────────────────────────────────────

@pytest.mark.parametrize("brand", ["1win", "mostbet", "bet365", "DraftKings"])
def test_trademark_flagged_as_soft(brand):
    violations = _gate()._fast_check(f"Лучше чем {brand} прямо сейчас", "betting")
    assert any(v["rule"] == "trademark_mention" and v["severity"] == "soft"
               for v in violations), brand


# ── короткий путь check(): hard → BLOCKED без LLM ───────────────────

@pytest.mark.asyncio
async def test_check_hard_block_short_circuits_without_llm(monkeypatch):
    # Ключ нужен только для __init__; LLM не вызывается на hard-пути.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    gate = ComplianceGate()
    result = await gate.check("This product cures cancer, guaranteed!", "nutra", "US")
    assert result.risk_level == RiskLevel.BLOCKED
    assert result.passed is False
    assert result.is_blocked is True
