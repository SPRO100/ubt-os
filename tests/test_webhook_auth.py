"""Unit-тесты для HMAC-аутентификации вебхуков."""
import hashlib
import hmac
import json
import os
from io import BytesIO
from unittest.mock import MagicMock, patch
import pytest

# Импортируем только функцию верификации — без подъёма всего сервера
from ubt_os.main import WebhookHandler


def _make_handler(secret: str | None, body: bytes, sig: str = "") -> WebhookHandler:
    """Создаёт WebhookHandler с замоканными headers и env."""
    handler = WebhookHandler.__new__(WebhookHandler)
    handler.headers = {"X-Webhook-Signature": sig}
    with patch.dict(os.environ, {"WEBHOOK_SECRET": secret} if secret else {}, clear=False):
        return handler


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_no_secret_always_passes():
    handler = _make_handler(None, b'{"action":"test"}')
    with patch.dict(os.environ, {}, clear=False):
        # Удаляем WEBHOOK_SECRET если он есть
        os.environ.pop("WEBHOOK_SECRET", None)
        assert handler._verify_signature(b'{"action":"test"}') is True


def test_valid_signature_passes():
    body = b'{"action":"run"}'
    secret = "my-secret"
    sig = _sign(secret, body)
    handler = WebhookHandler.__new__(WebhookHandler)
    handler.headers = {"X-Webhook-Signature": sig}
    with patch.dict(os.environ, {"WEBHOOK_SECRET": secret}):
        assert handler._verify_signature(body) is True


def test_invalid_signature_blocked():
    body = b'{"action":"run"}'
    handler = WebhookHandler.__new__(WebhookHandler)
    handler.headers = {"X-Webhook-Signature": "wrong"}
    with patch.dict(os.environ, {"WEBHOOK_SECRET": "my-secret"}):
        assert handler._verify_signature(body) is False


def test_missing_signature_header_blocked():
    body = b'{"action":"run"}'
    handler = WebhookHandler.__new__(WebhookHandler)
    handler.headers = {}
    with patch.dict(os.environ, {"WEBHOOK_SECRET": "my-secret"}):
        assert handler._verify_signature(body) is False
