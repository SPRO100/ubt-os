"""POST /run/pipeline — generic-роут для произвольной вертикали (в отличие
от /run/nutra и /run/ubt, оставленных для обратной совместимости с n8n)."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from ubt_os.main import WebhookHandler


@asynccontextmanager
async def _fake_lock(name, ttl_seconds=600):
    yield True


async def test_run_pipeline_passes_lowercased_vertical_as_raw_string():
    with patch("ubt_os.core.pipeline_lock", _fake_lock), \
         patch(
             "ubt_os.pipelines.video_pipeline.run_video_pipeline",
             new=AsyncMock(return_value={"status": "ok", "created": 2}),
         ) as rvp:
        h = WebhookHandler.__new__(WebhookHandler)
        result = await h._run_pipeline({"vertical": "Tourism", "geo": "ru", "count": 2, "output": "text"})

        assert result == {"status": "ok", "created": 2}
        rvp.assert_awaited_once()
        assert rvp.await_args.args[0] == "tourism"
        assert rvp.await_args.kwargs["geo"] == "ru"
        assert rvp.await_args.kwargs["output"] == "text"


async def test_run_pipeline_defaults_to_nutra_when_vertical_missing():
    with patch("ubt_os.core.pipeline_lock", _fake_lock), \
         patch(
             "ubt_os.pipelines.video_pipeline.run_video_pipeline",
             new=AsyncMock(return_value={"status": "ok", "created": 1}),
         ) as rvp:
        h = WebhookHandler.__new__(WebhookHandler)
        await h._run_pipeline({})

        assert rvp.await_args.args[0] == "nutra"


async def test_run_pipeline_skips_when_lock_busy():
    @asynccontextmanager
    async def _busy_lock(name, ttl_seconds=600):
        yield False

    with patch("ubt_os.core.pipeline_lock", _busy_lock):
        h = WebhookHandler.__new__(WebhookHandler)
        result = await h._run_pipeline({"vertical": "auto"})

        assert result == {"status": "skipped", "reason": "lock_busy"}
