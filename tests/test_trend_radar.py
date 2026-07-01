"""Тесты нормализации входа A32 trend_radar (без сети/LLM)."""
from ubt_os.agents.trend_radar import _as_items


def test_as_items_from_strings():
    items = _as_items(["#glowup", "#nutra"], ["original sound - x"])
    kinds = [(i["kind"], i["name"]) for i in items]
    assert ("hashtag", "#glowup") in kinds
    assert ("sound", "original sound - x") in kinds
    assert all(i["growth_pct"] == 0.0 for i in items)


def test_as_items_from_dicts_with_growth():
    items = _as_items(
        [{"name": "#detox", "growth_pct": 45}],
        [{"name": "trending beat", "growth_pct": "120"}],
    )
    by_name = {i["name"]: i for i in items}
    assert by_name["#detox"]["growth_pct"] == 45.0
    assert by_name["#detox"]["kind"] == "hashtag"
    assert by_name["trending beat"]["growth_pct"] == 120.0
    assert by_name["trending beat"]["kind"] == "sound"


def test_as_items_skips_invalid_and_empty():
    items = _as_items([{"no_name": 1}, ""], [None, {"name": "ok"}])
    names = [i["name"] for i in items]
    assert names == ["ok"]


def test_as_items_empty_inputs():
    assert _as_items([], []) == []
    assert _as_items(None, None) == []
