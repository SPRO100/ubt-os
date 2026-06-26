"""
Centralized structured JSON logging для UBT OS.

Использование:
    from ubt_os.core.logging_config import setup_logging, get_logger
    setup_logging()  # вызвать один раз при старте
    logger = get_logger("ubt_os.my_module")
    logger.info("message", extra={"request_id": "abc", "account_id": "123"})

Формат вывода (Railway/Datadog совместимый):
    {"ts": "2026-06-26T12:00:00Z", "level": "INFO", "logger": "ubt_os.main",
     "msg": "message", "request_id": "abc", "account_id": "123"}
"""
from __future__ import annotations
import json
import logging
import os
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone

# Контекстная переменная для correlation ID — пробрасывается через async цепочки
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def get_request_id() -> str | None:
    return _request_id_var.get()


class JsonFormatter(logging.Formatter):
    """Форматирует лог-записи как однострочный JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }

        # Correlation ID из context var
        request_id = _request_id_var.get()
        if request_id:
            entry["request_id"] = request_id

        # Extra-поля (account_id, vertical_id и т.д.)
        for key, val in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
                entry[key] = val

        # Трейсбек при наличии исключения
        if record.exc_info:
            entry["exc"] = "".join(traceback.format_exception(*record.exc_info)).strip()

        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging(level: str | None = None) -> None:
    """Настраивает глобальный logging. Вызывать один раз при старте."""
    log_level = getattr(logging, (level or os.getenv("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "json")

    root = logging.getLogger()
    root.setLevel(log_level)

    # Убираем существующие хендлеры
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        ))

    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
