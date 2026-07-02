"""Тесты таксономии базы знаний (knowledge_taxonomy.py)."""
import pytest
from ubt_os.core.knowledge_taxonomy import (
    build_entry_key,
    parse_entry_key,
    vault_path_for,
    page_template,
    taxonomy_overview,
)


def test_build_entry_key_canonical():
    key = build_entry_key("warmup", "tiktok", "nutra", "grey")
    assert key == "warmup.tiktok.nutra.grey"


def test_build_entry_key_defaults():
    key = build_entry_key("zaliv")
    assert key == "zaliv.any.any.white"


def test_build_entry_key_invalid_process():
    with pytest.raises(ValueError, match="неизвестный процесс"):
        build_entry_key("unknown_proc")


def test_build_entry_key_invalid_platform():
    with pytest.raises(ValueError, match="неизвестная площадка"):
        build_entry_key("zaliv", "snapchat")


def test_build_entry_key_invalid_scheme():
    with pytest.raises(ValueError, match="неизвестная схема"):
        build_entry_key("zaliv", "tiktok", "nutra", "pink")


def test_parse_entry_key_full():
    ax = parse_entry_key("warmup.facebook.betting.black")
    assert ax["process"] == "warmup"
    assert ax["platform"] == "facebook"
    assert ax["vertical"] == "betting"
    assert ax["scheme"] == "black"
    assert "Прогрев" in ax["process_label"]
    assert "Facebook" in ax["platform_label"]


def test_parse_entry_key_short_pads_any():
    ax = parse_entry_key("zaliv")
    assert ax["platform"] == "any"
    assert ax["vertical"] == "any"
    assert ax["scheme"] == "any"


def test_vault_path_contains_key():
    key = "master_prompt.instagram.nutra.white"
    path = vault_path_for(key)
    assert key in path
    assert "master_prompt" in path
    assert "instagram" in path


def test_page_template_has_frontmatter():
    key = "content.tiktok.nutra.grey"
    page = page_template(key, "TikTok нутра", "Хук: боль → решение → CTA")
    assert "---" in page
    assert f"entry_key: {key}" in page
    assert "TikTok нутра" in page
    assert "Хук: боль → решение → CTA" in page
    assert "tags:" in page


def test_taxonomy_overview_all_axes():
    ov = taxonomy_overview()
    assert set(ov.keys()) == {"platforms", "processes", "schemes", "verticals"}
    assert "tiktok" in ov["platforms"]
    assert "zaliv" in ov["processes"]
    assert "grey" in ov["schemes"]
    assert "nutra" in ov["verticals"]
