"""Тесты extract_json — устойчивость к «грязным» ответам LLM."""
import json

import pytest

from ubt_os.utils.llm_utils import extract_json


def test_plain_json():
    assert extract_json('{"a": 1, "b": 2}') == {"a": 1, "b": 2}


def test_fenced_json_block():
    text = '```json\n{"risk_level": "safe", "score": 90}\n```'
    assert extract_json(text) == {"risk_level": "safe", "score": 90}


def test_fenced_block_without_lang():
    assert extract_json('```\n{"x": true}\n```') == {"x": True}


def test_text_before_and_after_json():
    text = 'Конечно! Вот результат:\n{"score": 42, "ok": true}\nНадеюсь, помог.'
    assert extract_json(text) == {"score": 42, "ok": True}


def test_json_array():
    assert extract_json('Список: [1, 2, 3]') == [1, 2, 3]


def test_nested_with_braces_in_strings():
    text = '{"note": "use {curly} braces", "items": [{"k": "}"}]}'
    assert extract_json(text) == {"note": "use {curly} braces", "items": [{"k": "}"}]}


def test_fallback_on_garbage():
    assert extract_json("совсем не json", fallback={"default": True}) == {"default": True}


def test_raises_without_fallback():
    with pytest.raises(json.JSONDecodeError):
        extract_json("no json here at all")
