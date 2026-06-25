"""Unit-тесты для утилит LLM-парсинга."""
import json
import pytest

from ubt_os.utils.llm_utils import extract_json


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
