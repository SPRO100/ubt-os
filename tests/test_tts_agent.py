"""Тесты чистой логики A35 tts_agent (без сети)."""
from ubt_os.agents.tts_agent import chunk_text, estimate_duration, pick_provider


def test_chunk_text_short_single():
    assert chunk_text("Короткий скрипт.") == ["Короткий скрипт."]


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_splits_long_on_sentences():
    sentence = "Это предложение номер раз. "
    text = sentence * 200  # заведомо больше 2500 символов
    chunks = chunk_text(text, max_chars=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    # склейка кусков восстанавливает исходный текст (по словам)
    assert " ".join(chunks).split() == text.split()


def test_estimate_duration():
    # 150 слов при 150 wpm ≈ 60с
    assert estimate_duration(" ".join(["word"] * 150), wpm=150) == 60.0
    assert estimate_duration("") == 0.0


def test_pick_provider_priority():
    assert pick_provider("http://tts:8000", None) == "local"
    assert pick_provider(None, "el-key") == "elevenlabs"
    assert pick_provider("http://tts:8000", "el-key") == "local"   # self-hosted приоритетнее
    assert pick_provider(None, None) is None
