"""Unit-тесты аутентификации вебхуков: HMAC (n8n) + Bearer-токен (dashboard)."""
import hashlib
import hmac

from ubt_os.main import WebhookHandler


def _handler(headers: dict) -> WebhookHandler:
    h = WebhookHandler.__new__(WebhookHandler)
    h.headers = headers
    return h


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ── dev-режим: ни секрета, ни токена → пропускаем ───────────────────

def test_no_secret_no_token_passes(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("AGENTS_API_TOKEN", raising=False)
    assert _handler({})._authorized(b'{"action":"test"}') is True


# ── HMAC-путь (n8n) ─────────────────────────────────────────────────

def test_valid_signature_passes(monkeypatch):
    body, secret = b'{"action":"run"}', "my-secret"
    monkeypatch.setenv("WEBHOOK_SECRET", secret)
    monkeypatch.delenv("AGENTS_API_TOKEN", raising=False)
    assert _handler({"X-Webhook-Signature": _sign(secret, body)})._authorized(body) is True


def test_invalid_signature_blocked(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "my-secret")
    monkeypatch.delenv("AGENTS_API_TOKEN", raising=False)
    assert _handler({"X-Webhook-Signature": "wrong"})._authorized(b'{"action":"run"}') is False


def test_missing_signature_header_blocked(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "my-secret")
    monkeypatch.delenv("AGENTS_API_TOKEN", raising=False)
    assert _handler({})._authorized(b'{"action":"run"}') is False


# ── Bearer-путь (dashboard) ─────────────────────────────────────────

def test_valid_bearer_token_passes(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("AGENTS_API_TOKEN", "dash-token")
    assert _handler({"Authorization": "Bearer dash-token"})._authorized(b"{}") is True


def test_invalid_bearer_token_blocked(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("AGENTS_API_TOKEN", "dash-token")
    assert _handler({"Authorization": "Bearer nope"})._authorized(b"{}") is False


def test_missing_auth_header_blocked_when_token_set(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("AGENTS_API_TOKEN", "dash-token")
    assert _handler({})._authorized(b"{}") is False


# ── оба механизма заданы: любой валидный проходит ───────────────────

def test_either_mechanism_accepted(monkeypatch):
    body = b'{"action":"x"}'
    monkeypatch.setenv("WEBHOOK_SECRET", "s")
    monkeypatch.setenv("AGENTS_API_TOKEN", "t")
    assert _handler({"Authorization": "Bearer t"})._authorized(body) is True
    assert _handler({"X-Webhook-Signature": _sign("s", body)})._authorized(body) is True
    assert _handler({})._authorized(body) is False
