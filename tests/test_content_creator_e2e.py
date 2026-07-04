"""E2E-прогон A21 content_creator → A19 text_humanizer для вертикали ВНЕ
nutra/betting (напр. "tourism" — реальный проект пользователя). Только LLM
замокан; сам ContentCreator/TextHumanizer выполняется по-настоящему — тест
ловит регресс жёсткого Vertical(str, Enum), который падал с
AttributeError: 'str' object has no attribute 'value' на любой вертикали
кроме nutra/betting.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ubt_os.agents.content_creator import ContentCreator, ContentFormat
from ubt_os.agents.text_humanizer import TextHumanizer


def _llm_response(payload: dict):
    resp = MagicMock()
    resp.content = [MagicMock(text=json.dumps(payload))]
    return resp


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


async def test_content_creator_handles_non_binary_vertical(env):
    """Проект "Турагентство" → vertical="tourism", не nutra и не betting."""
    with patch("ubt_os.agents.content_creator.AsyncAnthropic") as creator_llm_cls, \
         patch("ubt_os.agents.text_humanizer.AsyncAnthropic") as humanizer_llm_cls:
        creator_llm_cls.return_value.messages.create = AsyncMock(
            return_value=_llm_response({"script": "Едем в Турцию по системе всё включено", "hook": "..."})
        )
        humanizer_llm_cls.return_value.messages.create = AsyncMock(
            return_value=_llm_response({
                "humanized_text": "Едем в Турцию, всё включено — без сюрпризов",
                "original_score": {"total": 20},
                "final_score": {"total": 42},
                "changes_made": ["убрал канцелярит"],
                "passed": True,
            })
        )

        creator = ContentCreator()
        piece = await creator.create(ContentFormat.HOOK_PROBLEM, "tourism", "RU", offer="TezTour")

        assert piece.vertical == "tourism"
        assert piece.geo == "RU"
        assert piece.humanize_score == 42
        assert piece.passed_quality is True
        assert piece.humanized_text == "Едем в Турцию, всё включено — без сюрпризов"


async def test_content_creator_batch_handles_arbitrary_verticals(env):
    with patch("ubt_os.agents.content_creator.AsyncAnthropic") as creator_llm_cls, \
         patch("ubt_os.agents.text_humanizer.AsyncAnthropic") as humanizer_llm_cls:
        creator_llm_cls.return_value.messages.create = AsyncMock(
            return_value=_llm_response({"script": "Ремонт под ключ за 30 дней"})
        )
        humanizer_llm_cls.return_value.messages.create = AsyncMock(
            return_value=_llm_response({
                "humanized_text": "Ремонт под ключ за 30 дней",
                "original_score": {"total": 15},
                "final_score": {"total": 38},
                "changes_made": [],
                "passed": True,
            })
        )

        creator = ContentCreator()
        pieces = await creator.create_batch([
            {"format": "short_hook_problem_solution", "vertical": "construction", "geo": "PL"},
        ])

        assert len(pieces) == 1
        assert pieces[0].vertical == "construction"


def test_default_format_strings_match_content_format_enum():
    """main.py._run_agent и Launch.jsx/Tasks.jsx (дашборд) шлют строковые
    дефолты format напрямую в ContentFormat(...) — раньше они не совпадали
    с реальными значениями enum (ContentFormat.HOOK_PROBLEM.value ==
    "short_hook_problem_solution", а не "hook_problem"), что валило
    ValueError на дефолтном выборе формата A21-карточки."""
    assert ContentFormat("short_hook_problem_solution") == ContentFormat.HOOK_PROBLEM
    assert ContentFormat("before_after_testimonial") == ContentFormat.BEFORE_AFTER


async def test_text_humanizer_handles_arbitrary_vertical(env):
    with patch("ubt_os.agents.text_humanizer.AsyncAnthropic") as humanizer_llm_cls:
        humanizer_llm_cls.return_value.messages.create = AsyncMock(
            return_value=_llm_response({
                "humanized_text": "Займы под 0% на первые 30 дней",
                "original_score": {"total": 12},
                "final_score": {"total": 40},
                "changes_made": ["упростил"],
                "passed": True,
            })
        )
        humanizer = TextHumanizer()
        result = await humanizer.humanize("Займы под 0% на первые 30 дней", geo="US", vertical="finance")

        assert result.final_score.get("total") == 40
        assert result.passed is True
