"""Тесты чистой логики A36 post_analytics_agent (без сети)."""
from ubt_os.agents.post_analytics_agent import MetricsResult, METRICS_FETCHERS


def test_engagement_rate_uses_impressions_first():
    r = MetricsResult(success=True, impressions=1000, reach=2000, likes=50, comments=10, shares=5, saves=5)
    # (50+10+5+5) / 1000 * 100 = 7.0
    assert r.engagement_rate == 7.0


def test_engagement_rate_falls_back_to_reach():
    r = MetricsResult(success=True, impressions=0, reach=500, likes=25, comments=0, shares=0, saves=0)
    assert r.engagement_rate == 5.0


def test_engagement_rate_falls_back_to_views():
    r = MetricsResult(success=True, impressions=0, reach=0, views=200, likes=10, comments=0, shares=0, saves=0)
    assert r.engagement_rate == 5.0


def test_engagement_rate_zero_without_any_base():
    r = MetricsResult(success=True, likes=10, comments=5)
    assert r.engagement_rate == 0.0


def test_engagement_rate_zero_engagement():
    r = MetricsResult(success=True, impressions=1000)
    assert r.engagement_rate == 0.0


def test_metrics_fetchers_cover_publisher_platforms():
    # Должны совпадать с платформами, в которые реально публикуем (social_publisher.PLATFORM_CLIENTS)
    from ubt_os.pipelines.social_publisher import PLATFORM_CLIENTS
    assert set(PLATFORM_CLIENTS) == set(METRICS_FETCHERS)
