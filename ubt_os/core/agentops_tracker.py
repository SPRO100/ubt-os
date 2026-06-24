"""
AgentOps — трекинг расходов LiteLLM Router.

Подключается через LiteLLM callbacks. Пишет в Supabase таблицу `llm_usage_events`.
Схема: model, input_tokens, output_tokens, cost_usd, agent_name, vertical, duration_ms, ts.

Использование:
    from ubt_os.core.agentops_tracker import setup_agentops
    setup_agentops()  # вызвать один раз при старте, до первого LiteLLM-вызова
"""
from __future__ import annotations
import os
import time
import logging
from typing import Any

logger = logging.getLogger("ubt_os.agentops")

# Стоимость за 1M токенов (input / output) по состоянию на июнь 2026
_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6":         (3.00,  15.00),
    "claude-haiku-4-5-20251001": (0.25,   1.25),
    "claude-haiku-4-5":          (0.25,   1.25),
    "claude-opus-4-8":           (15.00,  75.00),
    # fallback
    "default":                   (3.00,  15.00),
}

def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = _PRICING.get(model, _PRICING["default"])
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


class _UbtLiteLLMCallback:
    """LiteLLM CustomLogger — пишет usage в Supabase и stdout."""

    def __init__(self):
        self._db = None

    def _get_db(self):
        if self._db is None:
            from supabase import create_client
            self._db = create_client(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_SERVICE_KEY"],
            )
        return self._db

    # ── LiteLLM callback interface ──────────────────────────

    def log_success_event(self, kwargs: dict, response_obj: Any, start_time, end_time):
        try:
            self._write(kwargs, response_obj, start_time, end_time, error=None)
        except Exception as e:
            logger.warning(f"AgentOps log_success_event error: {e}")

    def log_failure_event(self, kwargs: dict, response_obj: Any, start_time, end_time):
        try:
            self._write(kwargs, response_obj, start_time, end_time,
                        error=str(response_obj) if response_obj else "unknown")
        except Exception as e:
            logger.warning(f"AgentOps log_failure_event error: {e}")

    def _write(self, kwargs: dict, response_obj: Any, start_time, end_time, error):
        model = kwargs.get("model", "unknown")
        meta  = kwargs.get("metadata") or {}
        agent_name = meta.get("agent_name", "unknown")
        vertical   = meta.get("vertical", "unknown")

        usage = getattr(response_obj, "usage", None) if response_obj else None
        input_tokens  = getattr(usage, "prompt_tokens",     0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        cost_usd      = _calc_cost(model, input_tokens, output_tokens)

        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        row = {
            "model":         model,
            "agent_name":    agent_name,
            "vertical":      vertical,
            "input_tokens":  input_tokens,
            "output_tokens": output_tokens,
            "cost_usd":      round(cost_usd, 8),
            "duration_ms":   duration_ms,
            "error":         error,
        }

        logger.info(
            f"[LLM] {agent_name}/{vertical} {model} "
            f"in={input_tokens} out={output_tokens} "
            f"cost=${cost_usd:.5f} {duration_ms}ms"
        )

        try:
            self._get_db().table("llm_usage_events").insert(row).execute()
        except Exception as e:
            logger.warning(f"AgentOps DB write error: {e}")


_callback_instance: _UbtLiteLLMCallback | None = None


def setup_agentops():
    """Регистрирует callback в LiteLLM. Идемпотентно."""
    global _callback_instance
    if _callback_instance is not None:
        return

    try:
        import litellm
        _callback_instance = _UbtLiteLLMCallback()
        litellm.callbacks = getattr(litellm, "callbacks", [])
        if _callback_instance not in litellm.callbacks:
            litellm.callbacks.append(_callback_instance)
        logger.info("AgentOps: LiteLLM callback зарегистрирован")
    except ImportError:
        logger.warning("AgentOps: litellm не установлен — трекинг отключён")


def get_usage_summary(days: int = 7) -> dict:
    """Возвращает агрегат расходов за N дней из Supabase."""
    try:
        from supabase import create_client
        db = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_KEY"],
        )
        from datetime import datetime, timezone, timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = (
            db.table("llm_usage_events")
            .select("model,agent_name,vertical,input_tokens,output_tokens,cost_usd")
            .gte("created_at", since)
            .execute()
        ).data

        total_cost    = sum(r["cost_usd"] for r in rows)
        total_input   = sum(r["input_tokens"] for r in rows)
        total_output  = sum(r["output_tokens"] for r in rows)
        by_model: dict[str, float] = {}
        by_agent: dict[str, float] = {}
        for r in rows:
            by_model[r["model"]] = by_model.get(r["model"], 0) + r["cost_usd"]
            by_agent[r["agent_name"]] = by_agent.get(r["agent_name"], 0) + r["cost_usd"]

        return {
            "days":          days,
            "calls":         len(rows),
            "total_cost_usd": round(total_cost, 4),
            "total_input_tokens":  total_input,
            "total_output_tokens": total_output,
            "by_model":      {k: round(v, 4) for k, v in sorted(by_model.items(), key=lambda x: -x[1])},
            "by_agent":      {k: round(v, 4) for k, v in sorted(by_agent.items(), key=lambda x: -x[1])},
        }
    except Exception as e:
        return {"error": str(e)}
