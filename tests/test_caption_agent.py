"""Тесты чистой логики A34 caption_agent (без сети/ffmpeg)."""
from ubt_os.agents.caption_agent import (
    _fmt_srt_ts, _fmt_ass_ts, group_words, build_srt, build_ass,
)


def test_srt_timestamp_format():
    assert _fmt_srt_ts(0) == "00:00:00,000"
    assert _fmt_srt_ts(1.234) == "00:00:01,234"
    assert _fmt_srt_ts(3661.5) == "01:01:01,500"
    assert _fmt_srt_ts(-5) == "00:00:00,000"


def test_ass_timestamp_format():
    assert _fmt_ass_ts(0) == "0:00:00.00"
    assert _fmt_ass_ts(1.23) == "0:00:01.23"
    assert _fmt_ass_ts(61.5) == "0:01:01.50"


WORDS = [
    {"word": "lose", "start": 0.0, "end": 0.3},
    {"word": "weight", "start": 0.3, "end": 0.7},
    {"word": "fast", "start": 0.7, "end": 1.0},
    {"word": "naturally", "start": 1.1, "end": 1.6},
    {"word": "now", "start": 3.0, "end": 3.3},   # большой разрыв → новый сегмент
]


def test_group_words_by_max_and_gap():
    segs = group_words(WORDS, max_words=4, max_gap=0.6)
    # 4 слова подряд → первый сегмент; "now" после паузы 1.4с → отдельный
    assert len(segs) == 2
    assert segs[0]["text"] == "lose weight fast naturally"
    assert segs[0]["start"] == 0.0 and segs[0]["end"] == 1.6
    assert segs[1]["text"] == "now"


def test_group_words_skips_empty():
    segs = group_words([{"word": "  ", "start": 0, "end": 1}, {"word": "hi", "start": 1, "end": 2}])
    assert len(segs) == 1 and segs[0]["text"] == "hi"


def test_build_srt_structure():
    srt = build_srt(group_words(WORDS))
    assert "1\n00:00:00,000 --> 00:00:01,600\nlose weight fast naturally" in srt
    assert "-->" in srt


def test_build_ass_has_header_and_dialogue():
    ass = build_ass(group_words(WORDS), style="tiktok")
    assert "[Script Info]" in ass
    assert "Style: Cap," in ass
    assert "Dialogue: 0," in ass
    # текст в верхнем регистре
    assert "LOSE WEIGHT FAST NATURALLY" in ass


def test_build_ass_unknown_style_falls_back():
    ass = build_ass(group_words(WORDS), style="does-not-exist")
    assert "Style: Cap," in ass
