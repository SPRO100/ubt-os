"""Unit-тесты для утилит LLM-парсинга."""
import json
import pytest

from ubt_os.utils.llm_utils import extract_json, response_text


def test_plain_json():
    data = extract_json('{"key": "value"}')
    assert data == {"key": "value"}


def test_markdown_wrapped_json():
    text = '```json\n{"key": "value"}\n```'
    assert extract_json(text) == {"key": "value"}


def test_markdown_no_lang():
    text = '```\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_json_array():
    assert extract_json('[1, 2, 3]') == [1, 2, 3]


def test_invalid_json_raises():
    with pytest.raises(json.JSONDecodeError):
        extract_json("not json at all")


def test_invalid_json_with_fallback():
    result = extract_json("not json", fallback={})
    assert result == {}


def test_whitespace_stripped():
    result = extract_json('  \n{"x": 42}\n  ')
    assert result == {"x": 42}


# ── response_text: content[0] не всегда TextBlock ─────────

class _Block:
    def __init__(self, text=None):
        if text is not None:
            self.text = text


class _Resp:
    def __init__(self, blocks):
        self.content = blocks


def test_response_text_joins_text_blocks():
    resp = _Resp([_Block("Привет, "), _Block("мир")])
    assert response_text(resp) == "Привет, мир"


def test_response_text_skips_thinking_block():
    thinking = _Block()          # ThinkingBlock — без .text
    resp = _Resp([thinking, _Block('{"a": 1}')])
    assert response_text(resp) == '{"a": 1}'


def test_response_text_empty_content():
    assert response_text(_Resp([])) == ""
    assert response_text(object()) == ""
