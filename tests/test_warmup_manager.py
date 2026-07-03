"""Unit-тесты для A28 warmup_manager: состояние в Supabase, не в локальном файле."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from ubt_os.agents.warmup_manager import WarmupManager, WarmupStatus


def _account(**overrides):
    base = {
        "id": "tiktok_us_001",
        "geo": "US",
        "account_type": "new",
        "platform": "tiktok",
        "device_type": "GLOBAL",
        "proxy_type": "mobile",
        "has_local_sim": True,
        "bio_link_enabled": False,
        "status": "warming",
        "warming_started_at": None,
    }
    base.update(overrides)
    return base


def test_check_not_found_returns_not_started():
    with patch("ubt_os.agents.warmup_manager.AccountReader.get_by_id", return_value=None):
        result = WarmupManager().check("ghost_account")
    assert result.status == WarmupStatus.NOT_STARTED
    assert result.ready_to_publish is False


def test_check_day1_warming_up():
    started = datetime.now(timezone.utc).isoformat()
    acc = _account(warming_started_at=started)
    with patch("ubt_os.agents.warmup_manager.AccountReader.get_by_id", return_value=acc), \
         patch("ubt_os.agents.warmup_manager.AccountWriter.update_status") as mock_update:
        result = WarmupManager().check("tiktok_us_001")
    assert result.current_day == 1
    assert result.status == WarmupStatus.WARMING_UP
    assert result.ready_to_publish is False
    # Персистит день/фазу в Supabase, не в файл
    mock_update.assert_called_once()
    args, kwargs = mock_update.call_args
    assert args[0] == "tiktok_us_001"
    assert args[1] == "warming"


def test_check_ready_after_total_days():
    started = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    acc = _account(warming_started_at=started, account_type="new")
    with patch("ubt_os.agents.warmup_manager.AccountReader.get_by_id", return_value=acc), \
         patch("ubt_os.agents.warmup_manager.AccountWriter.update_status") as mock_update:
        result = WarmupManager().check("tiktok_us_001")
    assert result.ready_to_publish is True
    assert result.status == WarmupStatus.READY
    # Готовый аккаунт должен перейти в 'active', чтобы попасть в AccountReader.get_active()
    args, _ = mock_update.call_args
    assert args[1] == "active"


def test_check_blocked_on_critical_infra_issue():
    started = datetime.now(timezone.utc).isoformat()
    acc = _account(warming_started_at=started, proxy_type="datacenter")
    with patch("ubt_os.agents.warmup_manager.AccountReader.get_by_id", return_value=acc), \
         patch("ubt_os.agents.warmup_manager.AccountWriter.update_status"):
        result = WarmupManager().check("tiktok_us_001")
    assert result.status == WarmupStatus.BLOCKED
    assert any(i["severity"] == "critical" for i in result.infra_issues)


def test_check_does_not_overwrite_protected_status():
    started = datetime.now(timezone.utc).isoformat()
    acc = _account(warming_started_at=started, status="hard_banned")
    with patch("ubt_os.agents.warmup_manager.AccountReader.get_by_id", return_value=acc), \
         patch("ubt_os.agents.warmup_manager.AccountWriter.update_status") as mock_update:
        WarmupManager().check("tiktok_us_001")
    mock_update.assert_not_called()


def test_register_unknown_account_returns_error():
    with patch("ubt_os.agents.warmup_manager.AccountReader.get_by_id", return_value=None):
        result = WarmupManager().register("does_not_exist")
    assert result.status == WarmupStatus.NOT_STARTED
    assert "не найден" in result.message
