"""Unit-тесты для Circuit Breaker (FIX #2)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from ubt_os.core.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    MaxRetriesExceeded,
    call_agent_with_retry,
)


# Async-тесты нужны чтобы `asyncio.create_task` в record_failure работал

@pytest.mark.asyncio
async def test_circuit_starts_closed():
    cb = CircuitBreaker("test")
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold():
    cb = CircuitBreaker("test", failure_threshold=3)
    with patch("ubt_os.core.circuit_breaker._send_telegram_alert", new_callable=AsyncMock):
        for _ in range(3):
            cb.record_failure()
    assert cb._state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_resets_on_success():
    cb = CircuitBreaker("test", failure_threshold=3)
    cb._failure_count = 2
    cb.record_success()
    assert cb._failure_count == 0
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_half_open_after_timeout():
    import time
    cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.001)
    with patch("ubt_os.core.circuit_breaker._send_telegram_alert", new_callable=AsyncMock):
        cb.record_failure()
    assert cb._state == CircuitState.OPEN
    await asyncio.sleep(0.01)
    assert cb.state == CircuitState.HALF


@pytest.mark.asyncio
async def test_allow_request_open_blocks():
    cb = CircuitBreaker("test", failure_threshold=1)
    with patch("ubt_os.core.circuit_breaker._send_telegram_alert", new_callable=AsyncMock):
        cb.record_failure()
    assert not cb.allow_request()


@pytest.mark.asyncio
async def test_call_agent_success():
    cb = CircuitBreaker("test")
    mock_fn = AsyncMock(return_value="ok")
    result = await call_agent_with_retry(mock_fn, breaker=cb)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_call_agent_raises_on_open_circuit():
    cb = CircuitBreaker("test", failure_threshold=1)
    with patch("ubt_os.core.circuit_breaker._send_telegram_alert", new_callable=AsyncMock):
        cb.record_failure()
    with pytest.raises(CircuitOpenError):
        await call_agent_with_retry(AsyncMock(), breaker=cb)


@pytest.mark.asyncio
async def test_call_agent_retries_on_connection_error():
    """Агент ретраит при APIConnectionError, потом успешно отвечает."""
    import anthropic
    cb = CircuitBreaker("test", failure_threshold=10)
    call_count = 0

    async def flaky_fn():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise anthropic.APIConnectionError(request=None)
        return "recovered"

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await call_agent_with_retry(flaky_fn, breaker=cb, max_retries=3)

    assert result == "recovered"
    assert call_count == 3


@pytest.mark.asyncio
async def test_call_agent_raises_max_retries():
    """После исчерпания retry бросает MaxRetriesExceeded."""
    import anthropic
    cb = CircuitBreaker("test", failure_threshold=10)

    async def always_fail():
        raise anthropic.APIConnectionError(request=None)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(MaxRetriesExceeded):
            await call_agent_with_retry(always_fail, breaker=cb, max_retries=2)
