"""Unit-тесты для защиты от Path Traversal в _safe_vault_path."""
import os
import pytest
from unittest.mock import patch

from ubt_os.main import WebhookHandler


VAULT = "/opt/ubt-os/obsidian-vault"


def safe_path(rel: str):
    with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": VAULT}):
        return WebhookHandler._safe_vault_path(rel)


def test_normal_path_ok():
    p = safe_path("daily/2026-06-25.md")
    assert str(p).startswith(VAULT)


def test_nested_path_ok():
    p = safe_path("projects/ubt-os/notes.md")
    assert "ubt-os" in str(p)


def test_traversal_blocked():
    with pytest.raises(ValueError, match="Path escapes vault"):
        safe_path("../../etc/passwd")


def test_absolute_traversal_blocked():
    with pytest.raises(ValueError, match="Path escapes vault"):
        safe_path("/etc/passwd")


def test_encoded_traversal_blocked():
    with pytest.raises(ValueError, match="Path escapes vault"):
        safe_path("../../../root/.ssh/id_rsa")
