"""Unit-тесты для A18 knowledge_synthesizer: запись в kb_entries, не в legacy."""
from unittest.mock import MagicMock, patch

from ubt_os.agents.knowledge_synthesizer import KnowledgeWriter


def test_save_daily_writes_to_kb_entries_with_date_key():
    db = MagicMock()
    writer = KnowledgeWriter(db)
    synthesis = {
        "what_worked": ["UGC-хук с числом дал +40% ER"],
        "what_failed": ["Before/After формат не зашёл на betting"],
        "why_analysis": "Аудитория лучше реагирует на конкретику",
        "experiment_tomorrow": "Протестировать вопрос-хук на 3 аккаунтах",
        "new_hypothesis": {"statement": "Хуки с числом дают выше ER", "confidence": 0.6},
    }
    with patch("ubt_os.agents.knowledge_synthesizer.save_kb_entry", return_value=True) as mock_save:
        entry_key = writer.save_daily(synthesis)

    assert entry_key is not None
    assert entry_key.startswith("analytics.any.any.white.")
    mock_save.assert_called_once()
    _, kwargs = mock_save.call_args
    assert kwargs["category"] == "analytics"
    assert "UGC-хук" in kwargs["content"]
    assert "Хуки с числом" in kwargs["content"]


def test_save_weekly_skips_when_no_compound_learning():
    db = MagicMock()
    writer = KnowledgeWriter(db)
    with patch("ubt_os.agents.knowledge_synthesizer.save_kb_entry") as mock_save:
        result = writer.save_weekly({"winning_patterns": []})
    assert result is None
    mock_save.assert_not_called()


def test_save_weekly_writes_compound_learning():
    db = MagicMock()
    writer = KnowledgeWriter(db)
    synthesis = {
        "winning_patterns": [],
        "compound_learning": "Grey-схема требует прокладку на всех вертикалях",
        "next_week_priority": "Масштабировать TikTok betting",
    }
    with patch("ubt_os.agents.knowledge_synthesizer.save_kb_entry", return_value=True) as mock_save:
        entry_key = writer.save_weekly(synthesis)

    assert entry_key is not None
    assert "weekly-W" in entry_key
    _, kwargs = mock_save.call_args
    assert "Grey-схема" in kwargs["content"]
