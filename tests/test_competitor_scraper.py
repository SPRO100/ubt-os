"""Тесты нормализации A33 competitor_scraper (без сети/БД)."""
from ubt_os.agents.competitor_scraper import _dig, _extract_items, _normalize


def test_dig_nested_and_missing():
    obj = {"a": {"b": [{"c": 5}]}}
    assert _dig(obj, "a", "b", 0, "c") == 5
    assert _dig(obj, "a", "x", default="d") == "d"
    assert _dig(obj, "a", "b", 9, "c", default=0) == 0


def test_extract_items_various_wrappers():
    assert len(_extract_items([{"x": 1}, {"y": 2}])) == 2
    assert len(_extract_items({"data": [{"x": 1}]})) == 1
    assert len(_extract_items({"aweme_list": [{"x": 1}, {"y": 2}]})) == 2
    assert _extract_items({"nope": 123}) == []
    assert _extract_items("garbage") == []


def test_normalize_tiktok_shape():
    raw = {
        "share_url": "https://tiktok.com/@u/video/123",
        "desc": "before after nutra result",
        "author": {"nickname": "GuruNutra"},
        "video": {"cover": {"url_list": ["https://cdn/cover.jpg"]}},
        "statistics": {"play_count": 1000, "digg_count": 200, "comment_count": 50, "share_count": 50},
    }
    s = _normalize(raw, "nutra", "US", "tiktok")
    assert s["video_url"].endswith("/123")
    assert s["account_name"] == "GuruNutra"
    assert s["thumbnail_url"] == "https://cdn/cover.jpg"
    assert s["views"] == 1000
    # ER = (200+50+50)/1000 = 0.3
    assert s["er"] == 0.3
    assert s["vertical"] == "nutra" and s["geo"] == "US"


def test_normalize_requires_video_url():
    assert _normalize({"desc": "no url"}, "nutra", "US", "tiktok") is None


def test_normalize_zero_plays_no_division_error():
    raw = {"video_url": "u", "statistics": {"play_count": 0, "digg_count": 5}}
    s = _normalize(raw, "betting", "BR", "tiktok")
    assert s["er"] == 0.0
    assert s["views"] == 0
