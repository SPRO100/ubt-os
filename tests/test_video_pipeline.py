"""Тесты видео-пайплайна nutra/ubt (A21 → A25 → очередь A30) — всё на моках."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ubt_os.pipelines import video_pipeline as vp


def _piece(text="Честный отзыв о продукте", score=85):
    p = MagicMock()
    p.humanized_text = text
    p.humanize_score = score
    return p


def _check(passed=True, blocked=False, clean=None, score=90):
    c = MagicMock()
    c.passed = passed
    c.is_blocked = blocked
    c.clean_version = clean
    c.score = score
    c.reason = "ok" if passed else "нарушения"
    c.violations = []
    return c


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


async def test_pipeline_queues_video(env):
    with patch.object(vp, "AccountReader") as reader, \
         patch.object(vp, "ContentCreator") as creator_cls, \
         patch.object(vp, "ComplianceGate") as gate_cls, \
         patch.object(vp, "ContentPlanWriter") as plan_w, \
         patch.object(vp, "VideoWriter") as video_w, \
         patch.object(vp, "HiggsFieldQueue") as queue_cls:
        reader.get_active.return_value = [{"id": "tiktok_us_001", "vertical": "nutra"}]
        creator_cls.return_value.create = AsyncMock(return_value=_piece())
        gate_cls.return_value.check = AsyncMock(return_value=_check())
        plan_w.create.return_value = {"id": "plan-1"}
        video_w.create.return_value = {"id": "video-1"}
        queue = queue_cls.return_value
        queue.enqueue = AsyncMock()

        result = await vp.run_video_pipeline("nutra", geo="US", offer="TestOffer")

        assert result["status"] == "ok"
        assert result["created"] == 1
        assert result["blocked"] == 0
        queue.enqueue.assert_awaited_once()
        job = queue.enqueue.await_args.args[0]
        assert job.job_id == "video-1"
        assert job.vertical == "nutra"
        assert job.content_plan_id == "plan-1"


async def test_pipeline_blocks_bad_content(env):
    with patch.object(vp, "AccountReader") as reader, \
         patch.object(vp, "ContentCreator") as creator_cls, \
         patch.object(vp, "ComplianceGate") as gate_cls, \
         patch.object(vp, "ContentPlanWriter") as plan_w, \
         patch.object(vp, "HiggsFieldQueue") as queue_cls:
        reader.get_active.return_value = [{"id": "acc1"}]
        creator_cls.return_value.create = AsyncMock(return_value=_piece("гарантированно похудеешь"))
        gate_cls.return_value.check = AsyncMock(
            return_value=_check(passed=False, blocked=True, score=10))
        queue = queue_cls.return_value
        queue.enqueue = AsyncMock()

        result = await vp.run_video_pipeline("nutra")

        assert result["created"] == 0
        assert result["blocked"] == 1
        plan_w.create.assert_not_called()
        queue.enqueue.assert_not_awaited()


async def test_pipeline_uses_clean_version_on_warning(env):
    with patch.object(vp, "AccountReader") as reader, \
         patch.object(vp, "ContentCreator") as creator_cls, \
         patch.object(vp, "ComplianceGate") as gate_cls, \
         patch.object(vp, "ContentPlanWriter") as plan_w, \
         patch.object(vp, "VideoWriter") as video_w, \
         patch.object(vp, "HiggsFieldQueue") as queue_cls:
        reader.get_active.return_value = [{"id": "acc1"}]
        creator_cls.return_value.create = AsyncMock(return_value=_piece("рискованный текст"))
        gate_cls.return_value.check = AsyncMock(
            return_value=_check(passed=False, blocked=False, clean="безопасный текст"))
        plan_w.create.return_value = {"id": "p1"}
        video_w.create.return_value = {"id": "v1"}
        queue_cls.return_value.enqueue = AsyncMock()

        result = await vp.run_video_pipeline("nutra")

        assert result["created"] == 1
        assert plan_w.create.call_args.kwargs["script"] == "безопасный текст"


async def test_pipeline_no_accounts(env):
    with patch.object(vp, "AccountReader") as reader:
        reader.get_active.return_value = []
        result = await vp.run_video_pipeline("betting")
        assert result["status"] == "skipped"


async def test_pipeline_batch_rotates_formats(env):
    with patch.object(vp, "AccountReader") as reader, \
         patch.object(vp, "ContentCreator") as creator_cls, \
         patch.object(vp, "ComplianceGate") as gate_cls, \
         patch.object(vp, "ContentPlanWriter") as plan_w, \
         patch.object(vp, "VideoWriter") as video_w, \
         patch.object(vp, "HiggsFieldQueue") as queue_cls:
        reader.get_active.return_value = [{"id": "acc1"}]
        create = AsyncMock(return_value=_piece())
        creator_cls.return_value.create = create
        gate_cls.return_value.check = AsyncMock(return_value=_check())
        plan_w.create.return_value = {"id": "p"}
        video_w.create.return_value = {"id": "v"}
        queue_cls.return_value.enqueue = AsyncMock()

        result = await vp.run_video_pipeline("nutra", count=3)

        assert result["created"] == 3
        used_formats = [call.args[0] for call in create.await_args_list]
        assert len(set(used_formats)) == 3  # три разных формата
